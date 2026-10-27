import sys
sys.path[:0]=['/tmp/pcb-trials/timiq/krt/py_router']
from kicad_parser import parse_kicad_pcb
p=parse_kicad_pcb('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
want=['BOX1','J1','J2','J3','J4','J5','J6','J7','J8','J9','J10','J11','J12','D1','D2','D3','D4','D5','D6','D7','D8','Q1','U1','U2','U23','U24','U4']+['FIX%d'%i for i in range(1,9)]+['TP%d'%i for i in range(1,10)]
for r in want:
    fp=p.footprints.get(r)
    if not fp: print(r,'missing'); continue
    nets=sorted({pd.net_name for pd in fp.pads if pd.net_name})
    print(r,(fp.footprint_name or '').split(':')[-1],'val=',getattr(fp,'value',None),'x=%.3f y=%.3f rot=%.1f'%(fp.x,fp.y,fp.rotation or 0),'layer=',getattr(fp,'layer',None),'pads=',len(fp.pads),'locked=',getattr(fp,'locked',None),'nets=',nets[:4],len(nets))
