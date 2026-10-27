import pcbnew, json, collections, sys
mm = pcbnew.ToMM
b = pcbnew.LoadBoard('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
grp = json.load(open('/tmp/pcb-trials/timiq/run/groups.json'))['groups']
g_of = {r: g['name'] for g in grp for r in g['refs']}
cans = {}
for c in ['J7', 'J8', 'J9', 'J10', 'J11', 'J12']:
    f = b.FindFootprintByReference(c); p = f.GetPosition(); x, y = mm(p.x), mm(p.y)
    cans[c] = (x - 0.6548, y - 31.3, x + 30.1452, y - 0.5)
tab = collections.defaultdict(lambda: collections.Counter())
inside_of = {}
for f in b.GetFootprints():
    r = f.GetReference()
    if r in cans: continue
    p = f.GetPosition(); x, y = mm(p.x), mm(p.y); face = 'B' if f.IsFlipped() else 'F'
    for c, (x0, y0, x1, y1) in cans.items():
        if x0 <= x <= x1 and y0 <= y <= y1:
            tab[c][(g_of.get(r, '?'), face)] += 1; inside_of[r] = c
for c in cans:
    print(c, [round(v, 2) for v in cans[c]], dict(sorted(tab[c].items())))
json.dump({'rects': cans, 'inside': inside_of}, open('human_cans.json', 'w'))
