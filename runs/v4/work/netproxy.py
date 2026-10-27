"""Pin-adjacent passives from the netlist, by script. Output: rows for intent proximity[] + a census.
 IC = U* refs. GND = net named GND. A passive is `direct` to IC X when one of its pads is on a non-GND net
 that touches exactly one IC pin (an X pin). A chain part is a passive on a small local net (no IC pin, <= 5 pads,
 not GND) shared with a part already in the chain: it is claimed against that neighbour (a shared net, so the
 placer prices it), and the chain's IC is its root."""
import sys, re, json
sys.path.insert(0,'/tmp/pcb-trials/timiq/v4/work')
from common import *
MAX_SHUNT, MAX_SERIES = 3.0, 5.0
LOCAL_NET_MAX_PADS = 5
def analyse(p, skip=()):
    nets = {}
    for r, f in p.footprints.items():
        for pd in f.pads:
            if pd.net_id: nets.setdefault(pd.net_id, []).append((r, str(pd.pad_number)))
    name = {n.net_id: n.name for n in p.nets.values()}
    gnd = {i for i, n in name.items() if n == 'GND'}
    isic = lambda r: r.startswith('U')
    ispass = lambda r: re.match(r'^[RCL]\d+$', r) is not None
    icpins = {i: [(r, pn) for r, pn in pl if isic(r)] for i, pl in nets.items()}
    pas = {}
    for r, f in p.footprints.items():
        if ispass(r) and r not in skip:
            pas[r] = [(str(pd.pad_number), pd.net_id) for pd in f.pads if pd.net_id]
    rows, census = [], {'direct': 0, 'chain': 0, 'bridge': [], 'shunt_cap_3mm': 0, 'series_5mm': 0}
    direct = {}      # P -> (ic, icpad, ppad, other_net)
    bridge = []
    for r, pl in pas.items():
        hits = []
        for pn, nid in pl:
            if nid in gnd: continue
            ip = icpins.get(nid, [])
            if len(ip) == 1: hits.append((ip[0][0], ip[0][1], pn, nid))
        if not hits: continue
        ics = {h[0] for h in hits}
        if len(ics) > 1:
            bridge.append(r); continue
        h = hits[0]
        direct[r] = h
    def kind(r, via_net_pad):
        # shunt cap: a C with its other pad on GND
        pl = pas[r]
        other = [nid for pn, nid in pl if pn != via_net_pad]
        return 'shunt' if r.startswith('C') and other and all(o in gnd for o in other) else 'series'
    out = []
    for r, (ic, icpad, ppad, nid) in sorted(direct.items()):
        k = kind(r, ppad)
        out.append({'ref': r, 'near': ic, 'max_mm': MAX_SHUNT if k == 'shunt' else MAX_SERIES, 'basis': 'pad_edge',
                    'pads': {r: [ppad], ic: [icpad]}, 'hop': 1, 'root': ic, 'kind': k,
                    'why': f'{r} sits on {name[nid]}, which touches exactly one IC pin ({ic}.{icpad}): '
                           f'{"decap/filter cap" if k=="shunt" else "series or pull part"} belongs at the pin'})
    # chains
    claimed = {o['ref']: o for o in out}
    frontier = list(claimed)
    for hop in (2, 3):
        new = []
        for pr in frontier:
            for pn, nid in pas[pr]:
                if nid in gnd or icpins.get(nid): continue
                if len(nets[nid]) > LOCAL_NET_MAX_PADS: continue
                if any(not (re.match(r'^[RCL]\d+$', rr) or rr.startswith('TP')) for rr, _ in nets[nid]): continue
                for q, qpn in nets[nid]:
                    if q == pr or q in claimed or q not in pas: continue
                    k = kind(q, qpn)
                    o = {'ref': q, 'near': pr, 'max_mm': MAX_SHUNT if k == 'shunt' else MAX_SERIES, 'basis': 'pad_edge',
                         'pads': {q: [qpn], pr: [pn]}, 'hop': hop, 'root': claimed[pr]['root'], 'kind': k,
                         'why': f'{q} is on the local net {name[nid]} shared with {pr}, hop {hop} of the chain to {claimed[pr]["root"]}'}
                    claimed[q] = o; new.append(q); out.append(o)
        frontier = new
    return out, bridge, name, gnd
if __name__ == '__main__':
    p = parse_kicad_pcb(HUMAN)
    out, bridge, name, gnd = analyse(p)
    from collections import Counter
    print(len(out), Counter((o['hop'], o['kind']) for o in out), 'bridge', len(bridge), bridge)
    json.dump(out, open('/tmp/pcb-trials/timiq/v4/work/proximity_raw.json', 'w'), indent=1)
    for o in out:
        if o['hop'] > 1: print(o['ref'], '->', o['near'], o['root'], o['kind'])
