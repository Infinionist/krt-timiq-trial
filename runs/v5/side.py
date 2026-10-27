import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
for r in sys.argv[2:]:
    f=b.FindFootprintByReference(r); p=f.GetPosition()
    print(r,'B' if f.IsFlipped() else 'F',round(pcbnew.ToMM(p.x),3),round(pcbnew.ToMM(p.y),3),f.GetOrientationDegrees(),f.IsLocked())
