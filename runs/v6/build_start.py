#!/usr/bin/env python3
"""v6 start board: v5/fixed.kicad_pcb (cans stripped, mechanical seated, synthesized courtyards, all parts on F) minus v5's guidance:
anchor markers MK7-MK12 removed, status LEDs D2-D8 moved off the outline into the pile, plain design brief, mechanical.json with only
the board's physical facts (FIX1-8, J1-J6, BOX1)."""
import json, re, subprocess, sys, shutil
sys.path.insert(0, '/tmp/pcb-trials/timiq/v5')
import cans_io
V5, V6, RUN, K = '/tmp/pcb-trials/timiq/v5', '/tmp/pcb-trials/timiq/v6', '/tmp/pcb-trials/timiq/run', '/tmp/pcb-trials/timiq/krt'
PY = K + '/.venv/bin/python'
r = subprocess.run([PY, '-X', 'utf8', K + '/py_router/copy_board.py', V5 + '/fixed.kicad_pcb', V6 + '/start.kicad_pcb'], capture_output=True, text=True)
print(r.stdout, r.stderr); assert r.returncode == 0
shutil.copy(RUN + '/fixed.design-brief.json', V6 + '/start.design-brief.json')
t = open(V6 + '/start.kicad_pcb', encoding='utf-8').read()
spans = [(s, e, ref) for s, e, ref in cans_io.scan_footprints(t) if re.fullmatch(r'MK\d+', ref)]
for s, e, ref in sorted(spans, reverse=True):
    # drop the block and its line
    ls = t.rfind('\n', 0, s) + 1
    le = t.find('\n', e)
    t = t[:ls] + t[le + 1:]
print('removed', [x[2] for x in spans])
open(V6 + '/start.kicad_pcb', 'w', encoding='utf-8').write(t)
# pile bbox: positions of every free part
xs, ys = [], []
mech = {f['ref']: f for f in json.load(open(RUN + '/mechanical.json'))['fixed']}
for s, e, ref in cans_io.scan_footprints(t):
    x, y, rot, face = cans_io.footprint_pose(t[s:e])
    if ref not in mech:
        xs.append(x); ys.append(y)
print('free parts', len(xs), 'bbox', min(xs), min(ys), max(xs), max(ys))
keep = ['FIX%d' % i for i in range(1, 9)] + ['J%d' % i for i in range(1, 7)] + ['BOX1']
json.dump({'schema': 1, 'context': {'rule': 'v6: the board physical facts only (holes, SMAs, J5, J6, enclosure BOX1)'},
           'fixed': [dict(mech[r], reason='v6 physical fact: mounting hardware / connector at its fixed pose') for r in keep]},
          open(V6 + '/mechanical.json', 'w'), indent=1)
