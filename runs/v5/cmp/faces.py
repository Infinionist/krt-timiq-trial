import pcbnew, json, sys
R = json.load(open('/tmp/pcb-trials/timiq/v5/human_cans.json'))['rects']
for name, path in [('human', '/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb'), ('seed0', '/tmp/pcb-trials/timiq/v5/seeds/s0.kicad_pcb')]:
    b = pcbnew.LoadBoard(path); out = []
    for c, (x0, y0, x1, y1) in R.items():
        f = bk = ic = icb = 0
        for fp in b.GetFootprints():
            p = fp.GetPosition(); x, y = pcbnew.ToMM(p.x), pcbnew.ToMM(p.y); r = fp.GetReference()
            if r.startswith('J') or r.startswith('MK') or not (x0 <= x <= x1 and y0 <= y <= y1): continue
            on_b = fp.IsFlipped(); f += not on_b; bk += on_b
            if r.startswith('U'): ic += 1; icb += on_b
        out.append(f"{c} F{f}/B{bk} (U {ic}, U on B {icb})")
    print(name, '; '.join(out))
