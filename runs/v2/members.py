import sys, json, math
sys.path.insert(0,'/tmp/pcb-trials/timiq/v2/krt/py_placer'); import _path
from kicad_parser import parse_kicad_pcb
b=parse_kicad_pcb('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
cans=['J7','J8','J9','J10','J11','J12']
out={}
for c in cans:
    f=b.footprints[c]
    xs=[p.global_x for p in f.pads]; ys=[p.global_y for p in f.pads]
    box=(min(xs),min(ys),max(xs),max(ys))
    print(c,f.x,f.y,f.rotation,box)
    mem=[]
    for r,g in b.footprints.items():
        if r==c: continue
        if box[0]<g.x<box[2] and box[1]<g.y<box[3]: mem.append(r)
    out[c]=sorted(mem); print(c,len(mem),sorted(mem))
json.dump(out,open('/tmp/pcb-trials/timiq/v2/human_members.json','w'),indent=1)
print('sides')
for c,m in out.items():
    from collections import Counter
    print(c, Counter(b.footprints[r].layer for r in m))
