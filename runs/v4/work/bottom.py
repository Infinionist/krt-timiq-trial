"""Bottom-side passive distance to the IC pin each serves (by script, from the netlist). Used by score_v4.py."""
import sys, re, math, statistics
sys.path.insert(0,'/tmp/pcb-trials/timiq/v4/work')
from common import *
LOCAL = 5
def served_pins(p):
    """{passive: [(ic, pad)]}: IC pins on the passive's non-GND nets, and through local nets (<=5 pads, no IC pin) of other passives, up to 3 hops."""
    nets = {}
    for r, f in p.footprints.items():
        for pd in f.pads:
            if pd.net_id: nets.setdefault(pd.net_id, []).append((r, str(pd.pad_number)))
    gnd = {n.net_id for n in p.nets.values() if n.name == 'GND'}
    ispas = lambda r: re.match(r'^[RCL]\d+$', r) is not None
    ic_on = {i: [(r, pn) for r, pn in pl if r.startswith('U')] for i, pl in nets.items()}
    pas_nets = {r: [pd.net_id for pd in f.pads if pd.net_id and pd.net_id not in gnd] for r, f in p.footprints.items() if ispas(r)}
    out = {}
    for r in pas_nets:
        pins, seen_n, seen_p = [], set(), {r}
        frontier = [(n, 0) for n in pas_nets[r]]
        while frontier:
            n, hop = frontier.pop()
            if n in seen_n: continue
            seen_n.add(n)
            if ic_on.get(n):
                pins += ic_on[n]
                continue
            if hop >= 3 or len(nets[n]) > LOCAL: continue
            for q, _ in nets[n]:
                if q in seen_p or q not in pas_nets: continue
                seen_p.add(q)
                frontier += [(m, hop + 1) for m in pas_nets[q]]
        out[r] = sorted(set(pins))
    return out
def metric(boardpath, served=None):
    p = parse_kicad_pcb(boardpath)
    served = served or served_pins(p)
    ds = {}
    for r, pins in served.items():
        f = p.footprints[r]
        if f.layer != 'B.Cu' or not pins: continue
        best = min(math.hypot(f.x - p.footprints[ic].x * 0 - next(pd.global_x for pd in p.footprints[ic].pads if str(pd.pad_number) == pn),
                              f.y - next(pd.global_y for pd in p.footprints[ic].pads if str(pd.pad_number) == pn)) for ic, pn in pins)
        ds[r] = best
    v = sorted(ds.values())
    return {'n_bottom_passives': len(v), 'median_mm': round(statistics.median(v), 2) if v else None,
            'gt10': sum(1 for x in v if x > 10), 'gt20': sum(1 for x in v if x > 20),
            'worst': sorted(ds.items(), key=lambda kv: -kv[1])[:8]}, ds
if __name__ == '__main__':
    for b in sys.argv[1:]:
        m, _ = metric(b); print(b, {k: v for k, v in m.items() if k != 'worst'}, [(r, round(d, 1)) for r, d in m['worst']])
