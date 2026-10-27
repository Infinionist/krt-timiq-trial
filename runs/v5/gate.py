#!/usr/bin/env python3
"""gate.py : the pre-placement gate of TimIQ plan v2 step 2 (a script decides, no model).

PASS (exit 0) only when ALL hold; otherwise prints what is missing and exits 1 (2 on a usage or tool error):
  1. check_floorplan --plan-only: 0 errors                       (KRT)
  2. check_groups: 0 errors                                      (KRT)
  3. every IC (a U* reference on the board) is covered by one of (netlist rows count: an IC with no datasheet is covered by them):
       - a templates[] row in the intent whose anchor is the IC,
       - a proximity[] row in the intent naming the IC as ref or near (datasheet row or netlist row),
       - a written skip in the groups file: templates[] entry {chip: IC, skip: "<reason>"} or {chip: IC, kind: "none", why: "<reason>"}
         whose reason is real: >= 25 characters, not one of the excuses plan v2 rejects ("not fetched", "time cap", "4h15",
         "held by the decap rule", "held by decap rule", "left to the group"), AND (when netrows.json is present) the IC has no passive
         on its local nets at all (netrows.json ic_candidates == 0): a skip never hides an IC the netlist could serve.
  4. every shield can (cans.json, option (d): the cans are NOT on the placing board; plan v3: faces are free) has: a member block 'can<J>' (ALL its members, anchors included, no side)
     with the zone the cans.json says; NO anchor zone block and NO block with `exclusive` anywhere (Infinionist 10-27: exclusive pushes an IC's own decaps out; the anchor is a soft start);
     the anchor marker MK<n> (cans.json anchor_marker): fixed pose in the intent inside the can interior, and one proximity row per anchor IC to it (basis body, 6-8 mm: a pull, not a wall);
     a keep-out 'can-<J>' allowing exactly the members + the can's 'optional' refs (allowed inside, not members) + BOX1 + the marker; and no can footprint (J7-J12) on the placing board.
  5. every footprint of the placing board has a courtyard (add_courtyards.py; BOX1, the pin frame, carries a 0.2 mm POINT courtyard instead: plan v4).
  7. pre-flight (plan v4 fix 1, seconds): KRT's own legality for every declared (fixed) pose against every keep-out and hole clearance (preflight_probe.py = place_simple's set-up up to
     the anneal), no two zones overlap (no nesting: KRT's only nesting is `exclusive`, which is not used), and, plan v5 (Infinionist 10-27, fillcheck.py):
       fit    every member's box (courtyard + pads) has a pose in the usable room of its zone, on its face, at some quarter turn (U4 in J12, U13 vs the J9 frame);
       fill   every zone (each can interior, the power supergroup) and the free region outside the cans: sum of member courtyards with KRT's clearance / usable area <= --fill-max
              (0.65; TIGHT above 0.55 = KRT's own CROWDED_UTILISATION). Plan v5b: the table gives F0 (front, nothing flipped), F and B (front and back with the parts the groups list
              flippable flipped); F and B must each be <= the limit. The FILL TABLE is printed on every run (decide_faces.py chooses the flippable parts, this gate judges);
       faces  plan v5b (faces_v5.py has the rule): a can whose group lists nothing flippable has group side F and block side F; a can with flippable parts has NEITHER (KRT: a declared
              side overrides flippable); every flippable part is a member of that can and a small SMD passive (R, C, FB; courtyard < 20 mm2) that is not RF-path (faces_v5.rf_path, from
              the netlist); no IC or other member is flippable; every member starts on F; cans.json agrees; no big part outside the cans is flippable or on B;
       rows   no proximity row is unsatisfiable (its two ends in zones too far apart: rowcheck.unsatisfiable_rows), and none moves a part into another group (KRT's own fold_followers:
              a row between two groups is a membership claim; plan v4's power rows folded 11 groups into one);
       zones  every can block has tolerance_mm 0.0 (the 0.5 default put U13 on the J9 frame pads); no pw_* tile (power = groups + one loose supergroup block power_strip).
  6. input facts of plan v3 (inputs_problems): every keep-out of the intent allows BOX1 (the pin frame stands over the whole box); every proximity row that names a
     part at a pin (it has 'pads') has max_mm == PIN_ROW_MM (3.0, plan v3 item 5; 2.0 was the skill default); the intent for the reattached boards
     (intent_reattached.json) allows BOX1 and all six cans in each can keep-out and carries an overlap_waiver for every can x (member + optional part).

usage: gate.py [--board B] [--intent I] [--reattached R] [--groups G] [--cans C] [--netrows N] [--fill-max F] [--json OUT]
Defaults are the files in /tmp/pcb-trials/timiq/v5/.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
KRT = '/tmp/pcb-trials/timiq/krt'
PY = KRT + '/.venv/bin/python'
BAD_REASON = [r'not fetched', r'time cap', r'4h15', r'held by (the )?decap', r'left to the group', r'within the time']
MIN_REASON = 25
PIN_ROW_MM = 3.0      # plan v3 item 5: a part named at a pin sits within 3.0 mm (pad edge); written here on purpose, not imported from plan_v3
CANS = ['J7', 'J8', 'J9', 'J10', 'J11', 'J12']


def krt(args):
    r = subprocess.run([PY, '-X', 'utf8'] + args, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def summary(text):
    for line in text.splitlines():
        if line.startswith('JSON_SUMMARY:'):
            return json.loads(line[len('JSON_SUMMARY:'):])
    return None


def ics_on_board(board):
    t = open(board, encoding='utf-8').read()
    return sorted(set(re.findall(r'\(property "Reference" "(U\d+)"', t)), key=lambda s: int(s[1:]))


def reason_problem(reason):
    if not isinstance(reason, str) or len(reason.strip()) < MIN_REASON:
        return f'reason shorter than {MIN_REASON} characters'
    for pat in BAD_REASON:
        if re.search(pat, reason, re.I):
            return f'reason is one plan v2 rejects (matches "{pat}")'
    return None


def coverage(ics, intent, groups, candidates=None):
    """candidates: {ic: [passives on its local nets]} (netrows.json). An IC is covered when it is a template anchor or named in a proximity row,
    or when one of its candidates is claimed by a proximity row (either end of the passive) or is a template member."""
    """returns {ic: ('template'|'proximity'|'skip' or None, detail)}."""
    tmpl = {t.get('anchor') for t in intent.get('templates', [])}
    prox = {}
    for p in intent.get('proximity', []):
        for r in (p.get('ref'), p.get('near')):
            prox.setdefault(r, 0)
            prox[r] += 1
    skips, bad_skips = {}, {}
    for g in groups.get('groups', []):
        for t in g.get('templates', []) or []:
            chip = t.get('chip')
            if not chip:
                continue
            reason = t.get('skip') if t.get('skip') else (t.get('why') if t.get('kind') == 'none' else None)
            if reason is None:
                continue
            prob = reason_problem(reason)
            (bad_skips if prob else skips)[chip] = prob or reason
    claimed = {p.get('ref') for p in intent.get('proximity', [])} | {m.get('ref') for t in intent.get('templates', []) for m in t.get('members', [])}
    out = {}
    for ic in ics:
        if ic in tmpl:
            out[ic] = ('template', 'intent templates[] row')
        elif ic in prox:
            out[ic] = ('proximity', f'{prox[ic]} proximity row(s)')
        elif candidates is not None and any(c in claimed for c in candidates.get(ic, ())):
            out[ic] = ('proximity', f"claims its passive(s) {sorted(c for c in candidates[ic] if c in claimed)[:4]}")
        elif ic in skips and candidates is not None and candidates.get(ic):
            out[ic] = (None, f'skip rejected: {len(candidates[ic])} passive(s) sit on its local nets (netrows.json) and none is claimed; a skip cannot hide them')
        elif ic in skips:
            out[ic] = ('skip', skips[ic][:70])
        elif ic in bad_skips:
            out[ic] = (None, f'skip rejected: {bad_skips[ic]}')
        else:
            out[ic] = (None, 'no template row, no proximity row, no written skip')
    return out


def ics_all_refs(board):
    t = open(board, encoding='utf-8').read()
    return set(re.findall(r'\(property "Reference" "([^"]+)"', t))


def cans_problems(cans, intent, board_refs):
    """{can/what: problem}: see check 4 in the module doc. Plan v3: one block 'can<J>' per can (no side: faces are free) holding the members except its anchors, one
    the keep-out allowing members + optional + BOX1 + the anchor marker, the marker and the anchor rows (plan v4: no anchor zone; the power tiles are check 7)."""
    bad = {}
    for b in intent.get('blocks', []):
        if b.get('exclusive'):
            bad[f"intent/exclusive/{b.get('name')}"] = 'block is `exclusive` (Infinionist 10-27: not allowed, it pushes an IC\'s own decaps out of the area; the anchor is a soft pull)'
    blocks = {b.get('name'): b for b in intent.get('blocks', [])}
    kos = {k.get('name'): k for k in intent.get('keepouts', [])}
    rz = lambda z: [round(v, 3) for v in (z or [])]
    for can, c in cans.items():
        if can in board_refs:
            bad[f'{can}/board'] = 'the can footprint is on the placing board (option (d): it must be off, see reattach.py)'
        members = c.get('members')
        anchors = c.get('anchors')
        if not isinstance(members, list) or not isinstance(anchors, list) or not members or not anchors or not set(anchors) <= set(members):
            bad[f'{can}/members'] = 'cans.json has no member list / anchors (or anchors outside the members)'
            continue
        b = blocks.get(f'can{can}')
        if b is None:
            bad[f'{can}/block'] = f'no block can{can} in the intent (rerun build_inputs.py)'
        elif sorted(b.get('refs') or []) != sorted(members):
            bad[f'{can}/block'] = 'block refs differ from cans.json members (the anchors are members now)'
        elif b.get('side') != (None if c.get('flippable') else 'F'):
            bad[f'{can}/block'] = (f"block side {b.get('side')!r}: plan v5 pins a can block to the front (Infinionist 10-27); plan v5b: a can with flippable small passives has no block side "
                                   f"(a block side overrides flippable in KRT)")
        elif rz(b.get('zone')) != rz(c['zone']):
            bad[f'{can}/block'] = 'block zone differs from the can interior'
        if f'can{can}_anchor' in blocks:
            bad[f'{can}/anchor'] = f'block can{can}_anchor is in the intent: plan v4 has no anchor zone (Infinionist 10-27)'
        mk = c.get('anchor_marker') or {}
        z = c['zone']
        fx = {f.get('ref'): f for f in intent.get('fixed_poses', [])}
        if not mk.get('ref'):
            bad[f'{can}/marker'] = 'cans.json has no anchor_marker'
        elif mk['ref'] not in board_refs:
            bad[f'{can}/marker'] = f"marker {mk['ref']} is not on the placing board"
        elif mk['ref'] not in fx or abs(fx[mk['ref']].get('x', 1e9) - mk['x']) > 1e-3 or abs(fx[mk['ref']].get('y', 1e9) - mk['y']) > 1e-3:
            bad[f'{can}/marker'] = f"marker {mk['ref']} has no fixed pose at ({mk['x']}, {mk['y']}) in the intent"
        elif not (z[0] < mk['x'] < z[2] and z[1] < mk['y'] < z[3]):
            bad[f'{can}/marker'] = f"marker {mk['ref']} is outside the can interior"
        else:
            rows = {(r.get('ref'), r.get('near')): r for r in intent.get('proximity', [])}
            for ic in anchors:
                r = rows.get((ic, mk['ref']))
                if r is None:
                    bad[f'{can}/anchor-row/{ic}'] = f"no proximity row {ic} -> {mk['ref']} (the anchor pull)"
                elif r.get('basis') != 'body' or not (ANCHOR_PULL[0] <= r.get('max_mm', 0) <= ANCHOR_PULL[1]):
                    bad[f'{can}/anchor-row/{ic}'] = f"row {ic} -> {mk['ref']}: basis {r.get('basis')!r}, max_mm {r.get('max_mm')} (must be body, {ANCHOR_PULL[0]:g}-{ANCHOR_PULL[1]:g} mm: a pull, not a wall)"
        k = kos.get(f'can-{can}')
        want = sorted(members + list(c.get('optional') or []) + ['BOX1'] + ([mk['ref']] if mk.get('ref') else []))
        if k is None:
            bad[f'{can}/keepout'] = f'no keep-out can-{can} in the intent'
        elif sorted(k.get('allow') or []) != want:
            bad[f'{can}/keepout'] = 'keep-out allow list differs from the can members + optional parts + BOX1 + the anchor marker'
    return bad


ANCHOR_PULL = (6.0, 8.0)   # plan v4 (Infinionist 10-27): the anchor IC -> marker proximity row, mm body to body (written here on purpose, not imported from plan_v3)


def _rect_overlap(a, b):
    w, h = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 1e-6 and h > 1e-6 else 0.0


def _inside(a, b, tol=1e-6):
    return a[0] >= b[0] - tol and a[1] >= b[1] - tol and a[2] <= b[2] + tol and a[3] <= b[3] + tol


def overlap_problems(intent):
    """{pair: problem}: two zones overlapping on a shared face. No nesting is allowed: KRT's only nesting is `exclusive` (anchor zones), which plan v4 does not use."""
    bad = {}
    bl = [b for b in intent.get('blocks', []) if b.get('zone')]
    for i, a in enumerate(bl):
        for b in bl[i + 1:]:
            if a.get('side') and b.get('side') and a['side'] != b['side']:
                continue
            area = _rect_overlap(a['zone'], b['zone'])
            if area > 0:
                bad[f"{a['name']}+{b['name']}"] = f'zones overlap by {area:.1f} mm2 (KRT intent_zone_overlap)'
    return bad


def power_problems(intent, groups, fixed):
    """{what: problem}: every part of the groups whose role is power (except the pw_misc leftovers and fixed parts) is a member of exactly one block `power_strip` (the loose power
    supergroup: a zone, not exclusive, generous tolerance, no side); no pw_* tile with a zone (tile_problems, fillcheck); no old one-piece block named 'power'."""
    bad = {}
    if any(b.get('name') == 'power' for b in intent.get('blocks', [])):
        bad['power/old'] = "the one-piece 'power' block of plan v3 is still in the intent"
    sg = [b for b in intent.get('blocks', []) if b.get('name') == 'power_strip']
    if len(sg) != 1 or not sg[0].get('zone'):
        bad['power/supergroup'] = f"{len(sg)} block(s) 'power_strip' with a zone (want exactly one: the loose power supergroup)"
    else:
        s = sg[0]
        if s.get('exclusive'):
            bad['power/supergroup-exclusive'] = 'power_strip is exclusive (it must be a loose, non-exclusive zone)'
        if s.get('side') is not None:
            bad['power/supergroup-side'] = f"power_strip has side {s.get('side')!r} (no face is declared for the supergroup)"
        if not (s.get('tolerance_mm') or 0) >= POWER_TOL_MIN:
            bad['power/supergroup-tolerance'] = f"power_strip tolerance_mm {s.get('tolerance_mm')!r} is not generous (>= {POWER_TOL_MIN:g} mm)"
    where = {}
    for b in sg:
        for r in b.get('refs', []):
            where.setdefault(r, []).append(b['name'])
    for g in groups.get('groups', []):
        if g.get('role') != 'power' or g['name'] == 'pw_misc':
            continue
        for r in g['refs']:
            if r in fixed:
                continue
            n = where.get(r, [])
            if len(n) != 1:
                bad[f"power/{g['name']}/{r}"] = f'in {len(n)} power_strip block(s) {n}'
    return bad


POWER_TOL_MIN = 2.0        # the supergroup's tolerance is "generous": at least this many mm (plan v5 builds 4.0)


def preflight_problems(intent, groups, probe, fixed=(), cans=None, fill_max=None, claims=False, netinfo=None, rf_parts=None):
    """all of check 7 on already-loaded data (probe = preflight_probe.py's JSON). {key: problem}. cans (cans.json) switches the can face / tolerance rules on."""
    import fillcheck
    fill_max = fillcheck.LIMIT if fill_max is None else fill_max
    bad = {}
    for r, why in (probe.get('refused') or {}).items():
        bad[f'fixed-pose/{r}'] = 'declared pose illegal for KRT: ' + '; '.join(why)
    for r in probe.get('too_big') or []:
        bad[f'too-big/{r}'] = 'does not fit the usable board area at either quarter turn'
    bad.update({f'fit/{k}': v for k, v in fillcheck.fit_problems(intent, probe).items()})
    bad.update({f'overlap/{k}': v for k, v in overlap_problems(intent).items()})
    bad.update({f'fill/{k}': v for k, v in fillcheck.fill_problems(intent, groups, probe, fill_max).items()})
    bad.update(power_problems(intent, groups, set(fixed)))
    bad.update(fillcheck.tile_problems(intent))
    import rowcheck
    rects = {r: probe['rects'][r] for r in (probe.get('fixed') or []) if r in (probe.get('rects') or {})}
    bad.update({f'row/{a}->{b}': v for (a, b), v in rowcheck.unsatisfiable_rows(intent.get('blocks', []), intent.get('proximity', []), rects).items()})
    if claims:
        bad.update({f'claim/{r}': v for r, v in rowcheck.claim_problems(groups, intent.get('proximity', [])).items()})
    if cans is not None:
        bad.update({f'faces/{k}': v for k, v in fillcheck.face_problems(intent, groups, probe, cans, netinfo=netinfo, rf_parts=rf_parts).items()})
        bad.update({f'zones/{k}': v for k, v in fillcheck.zone_problems(intent, cans).items()})
    return bad


def inputs_problems(intent, reattached, cans):
    """{what: problem}: check 6 of the module doc. reattached = the intent of the boards with the cans back on (None: not given -> a problem)."""
    bad = {}
    for k in intent.get('keepouts', []):
        if 'BOX1' not in (k.get('allow') or []):
            bad[f"intent/keepout/{k.get('name')}"] = 'BOX1 (the pin frame over the whole box) is not in this keep-out allow list'
    for i, r in enumerate(intent.get('proximity', [])):
        if r.get('pads') and r.get('max_mm') != PIN_ROW_MM and (r.get('context') or {}).get('kind') != 'power_loose':
            bad[f"intent/pin-row/{r.get('ref')}->{r.get('near')}"] = f"pin row max_mm {r.get('max_mm')} (plan v3 item 5: {PIN_ROW_MM:g})"
    if reattached is None:
        bad['reattached'] = 'no intent_reattached.json'
        return bad
    kos = {k.get('name'): k for k in reattached.get('keepouts', [])}
    for can in cans:
        k = kos.get(f'can-{can}')
        if k is None:
            bad[f'reattached/keepout/can-{can}'] = 'no such keep-out'
            continue
        miss = [r for r in ['BOX1'] + CANS if r not in (k.get('allow') or [])]
        if miss:
            bad[f'reattached/keepout/can-{can}'] = f'allow list lacks {miss}'
    have = {tuple(sorted(w.get('pair') or [])) for w in reattached.get('overlap_waivers', [])}
    for can, c in cans.items():
        miss = [r for r in list(c.get('members') or []) + list(c.get('optional') or []) + [(c.get('anchor_marker') or {}).get('ref')] if r and tuple(sorted((can, r))) not in have]
        if miss:
            bad[f'reattached/waiver/{can}'] = f'no overlap_waiver for {len(miss)} part(s): {miss[:6]}'
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--board', default=HERE + '/fixed.kicad_pcb')
    ap.add_argument('--intent', default=HERE + '/intent.json')
    ap.add_argument('--reattached', default=HERE + '/intent_reattached.json')
    ap.add_argument('--groups', default=HERE + '/groups.json')
    ap.add_argument('--cans', default=HERE + '/cans.json')
    ap.add_argument('--netrows', default=HERE + '/netrows.json')
    ap.add_argument('--mech', default=HERE + '/mechanical.json')
    ap.add_argument('--fill-max', type=float, default=None, help='fill limit per zone (single face, with clearance); default fillcheck.LIMIT 0.65')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    for f in (a.board, a.intent, a.groups):
        if not os.path.exists(f):
            print(f'gate: missing input {f}', file=sys.stderr)
            return 2
    res = {'checks': {}, 'missing': {}}
    fails = []

    rc, txt = krt([KRT + '/py_tools/check_floorplan.py', a.board, '--intent', a.intent, '--plan-only', '--allow-unplaced'])
    s = summary(txt)
    if s is None:
        print('gate: check_floorplan --plan-only gave no JSON_SUMMARY:\n' + txt[-800:], file=sys.stderr)
        return 2
    n = s.get('plan_errors')
    res['checks']['plan_only_errors'] = n
    if n != 0:
        fails.append(f'check_floorplan --plan-only: {n} error(s)')
        res['missing']['plan_only'] = [l.strip() for l in txt.splitlines() if '[error' in l.lower()][:20]

    rc, txt = krt([KRT + '/py_tools/check_groups.py', a.board, '--groups', a.groups, '--intent', a.intent])
    s = summary(txt)
    if s is None:
        print('gate: check_groups gave no JSON_SUMMARY:\n' + txt[-800:], file=sys.stderr)
        return 2
    res['checks']['check_groups_errors'] = s.get('errors')
    if s.get('errors') != 0:
        fails.append(f'check_groups: {s.get("errors")} error(s)')
        res['missing']['groups'] = [l.strip() for l in txt.splitlines() if 'ERROR' in l][:20]

    intent = json.load(open(a.intent))
    groups = json.load(open(a.groups))
    ics = ics_on_board(a.board)
    cands = None
    if os.path.exists(a.netrows):
        cands = json.load(open(a.netrows)).get('ic_candidates')
    cov = coverage(ics, intent, groups, cands)
    miss = {ic: d for ic, (k, d) in cov.items() if k is None}
    res['checks']['ics'] = len(ics)
    res['checks']['ics_uncovered'] = len(miss)
    res['missing']['ics'] = miss
    if miss:
        fails.append(f'{len(miss)} of {len(ics)} ICs have no template row, proximity row or valid skip')

    cans_missing = {}
    if os.path.exists(a.cans):
        cans = json.load(open(a.cans))
        cans_missing = cans_problems(cans, intent, ics_all_refs(a.board))
    else:
        cans_missing['cans.json'] = 'missing'
    res['checks']['cans_problems_count'] = len(cans_missing)
    res['missing']['cans'] = cans_missing
    if cans_missing:
        fails.append(f'{len(cans_missing)} can problem(s)')

    import add_courtyards
    t = open(a.board, encoding='utf-8').read()
    import cans_io
    nocy = sorted(r for s_, e_, r in cans_io.scan_footprints(t) if r != 'BOX1' and not add_courtyards.has_courtyard(t[s_:e_]))
    res['checks']['footprints_without_courtyard'] = len(nocy)
    fs = add_courtyards.frame_courtyard_size(t, 'BOX1')
    if fs is None or max(fs) > 0.5:
        fails.append(f'BOX1 (the pin frame) must carry a POINT courtyard (<= 0.5 mm): has {fs} (add_courtyards.point_courtyard; without one KRT grades it on its pad box = the whole box and refuses its pose in every exclusive zone)')
    if nocy:
        fails.append(f'{len(nocy)} footprint(s) without a courtyard (run add_courtyards.py): {nocy[:8]}')

    inputs_bad = inputs_problems(intent, json.load(open(a.reattached)) if os.path.exists(a.reattached) else None,
                                 json.load(open(a.cans)) if os.path.exists(a.cans) else {})
    res['checks']['input_problems_count'] = len(inputs_bad)
    res['missing']['inputs'] = inputs_bad
    if inputs_bad:
        fails.append(f'{len(inputs_bad)} input problem(s) (BOX1 allow lists, pin rows {PIN_ROW_MM:g} mm, reattached intent)')

    # check 7: the pre-flight (seconds)
    pj = tempfile.mktemp(suffix='.probe.json')
    r = subprocess.run([PY, '-X', 'utf8', HERE + '/preflight_probe.py', a.board, a.groups, a.intent, '--out', pj], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(pj):
        print('gate: preflight_probe failed:\n' + (r.stdout + r.stderr)[-1200:], file=sys.stderr)
        return 2
    probe = json.load(open(pj))
    os.remove(pj)
    fixed_refs = {f['ref'] for f in json.load(open(a.mech))['fixed']} if os.path.exists(a.mech) else set()
    import fillcheck
    fill_max = fillcheck.LIMIT if a.fill_max is None else a.fill_max
    cans_d = json.load(open(a.cans)) if os.path.exists(a.cans) else None
    import faces_v5
    netinfo = faces_v5.board_netinfo(a.board)
    rf = faces_v5.rf_path(netinfo, intent)
    pre_bad = preflight_problems(intent, groups, probe, fixed_refs, cans_d, fill_max, claims=True, netinfo=netinfo, rf_parts=rf['parts'])
    table = fillcheck.fill_table(intent, groups, probe, fill_max)
    res['fill_table'] = table
    res['flippable'] = {g['name']: g['flippable'] for g in groups.get('groups', []) if g.get('flippable')}
    res['rf_path_parts_in_cans'] = {can: sorted(r for r in c['members'] if r in rf['parts']) for can, c in (cans_d or {}).items()}
    res['limit'] = fill_max
    res['anchored'] = probe.get('anchored')
    res['n_movable'] = len(probe.get('movable') or [])
    res['checks']['preflight_problems_count'] = len(pre_bad)
    res['missing']['preflight'] = pre_bad
    if pre_bad:
        fails.append(f'{len(pre_bad)} pre-flight problem(s) (fixed poses, zone fit, overlaps, fill, faces, zones, power supergroup)')

    res['pass'] = not fails
    print('GATE ' + ('PASS' if not fails else 'FAIL'))
    for f in fails:
        print('  FAIL:', f)
    if miss:
        print('  ICs missing (template row / proximity row / valid skip):')
        for ic, d in miss.items():
            print(f'    {ic}: {d}')
    if cans_missing:
        print('  can problems:')
        for k, d in cans_missing.items():
            print(f'    {k}: {d}')
    print('  fill table (single face, member courtyards with KRT clearance / usable area; limit %g, TIGHT above %g):' % (fill_max, fillcheck.WARN))
    for line in fillcheck.format_table(table):
        print('    ' + line)
    if pre_bad:
        print('  pre-flight problems:')
        for k, d in pre_bad.items():
            print(f'    {k}: {d}')
    if inputs_bad:
        print('  input problems:')
        for k, d in inputs_bad.items():
            print(f'    {k}: {d}')
    for k in ('plan_only', 'groups'):
        for l in res['missing'].get(k, []):
            print(f'    {k}: {l}')
    print('  ok: ' + ', '.join(f'{ic}={k}' for ic, (k, d) in cov.items() if k))
    if a.json:
        json.dump(res, open(a.json, 'w'), indent=1)
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
