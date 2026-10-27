#!/usr/bin/env python3
"""score_v4.py BOARD LABEL OUT.json -> the variant-4 scoreboard, by script (extends v2/work/score_v2.py).
 shields incl. back_members, wire, bottom-passive distance (direct IC pins, pad centre to passive centre), the box (parts that should be inside
 but are not, outsiders inside, wall-band hits), hole clearance, and check_floorplan's error count by rule under intent_v4."""
import sys, json, math, contextlib, io, os, shutil, subprocess, statistics
sys.path.insert(0, '/tmp/pcb-trials/timiq/v4/work')
from common import *
import place_simple as ps
from placement import floorplan, shields as sh
from placement.groups import parse_sources
from placement.grouping import load_groups
from placement.simple import legal, mst_l1
from placement.heights import to_board
import bottom
board, label, outp = sys.argv[1:4]
IP = '/tmp/pcb-trials/timiq/v4/in/intent_v4.json'; GP = '/tmp/pcb-trials/timiq/v4/in/groups_v2.json'
q = io.StringIO()
with contextlib.redirect_stdout(q), contextlib.redirect_stderr(q):
    doc = load_groups(GP); base = json.load(open(IP)); intent = floorplan.load_intent(IP)
    pcb = parse_kicad_pcb(board)
    blocks, _ = floorplan.resolve_blocks(intent, pcb, parse_sources('auto'))
    a = ps.build_parser().parse_args([board, '/dev/null', '--groups', GP, '--intent', IP])
    state, model, movable, _n = ps.build(pcb, board, doc, base, a, intent, blocks, set())
    G = {g.ref: g for g in legality.graded_parts_from_file(pcb, board)}
out = {'board': board, 'label': label}
fixed = {f['ref'] for f in base['fixed_poses']}
# ---- shields (front members, back members)
shl, problems = sh.resolve(intent.shields, pcb.footprints)
parts = {r: x for r, x in G.items() if r not in state.container_refs}
g = sh.grade(pcb, shl, parts, state.heights.under_height)
fm = sum(len(s.members) for s in shl); bm = sum(len(s.back) for s in shl)
back_out = [r for r in g['outside'] if r.get('face') == 'back']
front_out = [r for r in g['outside'] if r.get('face') != 'back']
out['shields'] = {'front_declared': fm, 'front_outside': len(front_out), 'front_on_wall': len(g['wall']), 'strangers_inside': len(g['stranger']),
                  'back_declared': bm, 'back_outside': len(back_out), 'too_tall': len(g['too_tall']),
                  'detail_outside': (front_out + back_out)[:8], 'resolve_problems': problems}
# ---- wire
rails = set(model.rails) if hasattr(model, 'rails') else set()
hp = mst = 0.0; nets = {}
for r, f in pcb.footprints.items():
    for p in f.pads:
        if p.net_id: nets.setdefault(p.net_id, []).append((r, p.global_x, p.global_y))
for n, pts in nets.items():
    if len(pts) < 2: continue
    xs = [x[1] for x in pts]; ys = [x[2] for x in pts]
    hp += (max(xs) - min(xs)) + (max(ys) - min(ys))
    if n not in rails:
        m = mst_l1([(x[1], x[2]) for x in pts]); mst += m[0] if isinstance(m, tuple) else m
out['wire'] = {'hpwl_mm': round(hp), 'mst_signal_mm': round(mst)}
cans = [s.can for s in shl]
out['illegal_parts'] = [r for r, p in state.parts.items() if not legal(state, r, p.x, p.y, p.rot)]
# ---- bottom passives
pc = parse_kicad_pcb(HUMAN)
served = bottom.served_pins(pc)
ds = {}
for r, pins in served.items():
    f = pcb.footprints[r]
    if f.layer != 'B.Cu' or not pins: continue
    own = {pd.net_id for pd in f.pads if pd.net_id}
    pins2 = [(ic, pn) for ic, pn in pins if any(str(x.pad_number) == pn and x.net_id in own for x in pcb.footprints[ic].pads)]
    if not pins2: continue
    ds[r] = min(math.hypot(f.x - x.global_x, f.y - x.global_y) for ic, pn in pins2 for x in pcb.footprints[ic].pads if str(x.pad_number) == pn)
v = sorted(ds.values())
out['bottom_passives'] = {'n': len(v), 'median_mm': round(statistics.median(v), 2), 'gt10mm': sum(d > 10 for d in v), 'gt20mm': sum(d > 20 for d in v),
                          'worst': [(r, round(d, 1)) for r, d in sorted(ds.items(), key=lambda kv: -kv[1])[:8]]}
# ---- the box
ph, Gh = load(HUMAN)
mem_cans = set(json.load(open('/tmp/pcb-trials/timiq/run2_work/membership.json')))
cls = {}
for r, gg in Gh.items():
    if r in fixed or r.startswith(('FIX', 'BOX')): continue
    qq = gg.rect
    if r in mem_cans: cls[r] = 'can'; continue
    cls[r] = 'inner' if inside(qq, INN) else 'mid' if inside(qq, MID) else 'outer' if inside(qq, OUT) else 'straddle' if inter(qq, OUT) else 'outside'
zone = {'inner': INN, 'mid': MID, 'outer': OUT, 'can': OUT}
miss = [r for r, c in cls.items() if c in zone and r in G and not inside(G[r].rect, zone[c], 0.01)]
miss_inn = [r for r, c in cls.items() if c in zone and r in G and not inside(G[r].rect, INN, 0.01)]
outs_in = [r for r, c in cls.items() if c == 'outside' and r in G and inter(G[r].rect, OUT)]
outs_inn = [r for r, c in cls.items() if c == 'outside' and r in G and inter(G[r].rect, INN)]
band = [r for r, gg in G.items() if r not in fixed and not r.startswith(('FIX', 'BOX')) and inter(gg.rect, MID) and not inside(gg.rect, INN, 0.01)]
band_F = [r for r in band if pcb.footprints[r].layer == 'F.Cu']
out['box'] = {'should_be_inside_but_outside_their_zone': len(miss), 'should_be_inside_but_outside_inner_square': len(miss_inn),
              'outsiders_in_box_outline': len(outs_in), 'outsiders_in_inner_square': len(outs_inn),
              'wall_band_hits_all': len(band), 'wall_band_hits_F': len(band_F),
              'detail_missing': miss[:10], 'detail_outsiders': outs_in[:10]}
# ---- holes
def dist_rect(cx, cy, r): return math.hypot(max(r[0] - cx, 0, cx - r[2]), max(r[1] - cy, 0, cy - r[3]))
hits, hits35 = [], []
for k in intent.keepouts:
    if not k.get('circle'): continue
    cx, cy, rad = k['circle']
    drill_r = rad - 3.5 if 'x' else 0
    for r, gg in G.items():
        if r in (k.get('allow') or ()): continue
        d = min(dist_rect(cx, cy, gg.rect), dist_rect(cx, cy, gg.tht_rect) if gg.tht_rect else 99)
        if d < rad - 1e-6: hits.append((k['name'], r, round(d, 2)))
# the plain 3.5 mm rule (hole edge) at every hole, excluding the host and BOX1 and the fixed parts
for h in json.load(open('/tmp/pcb-trials/timiq/run2_work/holes.json')):
    pass
for k in intent.keepouts:
    if not k.get('circle'): continue
    cx, cy, rad = k['circle']
    why = k['context']['why']
    d_hole = float(why.split('drill ')[1].split(' mm')[0])
    for r, gg in G.items():
        if r in fixed or r.startswith(('FIX', 'BOX')): continue
        d = min(dist_rect(cx, cy, gg.rect), dist_rect(cx, cy, gg.tht_rect) if gg.tht_rect else 99) - d_hole / 2
        if d < 3.5 - 1e-6: hits35.append((k['name'], r, round(d, 2)))
out['holes'] = {'hits_vs_declared_radius': len(hits), 'hits_vs_plain_3.5mm': len(hits35), 'detail_declared': hits[:8], 'detail_3.5': sorted(hits35, key=lambda x: x[2])[:10]}
# ---- check_floorplan under intent_v4
work = f'/tmp/pcb-trials/timiq/v4/work/cf_{label}'
shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
shutil.copy(board, f'{work}/b.kicad_pcb')
for ext in ('.kicad_pro', '.kicad_prl'):
    src = os.path.splitext(board)[0] + ext
    if os.path.exists(src): shutil.copy(src, f'{work}/b{ext}')
shutil.copy('/tmp/pcb-trials/timiq/v4/in/v4.design-brief.json', f'{work}/b.design-brief.json')
subprocess.run([sys.executable, '-X', 'utf8', '/tmp/pcb-trials/timiq/v2/krt/py_tools/check_floorplan.py', f'{work}/b.kicad_pcb', '--intent', IP,
                '--json', f'{work}/cf.json', '--allow-routed'], capture_output=True, text=True, timeout=900)
try:
    cf = json.load(open(f'{work}/cf.json'))
    from collections import Counter
    c = Counter((x['rule'], x['severity']) for x in cf['violations'])
    out['check_floorplan'] = {f'{r}:{s}': n for (r, s), n in sorted(c.items())}
    out['check_floorplan_errors'] = sum(n for (r, s), n in c.items() if s == 'error')
    out['proximity_errors'] = [x['message'][:90] for x in cf['violations'] if x['rule'] == 'proximity' and x['severity'] == 'error'][:6]
except Exception as ex:
    out['check_floorplan'] = f'failed: {ex}'
json.dump(out, open(outp, 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k not in ('illegal_parts',)}, indent=1)[:4000])
