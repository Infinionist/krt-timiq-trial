import sys, re, json
KRT='/tmp/pcb-trials/timiq/krt'
for d in ('py_router','py_placer'): sys.path.insert(0, KRT+'/'+d)
from kicad_parser import parse_kicad_pcb
pcb=parse_kicad_pcb('/tmp/pcb-trials/timiq/v5/fixed.kicad_pcb')
names={nid:n.name for nid,n in pcb.nets.items()}
nets={}
for ref,fp in pcb.footprints.items():
    for p in fp.pads:
        if p.net_id>0: nets.setdefault(names[p.net_id],[]).append((ref,str(p.pad_number)))
json.dump(nets, open('/tmp/pcb-trials/timiq/v5/probe3/nets.json','w'))
print(len(nets))
