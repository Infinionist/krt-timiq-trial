import pcbnew, json, sys
src, dst = sys.argv[1], sys.argv[2]
hum = pcbnew.LoadBoard('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
mm = pcbnew.ToMM
grp = json.load(open('/tmp/pcb-trials/timiq/run/groups.json'))
pll = set(next(g for g in grp['groups'] if g['name']=='pll')['refs'])
rect = (131,160,162,190)
keep = {'J7'}
faces = {}
for f in hum.GetFootprints():
    r = f.GetReference(); p = f.GetPosition(); x, y = mm(p.x), mm(p.y)
    if r in pll and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
        keep.add(r); faces[r] = 'B' if f.IsFlipped() else 'F'
b = pcbnew.LoadBoard(src)
for f in list(b.GetFootprints()):
    if f.GetReference() not in keep:
        b.Remove(f)
pcbnew.SaveBoard(dst, b)
json.dump({'keep': sorted(keep), 'faces': faces}, open(dst + '.members.json', 'w'))
print(len(keep), 'kept', sum(1 for v in faces.values() if v=='F'), 'F', sum(1 for v in faces.values() if v=='B'), 'B')
