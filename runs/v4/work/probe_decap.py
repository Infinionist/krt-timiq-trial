import sys, json, io, contextlib
KRT='/tmp/pcb-trials/timiq/v2/krt'
sys.path.insert(0, KRT+'/py_placer'); import _path
import place_simple as ps
from kicad_parser import parse_kicad_pcb
from placement import floorplan
from placement.groups import parse_sources
from placement.grouping import load_groups
from placement.quench import TetherGateView
board=sys.argv[1]; ip=sys.argv[2] if len(sys.argv)>2 else '/tmp/pcb-trials/timiq/v4/in/intent_v4.json'; gp='/tmp/pcb-trials/timiq/v4/in/groups_v2.json'
q=io.StringIO()
with contextlib.redirect_stdout(q), contextlib.redirect_stderr(q):
    doc=load_groups(gp); base=json.load(open(ip)); intent=floorplan.load_intent(ip); pcb=parse_kicad_pcb(board)
    blocks,_=floorplan.resolve_blocks(intent,pcb,parse_sources('auto'))
    a=ps.build_parser().parse_args([board,'/dev/null','--groups',gp,'--intent',ip])
    state,model,movable,notes=ps.build(pcb,board,doc,base,a,intent,blocks,set())
spec={k:v for k,v in floorplan.tether_gate_spec(intent).items() if k in ('decap_distance','decap_pin_distance')}
v=TetherGateView(pcb,board,state.parts,spec)
T=v._tether_terms
from collections import Counter
print(Counter(t.kind for t in T), len(T))
print(model.claims[:2], len(model.claims), len(model._cmax))
