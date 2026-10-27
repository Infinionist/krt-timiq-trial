#!/usr/bin/env python3
"""Plan v5 / v5b must-fail tests (Infinionist 10-27 call 5; v5b: passives under cans may go bottom, faces_v5.py). Run with KRT's venv python: /tmp/pcb-trials/timiq/krt/.venv/bin/python /tmp/pcb-trials/timiq/v5/tests/test_v5.py (exit 0 = all hold).
Each case: the REAL inputs pass the rule, a doctored copy fails it (so a rule that always passes or always fails is caught)."""
import json, os, subprocess, sys, tempfile
V5 = '/tmp/pcb-trials/timiq/v5'
sys.path.insert(0, V5)
import gate, fillcheck, rowcheck, faces_v5, decide_faces, designer_check  # noqa: E402
fails = []
def expect(name, cond):
    print(('ok    ' if cond else 'FAIL  ') + name)
    if not cond:
        fails.append(name)
dc = lambda o: json.loads(json.dumps(o))
it, gr, cans = (json.load(open(f'{V5}/{n}.json')) for n in ('intent', 'groups', 'cans'))
mech = {f['ref'] for f in json.load(open(V5 + '/mechanical.json'))['fixed']}
pj = tempfile.mktemp(suffix='.json')
r = subprocess.run([sys.executable, '-X', 'utf8', V5 + '/preflight_probe.py', V5 + '/fixed.kicad_pcb', V5 + '/groups.json', V5 + '/intent.json', '--out', pj], capture_output=True, text=True)
probe = json.load(open(pj)); os.remove(pj)
NI = faces_v5.board_netinfo(V5 + '/fixed.kicad_pcb')
RF = faces_v5.rf_path(NI, it)
pre = lambda i=it, g=gr, p=probe, c=cans, **kw: gate.preflight_problems(i, g, p, mech, c, netinfo=NI, rf_parts=RF['parts'], **kw)
gcan = lambda g, can: [x for x in g['groups'] if x['name'] == f'can{can}'][0]
base = pre(fill_max=1.0)
expect('real inputs: every rule but the fill limit passes (fixed poses, fit, overlap, power supergroup, tiles, faces, zones, rows)', base == {})
expect('real inputs: the whole pre-flight passes with the fill limit 0.65 (plan v5b: the flippable passives bring J7, J8, J12 under it)', pre() == {})
flips = {c: gcan(gr, c).get('flippable') or [] for c in cans}
expect('real inputs: flippable counts J7 12, J8 13, J9-J11 0, J12 15; cans without flips keep side F, the others have none', [len(flips[c]) for c in cans] == [12, 13, 0, 0, 0, 15]
       and all((gcan(gr, c).get('side') == 'F') == (not flips[c]) for c in cans) and all(([b for b in it['blocks'] if b['name'] == f'can{c}'][0].get('side') == 'F') == (not flips[c]) for c in cans))
# 1. flippable rules (faces_v5): ICs, RF-path parts, big parts, parts of another can, a group side that overrides
def with_flip(can, ref, **kw):
    g = dc(gr); x = gcan(g, can); x['flippable'] = list(x.get('flippable') or []) + [ref]
    c = dc(cans); c[can]['flippable'] = list(x['flippable'])
    return g, c
g, c = with_flip('J7', 'U1')
expect('MUST FAIL: IC U1 listed flippable', f'faces/J7/flippable/U1' in pre(g=g, c=c, fill_max=1.0))
rf_j7 = [r for r in cans['J7']['members'] if r in RF['parts'] and r[0] in 'RC'][0]
g, c = with_flip('J7', rf_j7)
expect(f'MUST FAIL: RF-path part {rf_j7} ({RF["parts"][rf_j7][0][:40]}) listed flippable', f'faces/J7/flippable/{rf_j7}' in pre(g=g, c=c, fill_max=1.0))
g, c = with_flip('J8', 'L8')
expect('MUST FAIL: L8 (RF choke, not R / C / FB) listed flippable', 'faces/J8/flippable/L8' in pre(g=g, c=c, fill_max=1.0))
dims_big = dc(probe); big_c = flips['J7'][0]; dims_big['dims'][big_c] = [6.0, 4.0]
expect(f'MUST FAIL: {big_c} with a courtyard of 24 mm2 (>= 20) listed flippable', f'faces/J7/flippable/{big_c}' in pre(p=dims_big, fill_max=9.0))
g, c = with_flip('J7', cans['J9']['members'][0])
expect('MUST FAIL: a part of J9 listed flippable in the J7 group (a bottom part must stay inside its own can)', f"faces/J7/flippable/{cans['J9']['members'][0]}" in pre(g=g, c=c, fill_max=1.0))
g = dc(gr); gcan(g, 'J7')['side'] = 'F'
expect('MUST FAIL: J7 lists flippable parts AND keeps group side F (KRT: a declared side overrides flippable)', 'faces/J7/group-side' in pre(g=g, fill_max=1.0))
i2 = dc(it); [b for b in i2['blocks'] if b['name'] == 'canJ12'][0]['side'] = 'F'
expect('MUST FAIL: J12 lists flippable parts AND keeps block side F', 'faces/J12/block-side' in pre(i=i2, fill_max=1.0))
c = dc(cans); c['J8'].pop('flippable')
expect('MUST FAIL: cans.json disagrees with the group about J8 (designer_check reads cans.json)', 'faces/J8/cans-json' in pre(c=c, fill_max=1.0))
no_kw = dc(it); no_kw['keep_away'] = []; no_kw['proximity'] = [p_ for p_ in no_kw['proximity'] if not str(p_.get('why', '')).startswith('plan v3 chain')]; no_kw['templates'] = []
RF0 = faces_v5.rf_path(NI, no_kw)
sample = [r for r in RF['parts'] if r not in RF0['parts'] and r[0] in 'RC' and r in set(cans['J7']['members'])]
expect(f'RF rule: without the keep_away victims / chains / templates fewer parts are RF-path ({len(RF["parts"])} -> {len(RF0["parts"])}); the SMAs still seed it', len(RF0['parts']) < len(RF['parts']) and 'R8' in RF0['parts'] and bool(sample))
g, c = with_flip('J7', sample[0])
expect(f'RF rule is what stops {sample[0]}: flippable with the RF list from the full inputs FAILS, with the list cut down it passes', f'faces/J7/flippable/{sample[0]}' in pre(g=g, c=c, fill_max=1.0)
       and f'faces/J7/flippable/{sample[0]}' not in gate.preflight_problems(it, g, probe, mech, c, 1.0, netinfo=NI, rf_parts=RF0['parts']))
g = dc(gr); [x for x in g['groups'] if x['name'] == 'canJ9'][0].pop('side')
expect('MUST FAIL: can group without side F (J9 lists nothing flippable)', 'faces/J9/group-side' in pre(g=g, fill_max=1.0))
i2 = dc(it); [b for b in i2['blocks'] if b['name'] == 'canJ10'][0].pop('side')
expect('MUST FAIL: can block without side F (J10 lists nothing flippable)', 'faces/J10/block-side' in pre(i=i2, fill_max=1.0))
# 2. a can member on B at the start
m = cans['J7']['members'][5]
p2 = dc(probe); p2['side'][m] = 'B'
expect(f'MUST FAIL: can member {m} stands on B on the placing board (every part starts on the front)', f'faces/J7/on-B/{m}' in pre(p=p2, fill_max=1.0))
u = [x for x in probe['dims'] if x.startswith('U') and x not in cans['J7']['members'] and x not in mech and x not in {y for c in cans.values() for y in c['members']}][0]
p3 = dc(probe); p3['side'][u] = 'B'
expect(f'MUST FAIL: big part {u} outside the cans stands on B', f'faces/outside/on-B/{u}' in pre(p=p3, fill_max=1.0))
# 3. a pw_ tile present
i3 = dc(it); i3['blocks'].append({'name': 'pw_U39', 'refs': ['U39'], 'zone': [200, 66, 212, 78], 'tolerance_mm': 0.0})
expect('MUST FAIL: a pw_U39 tile (block with a zone)', 'tile/pw_U39' in pre(i=i3, fill_max=1.0))
i3 = dc(it); i3['blocks'] = [b for b in i3['blocks'] if b['name'] != 'power_strip']
expect('MUST FAIL: no power_strip supergroup', 'power/supergroup' in pre(i=i3, fill_max=1.0))
# 4. a zone over the fill limit
g0, i0 = decide_faces.neutral(gr, it)
expect('MUST FAIL: with nothing flippable (all on F) the fill limit FAILS exactly canJ7, canJ8, canJ12 (the run v5 finding)',
       sorted(k for k in gate.preflight_problems(i0, g0, probe, mech, cans, netinfo=NI, rf_parts=RF['parts']) if k.startswith('fill/')) == ['fill/canJ12', 'fill/canJ7', 'fill/canJ8'])
i4 = dc(it); b = [b for b in i4['blocks'] if b['name'] == 'canJ11'][0]; b['zone'] = [b['zone'][0], b['zone'][1], b['zone'][0] + 20.0, b['zone'][1] + 20.0]
expect('MUST FAIL: canJ11 squeezed to 20 x 20 mm (fill over 0.65)', 'fill/canJ11' in pre(i=i4))
expect('real inputs: canJ11 is under the limit', 'fill/canJ11' not in pre())
i4 = dc(it); [b for b in i4['blocks'] if b['name'] == 'canJ12'][0]['zone'] = [180.0, 110.0, 192.0, 120.0]
expect('MUST FAIL: U4 does not fit a 12 x 10 mm J12 zone (zone fit)', 'fit/canJ12/U4' in pre(i=i4, fill_max=9.0))
# 5. a fixed part illegal (KRT's own predicate through the pre-flight probe)
i5 = dc(it); h = [k for k in i5['keepouts'] if k['name'] == 'hole-FIX5-1'][0]
d2 = [f for f in i5['fixed_poses'] if f['ref'] == 'D2'][0]; d2['x'], d2['y'] = h['circle'][0], h['circle'][1]
f5 = tempfile.mktemp(suffix='.json'); json.dump(i5, open(f5, 'w')); o5 = tempfile.mktemp(suffix='.json')
subprocess.run([sys.executable, '-X', 'utf8', V5 + '/preflight_probe.py', V5 + '/fixed.kicad_pcb', V5 + '/groups.json', f5, '--out', o5], capture_output=True, text=True)
pb = json.load(open(o5)); os.remove(f5); os.remove(o5)
expect('MUST FAIL: D2 declared in the middle of hole FIX5-1 (fixed-pose/D2)', 'fixed-pose/D2' in gate.preflight_problems(i5, gr, pb, mech, cans, 1.0))
expect('real inputs: no declared pose is refused', probe['refused'] == {})
# 6. can zone tolerance 0, rows
i6 = dc(it); [b for b in i6['blocks'] if b['name'] == 'canJ9'][0]['tolerance_mm'] = 0.5
expect('MUST FAIL: canJ9 tolerance 0.5 (U13 on the J9 frame pads in run v4)', 'zones/J9/tolerance' in pre(i=i6, fill_max=1.0))
rows = [{'ref': 'R115', 'near': 'U26', 'max_mm': 3.0}]
expect('MUST FAIL: the run v4 row R115 -> U26 (J11 / J8) is unsatisfiable', ('R115', 'U26') in rowcheck.unsatisfiable_rows([dict(b, refs=b['refs'] + (['R115'] if b['name'] == 'canJ11' else [])) for b in it['blocks']], rows))
expect('real inputs: no unsatisfiable row', rowcheck.unsatisfiable_rows(it['blocks'], it['proximity'], {r: probe['rects'][r] for r in probe['fixed']}) == {})
rw = [{'ref': 'U41', 'near': 'L12', 'max_mm': 5.0}]
expect('MUST FAIL: a row between two power groups folds them (KRT fold_followers)', rowcheck.claim_problems(gr, rw) != {} and rowcheck.claim_problems(gr, it['proximity']) == {})
expect('toy: flippable_needed lists small passives only for an overfull non-can zone', fillcheck.flippable_needed([{'name': 'z', 'kind': 'zone', 'fill': 0.9, 'load_F_mm2': 90.0, 'usable_F_mm2': 100.0, 'load_B_mm2': 0.0, 'usable_B_mm2': 100.0}],
       {}, {'dims': {'C1': [2, 2], 'C2': [3, 3], 'U1': [8, 8]}, 'clearance': 0.2}, {'blocks': [{'name': 'z', 'refs': ['C1', 'C2', 'U1']}]}) == {'z': ['C1', 'C2']})

# 7. decide_faces: what is listed, and the FAIL verdict
OWN = faces_v5.decap_owners(V5 + '/fixed.kicad_pcb')
res = decide_faces.decide(gr, it, cans, probe, NI, OWN)
expect('decide: real inputs PASS; flippable counts 12 / 13 / 0 / 0 / 0 / 15; each can ends <= 0.65 on F and on B', res['verdict'] == 'PASS' and [len(res['plans'][c]['picks']) for c in cans] == [12, 13, 0, 0, 0, 15]
       and all(res['plans'][c]['F'] <= 0.65 and res['plans'][c]['B'] <= 0.65 for c in cans))
expect('decide: the picks are exactly what the groups file carries (idempotent: deciding on the decided inputs gives the same lists)',
       all(sorted(res['plans'][c]['picks']) == sorted(flips[c]) for c in cans) and decide_faces.decide(res['groups'], res['intent'], res['cans'], probe, NI, OWN)['groups'] == res['groups'])
pk = {c: res['plans'][c]['picks'] for c in cans}
bad_pick = [r for c in cans for r in pk[c] if faces_v5.ineligible_reason(r, NI, probe['dims'], RF['parts'])]
expect('decide: no pick is an IC, an RF-path part, a part of >= 20 mm2, or from another can', bad_pick == [] and all(set(pk[c]) <= set(cans[c]['members']) for c in cans))
j12_ics = [r for r in cans['J12']['members'] if r[0] == 'U']
own_first = [r for r in pk['J12'] if faces_v5.pref_ranks(OWN, j12_ics).get(r, 9) < 9]
expect(f'decide: the decaps of the can\'s own ICs come first (J12: {len(own_first)} of {len(pk["J12"])} picks serve its ICs)', len(own_first) >= 10)
i7 = dc(it); b7 = [b for b in i7['blocks'] if b['name'] == 'canJ8'][0]; b7['zone'] = [b7['zone'][0], b7['zone'][1], b7['zone'][0] + 27.0, b7['zone'][1] + 27.0]
r7 = decide_faces.decide(gr, i7, cans, probe, NI, OWN)
expect(f'MUST FAIL: J8 squeezed to 27 x 27 mm: every eligible part flipped and the front still over 0.65 -> verdict FAIL, shortfall {r7["shortfall"]}', r7['verdict'] == 'FAIL' and r7['shortfall'].get('J8', 0) > 0
       and r7['plans']['J8']['F'] > 0.65 and len(r7['plans']['J8']['picks']) == r7['plans']['J8']['eligible'])
toy_i = {'blocks': [{'name': 'canJ1', 'refs': ['U1', 'U2'], 'zone': [0, 0, 10, 10], 'side': 'F'}], 'keepouts': [], 'envelope': {'rect': [0, 0, 100, 100]}}
toy_g = {'groups': [{'name': 'canJ1', 'refs': ['U1', 'U2'], 'side': 'F'}]}
toy_p = {'dims': {'U1': [8, 8], 'U2': [8, 8]}, 'side': {}, 'clearance': 0.2, 'fixed': [], 'rects': {}, 'edge_clearance': 0.0}
toy_c = {'J1': {'members': ['U1', 'U2'], 'zone': [0, 0, 10, 10], 'side': 'F'}}
rt = decide_faces.decide(toy_g, toy_i, toy_c, toy_p, {'nets': {}, 'values': {}, 'footprints': {}}, {})
expect(f'MUST FAIL: a can over the limit with no eligible part (two ICs in 10 x 10) -> verdict FAIL, shortfall {rt["shortfall"]} mm2, nothing listed, side stays F', rt['verdict'] == 'FAIL' and rt['shortfall']['J1'] > 0
       and rt['plans']['J1']['picks'] == [] and rt['groups']['groups'][0].get('side') == 'F')
toy_i2 = dc(toy_i); toy_g2 = dc(toy_g); toy_g2['groups'][0]['refs'] += ['C1']; toy_i2['blocks'][0]['refs'] += ['C1']; toy_p2 = dc(toy_p); toy_p2['dims']['C1'] = [3, 2]; toy_p2['dims']['U1'] = [6, 6]
toy_p2['dims']['U2'] = [6, 6]
rt2 = decide_faces.decide(toy_g2, toy_i2, toy_c, toy_p2, {'nets': {}, 'values': {}, 'footprints': {}}, {})
expect('toy: two ICs and one small capacitor in 10 x 10: C1 is listed flippable and the can loses its group side; the ICs are never listed', rt2['plans']['J1']['picks'] == ['C1'] and rt2['groups']['groups'][0].get('side') is None and rt2['cans']['J1'].get('side') is None
       and rt2['groups']['groups'][0]['flippable'] == ['C1'])

# 8. the post-check on a placed board (designer_check.check_members, synthetic parts: no pcbnew needed)
def board_parts(over=None):
    parts = {}
    for can, c in cans.items():
        z = c['zone']; cx, cy = (z[0] + z[2]) / 2, (z[1] + z[3]) / 2
        for r in c['members'] + list(c.get('optional') or []):
            parts[r] = {'face': 'F', 'x': cx, 'y': cy, 'rot': 0.0, 'pads': [], 'box': (cx - 1, cy - 1, cx + 1, cy + 1), 'fp': 'x'}
    for r, f in (over or {}).items():
        parts[r].update(f)
    return parts
def post(parts, cs=cans):
    cf = tempfile.mktemp(suffix='.json'); json.dump(cs, open(cf, 'w'))
    rep = designer_check.Report(); designer_check.check_members(rep, parts, cf, 0.5); os.remove(cf)
    return dict((n, o) for n, o, d in rep.rows)['members']
fl = flips['J7'][0]; z7 = cans['J7']['zone']
expect('post-check: every member on F passes', post(board_parts()) is True)
expect(f'post-check: flippable {fl} on B inside the J7 rect passes', post(board_parts({fl: {'face': 'B'}})) is True)
out_box = (z7[2] + 5, z7[1] + 5, z7[2] + 7, z7[1] + 7)
expect(f'MUST FAIL: flippable {fl} on B outside the J7 rect', post(board_parts({fl: {'face': 'B', 'box': out_box}})) is False)
nf = [r for r in cans['J7']['members'] if r[0] == 'C' and r not in flips['J7']][0]
expect(f'MUST FAIL: {nf} (a J7 member that is not flippable) on B inside the rect', post(board_parts({nf: {'face': 'B'}})) is False)
expect('MUST FAIL: IC U1 on B inside the J7 rect', post(board_parts({'U1': {'face': 'B'}})) is False)
expect('MUST FAIL: an IC outside every can (U31) on B', post({**board_parts(), 'U31': {'face': 'B', 'x': 10.0, 'y': 10.0, 'rot': 0.0, 'pads': [], 'box': (9, 9, 11, 11), 'fp': 'x'}}) is False)
old = {c: {k: v for k, v in d.items() if k not in ('side', 'flippable')} for c, d in cans.items()}
expect('post-check: a cans file with neither side nor flippable (the human reference) puts no face rule on a member on B', post(board_parts({nf: {'face': 'B'}}), old) is True)
print('FAILED: ' + ', '.join(fails) if fails else 'ALL HOLD')
sys.exit(1 if fails else 0)
