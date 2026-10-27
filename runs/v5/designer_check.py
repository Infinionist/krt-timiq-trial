#!/usr/bin/env python3
"""designer_check.py BOARD : the "designer check" of TimIQ plan v2, one PASS/FAIL line per check (a script decides, no model).
Exit 0 only if every check passes; 1 if any fails; 2 on a usage or tool error.

  assembly   check_assembly says buildable (with --baseline and --intent as the placement loop calls it; `--baseline none` for a
             board that is nobody's placement run, such as the human board). --waive A/B,... names pairs accepted as the only
             blocking items (the human board's C20/R16).
  floorplan  check_floorplan --intent: 0 errors
  members    every member of every can (cans.json 'members', else refs F + B) has its pad box inside the can zone (+ --zone-tol); a can whose cans.json entry says
             "side": "F" (plan v5, Infinionist 10-27: members stand on top, under the can) FAILS for every member standing on B (the human-board reference file has no side: either face);
             no other part has its centre inside a can zone on either face. The can's 'optional' parts
             (build_inputs.py OPTIONAL: allowed inside, not members) are neither required inside nor intruders.
  band       no top-side (F) part touches a wall-band keep-out of the brief (allow lists honoured)
  box        every can present (J7-J12) lies inside the box rectangle
  window     J7-J10 are at their cans_poses.json poses (option (d); mechanical.json for older runs) and each overlaps the lid window (fractions printed)
  holes      no part's pad box is closer to a hole centre than its keep-out radius (holes.json; the part's allow list honoured)
  far        passives more than --far-mm (10) pad-edge from the nearest IC pin they serve: count <= --max-far. LED series resistors (a resistor on a
             net that carries a pad of an LED:* footprint) are left out: they serve a panel LED, not an IC.
  pin-rows   (WARN, never a failure; plan v4 fix 4) proximity misses of the plan v3 pin rows (intent rows with 'pads'): counted out of the floorplan check and
             printed as one WARN line. Intruders, members outside their can, keep-outs, holes, zones and every other floorplan error stay failures.
             The same for the anchor pull rows (anchor IC -> its marker MK<n>, plan v4): one WARN line 'anchor-pull'.
  info lines (printed as INFO, never a failure, JSON "pass": null):
  anchors    per can with an anchor_marker (cans.json): the anchor IC pad box gap to the marker point beyond anchor_max_mm (+ --anchor-tol) is a MISS, listed
  filter-reg power-entry parts L12-L14 and C143-C150: pad-edge distance to the nearest regulator U39-U45 (max and per part)
  keep_away  per rule of the brief's keep_away[]: the minimum aggressor-victim pad-edge gap in plan view (KRT's own currency), the closest pair,
             whether it is inside the rule's gap, and the minimum per victim group (plan_v3.SENSITIVE)

usage: designer_check.py BOARD [--intent I] [--baseline B|none] [--waive A/B,..] [--cans C] [--holes H] [--brief BR] [--mech M] [--poses P]
                         [--max-far N] [--far-mm D] [--zone-tol T] [--json OUT]
Run with the system python3 (pcbnew); KRT's tools are called through its venv.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plan_v3  # noqa: E402
KRT = '/tmp/pcb-trials/timiq/krt'
PY = KRT + '/.venv/bin/python'
# facts (FACTS 1, 6): box 120 x 120 at BOX1's origin; lid window
BOX = (124.2124, 94.9478, 244.2124, 214.9478)
WINDOW = (150.21, 148.95, 212.21, 190.95)
HUMAN_FAR = 28          # this script's own count on the human board (netlist-served pins, pad edge, all faces, LED series resistors left out); plan v2 quoted 17 for bottom passives by centre distance


def load_board(path):
    import pcbnew
    fd = os.dup(2)
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
    try:
        b = pcbnew.LoadBoard(path)
    finally:
        os.dup2(fd, 2)
    return pcbnew, b


def parts_of(pcbnew, b):
    mm = pcbnew.ToMM
    out = {}
    for f in b.GetFootprints():
        ref = f.GetReference()
        pads = []
        for p in f.Pads():
            bb = p.GetBoundingBox()
            pads.append((mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()), p.GetNetname(), p.GetNumber()))
        pos = f.GetPosition()
        box = None
        if pads:
            box = (min(p[0] for p in pads), min(p[1] for p in pads), max(p[2] for p in pads), max(p[3] for p in pads))
        out[ref] = {'fp': f.GetFPIDAsString(), 'face': 'B' if f.IsFlipped() else 'F', 'x': mm(pos.x), 'y': mm(pos.y), 'rot': f.GetOrientationDegrees(), 'pads': pads, 'box': box}
    return out


def inter_area(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def rect_gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def krt(args):
    r = subprocess.run([PY, '-X', 'utf8'] + args, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def summary(text):
    for line in text.splitlines():
        if line.startswith('JSON_SUMMARY:'):
            return json.loads(line[len('JSON_SUMMARY:'):])
    return None


class Report:
    def __init__(self):
        self.rows = []
        self.infos = []
        self.warns = []

    def add(self, name, ok, detail):
        self.rows.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name:9s} {detail}")

    def info(self, name, detail, data=None):
        self.infos.append((name, detail, data))
        print(f'INFO  {name:9s} {detail}')

    def warn(self, name, detail, data=None):
        """plan v4 fix 4: a reading that is graded WARN: printed, saved in the JSON (info + warn), never a failure."""
        self.warns.append((name, detail, data))
        print(f'WARN  {name:9s} {detail}')

    @property
    def ok(self):
        return all(r[1] for r in self.rows)


def check_assembly(rep, board, intent, baseline, waive):
    out = board + '.designer_ca.json'
    cmd = [KRT + '/py_tools/check_assembly.py', board, '--json', out]
    if intent:
        cmd += ['--intent', intent]
    if baseline and baseline != 'none':
        cmd += ['--baseline', baseline]
    rc, txt = krt(cmd)
    if not os.path.exists(out):
        print('designer_check: check_assembly produced no JSON:\n' + txt[-600:], file=sys.stderr)
        sys.exit(2)
    d = json.load(open(out))
    os.remove(out)
    pairs = {'/'.join(sorted((p['a'], p['b']))) for p in d.get('blocking_pairs', [])}
    other = {k: (len(d[k]) if isinstance(d.get(k), list) else d.get(k)) for k in
             ('courtyard_blocking_gating_pairs', 'courtyard_error_gating_pairs', 'silk_enclosed_gating_pairs', 'own_pad_gating_pairs',
              'locked_contact_pairs', 'coincident_origin_groups', 'graphic_pad_gating_pairs', 'testpoint_covered_gating_pairs')}
    other = {k: v for k, v in other.items() if v}
    other['containment_blocking'] = d.get('containment_blocking') or 0
    other['body_edge_band_gating'] = d.get('body_edge_band_gating') or 0
    other = {k: v for k, v in other.items() if v}
    waived = {'/'.join(sorted(w.split('/'))) for w in waive}
    if d.get('buildable'):
        rep.add('assembly', True, f"buildable (baseline {baseline or 'none'})")
    elif pairs and pairs <= waived and not other:
        rep.add('assembly', True, f"NOT buildable only on waived pair(s) {sorted(pairs)} (baseline {baseline or 'none'})")
    else:
        rep.add('assembly', False, f"NOT BUILDABLE: blocking {sorted(pairs)[:6]}{'...' if len(pairs) > 6 else ''} other gates {other} (baseline {baseline or 'none'})")


def pin_row_keys(intent_file):
    """{(ref, near)} of the plan v3 pin rows: proximity rows that name pads ('pads'). A miss of one of these is a WARN (plan v4 fix 4), never a failure."""
    try:
        rows = json.load(open(intent_file)).get('proximity') or []
    except (OSError, ValueError):
        return set()
    return {(r['ref'], r['near']) for r in rows if r.get('pads')}


def anchor_row_keys(intent_file):
    """{(ref, near)} of the plan v4 anchor pull rows: proximity rows whose `near` is an anchor marker MK<n> (Infinionist 10-27: a pull, not a wall: a miss is a WARN too)."""
    try:
        rows = json.load(open(intent_file)).get('proximity') or []
    except (OSError, ValueError):
        return set()
    return {(r['ref'], r['near']) for r in rows if re.match(r'^' + plan_v3.MARKER_PREFIX + r'\d+$', r.get('near', ''))}


def split_floorplan(violations, pin_rows, anchor_rows=frozenset()):
    """(failures, warns): the error-severity violations of check_floorplan, with the proximity misses of the pin rows and of the anchor pull rows moved out. Intruders, members
    outside their can, keep-outs, holes, templates, zones stay failures."""
    fails, warns = [], []
    for v in violations:
        if v.get('severity') != 'error':
            continue
        if v.get('rule') == 'proximity' and (v.get('ref'), (v.get('measured') or {}).get('near')) in (set(pin_rows) | set(anchor_rows)):
            warns.append(v)
        else:
            fails.append(v)
    return fails, warns


def check_floorplan(rep, board, intent):
    if not intent:
        rep.add('floorplan', False, 'no --intent given')
        return
    out = board + '.designer_cf.json'
    rc, txt = krt([KRT + '/py_tools/check_floorplan.py', board, '--intent', intent, '--json', out, '-q'])
    s = summary(txt)
    if s is None or not os.path.exists(out):
        print('designer_check: check_floorplan gave no JSON_SUMMARY / --json file:\n' + txt[-600:], file=sys.stderr)
        sys.exit(2)
    d = json.load(open(out))
    os.remove(out)
    pins_, anch_ = pin_row_keys(intent), anchor_row_keys(intent)
    fails, warns = split_floorplan(d.get('violations') or [], pins_, anch_)
    aw = [v for v in warns if (v['ref'], v['measured'].get('near')) in anch_]
    warns = [v for v in warns if (v['ref'], v['measured'].get('near')) not in anch_]
    by = {}
    for v in fails:
        by[v['rule']] = by.get(v['rule'], 0) + 1
    unlisted = max(0, (s.get('errors') or 0) - len(fails) - len(warns) - len(aw))      # errors KRT counts that are not in its violations list (aggregates): failures too
    if unlisted:
        by['(unlisted)'] = unlisted
    rep.add('floorplan', not fails and not unlisted, f"{len(fails) + unlisted} error(s) {dict(sorted(by.items())) if fails else ''}".strip()
            + (f" (+{len(warns)} pin-row proximity miss(es) graded WARN)" if warns else '') + (f" (+{len(aw)} anchor-pull miss(es) graded WARN)" if aw else ''))
    if aw:
        rep.warn('anchor-pull', f"{len(aw)} of {len(anch_)} anchor pull row(s) missed (anchor IC more than its max_mm from its marker; a pull, not a wall): "
                 + ', '.join(f"{v['ref']}->{v['measured'].get('near')} {v['measured'].get('gap_mm') or 0.0:.1f} mm" for v in aw), {'n': len(aw), 'rows': len(anch_)})
    if warns:
        gaps = sorted(((v['measured'].get('gap_mm') or 0.0, v['ref'], v['measured'].get('near')) for v in warns), reverse=True)
        n_rows = len(pin_row_keys(intent))
        rep.warn('pin-rows', f"{len(warns)} of {n_rows} pin-row proximity limit(s) missed (3 mm pad-edge rows); worst "
                 + ', '.join(f'{r}->{n} {g:.1f} mm' for g, r, n in gaps[:3]), {'n': len(warns), 'rows': n_rows, 'worst': gaps[:10]})


def can_members(c):
    """a can's member refs: plan v3 cans.json has 'members' (faces are free); older files (human_cans_ref.json) list refs per face."""
    if isinstance(c.get('members'), list):
        return list(c['members'])
    refs = c.get('refs') or {}
    if not all(isinstance(refs.get(f), list) for f in ('F', 'B')):
        return None
    return list(refs['F']) + list(refs['B'])


def check_members(rep, parts, cans_file, tol):
    cans = json.load(open(cans_file))
    member_of = {}
    must_front = set()
    optional = set()
    markers = {c['anchor_marker']['ref'] for c in cans.values() if c.get('anchor_marker')}      # plan v4 anchor markers: fixed points, not intruders
    todo = []
    for can, c in cans.items():
        refs = can_members(c)
        if refs is None:
            todo.append(can)
            continue
        optional |= set(c.get('optional') or ())
        for r in refs:
            member_of[r] = can
    if todo:
        rep.add('members', False, f"member refs not declared (TODO): {', '.join(todo)}")
        return
    bad = []
    # plan v5b (faces_v5.py): a can whose cans.json says side F, or lists `flippable`, is under the face rule: only its flippable small passives may stand on B, none outside the can
    # rect, and no IC anywhere. (A cans file with neither key, such as the human reference, is not.)
    import faces_v5
    faces = {r: p['face'] for r, p in parts.items()}
    boxes = {r: p['box'] for r, p in parts.items()}
    v5b = {c for c, v in cans.items() if v.get('side') == 'F' or v.get('flippable') is not None}
    fb = faces_v5.board_face_problems(faces, cans)
    bad += list(fb.values())
    must_front = {r for r, can in member_of.items() if can in v5b}
    bad += list(faces_v5.b_outside_problems(boxes, faces, cans, 0.01).values())
    for r, can in member_of.items():
        p = parts.get(r)
        z = cans[can]['zone']
        if p is None:
            bad.append(f'{r}: not on the board')
        elif p['face'] == 'B' and can in v5b:
            continue                    # a flippable part on B: the rules above decided (rect check with no tolerance)
        elif p['box'] is None or not (p['box'][0] >= z[0] - tol and p['box'][1] >= z[1] - tol and p['box'][2] <= z[2] + tol and p['box'][3] <= z[3] + tol):
            bad.append(f'{r}@{p["face"]}: outside {can} zone')
    intr = []
    for r, p in parts.items():
        if r in member_of or r in optional or r in cans or r == 'BOX1' or r in markers or r.startswith(('J7', 'J8', 'J9', 'J10', 'J11', 'J12')):
            continue
        for can, c in cans.items():
            z = c['zone']
            if z[0] <= p['x'] <= z[2] and z[1] <= p['y'] <= z[3]:
                intr.append(f'{r}@{p["face"]} in {can}')
    nf = sum(1 for r in member_of if r in parts and parts[r]['face'] == 'F')
    nflip = sum(len(c.get('flippable') or ()) for c in cans.values())
    rep.add('members', not bad and not intr,
            f"{len(member_of) - len(bad)}/{len(member_of)} members in their can ({'front, only the flippable small passives may stand on B' if must_front else 'either face'}; {nf} on F, {len(member_of) - nf} on B, {nflip} listed flippable); {len(intr)} intruder(s); {len(optional)} optional part(s) ignored"
            + (f"; e.g. {(bad + intr)[:4]}" if bad or intr else ''))


def check_band(rep, parts, brief):
    ko = [k for k in json.load(open(brief)).get('keepouts', []) if k.get('kind') == 'enclosure_wall_band']
    hits = []
    for r, p in parts.items():
        if p['face'] != 'F' or p['box'] is None:
            continue
        for k in ko:
            if r in (k.get('allow') or ()):
                continue
            if inter_area(p['box'], k['rect']) > 1e-6:
                hits.append(f"{r} in {k['name']}")
    rep.add('band', not hits, f"{len(hits)} top-side part(s) in the wall band" + (f": {hits[:6]}" if hits else ''))


def check_box(rep, parts):
    out = []
    n = 0
    for c in ('J7', 'J8', 'J9', 'J10', 'J11', 'J12'):
        p = parts.get(c)
        if not p or not p['box']:
            continue
        n += 1
        b = p['box']
        if not (b[0] >= BOX[0] and b[1] >= BOX[1] and b[2] <= BOX[2] and b[3] <= BOX[3]):
            out.append(c)
    rep.add('box', not out and n > 0, f"{n} can(s) checked, outside the box: {out}")


def check_window(rep, parts, mech, poses_file=None):
    m = {f['ref']: f for f in json.load(open(mech))['fixed']}
    if poses_file and os.path.exists(poses_file):      # option (d): the cans are not in mechanical.json, their poses are in cans_poses.json
        m.update({r: {'x': p['x'], 'y': p['y'], 'rot': p['rot']} for r, p in json.load(open(poses_file)).items()})
    bad, fr = [], {}
    for c in ('J7', 'J8', 'J9', 'J10'):
        p = parts.get(c)
        if p is None:
            bad.append(f'{c}: missing')
            continue
        f = m.get(c)
        if f and (abs(p['x'] - f['x']) > 0.01 or abs(p['y'] - f['y']) > 0.01 or abs(((p['rot'] - f['rot']) + 180) % 360 - 180) > 0.5 or p['face'] != 'F'):
            bad.append(f'{c}: moved off its mechanical.json pose')
        b = p['box']
        a = inter_area(b, WINDOW)
        fr[c] = round(a / ((b[2] - b[0]) * (b[3] - b[1])), 2)
        if a <= 0:
            bad.append(f'{c}: not under the window')
    rep.add('window', not bad, f"overlap fraction of each can with the window {fr}" + (f"; {bad}" if bad else ''))


def check_holes(rep, parts, holes_file):
    holes = json.load(open(holes_file))
    bad = []
    worst = None
    for h in holes:
        for r, p in parts.items():
            if r in h['allow'] or p['box'] is None:
                continue
            d = rect_gap((h['x'], h['y'], h['x'], h['y']), p['box'])
            slack = d - h['radius']
            if worst is None or slack < worst[0]:
                worst = (round(slack, 3), h['name'], r)
            if slack < -1e-6:
                bad.append(f"{r} {-slack:.2f} mm inside {h['name']}")
    rep.add('holes', not bad, f"{len(holes)} holes, {len(bad)} part(s) inside a keep-out circle; tightest slack {worst}" + (f"; {bad[:5]}" if bad else ''))


def served_pins(parts):
    """{passive: [(ic, pad index)]}: IC pins on the passive's non-GND nets, and through local nets (<= 5 pads, no IC pin) of other
    passives, up to 3 hops (same definition as the v4 bench)."""
    nets = {}
    for r, p in parts.items():
        for i, pad in enumerate(p['pads']):
            if pad[4]:
                nets.setdefault(pad[4], []).append((r, i))
    ispas = lambda r: re.match(r'^[RCL]\d+$', r) is not None
    pas_nets = {r: [pad[4] for pad in p['pads'] if pad[4] and pad[4] != 'GND'] for r, p in parts.items() if ispas(r)}
    ic_on = {n: [(r, i) for r, i in pl if r.startswith('U')] for n, pl in nets.items()}
    out = {}
    for r in pas_nets:
        pins, seen_n, seen_p = [], set(), {r}
        frontier = [(n, 0) for n in pas_nets[r]]
        while frontier:
            n, hop = frontier.pop()
            if n in seen_n:
                continue
            seen_n.add(n)
            if ic_on.get(n):
                pins += ic_on[n]
                continue
            if hop >= 3 or len(nets[n]) > 5:
                continue
            for q, _ in nets[n]:
                if q in seen_p or q not in pas_nets:
                    continue
                seen_p.add(q)
                frontier += [(m, hop + 1) for m in pas_nets[q]]
        out[r] = sorted(set(pins))
    return out


def led_resistors(parts):
    """refs of resistors that sit on a net carrying a pad of an LED footprint (FPID 'LED:...'): series resistors of a panel LED."""
    led_nets = {pad[4] for r, p in parts.items() if p['fp'].startswith('LED:') for pad in p['pads'] if pad[4] and pad[4] != 'GND'}
    return {r for r, p in parts.items() if re.match(r'^R\d+$', r) and any(pad[4] in led_nets for pad in p['pads'])}


def far_list(parts, far_mm):
    """([(ref, d)] over the far passives, worst first; n passives measured; sorted LED resistors left out)."""
    sv = served_pins(parts)
    leds = led_resistors(parts)
    far, n = [], 0
    for r, pins in sv.items():
        if not pins or r in leds:
            continue
        n += 1
        d = min(rect_gap(parts[r]['box'], parts[ic]['pads'][i][:4]) for ic, i in pins)
        if d > far_mm:
            far.append((r, round(d, 1)))
    far.sort(key=lambda t: -t[1])
    return far, n, sorted(r for r in leds if sv.get(r))


def check_far(rep, parts, far_mm, max_far):
    far, n, leds = far_list(parts, far_mm)
    rep.add('far', len(far) <= max_far, f"{len(far)} of {n} passives are > {far_mm:g} mm pad-edge from their IC pin (limit {max_far}; {len(leds)} LED series resistor(s) left out); worst {far[:5]}")


def info_anchors(rep, parts, cans_file, tol):
    """plan v4 (no anchor zone): per can with an anchor_marker (cans.json): the body (pad box) gap of each anchor IC to the marker point; a MISS is more than anchor_max_mm + tol."""
    cans = json.load(open(cans_file))
    rows, miss, n = [], [], 0
    for can, c in cans.items():
        mk = c.get('anchor_marker')
        if not mk or not c.get('anchors'):
            continue
        for r in c['anchors']:
            n += 1
            p = parts.get(r)
            if p is None or p['box'] is None:
                miss.append(f'{r} ({can}): not on the board')
                continue
            g = rect_gap(p['box'], (mk['x'], mk['y'], mk['x'], mk['y']))
            rows.append((can, r, round(g, 2), p['face']))
            if g > c.get('anchor_max_mm', plan_v3.ANCHOR_PULL_MM) + tol:
                miss.append(f"{r}@{p['face']} ({can}) {g:.1f} mm from its marker {mk['ref']} (pull {c.get('anchor_max_mm', plan_v3.ANCHOR_PULL_MM):g} mm)")
    if not n:
        rep.info('anchors', 'no anchor markers declared in the cans file', {'n': 0})
        return
    rep.info('anchors', f"{n - len(miss)}/{n} anchor ICs within their pull of the marker (+{tol:g} mm); {len(miss)} miss(es){': ' + '; '.join(miss) if miss else ''}",
             {'n': n, 'misses': miss, 'rows': rows})


def info_filter_regulator(rep, parts):
    """power-entry filter parts (L12-L14, C143-C150) against the regulators U39-U45 they serve: a regulator with a pad on one of the part's non-GND nets, or
    on a net of a filter inductor that shares one of those nets (J6 -> L -> rail -> regulator). Distance = pad-edge box gap to the NEAREST served regulator."""
    regs = [r for r in plan_v3.POWER_REGS if r in parts and parts[r]['box']]
    flt = [r for r in list(plan_v3.POWER_FILTERS) + [f'C{i}' for i in range(143, 151)] if r in parts and parts[r]['box']]
    if not regs or not flt:
        rep.info('filter-reg', 'no power-entry parts / regulators on the board', {})
        return
    nets_of = lambda r: {pad[4] for pad in parts[r]['pads'] if pad[4] and pad[4] != 'GND'}
    reg_nets = {g: nets_of(g) for g in regs}
    per = {}
    for r in flt:
        ns = set(nets_of(r))
        for ind in plan_v3.POWER_FILTERS:
            if ind in parts and ns & nets_of(ind):
                ns |= nets_of(ind)
        served = [g for g in regs if reg_nets[g] & ns]
        if not served:
            continue
        d, reg = min((rect_gap(parts[r]['box'], parts[g]['box']), g) for g in served)
        per[r] = (round(d, 1), reg)
    if not per:
        rep.info('filter-reg', 'no regulator is served by the power-entry parts on this board', {})
        return
    worst = max(per, key=lambda r: per[r][0])
    rep.info('filter-reg', f"power-entry parts to the nearest regulator they serve (box gap): max {per[worst][0]} mm ({worst} to {per[worst][1]}); "
             + ', '.join(f'{r} {d}->{g}' for r, (d, g) in per.items()), {'per': per, 'max_mm': per[worst][0], 'worst': worst})


def _pattern_re(pat):
    """a keep_away net pattern in route.py's syntax: '*' any run, '?' any one character, everything else literal; whole-name match."""
    return re.compile(''.join('.*' if ch == '*' else '.' if ch == '?' else re.escape(ch) for ch in pat) + r'\Z', re.S)


def keep_away_sides(parts, brief):
    """[{index, gap, agg, vic, agg_nets, vic_nets, label}] : the brief's keep_away rules resolved on this board: agg/vic = {net: [(ref, pad)]}."""
    rules = json.load(open(brief)).get('keep_away') or []
    nets = {}
    for r, p in parts.items():
        for pad in p['pads']:
            if pad[4]:
                nets.setdefault(pad[4], []).append((r, pad))
    out = []
    for i, row in enumerate(rules):
        agg_s, vic_s, gap = row['rule'].split(':')
        res = lambda s: {n: v for n, v in nets.items() if any(_pattern_re(x).match(n) for x in s.split(',') if x)}
        out.append({'index': i, 'gap': float(gap), 'agg': res(agg_s), 'vic': res(vic_s), 'label': (row.get('why') or '').split(' (')[0][:60]})
    return out


def keep_away_readings(parts, brief):
    """[{rule, gap, agg_nets, vic_nets, min, closest, inside, by_group}] : per brief keep_away rule, the minimum pad-edge gap (plan view) between an
    aggressor pad and a victim pad, excluding two pads of one net and two pads of one part (as KRT's rule_keep_away). by_group: min per
    plan_v3.SENSITIVE victim group."""
    grp_of = {n: g for g, ns in plan_v3.SENSITIVE.items() for n in ns}
    out = []
    for sd in keep_away_sides(parts, brief):
        A = [(r, pad) for n, v in sd['agg'].items() for r, pad in v]
        V = [(r, pad) for n, v in sd['vic'].items() for r, pad in v]
        best, bg = None, {}
        for ra, pa in A:
            for rv, pv in V:
                if ra == rv or pa[4] == pv[4]:
                    continue
                g = rect_gap(pa[:4], pv[:4])
                if best is None or g < best[0]:
                    best = (g, ra, pa, rv, pv)
                gname = grp_of.get(pv[4], '?')
                if gname not in bg or g < bg[gname][0]:
                    bg[gname] = (g, ra, rv)
        rec = {'index': sd['index'], 'gap_mm': sd['gap'], 'agg_nets': len(sd['agg']), 'vic_nets': len(sd['vic']), 'label': sd['label']}
        if best:
            g, ra, pa, rv, pv = best
            rec.update({'min_mm': round(g, 2), 'inside': g < sd['gap'] - 1e-6,
                        'closest': f'{ra} pad {pa[5]} ({pa[4]}) to {rv} pad {pv[5]} ({pv[4]})',
                        'by_group': {k: round(v[0], 2) for k, v in sorted(bg.items())}})
        out.append(rec)
    return out


def info_keep_away(rep, parts, brief):
    recs = keep_away_readings(parts, brief)
    if not recs:
        rep.info('keep_away', 'the brief declares no keep_away rules', {})
        return
    for r in recs:
        if 'min_mm' not in r:
            rep.info('keep_away', f"[{r['index']}] {r['label']}: nothing to measure ({r['agg_nets']} aggressor nets, {r['vic_nets']} victim nets)", r)
            continue
        rep.info('keep_away', f"[{r['index']}] {r['label']}: min {r['min_mm']} mm ({'INSIDE' if r['inside'] else 'outside'} the {r['gap_mm']:g} mm gap), {r['closest']}; "
                 f"{r['agg_nets']} aggressor / {r['vic_nets']} victim nets; by victim group {r['by_group']}", r)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board')
    ap.add_argument('--intent', default=HERE + '/intent.json')
    ap.add_argument('--baseline', default=HERE + '/fixed.kicad_pcb', help="board the run started from, or 'none'")
    ap.add_argument('--waive', default='', help='A/B,C/D : pairs accepted as the only blocking items')
    ap.add_argument('--cans', default=HERE + '/cans.json')
    ap.add_argument('--holes', default=HERE + '/holes.json')
    ap.add_argument('--brief', default=HERE + '/fixed.design-brief.json')
    ap.add_argument('--mech', default=HERE + '/mechanical.json')
    ap.add_argument('--poses', default=HERE + '/cans_poses.json', help='can poses (option (d)); overrides mechanical.json for J7-J12')
    ap.add_argument('--max-far', type=int, default=HUMAN_FAR)
    ap.add_argument('--far-mm', type=float, default=10.0)
    ap.add_argument('--zone-tol', type=float, default=0.5)
    ap.add_argument('--anchor-tol', type=float, default=0.0, help='an anchor IC further than anchor_max_mm + this from its marker is listed as a miss (info)')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    if not os.path.exists(a.board):
        print(f'designer_check: no such board {a.board}', file=sys.stderr)
        return 2
    for f in (a.cans, a.holes, a.brief, a.mech):
        if not os.path.exists(f):
            print(f'designer_check: missing {f}', file=sys.stderr)
            return 2
    pcbnew, b = load_board(a.board)
    parts = parts_of(pcbnew, b)
    rep = Report()
    print(f'designer_check {a.board}')
    check_assembly(rep, a.board, a.intent, a.baseline, [w for w in a.waive.split(',') if w])
    check_floorplan(rep, a.board, a.intent)
    check_members(rep, parts, a.cans, a.zone_tol)
    check_band(rep, parts, a.brief)
    check_box(rep, parts)
    check_window(rep, parts, a.mech, a.poses)
    check_holes(rep, parts, a.holes)
    check_far(rep, parts, a.far_mm, a.max_far)
    info_anchors(rep, parts, a.cans, a.anchor_tol)
    info_filter_regulator(rep, parts)
    info_keep_away(rep, parts, a.brief)
    print('DESIGNER CHECK ' + ('PASS' if rep.ok else 'FAIL') + f"  ({sum(1 for r in rep.rows if r[1])}/{len(rep.rows)}; {len(rep.infos)} info line(s), {len(rep.warns)} warning line(s) not counted)")
    if a.json:
        json.dump([{'check': n, 'pass': o, 'detail': d} for n, o, d in rep.rows]
                  + [{'check': n, 'pass': None, 'info': True, 'detail': d, 'data': x} for n, d, x in rep.infos]
                  + [{'check': n, 'pass': None, 'info': True, 'warn': True, 'detail': d, 'data': x} for n, d, x in rep.warns], open(a.json, 'w'), indent=1)
    return 0 if rep.ok else 1


if __name__ == '__main__':
    sys.exit(main())
