"""Measure the human board: cans' wall/inner rects, who sits under each, hole clearances. For our review only."""
import sys, json, math
sys.path[:0]=['/tmp/pcb-trials/timiq/krt/py_router','/tmp/pcb-trials/timiq/krt/py_placer']
from kicad_parser import parse_kicad_pcb
from placement import legality
BOARD = sys.argv[1] if len(sys.argv)>1 else '/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb'
p = parse_kicad_pcb(BOARD)
graded = legality.graded_parts_from_file(p, BOARD)
G = {g.ref: g for g in graded}
CANS = ['J7','J8','J9','J10','J11','J12']
def padrect(pd):
    w,h = pd.size_x, pd.size_y
    if int(round(pd.rotation or 0)) % 180 == 90: w,h = h,w
    return (pd.global_x-w/2, pd.global_y-h/2, pd.global_x+w/2, pd.global_y+h/2)
def can_geom(ref):
    fp = p.footprints[ref]
    rs = [padrect(pd) for pd in fp.pads]
    ox0=min(r[0] for r in rs); oy0=min(r[1] for r in rs); ox1=max(r[2] for r in rs); oy1=max(r[3] for r in rs)
    t = 1.0
    return (ox0,oy0,ox1,oy1), (ox0+t,oy0+t,ox1-t,oy1-t)
def inter(a,b): return min(a[2],b[2])-max(a[0],b[0]) > 0 and min(a[3],b[3])-max(a[1],b[1]) > 0
def gap(a,b):
    dx = max(a[0]-b[2], b[0]-a[2], 0); dy = max(a[1]-b[3], b[1]-a[3], 0)
    return math.hypot(dx,dy)
def side(ref): return p.footprints[ref].layer
if __name__ == '__main__':
    out = {}
    for c in CANS:
        o,i = can_geom(c)
        wall = [(o[0],o[1],o[2],o[1]+1),(o[0],o[3]-1,o[2],o[3]),(o[0],o[1],o[0]+1,o[3]),(o[2]-1,o[1],o[2],o[3])]
        mem=[]; strad=[]; onwall=[]; backs=[]
        for ref,g in G.items():
            if ref in CANS: continue
            r = g.rect
            if not inter(r,o): continue
            fl = side(ref)
            tag = (ref, fl)
            if any(inter(r,w) for w in wall): onwall.append((ref,fl))
            elif r[0]>=i[0] and r[1]>=i[1] and r[2]<=i[2] and r[3]<=i[3]: mem.append((ref,fl))
            else: strad.append((ref,fl))
        # nearest gap of any part pad to wall band (F side parts, outside+inside)
        out[c]=dict(outer=[round(v,3) for v in o], inner=[round(v,3) for v in i], inside_F=sorted(r for r,f in mem if f=='F.Cu'),
                    inside_B=sorted(r for r,f in mem if f!='F.Cu'), straddle=strad, on_wall=onwall)
    json.dump(out, open('/tmp/pcb-trials/timiq/run2_work/membership.json','w'), indent=1)
    for c,v in out.items():
        print(c, 'outer',v['outer'],'inner',v['inner'])
        print('  F inside', len(v['inside_F']), ' B inside', len(v['inside_B']), ' straddle', v['straddle'], ' onwall', v['on_wall'])
