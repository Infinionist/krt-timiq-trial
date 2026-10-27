import pcbnew, collections
b=pcbnew.LoadBoard('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
f=b.FindFootprintByReference('BOX1')
print('BOX1 pos',pcbnew.ToMM(f.GetX()),pcbnew.ToMM(f.GetY()),f.GetOrientationDegrees(), 'layer',b.GetLayerName(f.GetLayer()))
c=collections.Counter((type(g).__name__,b.GetLayerName(g.GetLayer())) for g in f.GraphicalItems()); print(c)
for p in f.Pads(): print(p.GetNumber(), pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y), p.GetAttribute(), pcbnew.ToMM(p.GetSizeX()), pcbnew.ToMM(p.GetSizeY()), pcbnew.ToMM(p.GetDrillSize().x))
bb=f.GetBoundingBox(False); print('bbox',[pcbnew.ToMM(v) for v in (bb.GetX(),bb.GetY(),bb.GetWidth(),bb.GetHeight())])
c=collections.Counter(b.GetLayerName(d.GetLayer()) for d in b.GetDrawings()); print('board drawings',c)
for d in []:
    if d.GetLayer()==pcbnew.Edge_Cuts: print(d.GetShapeStr(), pcbnew.ToMM(d.GetStart().x),pcbnew.ToMM(d.GetStart().y),pcbnew.ToMM(d.GetEnd().x),pcbnew.ToMM(d.GetEnd().y))
for r in ['J1','J5','J6','FIX1','J7','D2']:
    q=b.FindFootprintByReference(r); bb=q.GetBoundingBox(False)
    print(r,'bbox',[round(pcbnew.ToMM(v),2) for v in (bb.GetX(),bb.GetY(),bb.GetWidth(),bb.GetHeight())], 'side', 'B' if q.IsFlipped() else 'F', 'orient', q.GetOrientationDegrees(), 'pos', round(pcbnew.ToMM(q.GetX()),3), round(pcbnew.ToMM(q.GetY()),3))
