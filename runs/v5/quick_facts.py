import sys, pcbnew
def load(p):
    b = pcbnew.LoadBoard(p); out = {}
    for f in b.GetFootprints():
        r = f.GetReference(); bb = f.GetBoundingBox(False, False)
        out[r] = ('B.Cu' if f.GetLayer()==pcbnew.B_Cu else 'F.Cu', pcbnew.ToMM(bb.GetWidth())*pcbnew.ToMM(bb.GetHeight()), f.GetPosition())
    return out
run = load(sys.argv[1]); hum = load(sys.argv[2])
ics = sorted([r for r in run if r.startswith('U')], key=lambda r: int(r[1:]))
print("ICs on B (run):", [(r, round(run[r][1])) for r in ics if run[r][0] == 'B.Cu'])
print("ICs on B (human):", [(r, round(hum[r][1])) for r in ics if hum[r][0] == 'B.Cu'])
print("face differs:", [r for r in run if r in hum and run[r][0] != hum[r][0]][:20])
