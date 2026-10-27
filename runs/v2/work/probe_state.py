import sys, json, time
KRT='/tmp/pcb-trials/timiq/v2/krt'
sys.path.insert(0, KRT+'/py_placer'); import _path
import place_simple as ps
from kicad_parser import parse_kicad_pcb
from placement import floorplan
from placement.groups import parse_sources
board, intent_path, groups = sys.argv[1:4]
a = ps.build_parser().parse_args([board, '/dev/null', '--groups', groups, '--intent', intent_path])
from placement.grouping import load_groups
doc = load_groups(groups); base = json.load(open(intent_path)); intent = floorplan.load_intent(intent_path)
pcb = parse_kicad_pcb(board)
blocks, _ = floorplan.resolve_blocks(intent, pcb, parse_sources('auto'))
t=time.time()
state, model, movable, notes = ps.build(pcb, board, doc, base, a, intent, blocks, set())
print('built', time.time()-t, len(state.parts), len(movable))
from placement.simple import legal
bad=[r for r,p in state.parts.items() if not legal(state, r, p.x, p.y, p.rot)]
print('illegal at own pose', len(bad), bad[:60])
cans=['J7','J8','J9','J10','J11','J12']
bad2=[r for r,p in state.parts.items() if r not in cans and not legal(state, r, p.x, p.y, p.rot, set(cans))]
print('illegal ignoring cans', len(bad2))
only=[r for r in bad if r not in bad2 and r not in cans]
print('illegal only because of cans', len(only), only[:30])
h=state.heights
print('heights note', h.note, 'tops', len(h.top), 'covers', len(h.covers))
import collections
print(collections.Counter(v[1] for v in h.top.values()))
from placement import shields as sh
print('shields', {c:(len(s.members), s.under) for c,s in state.shields.items()})
print('preflight', sh.preflight(state, pcb, intent.shields, set(movable)))
import io
for c in cans:
    p=state.parts[c]
    state._why = {}
    ok = legal(state, c, p.x, p.y, p.rot)
    print(c, ok, state._why)
