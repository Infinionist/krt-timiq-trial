import sys
sys.path[:0]=['/tmp/pcb-trials/timiq/krt/py_router']
from kicad_parser import parse_kicad_pcb
a=parse_kicad_pcb(sys.argv[1]); b=parse_kicad_pcb(sys.argv[2])
bad=0; only=set(a.footprints)^set(b.footprints)
if only: print('only in one:',sorted(only)); bad+=1
mx=0
for r,fa in a.footprints.items():
    fb=b.footprints.get(r)
    if not fb: continue
    d=max(abs(fa.x-fb.x),abs(fa.y-fb.y),abs(((fa.rotation or 0)-(fb.rotation or 0)+180)%360-180))
    if fa.layer!=fb.layer: d=99
    for pa,pb in zip(fa.pads,fb.pads):
        d=max(d,abs(pa.global_x-pb.global_x),abs(pa.global_y-pb.global_y))
    mx=max(mx,d)
    if d>1e-3: bad+=1; print('differs',r,d)
print('footprints',len(a.footprints),len(b.footprints),'max pose/pad diff',mx,'bad',bad)
sys.exit(1 if bad else 0)
