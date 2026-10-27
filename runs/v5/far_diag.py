import sys, importlib.util
spec = importlib.util.spec_from_file_location('dc', '/tmp/pcb-trials/timiq/v5/designer_check.py'); dc = importlib.util.module_from_spec(spec); spec.loader.exec_module(dc)
def run(path):
    pcbnew, b = dc.load_board(path); parts = dc.parts_of(pcbnew, b); sv = dc.served_pins(parts)
    rows = {}
    for r, pins in sv.items():
        if not pins: continue
        d, ic, i = min((dc.rect_gap(parts[r]['box'], parts[ic]['pads'][i][:4]), ic, i) for ic, i in pins)
        nets = sorted({p[4] for p in parts[r]['pads'] if p[4]})
        rows[r] = (round(d, 1), ic, parts[ic]['pads'][i][4], sorted({q for q, _ in pins}), nets)
    return rows
a = run(sys.argv[1]); h = run(sys.argv[2])
far_a = {r for r, v in a.items() if v[0] > 10}; far_h = {r for r, v in h.items() if v[0] > 10}
print(f"far: run {len(far_a)}, human {len(far_h)}, both {len(far_a & far_h)}")
for tag, s in (('RUN ONLY', far_a - far_h), ('BOTH', far_a & far_h), ('HUMAN ONLY', far_h - far_a)):
    print(f"== {tag} ({len(s)})")
    for r in sorted(s, key=lambda r: -a[r][0]):
        d, ic, net, ics, nets = a[r]; print(f"  {r:6} run {d:6} human {h[r][0]:6}  nearest {ic} on {net}; ICs served {ics[:6]}; nets {nets}")
