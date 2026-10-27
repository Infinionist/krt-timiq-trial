#!/usr/bin/env python3
"""build_inputs.py : v5 step 2 (option (d), Infinionist 10-26). Builds, in /tmp/pcb-trials/timiq/v5/ (run with the system python3):
   fixed.kicad_pcb       run 1's pile WITHOUT the six shield cans J7-J12 (cans_side.json + cans_poses.json keep them; reattach.py puts them back),
                         every mechanical part seated at its pose, nothing locked,
   mechanical.json       run 1's 22 parts (no cans),
   fixed.design-brief.json  4 top-side wall-band keep-outs, 14 mounting-hole circles (radius = drill/2 + clearance, from the HOLE edge),
                         6 can keep-outs (the can's bbox, allow = its members),
   cans.json             per can: bbox, interior zone, sheets, members F/B (every sheet part on its human face),
   groups.json           run 1's sheets (no 'shields' group), skips that hold,
   intent.json           check_floorplan --emit-intent --decaps-from <human>, then: 12 can blocks (zone + side), datasheet + netlist proximity
                         rows, the U21/U22 rf front end templates.
Deterministic: rerun after changing CAN_SHEETS / EXCLUDE / holes.json. Soft decaps: nothing is added for them (see decaps note in the report)."""
import json, os, re, shutil, subprocess, sys
sys.path.insert(0, '/tmp/pcb-trials/timiq/v5')
import cans_io
V5 = '/tmp/pcb-trials/timiq/v5'
RUN = '/tmp/pcb-trials/timiq/run'
K = '/tmp/pcb-trials/timiq/krt'
PY = K + '/.venv/bin/python'
HUMAN = cans_io.HUMAN
# box (FACTS 1-3): Hammond 1590Q, BOX1 origin = the box's bottom-left corner, 120 x 120, wall band 2.75 inside the rim
BX0, BY1 = 124.2124, 214.9478
BX1, BY0 = BX0 + 120.0, BY1 - 120.0
BAND = 2.75
# can -> schematic sheet groups (groups.json names == schematic sheet files, checked by script 10-26)
CAN_SHEETS = {'J7': ['pll'], 'J8': ['mixers', 'iqmod'], 'J9': ['dac_if'], 'J10': ['dividers'], 'J11': ['adc'], 'J12': ['dac']}
# sheet parts kept OUT of the can: the panel LED D1 with its driver R1/Q1 (a status LED like the fixed D2-D8; the human has all three outside
# the box next to the SMAs). Lead's call to confirm; remove from this set to put them in J7.
EXCLUDE = {'D1', 'R1', 'Q1'}
# Per-part overrides of the sheet -> can rule (Infinionist 10-26: can membership != schematic sheet; calls made by function, as the original designer did).
# Each entry: refs moved to another can. A reason per entry (written into cans.json).
OVERRIDES = [
    {'refs': ['U10', 'U11'] + [f'C{i}' for i in range(45, 51)] + [f'R{i}' for i in range(50, 58)], 'can': 'J9',
     'reason': 'DAC output stage feeding the DAC IF (DAC sheet parts, but as the original designer put them: in the DAC IF can J9, not J12)'},
    {'refs': ['U3'], 'can': 'J8', 'reason': 'LO splitter into the mixers (pll sheet part, but as the original designer put it: in the mixer can J8, not J7)'},
]
# OPTIONAL parts: allowed inside the can's keep-out (added to its allow list) but NOT members of the can's block, so the placer may put them
# in the can or outside. Stock KRT expresses this directly: block membership (zone) and keep-out allow are separate lists.
OPTIONAL = {
    'J10': {'refs': ['C96', 'C97', 'R75', 'R76', 'R78', 'R79', 'R88', 'R89'],
            'reason': 'dividers-sheet parts the original designer placed either in the J10 can or just outside it (Infinionist 10-26): free to go either way'},
}
# bbox of each can (human footprint bbox, 34.4 mm); interior zone = pose + J7's zone offsets (frame pad-ring inner edge, 30.8 mm)
BBOX_HALF = None
def sh(cmd, log):
    r = subprocess.run(cmd, capture_output=True, text=True)
    open(log, 'w').write(r.stdout + r.stderr)
    return r.returncode

# 1. board: copy with siblings, strip the cans, seat the mechanical parts
sh([PY, '-X', 'utf8', K + '/py_router/copy_board.py', RUN + '/fixed.kicad_pcb', V5 + '/fixed.kicad_pcb'], V5 + '/build.copy.log')
rc = cans_io.main(['strip', V5 + '/fixed.kicad_pcb', V5 + '/fixed.kicad_pcb.tmp', V5 + '/cans_side.json', V5 + '/cans_poses.json'])
assert rc == 0
os.replace(V5 + '/fixed.kicad_pcb.tmp', V5 + '/fixed.kicad_pcb')
mech = json.load(open(RUN + '/mechanical.json'))
mech['fixed'].sort(key=lambda f: (f['ref'][0], int(''.join(c for c in f['ref'] if c.isdigit()) or 0)))
json.dump(mech, open(V5 + '/mechanical.json', 'w'), indent=1)
ops = []
for f in mech['fixed']:
    ops += ['set', f['ref'], str(f['x']), str(f['y']), '--rot', str(f['rot'])]
rc = sh([PY, '-X', 'utf8', K + '/py_placer/place_pose.py', V5 + '/fixed.kicad_pcb', V5 + '/fixed.seated.kicad_pcb'] + ops, V5 + '/build.seat.log')
print('seat rc', rc)
if rc == 0:
    shutil.copy(V5 + '/fixed.seated.kicad_pcb', V5 + '/fixed.kicad_pcb'); os.remove(V5 + '/fixed.seated.kicad_pcb')

# 2. cans.json: members by sheet, faces from the human board
poses = json.load(open(V5 + '/cans_poses.json'))
groups = json.load(open(RUN + '/groups.json'))
grp = {g['name']: g['refs'] for g in groups['groups']}
fixed_refs = {f['ref'] for f in mech['fixed']}
htext = open(HUMAN, encoding='utf-8').read()
hface = {r: cans_io.footprint_pose(htext[s:e])[3] for s, e, r in cans_io.scan_footprints(htext)}
j7 = poses['J7']
OFF = (131.01 - j7['x'], 159.66 - j7['y'], 161.81 - j7['x'], 190.46 - j7['y'])     # J7's interior rect relative to its origin (pad-ring inner edge)
BB = {'J7': [129.19, 157.87, 163.62, 192.26], 'J8': [167.01, 174.57, 201.44, 208.96], 'J9': [167.01, 136.75, 201.44, 171.14],
      'J10': [204.82, 162.29, 239.25, 196.67], 'J11': [129.19, 120.07, 163.62, 154.45], 'J12': [167.01, 98.93, 201.44, 133.32]}   # human footprint bboxes
OVR = {r: (o['can'], o['reason']) for o in OVERRIDES for r in o['refs']}
OPT = {r for o in OPTIONAL.values() for r in o['refs']}
for r in list(OVR) + sorted(OPT):
    assert r in hface and r not in fixed_refs, r
cans = {}
for can, sheets in CAN_SHEETS.items():
    p = poses[can]
    refs = [r for s in sheets for r in grp[s] if r not in fixed_refs and r not in EXCLUDE and r not in CAN_SHEETS
            and r not in OVR and r not in OPT]
    refs += [r for r, (cn, _) in OVR.items() if cn == can]
    opt = OPTIONAL.get(can, {})
    cans[can] = {'sheets': sheets, 'bbox': BB[can], 'zone': [round(p['x'] + OFF[0], 4), round(p['y'] + OFF[1], 4), round(p['x'] + OFF[2], 4), round(p['y'] + OFF[3], 4)],
                 'refs': {'F': sorted([r for r in refs if hface[r] == 'F'], key=lambda s: (s[0], int(s[1:]))), 'B': sorted([r for r in refs if hface[r] == 'B'], key=lambda s: (s[0], int(s[1:])))},
                 'optional': sorted(opt.get('refs', []), key=lambda s: (s[0], int(s[1:]))), 'optional_why': opt.get('reason', ''),
                 'overrides': {r: OVR[r][1] for r in sorted(OVR) if OVR[r][0] == can},
                 'pose': p, 'why': f"members = every part of sheet(s) {', '.join(sheets)} on its human face (fixed mechanical parts and EXCLUDE {sorted(EXCLUDE)} left out)"}
json.dump(cans, open(V5 + '/cans.json', 'w'), indent=1)

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
               'why': (f"{h['host']} hole, drill {h['drill']:g} mm: no part within {h['clearance_from_hole_edge']:g} mm of the HOLE edge (radius {h['radius']:g} from the centre)"
                       + (f" (3.5 mm default; the human board has {h['nearest_human_part']} closer, so the human's value)" if h['human_limited'] else ''))})
for can, c in cans.items():
    ki.append({'name': f'can-{can}', 'rect': c['bbox'], 'sides': ['F', 'B'], 'allow': c['refs']['F'] + c['refs']['B'] + c['optional'], 'kind': 'shield_can',
               'why': f"shield can {can} (off the placing board, re-attached by reattach.py): the {c['bbox'][2]-c['bbox'][0]:.1f} mm footprint box is reserved for its members, sheet(s) {', '.join(c['sheets'])}"
                      + (f"; optional (allowed inside, not members): {', '.join(c['optional'])}" if c['optional'] else '')})
brief = {'schema': 1, 'kind': 'design-brief', 'units': 'mm', 'board': 'fixed.kicad_pcb', 'interfaces': [], 'keepouts': ki,
         'unknown': ['lid_height_limit_27.5mm'],
         'context': {'rule': 'v5-plan-v2', 'note': 'lid height (27.5 mm) NOT declared (Infinionist 10-26: not a concern); cans J7-J12 are not on this board (cans_side.json + reattach.py)'}}
json.dump(brief, open(V5 + '/fixed.design-brief.json', 'w'), indent=1)

# 4. groups: run 1's sheets, no 'shields' group (the cans are off the board), no skip that plan v2 rejects (a netlist row covers that IC instead)
sys.path.insert(0, V5)
import gate
for g in groups['groups']:
    g['near'] = [n for n in (g.get('near') or []) if n != 'shields'] or g.get('near')
    if g.get('templates'):
        g['templates'] = [t for t in g['templates'] if not (t.get('skip') and gate.reason_problem(t['skip']))]
        if not g['templates']:
            del g['templates']
groups['groups'] = [g for g in groups['groups'] if g['name'] != 'shields']
json.dump(groups, open(V5 + '/groups.json', 'w'), indent=1)

# 5. intent
rc = sh([PY, '-X', 'utf8', K + '/py_tools/check_floorplan.py', V5 + '/fixed.kicad_pcb', '--emit-intent', V5 + '/intent.json', '--allow-unplaced',
         '--decaps-from', HUMAN], V5 + '/build.emit.log')
print('emit rc', rc)
rc = sh([PY, '-X', 'utf8', V5 + '/netrows.py', V5 + '/fixed.kicad_pcb', V5 + '/groups.json', V5 + '/mechanical.json', V5 + '/datasheet_rows.json', V5 + '/netrows.json'], V5 + '/build.netrows.log')
print('netrows rc', rc, open(V5 + '/build.netrows.log').read().strip()[-200:])
it = json.load(open(V5 + '/intent.json'))
nr = json.load(open(V5 + '/netrows.json'))
ds = json.load(open(V5 + '/datasheet_rows.json'))
member = {r for c in cans.values() for f in 'FB' for r in c['refs'][f]}
blocks = []
for b in it['blocks']:
    b['refs'] = [r for r in b['refs'] if r not in member]
    if b['refs']:
        blocks.append(b)
added = []
for can, c in cans.items():
    for face in ('F', 'B'):
        if c['refs'][face]:
            blocks.append({'name': f'can{can}_{face}', 'refs': c['refs'][face], 'zone': c['zone'], 'side': face,
                           'why': f"shield can {can} interior, {face} side: sheet(s) {', '.join(c['sheets'])}"})
            added.append(f'can{can}_{face}')
it['blocks'] = blocks
# proximity: datasheet rows (decaps among them dropped: soft, held by the decap term), then netlist rows; one row per (ref, near)
decaps = set(nr['decaps'])
prox, seen, dropped = [], {}, []
for r in ds['rows']:
    if r['ref'] in decaps:
        dropped.append(r['ref'])
        continue
    key = (r['ref'], r['near'])
    pads = {r['near']: list(r['pads'])} if r.get('pads') else {}
    if key in seen:
        row = seen[key]
        if pads:
            row['pads'][r['near']] = sorted(set(row['pads'].get(r['near'], [])) | set(pads[r['near']]), key=lambda s: (len(s), s))
        row['why'] += ' | ' + r['why'][:120]
        continue
    row = {'ref': r['ref'], 'near': r['near'], 'max_mm': 2.0 if pads else 5.0, 'basis': 'pad_edge', 'why': f"datasheet: {r['function']}; {r['why'][:200]}"}
    if pads:
        row['pads'] = pads
    seen[key] = row
    prox.append(row)
for r in nr['rows']:
    prox.append({k: v for k, v in r.items() if k != 'source_kind'})
it['proximity'] = prox
# templates: the two fitted PMA2-43LN+ rf front ends (fit_template.py, sketches in templates/)
it['templates'] = [json.load(open(V5 + f'/templates/row_{u}.json')) for u in ('U21', 'U22')]
it['min_reader'] = max(it.get('min_reader', 7), 15)
it.setdefault('context', {})['v5_notes'] = {'decap_rows_dropped_to_soft_term': sorted(set(dropped)), 'netlist_rows': nr['counts'],
                                            'can_keepouts': 'brief keepouts can-J*', 'exclude': sorted(EXCLUDE)}
json.dump(it, open(V5 + '/intent.json', 'w'), indent=1)
print('fixed_poses', len(it['fixed_poses']), 'keepouts', len(brief['keepouts']), 'proximity', len(prox), 'templates', len(it['templates']), 'decap rows dropped', len(set(dropped)), 'can blocks', added)
print({c: (len(v['refs']['F']), len(v['refs']['B'])) for c, v in cans.items()})
