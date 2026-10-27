import sys, json, collections
sys.path.insert(0,'/tmp/pcb-trials/timiq/v2/krt/py_placer'); import _path
from kicad_parser import parse_kicad_pcb
b=parse_kicad_pcb('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
m=json.load(open('/tmp/pcb-trials/timiq/v2/human_members.json'))
for c,refs in m.items():
    cnt=collections.Counter(b.footprints[r].footprint_name for r in refs if b.footprints[r].layer=='F.Cu')
    print(c, dict(cnt))
