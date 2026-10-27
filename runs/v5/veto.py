#!/usr/bin/env python3
"""veto.py VARIANT : for each member of tiny_<V>, ask the seat gate (quench.candidate_veto) about the member's HUMAN pose, all other
members still on the pile: which conjunct refuses it and against which part. Counts by (check, blocker)."""
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
    board = f'{D}/seat.kicad_pcb'
    doc = load_groups(f'{D}/groups.json'); base = json.load(open(f'{D}/intent.json')); intent = floorplan.load_intent(f'{D}/intent.json')
    pcb = parse_kicad_pcb(board)
    blocks, _ = floorplan.resolve_blocks(intent, pcb, parse_sources('auto'))
    a = ps.build_parser().parse_args([board, '/dev/null', '--groups', f'{D}/groups.json', '--intent', f'{D}/intent.json'])
    state, model, movable, _n = ps.build(pcb, board, doc, base, a, intent, blocks, {'J7'})
hum = parse_kicad_pcb('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
cnt = collections.Counter(); who = collections.defaultdict(list)
for r in sorted(movable):
    h = hum.footprints[r]
    p = state.parts[r]
    if p.side != 'F': continue
    rot = round(h.rotation, 1) if hasattr(h, 'rotation') else 0
    res = state.candidate_veto(r, h.x, h.y, rot)
    key = 'ADMITTED' if res is None else f'{res[0]} vs {res[1]}'
    cnt[key] += 1; who[key].append(r)
for k, v in cnt.most_common(): print(f'{v:3d}  {k}   {" ".join(who[k][:12])}')
