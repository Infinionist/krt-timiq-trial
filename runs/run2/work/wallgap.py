import sys; sys.argv=[sys.argv[0]]
sys.path.insert(0,'/tmp/pcb-trials/timiq/run2_work')
from analyze import *
rows=[]
for c in CANS:
    o,i=can_geom(c)
    wall=[(o[0],o[1],o[2],o[1]+1),(o[0],o[3]-1,o[2],o[3]),(o[0],o[1],o[0]+1,o[3]),(o[2]-1,o[1],o[2],o[3])]
    for ref,g in G.items():
        if ref in CANS or ref=='BOX1': continue
        if side(ref)!='F.Cu': continue
        # use pad rects (copper) for gap; and occupancy rect
        d=min(gap(g.rect,w) for w in wall)
        prs=[padrect(pd) for pd in p.footprints[ref].pads]
        dp=min(min(gap(r,w) for w in wall) for r in prs) if prs else 99
        rows.append((round(d,3),round(dp,3),c,ref))
rows.sort()
for r in rows[:14]: print(r)
