import pcbnew,sys,json
b=pcbnew.LoadBoard(sys.argv[1]); rect=[float(v) for v in sys.argv[2:6]]
grp=json.load(open('/tmp/pcb-trials/timiq/run/groups.json'))
pll=set(next(g for g in grp['groups'] if g['name']=='pll')['refs'])
mm=pcbnew.ToMM
for f in b.GetFootprints():
    p=f.GetPosition(); x,y=mm(p.x),mm(p.y)
    if rect[0]<=x<=rect[2] and rect[1]<=y<=rect[3]:
        r=f.GetReference()
        if r.startswith('J'): continue
        print(r,'PLL' if r in pll else '-', 'B' if f.IsFlipped() else 'F', round(x,2),round(y,2),f.GetOrientationDegrees(),f.GetFPIDAsString().split(':')[-1], f.GetValue())
