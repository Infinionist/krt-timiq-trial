import sys; sys.argv=[sys.argv[0]]
sys.path.insert(0,'/tmp/pcb-trials/timiq/run2_work')
from analyze import *
holes=[]
for host in ('J5','BOX1'):
    for pd in p.footprints[host].pads:
        if (pd.drill or 0)>=4.0: holes.append((host,pd.pad_number,pd.global_x,pd.global_y,pd.drill))
def dist_rect(cx,cy,r):
    dx=max(r[0]-cx,0,cx-r[2]); dy=max(r[1]-cy,0,cy-r[3]); return math.hypot(dx,dy)
res=[]
for host,num,cx,cy,d in holes:
    rows=[]
    for ref,g in G.items():
        if ref==host or ref=='BOX1': continue
        r=g.rect
        e=dist_rect(cx,cy,r)-d/2
        er=None
        if g.tht_rect: er=dist_rect(cx,cy,g.tht_rect)-d/2
        prs=[padrect(pd) for pd in p.footprints[ref].pads]
        ep=min([dist_rect(cx,cy,q)-d/2 for q in prs]) if prs else 99
        rows.append((round(min(e, er if er is not None else 99),3), round(ep,3), ref, p.footprints[ref].layer))
    rows.sort()
    print(host, num, (round(cx,3),round(cy,3)), 'drill', d, 'nearest (rect-edge gap, pad gap, ref, side):', rows[:4])
    res.append(dict(host=host,pad=num,x=round(cx,4),y=round(cy,4),drill=d,human_gap=rows[0][0],nearest=rows[0][2]))
import json; json.dump(res,open('/tmp/pcb-trials/timiq/run2_work/holes.json','w'),indent=1)
