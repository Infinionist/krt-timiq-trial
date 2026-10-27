#!/usr/bin/env python3
"""Must-fail tests for gate.py, designer_check.py and the plan v3 inputs (courtyards, pin rows, BOX1, waivers). Run: python3 /tmp/pcb-trials/timiq/v5/tests/test_scripts.py (exit 0 = all hold).
Each test states what must FAIL and what must PASS, so a gate that always passes (or always fails) is caught."""
import json
import os
import re
import subprocess
import sys
import tempfile

V5 = '/tmp/pcb-trials/timiq/v5'
sys.path.insert(0, V5)
import gate  # noqa: E402

HUMAN = '/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb'
OLD = V5 + '/probe3/old'        # the inputs and scripts before plan v3 (2.0 mm pin rows, no courtyards, no BOX1 in the can allow lists): fail-first fixtures
fails = []
TMP = []


def tmpjson(obj, suffix='.json'):
    f = tempfile.mktemp(suffix=suffix)
    json.dump(obj, open(f, 'w'))
    TMP.append(f)
    return f


def run(*cmd):
    return subprocess.run(list(cmd), capture_output=True, text=True)


def gate_cli(*args):
    return run(sys.executable, V5 + '/gate.py', *args)


def expect(name, cond):
    print(('ok    ' if cond else 'FAIL  ') + name)
    if not cond:
        fails.append(name)


# ---- gate.py: coverage rules (pure) ----
ics = ['U1', 'U2', 'U3', 'U4']
intent = {'templates': [{'anchor': 'U1'}], 'proximity': [{'ref': 'C1', 'near': 'U2'}]}
groups = {'groups': [{'templates': [
    {'chip': 'U3', 'kind': 'none', 'why': 'the oscillator module has no support parts to place'},
    {'chip': 'U4', 'skip': 'datasheet not fetched within the time cap'}]}]}
cov = gate.coverage(ics, intent, groups)
expect('gate: template row covers U1', cov['U1'][0] == 'template')
expect('gate: proximity row covers U2 (as near)', cov['U2'][0] == 'proximity')
expect('gate: a written reason covers U3', cov['U3'][0] == 'skip')
expect('gate MUST FAIL: the rejected excuse "not fetched ... time cap" does not cover U4', cov['U4'][0] is None)
expect('gate MUST FAIL: an IC with nothing is uncovered', gate.coverage(['U9'], {}, {'groups': []})['U9'][0] is None)
expect('gate MUST FAIL: a 10-character reason is rejected', gate.reason_problem('too short.') is not None)
expect('gate: a real reason passes', gate.reason_problem('SIM-73L+ passive mixer: no external support parts to place') is None)

# ---- gate.py: a skip never hides an IC the netlist could serve; an IC whose passives are claimed is covered ----
cand = {'U5': ['C27'], 'U6': []}
gs = {'groups': [{'templates': [{'chip': 'U5', 'skip': 'op-amp compensation only; nothing to place near it'},
                                  {'chip': 'U6', 'skip': 'op-amp with no support part on its signal nets'}]}]}
cov = gate.coverage(['U5', 'U6', 'U7'], {'proximity': []}, gs, cand)
expect('gate MUST FAIL: a valid-looking skip on an IC that has an unclaimed passive is rejected', cov['U5'][0] is None)
expect('gate: a skip on an IC with no passive candidates holds', cov['U6'][0] == 'skip')
cov = gate.coverage(['U5'], {'proximity': [{'ref': 'C27', 'near': 'U4'}]}, gs, cand)
expect('gate: an IC whose passive is claimed by a row (to another IC) is covered (netlist rows count)', cov['U5'][0] == 'proximity')
cov = gate.coverage(['U8'], {'templates': [{'anchor': 'U21', 'members': [{'ref': 'C108'}]}]}, {'groups': []}, {'U8': ['C108']})
expect('gate: an IC whose passive is a template member is covered', cov['U8'][0] == 'proximity')
expect('gate MUST FAIL: no rows, no skip, candidates unclaimed', gate.coverage(['U9'], {}, {'groups': []}, {'U9': ['R1']})['U9'][0] is None)

# ---- gate.py end to end on the real v5 inputs: passes; and every doctoring trips it ----
r = subprocess.run([sys.executable, V5 + '/gate.py'], capture_output=True, text=True)
expect('gate PASSES on the real v5 inputs (plan-only 0 errors, check_groups 0 errors, 45/45 ICs, cans)', r.returncode == 0 and 'GATE PASS' in r.stdout)
it = json.load(open(V5 + '/intent.json'))
it['blocks'].append({'name': 'doctored', 'refs': ['ZZ999'], 'zone': [140, 110, 150, 120], 'side': 'F'})
with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
    json.dump(it, f)
r = subprocess.run([sys.executable, V5 + '/gate.py', '--intent', f.name], capture_output=True, text=True)
expect('gate MUST FAIL: a doctored intent adds a plan-only error (check 1 trips)', r.returncode == 1 and 'plan-only' in r.stdout)
os.remove(f.name)
it = json.load(open(V5 + '/intent.json'))
it['proximity'] = [p for p in it['proximity'] if p['near'] != 'U1' and p['ref'] != 'U1']
it['proximity'] = [p for p in it['proximity'] if p['near'] != 'U38']
it['keepouts'] = [k for k in it['keepouts'] if k.get('name') != 'can-J11']
with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
    json.dump(it, f)
r = subprocess.run([sys.executable, V5 + '/gate.py', '--intent', f.name], capture_output=True, text=True)
expect('gate MUST FAIL: the can-J11 keep-out removed from the intent', r.returncode == 1 and 'no keep-out can-J11' in r.stdout)
os.remove(f.name)
c = json.load(open(V5 + '/cans.json'))
assert c['J9']['members'][0] not in c['J9']['anchors']
c['J9']['members'] = c['J9']['members'][1:]
r = gate_cli('--cans', tmpjson(c))
expect('gate MUST FAIL: cans.json and the intent disagree on a can member (block can J9)', r.returncode == 1 and 'J9/block' in r.stdout)
c = json.load(open(V5 + '/cans.json'))
M = lambda can: c[can]['members']
expect('cans.json: U10/U11 in J9, U3 in J8, none in J12/J7', {'U10', 'U11'} <= set(M('J9')) and 'U3' in M('J8')
       and not ({'U10', 'U11', 'C45', 'R57'} & set(M('J12'))) and 'U3' not in M('J7'))
expect('cans.json: U3 moved with R14,R16,R17,R165,C20 to J8 (plan v3 item 5)', {'U3', 'R14', 'R16', 'R17', 'R165', 'C20'} <= set(M('J8')))
expect('cans.json: the 8 J10 optional parts are in no can block', len(c['J10']['optional']) == 8 and not (set(c['J10']['optional']) & set(M('J10'))))
c['J10']['optional'] = c['J10']['optional'][1:]
r = gate_cli('--cans', tmpjson(c))
expect('gate MUST FAIL: an optional part dropped from cans.json but still allowed in the keep-out', r.returncode == 1 and 'J10/keepout' in r.stdout)

# ---- plan v3 block shapes (pure cans_problems on doctored copies): can<J> per can (no anchor zone since Infinionist 10-27) with the anchor marker and its pull rows ----
cans0 = json.load(open(V5 + '/cans.json'))
it0 = json.load(open(V5 + '/intent.json'))
refs0 = gate.ics_all_refs(V5 + '/fixed.kicad_pcb')
dcopy = lambda o: json.loads(json.dumps(o))
expect('gate: cans_problems on the real inputs is empty (can<J> blocks, markers, anchor rows; power tiles are in the section below)', gate.cans_problems(cans0, it0, refs0) == {})
x = dcopy(it0)
x['blocks'].append({'name': 'canJ9_anchor', 'refs': ['U10', 'U11'], 'zone': [172.0, 142.0, 195.0, 155.0], 'tolerance_mm': 1.0})
expect('gate MUST FAIL: an anchor zone block canJ9_anchor in the intent (no anchor zone, Infinionist 10-27)', 'J9/anchor' in gate.cans_problems(cans0, x, refs0))
x = dcopy(it0)
[b for b in x['blocks'] if b['name'] == 'canJ7'][0]['exclusive'] = True
expect('gate MUST FAIL: any exclusive block (it pushes the anchor IC own decaps out of the area)', 'intent/exclusive/canJ7' in gate.cans_problems(cans0, x, refs0))
x = dcopy(it0)
x['blocks'] = [b for b in x['blocks'] if b['name'] != 'pw_U39']
g0 = json.load(open(V5 + '/groups.json'))
expect('gate MUST FAIL: the pw_U39 power tile removed (its 8 parts have no tile; plan v4 replaced the one-piece power block)',
       sum(1 for k in gate.power_problems(x, g0, set()) if k.startswith('power/pw_U39/')) == 8)
x = dcopy(it0)
x['proximity'] = [r_ for r_ in x['proximity'] if r_['near'] != 'MK8']
expect('gate MUST FAIL: the anchor pull row U16 -> MK8 removed', 'J8/anchor-row/U16' in gate.cans_problems(cans0, x, refs0))
x = dcopy(it0)
[r_ for r_ in x['proximity'] if r_['near'] == 'MK8'][0]['max_mm'] = 2.0
expect('gate MUST FAIL: the anchor pull row at 2 mm is a wall, not a pull (6-8 mm)', 'J8/anchor-row/U16' in gate.cans_problems(cans0, x, refs0))
x = dcopy(it0)
[r_ for r_ in x['proximity'] if r_['near'] == 'MK8'][0]['max_mm'] = 20.0
expect('gate MUST FAIL: the anchor pull row at 20 mm pulls nothing', 'J8/anchor-row/U16' in gate.cans_problems(cans0, x, refs0))
x = dcopy(it0)
x['fixed_poses'] = [f_ for f_ in x['fixed_poses'] if f_['ref'] != 'MK10']
expect('gate MUST FAIL: marker MK10 without a fixed pose in the intent', 'J10/marker' in gate.cans_problems(cans0, x, refs0))
c_ = dcopy(cans0)
c_['J10']['anchor_marker']['x'] = 100.0
expect('gate MUST FAIL: marker MK10 outside / off its declared pose', 'J10/marker' in gate.cans_problems(c_, it0, refs0))
x = dcopy(it0)
[k_ for k_ in x['keepouts'] if k_['name'] == 'can-J12'][0]['allow'].remove('MK12')
expect('gate MUST FAIL: marker MK12 missing from the can-J12 keep-out allow list', 'J12/keepout' in gate.cans_problems(cans0, x, refs0))
x = dcopy(it0)
[b for b in x['blocks'] if b['name'] == 'canJ10'][0]['side'] = 'F'
expect('gate MUST FAIL: a can block pinned to a face (faces are free in plan v3)', 'J10/block' in gate.cans_problems(cans0, x, refs0))
x = dcopy(it0)
[b for b in x['blocks'] if b['name'] == 'canJ11'][0]['refs'].remove('U29')
expect('gate MUST FAIL: the anchor IC U29 missing from the member block (the anchors are members now: no anchor block holds them)', 'J11/block' in gate.cans_problems(cans0, x, refs0))

# ---- plan v3 item 1: courtyards. Old board (probe3/old) has none; a copy of the real board with one courtyard taken away ----
import add_courtyards  # noqa: E402
import cans_io  # noqa: E402
r = gate_cli('--board', OLD + '/fixed.kicad_pcb')
expect('gate MUST FAIL (fail-first, old board): footprints without a courtyard', r.returncode == 1 and 'without a courtyard' in r.stdout)
tb = open(V5 + '/fixed.kicad_pcb', encoding='utf-8').read()
fps = {ref: (a, b) for a, b, ref in cans_io.scan_footprints(tb)}
a, b = fps['C130']
blk = tb[a:b]
assert add_courtyards.has_courtyard(blk)
nb = tb[:a] + blk.replace('"F.CrtYd"', '"F.Fab"').replace('"B.CrtYd"', '"B.Fab"') + tb[b:]
assert not add_courtyards.has_courtyard(nb[a:a + len(blk)])
nocy = tempfile.mktemp(suffix='.kicad_pcb')
open(nocy, 'w', encoding='utf-8').write(nb)
TMP.append(nocy)
r = gate_cli('--board', nocy)
expect('gate MUST FAIL: the real board with the courtyard of C130 taken away names C130 (1 footprint)', r.returncode == 1 and '1 footprint(s) without a courtyard' in r.stdout and 'C130' in r.stdout)
r = gate_cli()
expect('gate: the real board has 0 footprints without a courtyard (BOX1 excepted)', r.returncode == 0 and 'without a courtyard' not in r.stdout)
expect('add_courtyards: every footprint has a courtyard, BOX1 (the pin frame) only the 0.2 mm POINT one (plan v4)', all(add_courtyards.has_courtyard(tb[a_:b_]) for ref_, (a_, b_) in fps.items())
       and add_courtyards.frame_courtyard_size(tb, 'BOX1') == (0.2, 0.2))

# ---- plan v3 item 5: pin rows are 3.0 mm (a part named at a pin); the old 2.0 mm rows fail ----
rea0 = json.load(open(V5 + '/intent_reattached.json'))
pins = [r_ for r_ in it0['proximity'] if r_.get('pads')]
expect('pin rows: all rows with pads in intent.json are 3.0 mm (286 of them: plan v4 adds the power-tile pin rows), the rest are 5.0 part rows', len(pins) == 286 and all(r_['max_mm'] == 3.0 for r_ in pins)
       and all(r_['max_mm'] == (7.0 if r_['near'].startswith('MK') else 5.0) for r_ in it0['proximity'] if not r_.get('pads')))
expect('pin rows: gate.inputs_problems on the real inputs is empty', gate.inputs_problems(it0, rea0, cans0) == {})
x = dcopy(it0)
[r_ for r_ in x['proximity'] if r_.get('pads')][5]['max_mm'] = 2.0
bad = gate.inputs_problems(x, rea0, cans0)
expect('pin rows MUST FAIL: one pin row at 2.0 mm', len(bad) == 1 and 'pin-row' in list(bad)[0] and '2' in list(bad.values())[0])
old_it = json.load(open(OLD + '/intent.json'))
expect('pin rows MUST FAIL (fail-first, old intent): 246 pin rows at 2.0 mm', sum(1 for k in gate.inputs_problems(old_it, rea0, cans0) if 'pin-row' in k) == 246)
r = gate_cli('--intent', OLD + '/intent.json')
expect('gate MUST FAIL (fail-first, old intent): pin rows at 2.0 mm reported by the CLI', r.returncode == 1 and 'pin row max_mm 2.0' in r.stdout)
r = gate_cli('--intent', tmpjson(x))
expect('gate MUST FAIL: the CLI on an intent with one 2.0 mm pin row', r.returncode == 1 and 'pin row max_mm 2.0' in r.stdout)

# ---- plan v3 item 6: BOX1 in the allow lists; post-check waivers (reattached intent) ----
x = dcopy(it0)
[k for k in x['keepouts'] if k['name'] == 'wall-band-left'][0]['allow'].remove('BOX1')
bad = gate.inputs_problems(x, rea0, cans0)
expect('BOX1 MUST FAIL: BOX1 missing from the wall-band-left allow list', list(bad) == ['intent/keepout/wall-band-left'])
x = dcopy(it0)
[k for k in x['keepouts'] if k['name'] == 'can-J8'][0]['allow'].remove('BOX1')
r = gate_cli('--intent', tmpjson(x))
expect('BOX1 MUST FAIL: BOX1 missing from the can-J8 allow list (CLI)', r.returncode == 1 and 'intent/keepout/can-J8' in r.stdout and 'J8/keepout' in r.stdout)
r = gate_cli('--intent', OLD + '/intent.json')
expect('BOX1 MUST FAIL (fail-first, old intent): the old can keep-outs lack BOX1', r.returncode == 1 and 'intent/keepout/can-J7' in r.stdout)
x = dcopy(rea0)
[k for k in x['keepouts'] if k['name'] == 'can-J9'][0]['allow'].remove('BOX1')
expect('BOX1 MUST FAIL: BOX1 missing from the can-J9 allow list of the reattached intent', list(gate.inputs_problems(it0, x, cans0)) == ['reattached/keepout/can-J9'])
x = dcopy(rea0)
[k for k in x['keepouts'] if k['name'] == 'can-J9'][0]['allow'].remove('J11')
expect('BOX1 MUST FAIL: a can missing from the reattached allow list', list(gate.inputs_problems(it0, x, cans0)) == ['reattached/keepout/can-J9'])
nw = len(rea0['overlap_waivers'])
expect('waivers: one per can x (member + optional part + anchor marker), 296 in all', nw == sum(len(c_['members']) + len(c_['optional']) + 1 for c_ in cans0.values()) == 296)
x = dcopy(rea0)
x['overlap_waivers'] = [w for w in x['overlap_waivers'] if w['pair'] != ['J7', 'C2']]
bad = gate.inputs_problems(it0, x, cans0)
expect('waiver MUST FAIL: the J7/C2 waiver removed', list(bad) == ['reattached/waiver/J7'] and 'C2' in bad['reattached/waiver/J7'])
r = gate_cli('--reattached', tmpjson(x))
expect('waiver MUST FAIL: the CLI with a reattached intent missing a waiver', r.returncode == 1 and 'reattached/waiver/J7' in r.stdout)
x = dcopy(rea0)
x['overlap_waivers'] = [w for w in x['overlap_waivers'] if w['pair'][0] != 'J10' or w['pair'][1] not in cans0['J10']['optional']]
expect('waiver MUST FAIL: the optional parts of J10 have no waiver', list(gate.inputs_problems(it0, x, cans0)) == ['reattached/waiver/J10'])
# the waivers are read by KRT (check_assembly on the human board, cans over their members): with all 296 more pairs are waived than with none or with J7's missing
KP = '/tmp/pcb-trials/timiq/krt/.venv/bin/python'


def waived(intent_file):
    out = tempfile.mktemp(suffix='.json')
    TMP.append(out)
    cmd = [KP, '-X', 'utf8', '/tmp/pcb-trials/timiq/krt/py_tools/check_assembly.py', HUMAN, '--json', out] + (['--intent', intent_file] if intent_file else [])
    subprocess.run(cmd, capture_output=True, text=True)
    return json.load(open(out))['waived']


w_none, w_all = waived(None), waived(V5 + '/intent_reattached.json')
x = dcopy(rea0)
x['overlap_waivers'] = [w for w in x['overlap_waivers'] if w['pair'][0] != 'J7']
w_no7 = waived(tmpjson(x))
expect(f'waivers: check_assembly reads them (waived pairs on the human board: none {w_none}, all {w_all}, without J7 {w_no7})', w_none < w_no7 < w_all)
r = subprocess.run([sys.executable, V5 + '/gate.py', '--board', V5 + '/t2/pile_again.kicad_pcb'], capture_output=True, text=True)
expect('gate MUST FAIL: a board that still carries the can footprints', r.returncode == 1 and 'on the placing board' in r.stdout)

# ---- reattach.py / cans_io.py (option (d)) ----
import cans_io  # noqa: E402
import reattach  # noqa: E402
PILE = '/tmp/pcb-trials/timiq/run/fixed.kicad_pcb'
side_f, poses_f = tempfile.mktemp(suffix='.json'), tempfile.mktemp(suffix='.json')
nocans = tempfile.mktemp(suffix='.kicad_pcb')
rc = cans_io.main(['strip', PILE, nocans, side_f, poses_f])
t0 = open(PILE).read()
t1 = open(nocans).read()
refs0 = {r for _, _, r in cans_io.scan_footprints(t0)}
refs1 = {r for _, _, r in cans_io.scan_footprints(t1)}
expect('cans_io strip: exactly J7-J12 leave the board', rc == 0 and refs0 - refs1 == set(cans_io.CANS) and refs1 <= refs0)
back = tempfile.mktemp(suffix='.kicad_pcb')
r = subprocess.run([sys.executable, V5 + '/reattach.py', nocans, back, '--side', side_f, '--poses', poses_f], capture_output=True, text=True)
expect('reattach: all six cans come back (exit 0)', r.returncode == 0 and 'reattached 6' in r.stdout)
tb = open(back).read()
fb = {r: tb[s:e] for s, e, r in cans_io.scan_footprints(tb)}
f1 = {r: t1[s:e] for s, e, r in cans_io.scan_footprints(t1)}
expect('reattach: every other footprint is byte-identical', all(fb[r] == f1[r] for r in f1) and set(fb) - set(f1) == set(cans_io.CANS))
pj = json.load(open(poses_f))
expect('reattach: each can sits at its declared pose', all(abs(cans_io.footprint_pose(fb[c])[0] - pj[c]['x']) < 1e-4 and abs(cans_io.footprint_pose(fb[c])[1] - pj[c]['y']) < 1e-4 for c in pj))
r = subprocess.run([sys.executable, V5 + '/reattach.py', back, back + '.2', '--side', side_f, '--poses', poses_f], capture_output=True, text=True)
expect('reattach MUST FAIL: a can already on the board (exit 1, nothing written)', r.returncode == 1 and 'already on the board' in r.stderr and not os.path.exists(back + '.2'))
sd = json.load(open(side_f))
sd['J7'] = sd['J7'].replace('(net "GND")', '(net "NO_SUCH_NET")', 1)
bad_side = tempfile.mktemp(suffix='.json')
json.dump(sd, open(bad_side, 'w'))
r = subprocess.run([sys.executable, V5 + '/reattach.py', nocans, back + '.3', '--side', bad_side, '--poses', poses_f], capture_output=True, text=True)
expect('reattach MUST FAIL: a pad net the board does not have', r.returncode == 1 and 'NO_SUCH_NET' in r.stderr)
probs = reattach.verify(t1, sd, pj)
expect('reattach.verify MUST FAIL on a board without the cans', len(probs) == 6)
p = tempfile.mktemp(suffix='.json')
json.dump({k: dict(v, x=v['x'] + 1.0) if k == 'J8' else v for k, v in pj.items()}, open(p, 'w'))
probs = reattach.verify(tb, json.load(open(side_f)), json.load(open(p)))
expect('reattach.verify MUST FAIL when a can sits off its declared pose', len(probs) == 1 and 'J8' in probs[0])
# without the cans the designer check's box check fails, with them it holds
hnc, hside, hposes, hback = (tempfile.mktemp(suffix=e) for e in ('.kicad_pcb', '.json', '.json', '.kicad_pcb'))
cans_io.main(['strip', HUMAN, hnc, hside, hposes])
subprocess.run([sys.executable, V5 + '/reattach.py', hnc, hback, '--side', hside, '--poses', hposes], capture_output=True, text=True)


def dcbox(b):
    out = tempfile.mktemp(suffix='.json')
    subprocess.run([sys.executable, V5 + '/designer_check.py', b, '--baseline', 'none', '--json', out], capture_output=True, text=True)
    return {x['check']: x['pass'] for x in json.load(open(out))}.get('box')
expect('designer_check box MUST FAIL on the board without the cans, and hold with them reattached', dcbox(hnc) is False and dcbox(hback) is True)
for f in (side_f, poses_f, nocans, back, bad_side, p, hnc, hside, hposes, hback):
    if os.path.exists(f):
        os.remove(f)

# ---- calibrate_holes.py: the clearance counts from the HOLE edge ----
import calibrate_holes as ch  # noqa: E402
expect('holes: no part near -> radius = drill/2 + 3.5 (BOX1 drill 4.0 -> 5.5; the pad-edge rule gave 6.25)', ch.radius_for(4.0, None) == 5.5 and ch.radius_for(4.0, None) != 5.5 / 2 + 3.5)
expect('holes: a human part hits at 3.475 from the centre of a 4.35 hole -> radius 3.425 (clearance 1.25 from the hole edge)', ch.radius_for(4.35, 3.475) == 3.425)
expect('holes: a part far away never raises the radius above drill/2 + 3.5 (3.1 hole -> 5.05)', ch.radius_for(3.1, 9.0) == 5.05)
expect('holes: the radius never drops below the hole itself', ch.radius_for(3.1, 1.0) == 1.55)
hj = json.load(open(V5 + '/holes.json'))
expect('holes.json: every radius = drill/2 + clearance_from_hole_edge, clearance <= 3.5', all(abs(h['radius'] - h['drill'] / 2 - h['clearance_from_hole_edge']) < 1e-6 and h['clearance_from_hole_edge'] <= 3.5 + 1e-9 for h in hj))
expect('holes.json MUST NOT carry the pad-edge key any more', all('clearance_from_pad_edge' not in h for h in hj))

# ---- netrows.py (KRT venv) ----
r = subprocess.run(['/tmp/pcb-trials/timiq/krt/.venv/bin/python', '-X', 'utf8', V5 + '/tests/test_netrows.py'], capture_output=True, text=True)
print(r.stdout.rstrip())
expect('netrows tests (own file, KRT venv)', r.returncode == 0)

# ---- designer_check.py ----
# the human board is graded against the NEUTRAL part of the v5 intent (fixed poses, wall band, holes): the claims the placer is asked to
# meet (can blocks, proximity, templates, can keep-outs) are stricter than the human's own layout, which fails them by design
_it = json.load(open(V5 + '/intent.json'))
for _k in ('blocks', 'proximity', 'templates'):
    _it.pop(_k, None)
_it['keepouts'] = [k for k in _it['keepouts'] if not k['name'].startswith('can-')]
_it['fixed_poses'] = [f_ for f_ in _it['fixed_poses'] if not f_['ref'].startswith('MK')]      # the human board has no anchor markers
NEUTRAL = tempfile.mktemp(suffix='.json')
json.dump(_it, open(NEUTRAL, 'w'))


def parse(out):
    """({check: pass} over the real checks, {check: [info rows]}) from a designer_check --json file."""
    if not os.path.exists(out):
        return {}, {}
    rows, infos = {}, {}
    for x in json.load(open(out)):
        if x.get('info'):
            infos.setdefault(x['check'], []).append(x)
        else:
            rows[x['check']] = x['pass']
    return rows, infos


def dcx(script, board, *args, cans=V5 + '/human_cans_ref.json'):
    out = tempfile.mktemp(suffix='.json')
    TMP.append(out)
    extra = ['--holes', V5 + '/holes.json', '--mech', V5 + '/mechanical.json', '--poses', V5 + '/cans_poses.json'] if script.startswith(OLD) else []
    p = subprocess.run([sys.executable, script, board, '--baseline', 'none', '--waive', 'C20/R16', '--cans', cans, '--json', out] + extra + list(args),
                       capture_output=True, text=True)
    return p, parse(out)


def dc(*args):
    p, (rows, infos) = dcx(V5 + '/designer_check.py', HUMAN, '--intent', NEUTRAL, *args)
    return p.returncode, rows


rc, rows = dc()
expect('designer_check: human board passes members/band/box/window/holes/assembly(waived)', all(rows.get(k) for k in ('members', 'band', 'box', 'window', 'holes', 'assembly')))
expect('designer_check: the human board passes overall with C20/R16 waived (target, 8/8 checks; info lines are not checks)', rc == 0 and all(rows.values()) and len(rows) == 8)
# doctored hole radii: every circle 40 mm wide must trip holes
h = json.load(open(V5 + '/holes.json'))
for x in h:
    x['radius'] = 40.0
rc, rows = dc('--holes', tmpjson(h))
expect('designer_check MUST FAIL: doctored 40 mm hole radii trip the holes check', rows.get('holes') is False)
rc, rows = dc('--max-far', '0')
expect('designer_check MUST FAIL: --max-far 0 trips the far check', rows.get('far') is False)
# the pile (not a placement) must not pass
p = subprocess.run([sys.executable, V5 + '/designer_check.py', V5 + '/fixed.kicad_pcb', '--baseline', 'none'], capture_output=True, text=True)
expect('designer_check MUST FAIL on the unplaced pile (exit 1)', p.returncode == 1)

# ---- plan v3 item 6 / task 1: members count on either face; optional parts are not intruders; a real intruder still fails ----
OLD_DC = OLD + '/designer_check.py'
c0 = json.load(open(V5 + '/human_cans_ref.json'))
moved = c0['J7']['refs']['F'][-1]
c = dcopy(c0)
c['J7']['refs']['F'].remove(moved)
c['J7']['refs']['B'].append(moved)
p, (rows, _i) = dcx(V5 + '/designer_check.py', HUMAN, '--intent', NEUTRAL, cans=tmpjson(c))
expect(f'designer_check: a member ({moved}) declared on the other face still counts, members PASS (faces are free, plan v3)', rows.get('members') is True)
p, (rows, _i) = dcx(OLD_DC, HUMAN, '--intent', NEUTRAL, cans=tmpjson(c))
expect(f'designer_check MUST FAIL (fail-first, old script): the same {moved} on the other face trips the old face check', rows.get('members') is False)
# a part that sits in a can but is no member: an intruder (real); listed as optional: not an intruder
victim = [r_ for r_ in c0['J9']['refs']['F'] if r_.startswith('C')][3]
c = dcopy(c0)
c['J9']['refs']['F'].remove(victim)
p, (rows, _i) = dcx(V5 + '/designer_check.py', HUMAN, '--intent', NEUTRAL, cans=tmpjson(c))
expect(f'designer_check MUST FAIL: {victim} sits in the J9 zone but is no member: a real intruder still fails', rows.get('members') is False and f'{victim}@' in p.stdout)
c['J9']['optional'] = [victim]
p, (rows, _i) = dcx(V5 + '/designer_check.py', HUMAN, '--intent', NEUTRAL, cans=tmpjson(c))
expect(f'designer_check: the same {victim} listed under "optional" is not an intruder (members PASS)', rows.get('members') is True and '1 optional' in p.stdout)
p, (rows, _i) = dcx(OLD_DC, HUMAN, '--intent', NEUTRAL, cans=tmpjson(c))
expect(f'designer_check MUST FAIL (fail-first, old script): the old script ignores "optional" and reports {victim} as an intruder', rows.get('members') is False)
c = dcopy(c0)
c['J9']['refs']['F'] = [r_ for r_ in c['J9']['refs']['F'] if r_ != victim]
c['J9']['refs']['B'] = [r_ for r_ in c['J9']['refs']['B'] if r_ != victim]
c['J9']['optional'] = [victim]
c['J9']['refs']['F'].append('C9999')       # a member that is not on the board must still fail
p, (rows, _i) = dcx(V5 + '/designer_check.py', HUMAN, '--intent', NEUTRAL, cans=tmpjson(c))
expect('designer_check MUST FAIL: a declared member that is not on the board', rows.get('members') is False and 'C9999' in p.stdout)

# ---- LED series resistors are left out of the far check ----
import designer_check as dcm  # noqa: E402
pcb, brd = dcm.load_board(HUMAN)
hp = dcm.parts_of(pcb, brd)
leds = dcm.led_resistors(hp)
expect('far: the 8 LED series resistors of the human board are R1, R154, R155, R160-R164', leds == {'R1', 'R154', 'R155', 'R160', 'R161', 'R162', 'R163', 'R164'})
farl, nmeas, lr = dcm.far_list(hp, 10.0)
expect('far: 28 of 372 passives far on the human board with the LED resistors out (HUMAN_FAR is 28)', len(farl) == 28 == dcm.HUMAN_FAR and nmeas == 372)
expect('far: no LED resistor in the far list', not ({r_ for r_, _d in farl} & leds))
rc, rows = dc('--max-far', '28')
expect('far: --max-far 28 passes on the human board', rows.get('far') is True)
rc, rows = dc('--max-far', '27')
expect('far MUST FAIL: --max-far 27 fails (the 28 left are real passives, not LED resistors)', rows.get('far') is False)
p, (rows, _i) = dcx(OLD_DC, HUMAN, '--intent', NEUTRAL, '--max-far', '28')
expect('far MUST FAIL (fail-first, old script): the old script counts the LED resistors (36) and fails the limit 28', rows.get('far') is False)

# ---- info lines: anchors (misses are info, not a failure), filter-reg, keep_away ----
c = dcopy(c0)
c['J7']['anchors'] = ['U1']
c['J7']['anchor_marker'] = {'ref': 'MK7', 'x': 0.0, 'y': 0.0}
c['J7']['anchor_max_mm'] = 7.0
p, (rows, infos) = dcx(V5 + '/designer_check.py', HUMAN, '--intent', NEUTRAL, cans=tmpjson(c))
a_ = infos.get('anchors', [{}])[0]
expect('anchors: an anchor IC far from its marker is an INFO miss, the run still passes (exit 0, 8/8)', p.returncode == 0 and 'anchors' not in rows and len(rows) == 8
       and len(a_.get('data', {}).get('misses', [])) == 1 and 'U1' in a_['data']['misses'][0] and 'INFO  anchors' in p.stdout)
p, (rows, infos) = dcx(V5 + '/designer_check.py', HUMAN, '--intent', NEUTRAL, cans=V5 + '/cans.json')
a_ = infos['anchors'][0]['data']
expect('anchors: plan v4 cans.json (markers, 7 mm pull) on the human board: 7 anchor ICs, 5 within the pull, U11 (9.1 mm) and U4 (9.4 mm) not; an info reading, not a failure',
       a_['n'] == 7 and len(a_['misses']) == 2 and any('U11@F (J9) 9.1' in m for m in a_['misses']) and any('U4@F (J12) 9.4' in m for m in a_['misses']))
p, (rows, infos) = dcx(OLD_DC, HUMAN, '--intent', NEUTRAL)
expect('anchors/filter-reg/keep_away MUST FAIL (fail-first, old script): the old script prints none of the new info lines', 'INFO' not in p.stdout)
p, (rows, infos) = dcx(V5 + '/designer_check.py', HUMAN, '--intent', NEUTRAL)
fr = infos['filter-reg'][0]['data']
expect('filter-reg: human board, power-entry parts to the regulator they serve: L13 -> U43 20.0 mm, L14 -> U45 20.4, C149 36.8 is the max', fr['per']['L13'] == [20.0, 'U43']
       and fr['per']['L14'] == [20.4, 'U45'] and fr['worst'] == 'C149' and fr['max_mm'] == 36.8)
expect('filter-reg: it is a reading, not a check (no "filter-reg" among the PASS/FAIL rows)', 'filter-reg' not in rows and 'keep_away' not in rows)
ka = infos['keep_away']
expect('keep_away: two rules read, the digital rule min 2.07 mm (U1 pad 20 to C3 pad 1) INSIDE the 3 mm gap, the power rule min 28.61 mm outside',
       len(ka) == 2 and ka[0]['data']['min_mm'] == 2.07 and ka[0]['data']['inside'] is True and 'C3 pad 1' in ka[0]['data']['closest']
       and ka[1]['data']['min_mm'] == 28.61 and ka[1]['data']['inside'] is False)
expect('keep_away: per victim group minima of rule 0: LO/PLL 2.07, ADC inputs 2.52, RF notches 3.65, DAC I/Q 14.0', ka[0]['data']['by_group'] == {
    'ADC inputs': 2.52, 'DAC I/Q outputs': 14.0, 'LO / PLL out': 2.07, 'RF to the SMA notches J1-J4': 3.65})
# KRT's own reading of the same rule on the same board (check_floorplan JSON) must agree with ours to 0.01 mm
kj = tempfile.mktemp(suffix='.json')
TMP.append(kj)
subprocess.run([KP, '-X', 'utf8', '/tmp/pcb-trials/timiq/krt/py_tools/check_floorplan.py', HUMAN, '--intent', V5 + '/intent.json', '--json', kj], capture_output=True, text=True)
kk = {m['index']: m['min_gap_mm'] for m in json.load(open(kj))['keep_away']}
expect(f'keep_away: our reading equals KRT check_floorplan min_gap_mm (KRT {kk}) within 0.01 mm', abs(kk[0] - ka[0]['data']['min_mm']) < 0.01 and abs(kk[1] - ka[1]['data']['min_mm']) < 0.01)
# a brief whose rule is violated: the reading shows INSIDE (pile board: parts stacked)
pp, (rp, ip) = dcx(V5 + '/designer_check.py', V5 + '/fixed.kicad_pcb')
expect('keep_away MUST FAIL-visible: on a board with parts piled up the digital rule reads INSIDE its gap (a reading that can say so)', any(r_['data'].get('inside') for r_ in ip['keep_away']))

# ================================================================ plan v4 (10-27): D2 / hole clearances, exclusive anchors, power tiles, courtyard probe, pin-row WARN ================================================================
RV3 = V5 + '/tests/runv3'          # the run v3 inputs (before plan v4): intent, groups, holes, preflight probe (D2 refused in hole-FIX5-1)
KPY = '/tmp/pcb-trials/timiq/krt/.venv/bin/python'
old3 = json.load(open(RV3 + '/intent.before.json'))
oldg = json.load(open(RV3 + '/groups.before.json'))
oldp = json.load(open(RV3 + '/probe_old.json'))
oldh = json.load(open(RV3 + '/holes.before.json'))
g0 = json.load(open(V5 + '/groups.json'))
mech_refs = {f['ref'] for f in json.load(open(V5 + '/mechanical.json'))['fixed']}
pj_new = tempfile.mktemp(suffix='.json')
TMP.append(pj_new)
r = run(KPY, '-X', 'utf8', V5 + '/preflight_probe.py', V5 + '/fixed.kicad_pcb', V5 + '/groups.json', V5 + '/intent.json', '--out', pj_new)
tbv = open(V5 + '/fixed.kicad_pcb', encoding='utf-8').read()
fpsv = {ref: (a, b) for a, b, ref in cans_io.scan_footprints(tbv)}
probe0 = json.load(open(pj_new)) if r.returncode == 0 and os.path.exists(pj_new) else {'refused': {'?': [r.stdout[-200:] + r.stderr[-200:]]}, 'dims': {}}
dims0 = probe0['dims']

viol = lambda rule, ref='C1', near=None, sev='error': {'rule': rule, 'ref': ref, 'severity': sev, 'measured': {'near': near}}
# ---- fix 1 (the gate's BOX1 courtyard check): frame_courtyard_size returned None for every footprint, so the gate failed on a board that HAS the point courtyard ----
expect('frame_courtyard_size: BOX1 (point courtyard) is (0.2, 0.2), not None (the regex bug)', add_courtyards.frame_courtyard_size(tbv, 'BOX1') == (0.2, 0.2))
u4 = add_courtyards.frame_courtyard_size(tbv, 'U4')
expect('frame_courtyard_size: U4 reads its real courtyard (11.7 x 11.528)', u4 is not None and round(u4[0], 1) == 11.7 and round(u4[1], 3) == 11.528)
expect('frame_courtyard_size MUST be None for a footprint without a courtyard (C130 with its courtyard moved to Fab)', add_courtyards.frame_courtyard_size(nb, 'C130') is None)
r = run(KPY, '-X', 'utf8', V5 + '/gate.py')
expect('gate PASSES on the real inputs (all checks, BOX1 point courtyard seen)', r.returncode == 0 and 'GATE PASS' in r.stdout)
a_, b_ = fpsv['BOX1']
bblk = tbv[a_:b_]
nb1 = tbv[:a_] + bblk.replace('"F.CrtYd"', '"F.Fab"') + tbv[b_:]
nb1f = tempfile.mktemp(suffix='.kicad_pcb')
open(nb1f, 'w', encoding='utf-8').write(nb1)
TMP.append(nb1f)
r = gate_cli('--board', nb1f)
expect('gate MUST FAIL: BOX1 without a courtyard (it would be graded on its pad box = the whole box)', r.returncode == 1 and 'BOX1 (the pin frame) must carry a POINT courtyard' in r.stdout)
big = add_courtyards.courtyard_item('F', (-5, -5, 5, 5))
nb2 = tbv[:a_] + bblk.replace('"F.CrtYd"', '"F.Fab"').replace('\n\t\t(pad ', '\n' + big + '\t\t(pad ', 1) + tbv[b_:]
nb2f = tempfile.mktemp(suffix='.kicad_pcb')
open(nb2f, 'w', encoding='utf-8').write(nb2)
TMP.append(nb2f)
r = gate_cli('--board', nb2f)
expect('gate MUST FAIL: BOX1 with a 10 x 10 mm courtyard (not a point)', r.returncode == 1 and 'BOX1 (the pin frame) must carry a POINT courtyard' in r.stdout)

# ---- fix 2: D2 stood inside hole-FIX5-1 in every run v3 seed ----
expect('run v3 probe (fail-first): KRT refused the declared pose of D2 in hole-FIX5-1', oldp['refused'] == {'D2': ["keep-out 'hole-FIX5-1'"]})
pb = gate.preflight_problems(old3, oldg, oldp, mech_refs)
expect('gate MUST FAIL: the run v3 inputs have D2 in hole-FIX5-1 (fixed-pose/D2)', 'fixed-pose/D2' in pb and 'hole-FIX5-1' in pb['fixed-pose/D2'])
r = gate_cli('--intent', RV3 + '/intent.before.json', '--groups', RV3 + '/groups.before.json')
expect('gate MUST FAIL: the CLI on the run v3 intent prints fixed-pose/D2', r.returncode == 1 and 'fixed-pose/D2' in r.stdout)
pjo = tempfile.mktemp(suffix='.json')
TMP.append(pjo)
r = run(KPY, '-X', 'utf8', V5 + '/preflight_probe.py', V5 + '/fixed.kicad_pcb', RV3 + '/groups.before.json', RV3 + '/intent.before.json', '--out', pjo)
expect('preflight_probe MUST FAIL on the run v3 intent: D2 refused (KRT\'s own predicate, 1.4 s, no placement)', r.returncode == 0 and json.load(open(pjo))['refused'].get('D2') == ["keep-out 'hole-FIX5-1'"])
expect('preflight_probe: 0 illegal fixed parts on the real inputs (refused empty, no too_big)', probe0.get('refused') == {} and probe0.get('too_big') == [])
expect('gate: preflight_problems on the real inputs is empty', gate.preflight_problems(it0, g0, probe0, mech_refs) == {})
h5 = {h['name']: h for h in hj}['hole-FIX5-1']
h5o = {h['name']: h for h in oldh}['hole-FIX5-1']
expect('holes.json: hole-FIX5-1 is cut back to 4.9 (the human clearance WITH courtyards; run v3 had 5.05) and D2 is not in its allow list', h5['radius'] == 4.9 and h5o['radius'] == 5.05 and 'D2' not in h5['allow'])
expect('calibrate_holes: the status LEDs D2-D8 count as human parts (not in FIXED); the other fixed parts stay', not any(r_.startswith('D') for r_ in ch.FIXED) and 'J5' in ch.FIXED)
cheat = {h['name']: h['radius'] for h in hj if h['name'] in ('hole-FIX6-1', 'hole-FIX7-1', 'hole-J5-2', 'hole-BOX1-5')}
expect('holes.json: the other tightened clearances stay (FIX6-1 4.6, FIX7-1 3.15, J5-2 2.325, BOX1-5 4.75)', cheat == {'hole-FIX6-1': 4.6, 'hole-FIX7-1': 3.15, 'hole-J5-2': 2.325, 'hole-BOX1-5': 4.75})

# ---- fix 3 (changed by Infinionist 10-27): NO exclusive anchor zone, no anchor zone at all: a marker MK<n> and a pull row per anchor IC ----
mk_rows = [r_ for r_ in it0['proximity'] if re.match(r'^MK\d+$', r_['near'])]
expect('anchors: no block of the real intent is exclusive or an anchor zone; 6 markers, 7 anchor pull rows (body, 7 mm); fit / overlap problems are empty',
       not any(b.get('exclusive') or b['name'].endswith('_anchor') for b in it0['blocks']) and len(mk_rows) == 7 and all(r_['basis'] == 'body' and r_['max_mm'] == 7.0 for r_ in mk_rows)
       and sorted({r_['near'] for r_ in mk_rows}) == sorted(c_['anchor_marker']['ref'] for c_ in cans0.values())
       and gate.fit_problems(it0, dims0) == {} and gate.overlap_problems(it0) == {})
expect('anchors: the markers are fixed poses of the intent (28 = 22 + 6) with a point courtyard, in the group of their anchor IC',
       len(it0['fixed_poses']) == 28 and all(add_courtyards.frame_courtyard_size(tbv, c_['anchor_marker']['ref']) == (0.2, 0.2) for c_ in cans0.values())
       and all(c_['anchor_marker']['ref'] in [g_ for g_ in g0['groups'] if c_['anchors'][0] in g_['refs']][0]['refs'] for c_ in cans0.values()))
x = dcopy(it0)
x['blocks'].append({'name': 'canJ12_anchor', 'refs': ['U4'], 'zone': [180.0, 114.0, 195.0, 129.0], 'tolerance_mm': 1.0, 'exclusive': True})
bad = gate.overlap_problems(x)
expect('anchor zone MUST FAIL: the plan v4 exclusive anchor zone (run v4 first cut) nested in canJ12 is an overlap and an exclusive block', list(bad) == ['canJ12+canJ12_anchor']
       and 'intent/exclusive/canJ12_anchor' in gate.cans_problems(cans0, x, refs0))
r = gate_cli('--intent', tmpjson(x))
expect('anchor zone MUST FAIL: the CLI on that intent (overlap/canJ12+canJ12_anchor and the exclusive block)', r.returncode == 1 and 'overlap/canJ12+canJ12_anchor' in r.stdout and 'intent/exclusive/canJ12_anchor' in r.stdout)
x = dcopy(it0)
x['blocks'].append({'name': 'canJ12_anchor', 'refs': ['U4'], 'zone': [180.0, 114.0, 195.0, 129.0], 'tolerance_mm': 1.0})
expect('anchor zone MUST FAIL: the same zone WITHOUT exclusive overlaps its can zone (intent_zone_overlap), the case run v3 died on', list(gate.overlap_problems(x)) == ['canJ12+canJ12_anchor'])
expect('anchor zone MUST FAIL (run v3 inputs): the 6 old anchor zones overlap their can zone (intent_zone_overlap)', len(gate.overlap_problems(old3)) == 6)
r = gate_cli('--intent', RV3 + '/intent.before.json', '--groups', RV3 + '/groups.before.json')
expect('anchor zone MUST FAIL (run v3 inputs): the CLI names the can anchor problems (anchor block, marker, pull row)', r.returncode == 1 and 'J9/anchor' in r.stdout and 'J9/marker' in r.stdout and 'overlap/canJ9+canJ9_anchor' in r.stdout)
x = dcopy(it0)
a2 = [b for b in x['blocks'] if b['name'] == 'canJ9'][0]
x['blocks'].append({'name': 'stray', 'refs': ['C1'], 'zone': [a2['zone'][0] + 2, a2['zone'][1] + 2, a2['zone'][2] - 2, a2['zone'][3] - 2]})
expect('overlap MUST FAIL: any zone inside a can zone (no nesting at all now)', 'canJ9+stray' in gate.overlap_problems(x) or 'stray+canJ9' in gate.overlap_problems(x))
# the pull is graded as a WARN by designer_check (a pull, not a wall)
arow = {(r_['ref'], r_['near']) for r_ in mk_rows}
vs2 = [viol('proximity', 'U1', 'MK7'), viol('proximity', 'U1', 'U2')]
fl2, wn2 = dcm.split_floorplan(vs2, set(), arow)
expect('anchor pull WARN: a miss of an anchor pull row is a warning, another part row stays a failure (and without the anchor rows known both fail)',
       len(wn2) == 1 and wn2[0]['measured']['near'] == 'MK7' and len(fl2) == 1 and len(dcm.split_floorplan(vs2, set())[0]) == 2)
expect('anchor pull WARN: designer_check.anchor_row_keys reads the 7 rows of the intent', dcm.anchor_row_keys(V5 + '/intent.json') == arow)

# ---- power tiles: pw_* ----
pw = [b for b in it0['blocks'] if b['name'].startswith('pw_')]
expect('power tiles: pw_in_R, pw_in_L, pw_7v5, pw_24v, pw_U39..pw_U45 are zoned blocks (11), the one-piece power block is gone',
       sorted(b['name'] for b in pw) == sorted(['pw_in_R', 'pw_in_L', 'pw_7v5', 'pw_24v'] + [f'pw_U{n}' for n in range(39, 46)]) and all(b.get('zone') for b in pw)
       and not any(b['name'] == 'power' for b in it0['blocks']))
expect('power tiles: gate.power_problems on the real inputs is empty (every power-group part in exactly one tile)', gate.power_problems(it0, g0, mech_refs) == {})
x = dcopy(it0)
[b for b in x['blocks'] if b['name'] == 'pw_U42'][0]['refs'].remove('U42')
bad = gate.power_problems(x, g0, mech_refs)
expect('power part MUST FAIL: U42 left out of every tile (no group block)', list(bad) == ['power/pw_U42/U42'] and 'in 0' in bad['power/pw_U42/U42'])
x = dcopy(it0)
[b for b in x['blocks'] if b['name'] == 'pw_U41'][0]['refs'].append('C165')   # C165 sits in another tile: now in two
expect('power part MUST FAIL: a part in two tiles', any('in 2 pw_* tile' in v for v in gate.power_problems(x, g0, mech_refs).values()))
r = gate_cli('--intent', tmpjson(dcopy(it0) | {'blocks': [b for b in it0['blocks'] if b['name'] != 'pw_U42']}))
expect('power part MUST FAIL: the CLI with the pw_U42 tile removed (8 parts without a tile)', r.returncode == 1 and 'power/pw_U42/' in r.stdout)
bad = gate.power_problems(old3, oldg, mech_refs)
expect('power part MUST FAIL (run v3 inputs): the one-piece power block (power/old) and 75 parts in no tile', 'power/old' in bad and sum(1 for k in bad if k.startswith('power/') and k != 'power/old') >= 70)
import power_v4  # noqa: E402
fx = dcm.parts_of(pcb, pcb.LoadBoard(V5 + '/fixed.kicad_pcb'))
NETS = {}
for r_, p_ in fx.items():
    for pad in p_['pads']:
        if pad[4]:
            NETS.setdefault(pad[4], []).append((r_, pad[5]))
power_refs = sorted({r_ for g in g0['groups'] if g['name'].startswith('pw_') and g['name'] != 'pw_misc' for r_ in g['refs'] if r_ != 'J6'}, key=lambda s: (s[0], int(s[1:])))
fpof = {r_: re.sub(r'^.*:', '', p_['fp']) for r_, p_ in fx.items()}
hpos = {r_: (p_['x'], p_['y']) for r_, p_ in hp.items()}
PWG, left = power_v4.split_groups(NETS, power_refs, ['U39', 'U40', 'U41', 'U42', 'U43', 'U44', 'U45'], ['L12', 'L13', 'L14'], ['J6'], fpof, hpos)
expect('power_v4.split_groups: the 75 power parts split into pw_in, pw_7v5, pw_24v and 7 regulator groups, no leftover', len(power_refs) == 75 and not left
       and sum(len(g['refs']) for g in PWG.values()) == 75 and {'pw_in', 'pw_7v5', 'pw_24v'} | {f'pw_U{n}' for n in range(39, 46)} == set(PWG))
expect('power_v4.split_groups: the groups equal those in groups.json (same refs per group)', all(sorted(PWG[g['name']]['refs']) == sorted(r_ for r_ in g['refs'] if r_ != 'J6') for g in g0['groups'] if g['name'] in PWG))
NETS2 = dcopy(NETS)
NETS2['NET_ORPHAN'] = [('C9999', '1'), ('R9999', '1')]
NETS2['GND'] = NETS2['GND'] + [('C9999', '2'), ('R9999', '2')]
PWG2, left2 = power_v4.split_groups(NETS2, power_refs + ['C9999', 'R9999'], ['U39', 'U40', 'U41', 'U42', 'U43', 'U44', 'U45'], ['L12', 'L13', 'L14'], ['J6'], dict(fpof, C9999='C_0603', R9999='R_0603'), hpos)
expect('power part MUST FAIL: a power part on no group net is returned as leftover (build_inputs asserts none)', sorted(left2) == ['C9999', 'R9999'])
fill = gate.fill_problems(it0, dims0)
expect('power tiles: fill (member courtyards / 2 x zone) <= 0.5 on the real inputs', fill == {})
x = dcopy(it0)
tl = [b for b in x['blocks'] if b['name'] == 'pw_U40'][0]
tl['zone'] = [tl['zone'][0], tl['zone'][1], tl['zone'][0] + 8.0, tl['zone'][1] + 8.0]
expect('power tile MUST FAIL: pw_U40 squeezed to 8 x 8 mm (fill > 0.5)', 'pw_U40' in gate.fill_problems(x, dims0))

# ---- fix 4: designer_check grades pin-row proximity misses as WARN ----
prow = {(r_['ref'], r_['near']) for r_ in it0['proximity'] if r_.get('pads')}
sample = sorted(prow)[0]
vs = [viol('proximity', sample[0], sample[1]), viol('proximity', 'C77', 'U77'), viol('zone_exclusive'), viol('zone_containment'), viol('keepout'), viol('proximity', sample[0], sample[1], 'warn')]
fl, wn = dcm.split_floorplan(vs, prow)
expect('pin-row WARN: a pin-row proximity miss is a warning, the others (non-pin-row proximity, intruder, containment, keepout) stay failures, severity warn is ignored',
       len(wn) == 1 and wn[0]['ref'] == sample[0] and sorted(v['rule'] for v in fl) == ['keepout', 'proximity', 'zone_containment', 'zone_exclusive'])
expect('pin-row WARN MUST FAIL the old behaviour: with no pin rows known the same miss is a failure', len(dcm.split_floorplan(vs, set())[0]) == 5)
PROX = tempfile.mktemp(suffix='.json')
TMP.append(PROX)
_p = dict(_it)
_p['proximity'] = [r_ for r_ in it0['proximity'] if r_.get('pads')]
json.dump(_p, open(PROX, 'w'))
p, (rows, infos) = dcx(V5 + '/designer_check.py', HUMAN, '--intent', PROX)
expect('designer_check: the human board against the 286 pin rows alone: floorplan PASS with the misses as one WARN line (exit 0, 8/8), never a failure',
       p.returncode == 0 and rows.get('floorplan') is True and len(rows) == 8 and 'WARN  pin-rows' in p.stdout and infos['pin-rows'][0]['warn'] is True and infos['pin-rows'][0]['data']['n'] > 100
       and infos['pin-rows'][0]['data']['rows'] == 286)
p, (rows, infos) = dcx(OLD_DC, HUMAN, '--intent', PROX, '--holes', V5 + '/holes.json', '--mech', V5 + '/mechanical.json', '--poses', V5 + '/cans_poses.json')
expect('pin-row WARN MUST FAIL (fail-first, old script): the old designer_check fails the floorplan check on the same pin-row misses (exit 1)', p.returncode == 1 and rows.get('floorplan') is False)
bx = hp['U1']['box']
_k = dict(_p)
_k['keepouts'] = _p['keepouts'] + [{'name': 'test-keepout', 'rect': [bx[0] - 1, bx[1] - 1, bx[2] + 1, bx[3] + 1], 'sides': ['F', 'B'], 'allow': []}]
p, (rows, infos) = dcx(V5 + '/designer_check.py', HUMAN, '--intent', tmpjson(_k))
expect('pin-row WARN: a real keep-out failure stays a failure next to the WARN (floorplan FAIL, exit 1, the WARN line still printed)', p.returncode == 1 and rows.get('floorplan') is False and 'WARN  pin-rows' in p.stdout
       and 'keepout' in p.stdout)

# ---- render_floorplan: the power tiles and the anchor markers are drawn and labelled ----
import render_floorplan as rf  # noqa: E402
sv = rf.svgs()
tile_names = ['pw_in_R', 'pw_in_L', 'pw_7v5', 'pw_24v'] + [f'pw_U{n}' for n in range(39, 46)]
expect('render: both views label all 11 power tiles and all 6 anchor markers (no anchor zone), and no longer draw a one-piece POWER zone',
       all(all(f'>{n}<' in s for n in tile_names) for s in sv.values()) and all(s.count('pull to MK') == 6 and 'exclusive' not in s for s in sv.values()) and all('POWER zone' not in s for s in sv.values()))

for _f in TMP + [NEUTRAL]:
    if os.path.exists(_f):
        os.remove(_f)
print('FAILED: ' + ', '.join(fails) if fails else 'ALL HOLD')
sys.exit(1 if fails else 0)
