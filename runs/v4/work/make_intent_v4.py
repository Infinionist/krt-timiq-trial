#!/usr/bin/env python3
"""Variant 4 intent + design brief: variant 2's intent (run 1's + shields[]) plus every constraint we know.
usage: make_intent_v4.py OUTDIR [--loosen loosen.json]
 loosen.json: {"proximity": {ref: max_mm}, "holes": {name: clear_mm}}  (rows the human board breaks, loosened to its value)"""
import sys, json, math, copy, os
sys.path.insert(0,'/tmp/pcb-trials/timiq/v4/work')
from common import *
import netproxy
outdir = sys.argv[1]
loosen = json.load(open(sys.argv[sys.argv.index('--loosen')+1])) if '--loosen' in sys.argv else {}
p, G = load(HUMAN)
base = json.load(open('/tmp/pcb-trials/timiq/v2/run/intent_v2.json'))
fixed = {f['ref'] for f in base['fixed_poses']}
mem = json.load(open('/tmp/pcb-trials/timiq/run2_work/membership.json'))
report = {}

# ---------------- 3. shields: F members as variant 2; back_members = the human's bottom parts under each can
def pad_box(ref):
    rs = [(pd.global_x - pd.size_x/2, pd.global_y - pd.size_y/2, pd.global_x + pd.size_x/2, pd.global_y + pd.size_y/2) for pd in p.footprints[ref].pads]
    return rs
shields = []
nback = 0
for can, m in mem.items():
    outer = m['outer']
    backs = list(m['inside_B'])
    # bottom parts the human has on the can's wall ring but wholly inside the footprint: under the can too
    for ref, lay in m['on_wall']:
        if lay == 'B.Cu' and inside(G[ref].rect, outer, 0.01): backs.append(ref)
    back = sorted(set(backs)); nback += len(back)
    shields.append({'can': can, 'underside_mm': 2.0, 'wall_clearance_mm': 0.2, 'members': sorted(m['inside_F']),
                    'back_members': back,
                    'source': "experiment: members = the F-face parts inside the human board's can, back_members = the B-face parts under its footprint (human map, run2_work/membership.json); lid height assumed"})
base['shields'] = shields
report['shields'] = {'cans': len(shields), 'front_members': sum(len(s['members']) for s in shields), 'back_members': nback}

# ---------------- 1. holes
movable_h = {r: g for r, g in G.items() if r not in fixed and not r.startswith(('FIX','BOX'))}
def dist_rect(cx, cy, r):
    return math.hypot(max(r[0]-cx, 0, cx-r[2]), max(r[1]-cy, 0, cy-r[3]))
holes = []
for host in ['J5', 'BOX1'] + [f'FIX{i}' for i in range(1, 9)]:
    for pd in p.footprints[host].pads:
        if (pd.drill or 0) >= 3.0:
            holes.append((host, str(pd.pad_number), pd.global_x, pd.global_y, pd.drill))
keepouts, hole_rows = [], []
for host, num, cx, cy, d in holes:
    gap = min(min(dist_rect(cx, cy, g.rect), dist_rect(cx, cy, g.tht_rect) if g.tht_rect else 99) for g in movable_h.values()) - d/2
    near = min(movable_h, key=lambda r: min(dist_rect(cx, cy, movable_h[r].rect), dist_rect(cx, cy, movable_h[r].tht_rect) if movable_h[r].tht_rect else 99))
    clear = 3.5 if gap >= 3.5 else math.floor((gap - 0.005) * 1000) / 1000
    name = f'hole-{host}-{num or "x"}' if host != 'J5' else f'hole-J5-{1 if cy > 120 else 2}'
    if name in loosen.get('holes', {}): clear = loosen['holes'][name]
    rad = round(d/2 + clear, 3)
    allow = [host, 'BOX1'] if host != 'BOX1' else ['BOX1']
    # a fixed part the human has inside the circle is exempt (its pose is not the placer's)
    for r in sorted(fixed):
        if r in allow: continue
        g = G[r]
        if min(dist_rect(cx, cy, g.rect), dist_rect(cx, cy, g.tht_rect) if g.tht_rect else 99) < rad: allow.append(r)
    allow = list(dict.fromkeys(allow))
    why = f'{host} mounting hole, drill {d:g} mm: no part within {clear:g} mm of the hole edge' + ('' if clear >= 3.5 else f' (the human board has a part at {gap:.3f} mm: {near})')
    keepouts.append({'name': name, 'circle': [round(cx, 4), round(cy, 4), rad], 'sides': ['F', 'B'], 'allow': allow,
                     'kind': 'mounting_hole', 'why': why})
    hole_rows.append({'name': name, 'host': host, 'drill': d, 'clear_mm': clear, 'human_gap_mm': round(gap, 3), 'nearest': near, 'allow': allow})
report['holes'] = hole_rows

# ---------------- 2. the box
cls = {}
for r, g in movable_h.items():
    q = g.rect
    if inside(q, INN): cls[r] = 'inner'
    elif inside(q, MID): cls[r] = 'mid'
    elif inside(q, OUT): cls[r] = 'outer'
    elif inter(q, OUT): cls[r] = 'straddle'
    else: cls[r] = 'outside'
for c_ in mem:                     # the six cans cannot fit the inner square (3 x 34.3 mm + gaps > 104.5 mm): zone = the outer square
    cls[c_] = 'can'
fixed_in_out = [r for r in sorted(fixed | {'BOX1'}) if inter(G[r].rect, OUT)]
allow_inside = sorted(r for r, c in cls.items() if c in ('inner', 'mid', 'outer', 'can')) + fixed_in_out
allow_inside = list(dict.fromkeys(allow_inside))
allow_band = sorted(r for r, c in cls.items() if c in ('mid', 'outer', 'can', 'straddle')) + fixed_in_out
allow_band = list(dict.fromkeys(allow_band))
blocks = base['blocks']
def blk(name, refs, zone, note):
    return {'name': name, 'refs': sorted(refs), 'zone': [round(v, 3) for v in zone], 'tolerance_mm': 0.0, 'note': note}
blocks += [
    blk('box_inside', [r for r, c in cls.items() if c == 'inner'], INN,
        'BOX1 (Hammond 1590Q): parts the human board has inside the inner square stay inside it'),
    blk('box_wallband', [r for r, c in cls.items() if c == 'mid'], MID,
        'loosened to the human board: these parts stand in the wall band (between the 126.96 and 131.96 squares) on the human board, so they may stay inside the middle square'),
    blk('box_cans', [r for r, c in cls.items() if c == 'can'], OUT,
        'the six shield cans: three 34.3 mm cans plus gaps (109 mm) do not fit the 104.5 mm inner square, and the human board has them in the wall band (J11 and J7 to 129.24 mm), so they are zoned to the outer square'),
    blk('box_outerband', [r for r, c in cls.items() if c == 'outer'], OUT,
        'loosened to the human board: these parts stand between the outer and middle squares on the human board'),
]
blocks[:] = [b for b in blocks if b['refs']]
def rect_row(name, rect, allow, why):
    return {'name': name, 'rect': [round(v, 3) for v in rect], 'sides': ['F', 'B'], 'allow': allow, 'kind': 'enclosure', 'why': why}
band = [('top', (OUT[0], OUT[1], OUT[2], INN[1])), ('bottom', (OUT[0], INN[3], OUT[2], OUT[3])),
        ('left', (OUT[0], INN[1], INN[0], INN[3])), ('right', (INN[2], INN[1], OUT[2], INN[3]))]
for nm, rc in band:
    keepouts.append(rect_row(f'box-wall-{nm}', rc, allow_band,
                             'BOX1 wall band and outer ring (assumed from the F.SilkS squares: 122.21/126.96/131.96 .. 236.46/241.46/246.21 x, 92.95/97.7/102.7 .. 207.2/212.2/216.95 y): no part, except those the human board has there'))
keepouts.append(rect_row('box-interior', INN, allow_inside,
                         'BOX1 interior (the inner square): only the RF-section parts the human board has inside the box, so the power supply, LEDs and connectors stay outside'))
report['box'] = {k: sum(1 for c in cls.values() if c == k) for k in ('inner', 'mid', 'outer', 'can', 'straddle', 'outside')}
report['box']['fixed_overlapping_box'] = fixed_in_out
report['box']['mid_refs'] = sorted(r for r, c in cls.items() if c == 'mid')
report['box']['outer_refs'] = sorted(r for r, c in cls.items() if c == 'outer')
report['box']['straddle_refs'] = sorted(r for r, c in cls.items() if c == 'straddle')
base['keepouts'] = [{**{k: v for k, v in k_.items() if k not in ('kind', 'why')},
                     'context': {'kind': k_['kind'], 'source': 'brief', 'why': k_['why']}} for k_ in keepouts]
base['blocks'] = blocks

# ---------------- 4. decaps
dec = json.load(open('/tmp/pcb-trials/timiq/_truth/intent_with_decaps.json'))['decaps']
base['decaps'] = dec
report['decaps'] = dec

# ---------------- 5. pin-adjacent passives
tm = {m['ref'] for t in base['templates'] for m in t['members']}
rows, bridge, name, gnd = netproxy.analyse(p, skip=tm)
prox = []
for o in rows:
    if o['ref'] in loosen.get('proximity', {}):
        if loosen['proximity'][o['ref']] is None:
            continue           # the human board is >10 mm from the inferred IC: the inference (part at the pin) is wrong; row dropped
        o = dict(o, max_mm=loosen['proximity'][o['ref']])
    prox.append({k: o[k] for k in ('ref', 'near', 'max_mm', 'basis', 'pads', 'why')})
base['proximity'] = prox
report['proximity'] = {'rows': len(prox), 'direct': sum(1 for o in rows if o['hop'] == 1), 'chain': sum(1 for o in rows if o['hop'] > 1),
                       'shunt_3mm': sum(1 for o in rows if o['kind'] == 'shunt'), 'series_5mm': sum(1 for o in rows if o['kind'] == 'series'),
                       'bridge_skipped': bridge, 'template_members_skipped': sorted(tm), 'loosened': {k: v for k, v in loosen.get('proximity', {}).items() if v is not None}, 'dropped_human_gt_10mm': loosen.get('dropped', {})}

base['min_reader'] = 16
base.setdefault('context', {})['variant4'] = 'every known constraint: holes, BOX1, shields with back_members, decaps, pin-adjacent proximity (netlist script), fixed poses'
base['context']['keepouts_note'] = 'v4: hole and BOX1 keep-outs declared by hand (design brief), see keepouts[]'
os.makedirs(outdir, exist_ok=True)
json.dump(base, open(f'{outdir}/intent_v4.json', 'w'), indent=1)
brief = {'schema': 1, 'kind': 'design-brief', 'units': 'mm', 'board': 'TimIQ_RF.kicad_pcb', 'interfaces': [],
         'context': {'rule': 'fa10-decl-v1', 'variant': 'v4'},
         'keepouts': [dict(k) for k in keepouts]}
json.dump(brief, open(f'{outdir}/v4.design-brief.json', 'w'), indent=1)
json.dump(report, open(f'{outdir}/report.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in report.items() if k not in ('holes',)}, indent=1)[:3000])
for h in hole_rows: print(h['name'], h['drill'], h['clear_mm'], h['human_gap_mm'], h['nearest'], h['allow'])
