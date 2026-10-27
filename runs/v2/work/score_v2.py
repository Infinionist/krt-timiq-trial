#!/usr/bin/env python3
"""score_v2.py BOARD INTENT GROUPS -> JSON: the shield scoreboard, by script."""
import sys, json, math, contextlib, io
KRT='/tmp/pcb-trials/timiq/v2/krt'
sys.path.insert(0, KRT+'/py_placer'); import _path
import place_simple as ps
from kicad_parser import parse_kicad_pcb
from placement import floorplan, legality, shields as sh
from placement.groups import parse_sources
from placement.grouping import load_groups
from placement.simple import legal, mst_l1
board, ip, gp = sys.argv[1:4]
q = io.StringIO()
with contextlib.redirect_stdout(q), contextlib.redirect_stderr(q):
    doc = load_groups(gp); base = json.load(open(ip)); intent = floorplan.load_intent(ip)
    pcb = parse_kicad_pcb(board)
    blocks, _ = floorplan.resolve_blocks(intent, pcb, parse_sources('auto'))
    a = ps.build_parser().parse_args([board, '/dev/null', '--groups', gp, '--intent', ip])
    state, model, movable, _n = ps.build(pcb, board, doc, base, a, intent, blocks, set())
    parts = {g.ref: g for g in legality.graded_parts_from_file(pcb, board)}
shl, problems = sh.resolve(intent.shields, pcb.footprints)
parts = {r: x for r, x in parts.items() if r not in state.container_refs}
g = sh.grade(pcb, shl, parts, state.heights.under_height)
members = sum(len(s.members) for s in shl)
bad = {k: len(v) for k, v in g.items()}
inside = members - bad['outside'] - bad['wall']
# legality at the board's own poses (the placer's seat gate, every part)
illegal = [r for r, p in state.parts.items() if not legal(state, r, p.x, p.y, p.rot)]
cans = [s.can for s in shl]
illegal_ign = [r for r, p in state.parts.items() if r not in cans and not legal(state, r, p.x, p.y, p.rot, set(cans))]
# wire: HPWL over all nets with >= 2 pads, and the Manhattan MST of the signal nets (KRT's own wire term)
rails = set(model.rails) if hasattr(model, 'rails') else set()
hp = hs = mst = 0.0
nets = {}
for r, f in pcb.footprints.items():
    for p in f.pads:
        if p.net_id:
            nets.setdefault(p.net_id, []).append((r, p.global_x, p.global_y))
for n, pts in nets.items():
    if len(pts) < 2: continue
    xs = [p[1] for p in pts]; ys = [p[2] for p in pts]
    h = (max(xs) - min(xs)) + (max(ys) - min(ys)); hp += h
    if n not in rails:
        hs += h
        mst += mst_l1([(p[1], p[2]) for p in pts])[0] if isinstance(mst_l1([(p[1], p[2]) for p in pts]), tuple) else mst_l1([(p[1], p[2]) for p in pts])
# nets crossing each can wall (non-rail nets with pads inside the can's inner and outside it)
from placement.heights import to_board
cross = {}; crossing_nets = set()
mem_of = {m: s.can for s in shl for m in s.members}
for s in shl:
    fp = pcb.footprints[s.can]
    inner, outer, ring = sh.boxes_local(fp, 0.0)
    I = to_board(inner, (fp.x, fp.y, fp.rotation or 0.0))
    cnt = 0
    for n, pts in nets.items():
        if n in rails: continue
        pts2 = [p for p in pts if p[0] != s.can]
        ins = [p for p in pts2 if I[0] <= p[1] <= I[2] and I[1] <= p[2] <= I[3] and p[0] in s.members]
        outs = [p for p in pts2 if p not in ins]
        if ins and outs:
            cnt += 1; crossing_nets.add(n)
    cross[s.can] = cnt
# utilisation: member courtyard area over the inner area
util = {}
for s in shl:
    fp = pcb.footprints[s.can]; inner, _o, _r = sh.boxes_local(fp, 0.0)
    ia = (inner[2]-inner[0])*(inner[3]-inner[1])
    ma = sum((parts[m].rect[2]-parts[m].rect[0])*(parts[m].rect[3]-parts[m].rect[1]) for m in s.members if m in parts)
    util[s.can] = round(ma/ia, 3)
out = {'board': board, 'members_declared': members, 'members_inside': inside, 'outside': bad['outside'],
       'on_wall': bad['wall'], 'strangers_inside': bad['stranger'], 'too_tall': bad['too_tall'], 'height_unknown': bad['unknown'],
       'resolve_problems': problems, 'illegal_parts': len(illegal), 'illegal_ignoring_cans': len(illegal_ign),
       'illegal_only_due_to_cans': len(set(illegal) - set(illegal_ign) - set(cans)), 'cans_illegal': [c for c in cans if c in illegal],
       'hpwl_all_mm': round(hp), 'hpwl_signal_mm': round(hs), 'mst_signal_mm': round(mst),
       'nets_crossing_by_can': cross, 'nets_crossing_total': sum(cross.values()),
       'utilisation_by_can': util, 'utilisation_total': round(sum(util.values())/len(util), 3),
       'detail_outside': g['outside'][:10], 'detail_wall': g['wall'][:10], 'detail_stranger': g['stranger'][:10]}
print(json.dumps(out, indent=1))
