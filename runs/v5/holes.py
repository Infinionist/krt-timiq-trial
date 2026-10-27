import pcbnew, math, json, sys
b = pcbnew.LoadBoard(sys.argv[1]); mm = pcbnew.ToMM
hosts = ['J5', 'BOX1'] + ['FIX%d' % i for i in range(1, 9)]
allp = []
for f in b.GetFootprints():
    r = f.GetReference()
    for p in f.Pads():
        if p.GetDrillSize().x > 0 and r in hosts and mm(p.GetDrillSize().x) >= 2.0:
            continue
        bb = p.GetBoundingBox()
        allp.append((r, p.GetNumber(), mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom())))
out = []
for h in hosts:
    f = b.FindFootprintByReference(h)
    for p in f.Pads():
        d = mm(p.GetDrillSize().x)
        if d < 2.0: continue
        c = p.GetPosition(); cx, cy = mm(c.x), mm(c.y)
        ps = p.GetSize(); pr = mm(max(ps.x, ps.y)) / 2
        best = None
        for r, n, x0, y0, x1, y1 in allp:
            if r == h: continue
            dd = math.hypot(max(x0 - cx, 0, cx - x1), max(y0 - cy, 0, cy - y1))
            if best is None or dd < best[0]: best = (dd, r, n)
        out.append(dict(host=h, pad=p.GetNumber(), x=round(cx, 4), y=round(cy, 4), drill=d, pad_d=mm(max(ps.x, ps.y)), shape=str(p.GetShape()),
                        layers='B' if p.IsOnLayer(pcbnew.B_Cu) else '', gap_hole_edge=round(best[0] - d / 2, 3), gap_pad_edge=round(best[0] - pr, 3), nearest=best[1] + '.' + best[2]))
for o in out: print(o)
json.dump(out, open(sys.argv[2], 'w'), indent=1)
