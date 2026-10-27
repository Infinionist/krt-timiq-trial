#!/usr/bin/env python3
"""build_inputs.py : v5 step 2. Builds, in /tmp/pcb-trials/timiq/v5/:
   fixed.kicad_pcb (run 1's pile with every mechanical part seated at its pose; nothing locked),
   mechanical.json (run 1's 22 parts + J7-J10 at the HUMAN poses, Infinionist 10-26),
   fixed.design-brief.json (4 top-side wall-band keep-outs, 14 mounting-hole circles),
   intent.json (check_floorplan --emit-intent --decaps-from <human board>), groups.json (run 1's sheets), cans.json.
Deterministic: rerun it after changing cans.json (refs) or holes.json."""
import json, os, shutil, subprocess, sys
V5 = '/tmp/pcb-trials/timiq/v5'
RUN = '/tmp/pcb-trials/timiq/run'
K = '/tmp/pcb-trials/timiq/krt'
PY = K + '/.venv/bin/python'
HUMAN = '/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb'   # the human layout (copper stripped, poses as downloaded)
# box (FACTS 1-3): Hammond 1590Q, BOX1 origin = the box's bottom-left corner, 120 x 120, wall band 2.75 inside the rim
BX0, BY1 = 124.2124, 214.9478
BX1, BY0 = BX0 + 120.0, BY1 - 120.0
BAND = 2.75
def sh(cmd, log):
    r = subprocess.run(cmd, capture_output=True, text=True)
    open(log, 'w').write(r.stdout + r.stderr)
    return r.returncode

# 1. board: copy with siblings, then seat the mechanical parts
sh([PY, '-X', 'utf8', K + '/py_router/copy_board.py', RUN + '/fixed.kicad_pcb', V5 + '/fixed.kicad_pcb'], V5 + '/build.copy.log')
# 2. mechanical.json
mech = json.load(open(RUN + '/mechanical.json'))
HJ = {'J7': (131.6648, 190.96), 'J8': (169.4854, 207.6605), 'J9': (169.4854, 169.84244), 'J10': (207.29584, 195.37452)}   # human_stripped, rot 0, F
have = {f['ref'] for f in mech['fixed']}
for ref, (x, y) in HJ.items():
    if ref not in have:
        mech['fixed'].append({'ref': ref, 'x': x, 'y': y, 'rot': 0.0,
            'reason': 'Infinionist 10-26: shield cans J7-J10 are fixed at the human pose under the lid window (design intent known before placement)'})
mech['fixed'].sort(key=lambda f: (f['ref'][0], int(''.join(c for c in f['ref'] if c.isdigit()) or 0)))
json.dump(mech, open(V5 + '/mechanical.json', 'w'), indent=1)
ops = []
for f in mech['fixed']:
    ops += ['set', f['ref'], str(f['x']), str(f['y']), '--rot', str(f['rot'])]
rc = sh([PY, '-X', 'utf8', K + '/py_placer/place_pose.py', V5 + '/fixed.kicad_pcb', V5 + '/fixed.seated.kicad_pcb'] + ops, V5 + '/build.seat.log')
print('seat rc', rc)
if rc == 0:
    shutil.copy(V5 + '/fixed.seated.kicad_pcb', V5 + '/fixed.kicad_pcb'); os.remove(V5 + '/fixed.seated.kicad_pcb')
# 3. brief
holes = json.load(open(V5 + '/holes.json'))
ki = []
inner = (BX0 + BAND, BY0 + BAND, BX1 - BAND, BY1 - BAND)
bands = {'top': [BX0, BY0, BX1, inner[1]], 'bottom': [BX0, inner[3], BX1, BY1],
         'left': [BX0, inner[1], inner[0], inner[3]], 'right': [inner[2], inner[1], BX1, inner[3]]}
for nm, r in bands.items():
    ki.append({'name': f'wall-band-{nm}', 'rect': [round(v, 4) for v in r], 'sides': ['F'], 'allow': ['BOX1', 'J5'], 'kind': 'enclosure_wall_band',
               'why': f'Hammond 1590Q wall band: no top-side part within {BAND} mm of the box rim (FACTS 3, 8); bottom parts may stand there (the human has them)'})
for h in holes:
    ki.append({'name': h['name'], 'circle': [h['x'], h['y'], h['radius']], 'sides': ['F', 'B'], 'allow': h['allow'], 'kind': 'mounting_hole',
               'why': (f"{h['host']} hole, pad {h['pad_d']:g} mm, drill {h['drill']:g} mm: no part within {h['clearance_from_pad_edge']:g} mm of the pad edge"
                       + (f" (3.5 mm default; the human board has {h['nearest_human_part']} closer, so the human's value)" if h['human_limited'] else ''))})
brief = {'schema': 1, 'kind': 'design-brief', 'units': 'mm', 'board': 'fixed.kicad_pcb', 'interfaces': [], 'keepouts': ki,
         'unknown': ['lid_height_limit_27.5mm'],
         'context': {'rule': 'v5-plan-v2', 'note': 'lid height limit (27.5 mm) NOT declared: keepouts[].max_height_mm binds every part whose height is unknown; 336 of 336 box parts are unknown (no 3D models, no IPC height in the names)'}}
json.dump(brief, open(V5 + '/fixed.design-brief.json', 'w'), indent=1)
# 4. groups (run 1's sheets) and cans
shutil.copy(RUN + '/groups.json', V5 + '/groups.json')
# 5. intent
rc = sh([PY, '-X', 'utf8', K + '/py_tools/check_floorplan.py', V5 + '/fixed.kicad_pcb', '--emit-intent', V5 + '/intent.json', '--allow-unplaced',
         '--decaps-from', HUMAN], V5 + '/build.emit.log')
print('emit rc', rc)
it = json.load(open(V5 + '/intent.json'))
cans = json.load(open(V5 + '/cans.json')) if os.path.exists(V5 + '/cans.json') else {}
added = []
for can, c in cans.items():
    for face in ('F', 'B'):
        refs = c['refs'].get(face)
        if isinstance(refs, list) and refs:
            it['blocks'].append({'name': f'can{can}_{face}', 'refs': refs, 'zone': c['zone'], 'side': face, 'why': c['why']})
            added.append(f'can{can}_{face}')
json.dump(it, open(V5 + '/intent.json', 'w'), indent=1)
print('fixed_poses', len(it['fixed_poses']), 'keepouts', len(brief['keepouts']), 'decaps', it.get('decaps'), 'can blocks added', added)
