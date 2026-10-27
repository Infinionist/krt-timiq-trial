import pcbnew,sys
b=pcbnew.LoadBoard(sys.argv[1])
for r in sys.argv[2:]:
    f=b.FindFootprintByReference(r)
    bb=f.GetBoundingBox(False,False)
    cy=f.GetCourtyard(pcbnew.F_CrtYd if not f.IsFlipped() else pcbnew.B_CrtYd)
    cb=cy.BBox() if cy.OutlineCount() else None
    pads=[p.GetBoundingBox() for p in f.Pads()]
    x0=min(p.GetX() for p in pads);x1=max(p.GetRight() for p in pads);y0=min(p.GetY() for p in pads);y1=max(p.GetBottom() for p in pads)
    mm=pcbnew.ToMM
    pos=f.GetPosition()
    print(r,'pos',mm(pos.x),mm(pos.y),'rot',f.GetOrientationDegrees(),'npads',len(pads))
    print('  bbox(nograph)',[round(mm(v),2) for v in (bb.GetX(),bb.GetY(),bb.GetRight(),bb.GetBottom())])
    if cb: print('  courtyard',[round(mm(v),2) for v in (cb.GetX(),cb.GetY(),cb.GetRight(),cb.GetBottom())])
    print('  pads',[round(mm(v),2) for v in (x0,y0,x1,y1)])
    print('  models',[m.m_Filename for m in f.Models()], 'attr',f.GetAttributes())
