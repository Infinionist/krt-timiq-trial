import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
want="FIX1 FIX2 FIX3 FIX4 FIX5 FIX6 FIX7 FIX8 BOX1 J1 J2 J3 J4 J5 J6 D2 D3 D4 D5 D6 D7 D8 D1 J7 J8 J9 J10 J11 J12".split()
for r in want:
    f=b.FindFootprintByReference(r)
    if not f: print(r,'MISSING'); continue
    p=f.GetPosition()
    print(r, pcbnew.ToMM(p.x), pcbnew.ToMM(p.y), f.GetOrientationDegrees(), 'B' if f.IsFlipped() else 'F', f.GetFPIDAsString(), f.IsLocked())
