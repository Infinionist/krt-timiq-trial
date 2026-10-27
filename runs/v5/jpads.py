import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1]); mm=pcbnew.ToMM
for r in sys.argv[2:]:
    f=b.FindFootprintByReference(r)
    rows=[]
    for p in f.Pads():
        bb=p.GetBoundingBox(); rows.append((p.GetNumber(),round(mm(bb.GetX()),2),round(mm(bb.GetY()),2),round(mm(bb.GetRight()),2),round(mm(bb.GetBottom()),2),p.GetNetname()))
    print(r,len(rows)); 
    for x in rows[:24]: print(' ',x)
    # silk/fab/crtyd extents
    for lay,name in ((pcbnew.F_SilkS,'silk'),(pcbnew.F_Fab,'fab'),(pcbnew.F_CrtYd,'crtyd')):
        xs=[];ys=[]
        for g in f.GraphicalItems():
            if g.GetLayer()==lay:
                bb=g.GetBoundingBox(); xs+= [mm(bb.GetX()),mm(bb.GetRight())]; ys+=[mm(bb.GetY()),mm(bb.GetBottom())]
        if xs: print(' ',name,round(min(xs),2),round(min(ys),2),round(max(xs),2),round(max(ys),2))
