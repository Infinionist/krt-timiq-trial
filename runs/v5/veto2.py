#!/usr/bin/env python3
"""veto2.py VARIANT : ask the seat gate about every member at the pose place_simple left it (out.kicad_pcb), others in place."""
import sys, io, contextlib, json, collections
sys.path.insert(0, '/tmp/pcb-trials/timiq/krt/py_placer'); import _path
from kicad_parser import parse_kicad_pcb
V = sys.argv[1]
D = f'/tmp/pcb-trials/timiq/v5/probe/tiny_{V}'
q = io.StringIO()
with contextlib.redirect_stdout(q), contextlib.redirect_stderr(q):
    import place_simple as ps
    from placement import floorplan
    from placement.groups import parse_sources
    from placement.grouping import load_groups
    board = f'{D}/out.kicad_pcb'
    doc = load_groups(f'{D}/groups.json'); base = json.load(open(f'{D}/intent.json')); intent = floorplan.load_intent(f'{D}/intent.json')
    pcb = parse_kicad_pcb(board)
    blocks, _ = floorplan.resolve_blocks(intent, pcb, parse_sources('auto'))
    a = ps.build_parser().parse_args([board, '/dev/null', '--groups', f'{D}/groups.json', '--intent', f'{D}/intent.json'])
    state, model, movable, _n = ps.build(pcb, board, doc, base, a, intent, blocks, {'J7'})
cnt = collections.Counter(); who = collections.defaultdict(list)
for r in sorted(movable):
    p = state.parts[r]
    from placement.simple import legal
    res = state.candidate_veto(r, p.x, p.y, p.rot)
    if res is None and not legal(state, r, p.x, p.y, p.rot): res = ('pose_ok(non-candidate conjunct)', None)
    if res is None and not state.intent_clear(r, p.grade_rects(p.x, p.y, p.rot)): res = ('intent_clear', None)
    key = 'ADMITTED' if res is None else f'{res[0]} vs {res[1]}'
    cnt[key] += 1; who[key].append(f'{r}@{p.side}')
for k, v in cnt.most_common(): print(f'{v:3d}  {k}   {" ".join(who[k][:14])}')
