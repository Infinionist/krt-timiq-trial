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
Plan v5 (Infinionist 10-27): every can is ONE group (canJ7..canJ12) with a block zone, tolerance 0; every part starts on the FRONT (set_faces: all of them);
power = groups (pw_in, pw_7v5, pw_24v, one per regulator) + ONE loose supergroup block 'power_strip' (no tiles) + loose proximity rows.
Plan v5b (Infinionist 10-27): inside a can every IC, RF-path part and part with courtyard >= 20 mm2 stays on F, locked; its small passives (R, C, FB) may go to B inside the can only.
decide_faces.py (fill, KRT venv; the rule is in faces_v5.py) lists them flippable in the can's group where the can is over the fill limit on F (and drops the group and block `side`
of that can: a declared side overrides flippable in KRT); a can that fits keeps side F. It rewrites groups.json, intent.json, cans.json and writes faces.json. Deterministic: rerun after changing CAN_SHEETS / EXCLUDE / holes.json. Soft decaps: nothing is added for them."""
import json, os, re, shutil, subprocess, sys
sys.path.insert(0, '/tmp/pcb-trials/timiq/v5')
import cans_io
import add_courtyards
import plan_v3
import power_v4
import geom4
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
OVERRIDES.append(plan_v3.U3_OVERRIDE)
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

# 1b. plan v3 item 1: a courtyard for every footprint that lacks one (BOX1, the pin frame, never gets one), body = outline + pads, margin 0.25 mm
text0 = open(V5 + '/fixed.kicad_pcb', encoding='utf-8').read()
AREA = {}
for s, e, r in cans_io.scan_footprints(text0):
    cy = add_courtyards.courtyard_rect(text0[s:e], 0.25)
    AREA[r] = round((cy[1][2] - cy[1][0]) * (cy[1][3] - cy[1][1]), 2) if cy else 0.0
rc = subprocess.run(
    [sys.executable, V5 + '/add_courtyards.py', V5 + '/fixed.kicad_pcb', V5 + '/fixed.cy.kicad_pcb', '--margin', '0.25', '--skip', 'BOX1', '--json', V5 + '/courtyards.json'],
    capture_output=True, text=True)
open(V5 + '/build.courtyards.log', 'w').write(rc.stdout + rc.stderr)
assert rc.returncode == 0, rc.stderr
os.replace(V5 + '/fixed.cy.kicad_pcb', V5 + '/fixed.kicad_pcb')
print(rc.stdout.strip())
_t = open(V5 + '/fixed.kicad_pcb', encoding='utf-8').read()
open(V5 + '/fixed.kicad_pcb', 'w', encoding='utf-8').write(add_courtyards.point_courtyard(_t, 'BOX1'))     # plan v4: the pin frame gets a point courtyard (see point_courtyard)
# 1c. plan v5 (Infinionist 10-27 call 2): every movable part STARTS on the front and the cans' groups say side F; nothing is flippable unless decide_faces.py finds the fit needs it.
#     (plan v3/v4 started only the big parts on F and left the rest on the human's face: 156 parts stood on B, and with faces free the placer sent 166 of 282 can members and the big ICs there.)
mech0 = json.load(open(V5 + '/mechanical.json'))
mech_refs = {f['ref'] for f in mech0['fixed']}
LARGE = sorted((r for r in AREA if r not in mech_refs and r not in cans_io.CANS), key=lambda s: (s[0], int(re.sub(r'\D', '', s) or 0)))      # every movable part (name kept: large_parts.json)
json.dump(LARGE, open(V5 + '/large_parts.json', 'w'))
rc = sh([PY, '-X', 'utf8', V5 + '/set_faces.py', V5 + '/fixed.kicad_pcb', V5 + '/fixed.faces.kicad_pcb', '--front-file', V5 + '/large_parts.json'], V5 + '/build.faces.log')
print('faces rc', rc, open(V5 + '/build.faces.log').read().strip().splitlines()[-1])
assert rc == 0
os.replace(V5 + '/fixed.faces.kicad_pcb', V5 + '/fixed.kicad_pcb')

DIMS = geom4.courtyard_dims(V5 + '/fixed.kicad_pcb')       # {ref: (w, h, face, rect)} courtyard as on the placing board
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
                 'side': 'F', 'pose': p, 'why': f"members = every part of sheet(s) {', '.join(sheets)} on its human face (fixed mechanical parts and EXCLUDE {sorted(EXCLUDE)} left out)"}
# plan v3 items 2 + 4: faces are no longer fixed to the human's, so a can's membership is one list; refs F/B stay as the human's faces (information only)
for can, c in cans.items():
    c['members'] = sorted(c['refs']['F'] + c['refs']['B'], key=lambda s: (s[0], int(s[1:])))
member_all = {r: cn for cn, c in cans.items() for r in c['members']}
# nets + positions for the anchor direction: the placing board's own nets, fixed poses, the can centres
import designer_check as dcm
_pc, _b = dcm.load_board(V5 + '/fixed.kicad_pcb')
_parts = dcm.parts_of(_pc, _b)
NETS = {}
for _r, _p in _parts.items():
    for _pad in _p['pads']:
        if _pad[4]:
            NETS.setdefault(_pad[4], []).append((_r, _pad[5]))
_hpc, _hb = dcm.load_board(HUMAN)
HPOS = {r: (p['x'], p['y']) for r, p in dcm.parts_of(_hpc, _hb).items()}
_fixed_pos = {f['ref']: (f['x'], f['y']) for f in mech['fixed']}
_grp_of = {r: g['name'] for g in groups['groups'] for r in g['refs']}
_grp_anchor = {g['name']: g.get('anchor') for g in groups['groups']}
NETS_REFS = set(_parts)
_cen = {cn: plan_v3._centre(c['zone']) for cn, c in cans.items()}


def place_of(r):
    """the place a part stands for: a fixed part is itself, a can member its can, a free part its group's fixed anchor connector (J5 digital, J6 power), else None."""
    if r in _fixed_pos:
        return r
    if r in member_all:
        return member_all[r]
    a = _grp_anchor.get(_grp_of.get(r))
    return a if a in _fixed_pos else None


def pos_of(pl):
    return _fixed_pos.get(pl) or _cen.get(pl)


for can, c in cans.items():
    a = plan_v3.ANCHORS[can]
    assert all(r in c['members'] for r in a['ics']), (can, a['ics'])
    vx, vy, nt, tg = plan_v3.exit_vector(can, a['ics'], member_all, NETS, pos_of, c['zone'], place_of)
    c['anchors'] = a['ics']
    mx, my = plan_v3.anchor_point(c['zone'], (vx, vy), [DIMS[r][:2] for r in a['ics']], margin=plan_v3.ANCHOR_MARGIN)
    c['anchor_marker'] = {'ref': f"{plan_v3.MARKER_PREFIX}{can[1:]}", 'x': mx, 'y': my}
    c['anchor_max_mm'] = plan_v3.ANCHOR_PULL_MM
    c['anchor_why'] = (f"{a['why']}. plan v4 (Infinionist 10-27: no exclusive zone, no zone at all): the anchor IC starts nowhere in particular; a proximity row pulls it (body to body, "
                       f"max {plan_v3.ANCHOR_PULL_MM:g} mm: a pull, not a wall) to the fixed point marker {c['anchor_marker']['ref']} at ({mx}, {my}) = the can centre shifted by the exit vector "
                       f"({vx:+.2f}, {vy:+.2f}) from {nt} target part(s) (where its signals go: other cans, J1-J5, J6); the can zone holds everything else")
    c['exit_vector'] = [round(vx, 3), round(vy, 3)]
    c['exit_targets'] = tg
json.dump(cans, open(V5 + '/cans.json', 'w'), indent=1)
# plan v4: the anchor markers MK7..MK12 (fixed points) on the placing board and in mechanical.json (so KRT emits them as fixed poses)
MARKERS = [(c['anchor_marker']['ref'], c['anchor_marker']['x'], c['anchor_marker']['y']) for c in cans.values()]
_t = open(V5 + '/fixed.kicad_pcb', encoding='utf-8').read()
open(V5 + '/fixed.kicad_pcb', 'w', encoding='utf-8').write(add_courtyards.add_markers(_t, MARKERS))
mech['fixed'] += [{'ref': r, 'x': x, 'y': y, 'rot': 0.0, 'reason': 'plan v4 anchor marker: a fixed point at the biased can centre; the can anchor IC is pulled to it by a proximity row'} for r, x, y in MARKERS]
json.dump(mech, open(V5 + '/mechanical.json', 'w'), indent=1)
fixed_refs |= {r for r, _x, _y in MARKERS}

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
    ki.append({'name': f'can-{can}', 'rect': c['bbox'], 'sides': ['F', 'B'], 'allow': c['members'] + c['optional'] + ['BOX1', c['anchor_marker']['ref']], 'kind': 'shield_can',
               'why': f"shield can {can} (off the placing board, re-attached by reattach.py): the {c['bbox'][2]-c['bbox'][0]:.1f} mm footprint box is reserved for its members, sheet(s) {', '.join(c['sheets'])}"
                      + (f"; optional (allowed inside, not members): {', '.join(c['optional'])}" if c['optional'] else '')})
# plan v3 item 3: keep-away rules (declared in the brief: check_floorplan grades them, route.py / route_diff.py price them on the tracks)
KA, KA_SENS, KA_DIG = plan_v3.keep_away_rules(NETS)
brief = {'schema': 1, 'kind': 'design-brief', 'units': 'mm', 'board': 'fixed.kicad_pcb', 'interfaces': [], 'keepouts': ki,
         'keep_away': [{'rule': r, 'why': w} for r, w in KA],
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
# plan v5 (Infinionist 10-27): one KRT group per can, side F, no flippable (groups_v5.can_groups); the markers MK7..MK12 join their can's group (the anchor IC's group, as in plan v4)
import groups_v5
new_groups, gnotes = groups_v5.can_groups(cans, groups['groups'], plan_v3.ANCHORS, fixed_refs, EXCLUDE)
groups['groups'] = new_groups
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
# power section (plan v4, Infinionist 10-27). The 75 parts of plan v3's one `power` block are split
# by the netlist (power_v4.split_groups): pw_in (J6 + pre-filter caps), a branch group per filter family (pw_7v5: L12 + its caps; pw_24v: L13, L14 + their caps), one group per
# regulator U39-U45 with its own in/out/NR/feedback parts. Not in them: J6 and the status LEDs (fixed), the test points (free), the LED series resistors (they follow their LEDs).
dnets = {n for n, pads in NETS.items() if any(r.startswith('D') for r, _ in pads)}
ledr = {r for n in dnets for r, _ in NETS[n] if re.match(r'^R\d+$', r)}
power_refs = sorted({r for g in groups['groups'] if g['name'] in plan_v3.POWER_GROUPS for r in g['refs']
                     if r not in fixed_refs and not r.startswith('TP') and r not in ledr}, key=lambda s: (s[0], int(s[1:])))
_fp_of = {r: re.sub(r'^.*:', '', p['fp']) for r, p in _parts.items()}
PW, pw_left = power_v4.split_groups(NETS, power_refs, plan_v3.POWER_REGS, plan_v3.POWER_FILTERS, ['J6'], _fp_of, HPOS)
assert not pw_left, f'power leftovers (the lead decides): {pw_left}'
# plan v5 (Infinionist 10-27 call 1): NO tiles. Power = these groups, a LOOSE location (proximity rows, anchored seeds) and at most one loose supergroup zone (block power_strip, below).
# The branch SIDES (7V5 right of J6, +-24V left) and the column order of plan v4 are gone with the tiles: nothing here is taken from the human board except which 1210 input cap
# serves which regulator (power_v4.split_groups, CHEAT 3: the shared rail does not say).
BRANCHES = [g for g in PW if PW[g]['kind'] == 'branch']
power_set = set(power_refs)
# the groups file: plan v3's power_in / ldo_pos / ldo_neg are replaced by the 10 logical groups (J6 stays in pw_in as its anchor; fixed parts may be listed)
_old = {g['name']: g for g in groups['groups'] if g['name'] in plan_v3.POWER_GROUPS}
_keep_J6 = [r for g in _old.values() for r in g['refs'] if r in fixed_refs or r.startswith('TP') or r in ledr]
groups['groups'] = [g for g in groups['groups'] if g['name'] not in plan_v3.POWER_GROUPS]
_names = {'pw_in': 'J6 power entry with its pre-filter caps', 'pw_7v5': 'the 7V5 branch: filter L12 and its bulk caps', 'pw_24v': 'the +-24V branch: filters L13/L14 and their bulk caps'}
for gname, gv in PW.items():
    if gv['kind'] == 'regulator':
        nb = [b_ for b_ in BRANCHES if PW[gname]['rail_in'] in PW[b_]['rails']]
    elif gv['kind'] == 'branch':
        nb = ['pw_in'] + [g for g in PW if PW[g]['kind'] == 'regulator' and PW[g]['rail_in'] in gv['rails']]
    else:
        nb = list(BRANCHES)
    groups['groups'].append({'name': gname, 'role': 'power', 'refs': gv['refs'] + (['J6'] if gname == 'pw_in' else []),
                             'anchor': 'J6' if gv['kind'] == 'input' else (gv.get('reg') or gv['filters'][0]), 'near': nb,
                             'why': _names.get(gname) or f"regulator {gv['reg']} ({gv['own_nets'][0] if gv['own_nets'] else ''} family) with its input cap, output caps and NR/feedback parts, found by netlist connectivity to its pins"})
_misc = [r for r in _keep_J6 if r != 'J6']          # test points, LED series resistors, fixed LEDs: listed for the lead, no zone (they follow their LEDs / are free)
groups['groups'].append({'name': 'pw_misc', 'role': 'power', 'refs': _misc, 'near': ['pw_in'],
                         'why': 'left over from the old power sheets: test points TP1-TP3, the LED series resistors and the fixed status LEDs; no zone (listed for the lead)'})
member = set(member_all) | set(power_refs)
blocks = []
for b in it['blocks']:
    b['refs'] = [r for r in b['refs'] if r not in member]
    if b['refs']:
        blocks.append(b)
added = []
for can, c in cans.items():
    blocks.append({'name': f'can{can}', 'refs': list(c['members']), 'zone': c['zone'], 'side': 'F', 'tolerance_mm': 0.0,
                   'why': f"shield can {can} interior, FRONT only (plan v5, Infinionist 10-27: members stand on top, under the can; group can{can} has side F, nothing flippable); sheet(s) {', '.join(c['sheets'])}. "
                          f"tolerance 0: the default 0.5 mm let U13 stand on the J9 frame pads in run v4"})
    added.append(f'can{can}')
# the ONE loose power supergroup (Infinionist 10-27): every power part, the strip above the
# box across the board width, tolerance POWER_TOL mm, not exclusive, no side
blocks.append({'name': 'power_strip', 'refs': list(power_refs), 'zone': plan_v3.POWER_STRIP, 'tolerance_mm': plan_v3.POWER_TOL,
               'why': f"plan v5 loose power supergroup: all {len(power_refs)} power parts (groups pw_in, pw_7v5, pw_24v, pw_U39..pw_U45), the top strip above the box, tolerance {plan_v3.POWER_TOL:g} mm, "
                      f"not exclusive, no side; the groups inside it are placed by loose proximity rows, `near` hints and anchored seeds, never by tiles",
               'context': {'kind': 'power_supergroup'}})
added.append('power_strip')
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
    row = {'ref': r['ref'], 'near': r['near'], 'max_mm': plan_v3.PIN_MM if pads else plan_v3.PART_MM, 'basis': 'pad_edge', 'why': f"datasheet: {r['function']}; {r['why'][:200]}"}
    if pads:
        row['pads'] = pads
    seen[key] = row
    prox.append(row)
for r in nr['rows']:
    prox.append({k: v for k, v in r.items() if k != 'source_kind'})
# plan v3 item 3: rows the chains replace (a shunt pinned to a far SMA), then the chains, link by link (5 mm part rows, one can each)
n0 = len(prox)
prox = [p for p in prox if (p['ref'], p['near']) not in set(plan_v3.DROP_ROWS)]
dropped_rows = n0 - len(prox)
assert dropped_rows == len(plan_v3.DROP_ROWS), (dropped_rows, plan_v3.DROP_ROWS)
have = {(p['ref'], p['near']) for p in prox}
opt_all = {r for c in cans.values() for r in c['optional']}
chain_rows, bad_chain = [], []
for name, links in plan_v3.CHAINS:
    for ref, near, why in links:
        if ref not in NETS_REFS or near not in NETS_REFS:
            bad_chain.append(f'{name}: {ref}/{near} not on the board')
            continue
        ca, cb = member_all.get(ref), member_all.get(near)
        if ca != cb or ca is None:
            bad_chain.append(f'{name}: {ref} ({ca}) and {near} ({cb}) are not in the same can')
            continue
        if (ref, near) in have:
            continue
        have.add((ref, near))
        chain_rows.append({'ref': ref, 'near': near, 'max_mm': plan_v3.PART_MM, 'basis': 'pad_edge', 'why': f'plan v3 chain "{name}" (in {ca}): {why}; {plan_v3.PART_MM:g} mm part row'})
assert not bad_chain, bad_chain
prox += chain_rows
# plan v4 (Infinionist 10-27): the anchor IC of each can is PULLED to its marker (body basis: the marker has no pad), max 7 mm; no anchor zone, nothing exclusive
anchor_rows = [{'ref': ic, 'near': c['anchor_marker']['ref'], 'max_mm': plan_v3.ANCHOR_PULL_MM, 'basis': 'body',
                'why': f"plan v4 anchor pull: {ic} starts near the biased centre of {can} (marker {c['anchor_marker']['ref']}), within {plan_v3.ANCHOR_PULL_MM:g} mm body to body; soft"}
               for can, c in cans.items() for ic in c['anchors']]
prox += anchor_rows
have |= {(r['ref'], r['near']) for r in anchor_rows}
# plan v5 power rows (Infinionist 10-27 call 1: location suggestions the KRT way, loose). KRT FACT (grouping.fold_followers, found 10-27 by running it on the v5 groups): a proximity row between
# parts of DIFFERENT groups is a membership claim, the subject (and, when it is its group's anchor, its whole group) joins the partner's group. Plan v4's rows "L12 near J6" and
# "U41 near L12" therefore folded all 11 power groups into one 78-part group pw_in (the 7 regulator groups, pw_7v5, pw_24v). So a loose group-to-group row cannot be written: the
# group-to-group suggestions are the groups' `near` hints (soft, set below) and the anchored seeds; rows stay INSIDE a group:
# (1) the parts of a regulator group -> their regulator's pins: pad-named, PIN_MM 3 (a regulator's own caps sit at its pins: the group's inside, not its place);
# (2) pw_in (J6 + its pre-filter caps): the cap rows to J6 are loosened to LOOSE_J6_MM (same group: no claim), tagged context.kind power_loose;
# (3) the filters L12-L14 -> J6 pin rows (pw_7v5 / pw_24v -> pw_in) are DROPPED (cross-group); the plan v4 chain rows regulator -> filter / regulator -> regulator are not written.
power_rows = []
for gname, gv in PW.items():
    if gv['kind'] == 'regulator':
        power_rows += [(row, 'reg->part') for row in power_v4.pin_rows(NETS, gv, plan_v3.PIN_MM)]
for row, kind in power_rows:
    if (row['ref'], row['near']) not in have:
        have.add((row['ref'], row['near']))
        prox.append(row)
loose_j6, dropped_cross = [], []
_gof = {r: g['name'] for g in groups['groups'] for r in g['refs']}
_keep = []
for r_ in prox:
    if r_['near'] == 'J6' and r_['ref'] in power_set:
        if _gof.get(r_['ref']) != _gof.get('J6'):
            dropped_cross.append((r_['ref'], r_['near'], 'cross-group row: it would move the part (and its group) into the group of J6'))
            continue
        r_['max_mm'] = plan_v3.LOOSE_J6_MM
        r_['context'] = dict(r_.get('context') or {}, kind='power_loose')
        r_['why'] += f" | plan v5: the input group is pulled LOOSELY to J6 ({plan_v3.LOOSE_J6_MM:g} mm instead of the 3 mm pin row)"
        loose_j6.append(r_['ref'])
    _keep.append(r_)
prox = _keep
# rows between two cans can never hold (a member stays in its can zone; the cans are 3.4+ mm apart): the netlist rows R74->U17 (J10 / J8), R115->U26 and R116->U27 (J11 / J8) are such
# rows, found by the gate's row feasibility check; dropped here, listed in the intent context. A row that crosses groups at all is a claim: the gate's claims check (KRT's own fold_followers)
# lists any that is left.
# LED series resistors (R157, R159 on the regulators' output rails feed a status LED) follow their LED, not the IC pin that shares their rail: a row to the regulator is a claim into the
# regulator's group (pw_misc -> pw_U44) and the designer check already leaves them out of the far check
for r_ in list(prox):
    if r_['ref'] in ledr and _gof.get(r_['ref']) != _gof.get(r_['near']):
        dropped_cross.append((r_['ref'], r_['near'], 'LED series resistor: follows its LED; the row would claim it into the group of the IC on its rail'))
        prox.remove(r_)
import rowcheck
_unsat = rowcheck.unsatisfiable_rows(it['blocks'], prox)
for (ra, rb), why in sorted(_unsat.items()):
    dropped_cross.append((ra, rb, why))
prox = [r_ for r_ in prox if (r_['ref'], r_['near']) not in _unsat]
it['proximity'] = prox
# templates: the two fitted PMA2-43LN+ rf front ends (fit_template.py, sketches in templates/)
it['templates'] = [json.load(open(V5 + f'/templates/row_{u}.json')) for u in ('U21', 'U22')]
it['min_reader'] = max(it.get('min_reader', 7), 15)
it.setdefault('context', {})['v5_notes'] = {'decap_rows_dropped_to_soft_term': sorted(set(dropped)), 'netlist_rows': nr['counts'],
                                            'can_keepouts': 'brief keepouts can-J*', 'exclude': sorted(EXCLUDE)}
it['context']['v5_notes']['plan_v3'] = {'courtyards': json.load(open(V5 + '/courtyards.json'))['margin_mm'], 'large_front': len(LARGE), 'chain_rows': len(chain_rows),
                                        'power_rows': len(power_rows), 'loose_j6_rows': sorted(loose_j6), 'dropped_cross_rows': dropped_cross, 'dropped_rows': plan_v3.DROP_ROWS, 'keep_away_rules': len(KA)}
assert it.get('keep_away') and len(it['keep_away']) == len(KA), 'the brief keep_away did not compile into the intent'
json.dump(it, open(V5 + '/intent.json', 'w'), indent=1)
json.dump(groups, open(V5 + '/groups.json', 'w'), indent=1)
# faces (plan v5b): nothing is flippable unless the fit needs it. decide_faces.py (KRT venv: pre-flight probe + fillcheck + faces_v5) measures every zone with all parts on F and, for a
# can over the fill limit, lists its smallest eligible passives flippable (decaps of its own ICs first), then rewrites groups.json / intent.json / cans.json (side dropped for those cans).
# rc 1 = a can does not fit even with every eligible passive flipped: the inputs are still written, the gate FAILS on the fill (the lead decides); rc 2 = tool error.
rc = sh([PY, '-X', 'utf8', V5 + '/decide_faces.py', V5 + '/fixed.kicad_pcb', V5 + '/groups.json', V5 + '/intent.json', '--cans', V5 + '/cans.json', '--write', '--json', V5 + '/faces.json'], V5 + '/build.decide_faces.log')
print('decide_faces rc', rc, open(V5 + '/build.decide_faces.log').read().strip().splitlines()[-1])
assert rc in (0, 1)
it = json.load(open(V5 + '/intent.json'))          # decide_faces rewrote it (block side dropped for the cans that list flippable parts)
groups = json.load(open(V5 + '/groups.json'))
# the intent for the reattached boards (cans J7-J12 back on): the can keep-outs also allow the cans themselves; overlap_waivers for every can vs its members and optional parts
# (check_assembly --intent reads them: a can's courtyard over what stands inside it is by design); intent_reattached.json is what the post checks read
ir = json.loads(json.dumps(it))
for k in ir['keepouts']:
    if k.get('name', '').startswith('can-J'):
        k['allow'] = list(k['allow']) + [c for c in cans_io.CANS if c not in k['allow']]
ir['overlap_waivers'] = [{'pair': [can, r], 'why': f"can {can} stands over its {'optional ' if r in c['optional'] else ''}part {r} by design (the can's courtyard encloses its interior)"}
                         for can, c in cans.items() for r in c['members'] + c['optional'] + [c['anchor_marker']['ref']]]
json.dump(ir, open(V5 + '/intent_reattached.json', 'w'), indent=1)
print('fixed_poses', len(it['fixed_poses']), 'keepouts', len(brief['keepouts']), 'proximity', len(prox), 'templates', len(it['templates']), 'decap rows dropped', len(set(dropped)), 'can blocks', added)
print({c: (len(v['refs']['F']), len(v['refs']['B'])) for c, v in cans.items()}, 'power supergroup', len(power_refs), 'parts started on F', len(LARGE))
print('anchor markers', {c: (v['anchor_marker']['ref'], v['anchor_marker']['x'], v['anchor_marker']['y']) for c, v in cans.items()})
