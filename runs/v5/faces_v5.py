#!/usr/bin/env python3
"""faces_v5.py : plan v5b (Infinionist 10-27: passives under a can may go to the BOTTOM). Pure functions; the only I/O is board_netinfo() (KRT's parser). Imported by decide_faces.py,
gate.py (KRT venv, shapely via fillcheck) and designer_check.py (system python3: it needs only the pure checks).

THE RULE (written once, here; fillcheck / gate / designer_check / decide_faces point at it)
  Inside each shield can (J7..J12):
    * every IC (U*), every RF-PATH part, and every part with courtyard >= 20 mm2 (fillcheck.SMALL_PASSIVE_MM2) stays on the FRONT, locked (never listed flippable);
    * a SMALL SMD PASSIVE of that can (class R, C or FB = ferrite bead; courtyard < 20 mm2; not RF-path) MAY go to the BOTTOM, but only inside its OWN can's outline (the can's block
      zone, tolerance 0, applies to both faces: the keep-out can-<J> already covers F and B and allows the members).
  How KRT is told (py_placer/placement/faces.py + floorplan.py): a group `side` or block `side` DECLARES the face and OVERRIDES `flippable`. So a can that needs flips has NO group side
  and NO block side; its small passives are listed `flippable` in its group (canJ<J>); every part still STARTS on F (set_faces); place_simple keeps a part on its face and flips a
  flippable one only where the front has no room (faces.needed_flips), so the non-flippable members stay on F by themselves. A can that needs no flips keeps `side: F`.
  Which parts are listed (decide_faces.py): for a can whose front fill is over fillcheck.LIMIT, the eligible parts smallest first, the decaps of the can's own ICs first (the human
  practice: caps behind their IC), until the front fill is <= LIMIT and the back fill (inside the can rect, minus whatever already stands on B) is <= LIMIT. Eligible parts all used up
  and still over: FAIL, with the shortfall in mm2. The limit is never loosened.

RF PATH (script, from the netlist and the inputs; listed in faces.json). A part is RF-path when it has a pad on an RF net. RF nets, rails excluded (a RAIL is GND or a net with more
  than LOCAL_MAX = 12 pads):
    1. the victim nets of the intent's keep_away rules (the sensitive nets the inputs already carry: RF to the SMA notches J1-J4, LO / PLL out, DAC I/Q, ADC inputs) and every
       non-rail net on a pad of an SMA connector (footprint name has SMA);
    2. the non-rail nets of the passives named by the intent's ordered RF chains (proximity rows whose why starts 'plan v3 chain': C80, C108, R123 ...) and of the members of its
       templates (the PMA2-43LN+ RF front ends): the series parts between ICs and their bias parts; and a non-rail net with pads on two or more of the ICs of those chains
       (U23 -> U24 direct nets);
    3. the series closure: a 2-pad passive (R, C, L, FB) with a pad on an RF net passes RF on to its other net when that net is not a rail and carries a pad of an IC or an SMA.
  A part with a pad on one of these nets is RF-path (shunt resistors, DC blocks, bias parts, chokes). L8-L11 (RF chokes) are RF-path and are not R/C/FB anyway.
"""
import fnmatch
import re

import fillcheck

LOCAL_MAX = 12                 # a net with more pads than this is a rail (same number as plan_v3.LOCAL_MAX / netrows.LOCAL_MAX)
FERRITE_RE = re.compile(r'^(BLM|MMZ|MPZ|BKP|BK\d|FBMH|HZ\d|FERRITE)', re.I)
KRT = '/tmp/pcb-trials/timiq/krt'


# ---------------------------------------------------------------- reading the board
def board_netinfo(board):
    """{'nets': {net: [[ref, pad]]}, 'values': {ref: value}, 'footprints': {ref: footprint name}} from a .kicad_pcb (KRT's own parser; run with KRT's venv python)."""
    import sys
    for d in ('py_router', 'py_placer'):
        if KRT + '/' + d not in sys.path:
            sys.path.insert(0, KRT + '/' + d)
    from kicad_parser import parse_kicad_pcb
    pcb = parse_kicad_pcb(board)
    names = {nid: n.name for nid, n in pcb.nets.items()}
    nets, vals, fps = {}, {}, {}
    for ref, fp in pcb.footprints.items():
        vals[ref] = fp.value or ''
        fps[ref] = fp.footprint_name or ''
        for p in fp.pads:
            if p.net_id > 0 and names.get(p.net_id):
                nets.setdefault(names[p.net_id], []).append([ref, str(p.pad_number)])
    return {'nets': nets, 'values': vals, 'footprints': fps}


def decap_owners(board):
    """{cap: [chips]}: KRT's own decap rule (placement.grouping.decap_view): every decoupling cap and the chips whose supply pins sit on its rail. KRT venv python."""
    import sys
    for d in ('py_router', 'py_placer'):
        if KRT + '/' + d not in sys.path:
            sys.path.insert(0, KRT + '/' + d)
    from kicad_parser import parse_kicad_pcb
    from placement.grouping import decap_view
    v = decap_view(parse_kicad_pcb(board))
    sp = v.supply_pins()
    return {cap: sorted({ic for ic, _n in sp.get(nid, ())}) for cap, nid in v.decaps().items()}


def pref_ranks(owners, ics):
    """{cap: rank} for plan_can: 0 = every chip the cap serves is one of `ics` (the can's own ICs), 1 = it serves at least one of them. owners: decap_owners()."""
    out = {}
    ics = set(ics)
    for cap, chips in owners.items():
        s = set(chips) & ics
        if s:
            out[cap] = 0 if s == set(chips) else 1
    return out


# ---------------------------------------------------------------- part classes
def part_class(ref, value=''):
    """'R', 'C', 'FB' (a ferrite bead: a FBnn reference, or an Lnn whose value is a ferrite part number), 'L', 'U', or the reference letters."""
    m = re.match(r'^([A-Za-z]+)\d+$', ref)
    p = m.group(1).upper() if m else ref
    if p == 'FB' or (p == 'L' and FERRITE_RE.match(value or '')):
        return 'FB'
    return p


def area_of(ref, dims):
    d = dims.get(ref)
    return None if not d else d[0] * d[1]


def ineligible_reason(ref, netinfo, dims, rf_parts, small_mm2=fillcheck.SMALL_PASSIVE_MM2):
    """None when `ref` may be flippable (small SMD passive R / C / FB, courtyard < small_mm2, not RF-path); else the reason it must stay on the front."""
    cls = part_class(ref, (netinfo.get('values') or {}).get(ref, ''))
    if cls == 'U':
        return 'an IC stays on the front'
    if cls not in ('R', 'C', 'FB'):
        return f'class {cls} is not a small passive (R, C, FB)'
    a = area_of(ref, dims)
    if a is None:
        return 'no courtyard size'
    if a >= small_mm2:
        return f'courtyard {a:.1f} mm2 >= {small_mm2:g}'
    if rf_parts is not None and ref in rf_parts:
        return 'RF-path part: ' + '; '.join(rf_parts[ref][:2])
    return None


# ---------------------------------------------------------------- the RF path
def _is_rail(n, nets):
    return (not n) or 'GND' in n.upper() or len(nets.get(n, ())) > LOCAL_MAX


def victim_nets(intent, nets):
    """nets matched by the victim field (2nd) of every keep_away rule of the intent ('aggressors:victims:gap'; KRT's net matcher: '?' is any one character)."""
    pats = []
    for k in intent.get('keep_away') or []:
        f = str(k.get('rule', '')).split(':')
        if len(f) >= 2:
            pats += [p for p in f[1].split(',') if p]
    out = set()
    for pat in pats:
        out |= {n for n in nets if fnmatch.fnmatchcase(n, pat)}
    return out


def chain_refs(intent):
    """refs named by the intent's ordered RF chains (proximity rows 'plan v3 chain ...': ref and near) and the anchor + members of its templates."""
    out = set()
    for p in intent.get('proximity') or []:
        if str(p.get('why', '')).startswith('plan v3 chain'):
            out |= {p.get('ref'), p.get('near')}
    for t in intent.get('templates') or []:
        out.add(t.get('anchor'))
        out |= {m.get('ref') for m in t.get('members') or []}
    out.discard(None)
    return out


def rf_path(netinfo, intent):
    """{'nets': [RF nets], 'parts': {ref: [reasons]}} by the module rule. Pure on (netinfo, intent)."""
    nets = netinfo['nets']
    by_ref, npads = {}, {}
    for n, pads in nets.items():
        for r, _p in pads:
            by_ref.setdefault(r, set()).add(n)
            npads[r] = npads.get(r, 0) + 1
    values = netinfo.get('values') or {}
    fps = netinfo.get('footprints') or {}
    sma = {r for r, f in fps.items() if 'SMA' in f.upper()}
    why = {}

    def add(n, w):
        if not _is_rail(n, nets) and n not in why:
            why[n] = w
            return True
        return False

    for n in victim_nets(intent, nets):
        add(n, f'victim net of the keep_away rules ({n})')
    for r in sorted(sma):
        for n in by_ref.get(r, ()):
            add(n, f'net on the SMA connector {r}')
    cr = chain_refs(intent)
    cpass = {r for r in cr if part_class(r, values.get(r, '')) in ('R', 'C', 'FB', 'L')}
    cics = {r for r in cr if r.startswith('U')}
    for r in sorted(cpass):
        for n in by_ref.get(r, ()):
            add(n, f'net of {r}, a part of an ordered RF chain / RF front end')
    for n, pads in nets.items():
        if len({r for r, _p in pads} & cics) >= 2:
            add(n, 'net between two ICs of the ordered RF chains')
    changed = True
    while changed:
        changed = False
        for n in list(why):
            for r, _p in nets.get(n, ()):
                if part_class(r, values.get(r, '')) not in ('R', 'C', 'FB', 'L') or len(by_ref.get(r, ())) != 2 or npads.get(r) != 2:     # a series part: a 2-pad passive on two nets
                    continue
                for m in by_ref[r] - set(why):
                    if _is_rail(m, nets) or not any(x.startswith('U') or x in sma for x, _ in nets[m]):
                        continue
                    if add(m, f'series closure through {r} from {n}'):
                        changed = True
    parts = {}
    for n, w in why.items():
        for r, _p in nets[n]:
            parts.setdefault(r, [])
            if w not in parts[r]:
                parts[r].append(w)
    return {'nets': sorted(why), 'parts': parts}


# ---------------------------------------------------------------- the flip plan of one can
def plan_can(row, members, dims, clearance, limit, netinfo, rf_parts, pref=None, small_mm2=fillcheck.SMALL_PASSIVE_MM2):
    """Which members of one can must be listed flippable. row: the can's row of fillcheck.fill_table with every member on F (usable_F/B_mm2, load_F/B_mm2).
    -> {'picks': [ref], 'F0', 'F', 'B' (fills), 'shortfall_mm2': mm2 of front load still above limit * usable_F (0 when it fits), 'eligible': n, 'ineligible': {ref: reason}}.
    Order: by `pref` rank (dict ref -> 0 for a decap serving only the can's own ICs, 1 for one that serves some of them; unlisted = 9), then smallest courtyard first, then reference. A part whose move would take the back fill over `limit` is skipped."""
    uF, uB = max(row['usable_F_mm2'], 1e-9), max(row['usable_B_mm2'], 1e-9)
    loadF, loadB = row['load_F_mm2'], row['load_B_mm2']
    inel = {}
    cands = []
    for r in members:
        why = ineligible_reason(r, netinfo, dims, rf_parts, small_mm2)
        if why:
            inel[r] = why
        else:
            cands.append(r)
    pref = pref or {}
    cands.sort(key=lambda r: (pref.get(r, 9), area_of(r, dims), r))
    F0 = loadF / uF
    picks = []
    for r in cands:
        if loadF / uF <= limit + 1e-9:
            break
        a = (dims[r][0] + clearance) * (dims[r][1] + clearance)
        if (loadB + a) / uB > limit + 1e-9:
            continue
        loadF -= a
        loadB += a
        picks.append(r)
    short = max(0.0, loadF - limit * uF)
    return {'picks': picks, 'F0': round(F0, 3), 'F': round(loadF / uF, 3), 'B': round(loadB / uB, 3), 'shortfall_mm2': round(short, 1) if short > 1e-6 else 0.0,
            'eligible': len(cands), 'ineligible': inel}


# ---------------------------------------------------------------- the checks on a board (pure; used by gate-side tests and designer_check)
def board_face_problems(faces, cans, small_ok=None):
    """{key: problem} on a PLACED board. faces: {ref: 'F'|'B'} (and any ref); cans: cans.json (members, zone, side, flippable); a can with `side` F or a `flippable` list is under the v5b rule.
    A part on B that is a member of a can must be listed flippable in that can's cans.json entry; no IC (U*) stands on B anywhere on a v5b board."""
    bad = {}
    v5 = {c for c, v in cans.items() if v.get('side') == 'F' or v.get('flippable') is not None}
    if not v5:
        return bad
    for can in sorted(v5):
        c = cans[can]
        flip = set(c.get('flippable') or [])
        for r in c.get('members') or []:
            if faces.get(r) == 'B' and r not in flip:
                bad[f'{can}/{r}'] = f'{r} is a can member that is not flippable and stands on B (only the small passives listed flippable may)'
    for r, f in faces.items():
        if f == 'B' and re.match(r'^U\d+$', r):
            bad[f'IC/{r}'] = f'IC {r} stands on B (every IC stays on the front)'
    return bad


def b_outside_problems(boxes, faces, cans, tol=0.0):
    """{key: problem}: a member of a v5b can that stands on B has its pad box outside that can's rect. boxes: {ref: [x0, y0, x1, y1] pad box}."""
    bad = {}
    for can, c in cans.items():
        if c.get('side') != 'F' and c.get('flippable') is None:
            continue
        z = c['zone']
        for r in c.get('members') or []:
            b = boxes.get(r)
            if faces.get(r) == 'B' and (b is None or not (b[0] >= z[0] - tol and b[1] >= z[1] - tol and b[2] <= z[2] + tol and b[3] <= z[3] + tol)):
                bad[f'{can}/{r}'] = f'{r} stands on B outside the {can} rect (a bottom part must stay inside its own can)'
    return bad
