#!/usr/bin/env python3
"""netrows.py BOARD GROUPS MECH DATASHEET_ROWS OUT : netlist proximity rows for the passives no datasheet row covers (TimIQ v5 step 2).

Run with KRT's venv python. For every passive (R, C, L, FB) that is NOT a decoupling cap (KRT's own `decap_view().decaps`: those are
soft, held by place_simple's decap term) and is not a member of a datasheet row/template:
  * it touches a LOCAL net (not GND, not a rail: net with <= LOCAL_MAX pads) that carries a pin of an anchor part
    (an IC `U*`, a transistor `Q*`, a connector `J*`, a diode `D*`): row {ref: P, near: ANCHOR, pads: {P: [..], ANCHOR: [..]}, max_mm: 2.0}
    (a part named at a pin: KRT skill default 2.0 mm). When two anchors qualify, the one in the passive's own sheet group wins, then the lowest ref.
  * else it shares a local net with a passive already placed by a row (<= MAX_HOPS hops): row {ref: P, near: Q, max_mm: 5.0}
    (a part named near a part: KRT skill default 5.0 mm).
Also records, per IC, the passives on its local nets (`ic_candidates`): gate.py accepts a written skip for an IC only when the list is empty,
and counts an IC as covered when one of them is claimed by a proximity row (to either end) or is a template member.
Writes OUT = {rows, ic_candidates, decaps, counts}."""
import json
import re
import sys

KRT = '/tmp/pcb-trials/timiq/krt'
for d in ('py_router', 'py_placer'):
    sys.path.insert(0, KRT + '/' + d)
from kicad_parser import parse_kicad_pcb  # noqa: E402
from placement.grouping import decap_view  # noqa: E402

LOCAL_MAX = 12
MAX_HOPS = 3
PIN_MM = 3.0       # plan v3 item 5: 3.0 mm for a part named at a pin (was the skill default 2.0); part rows stay 5.0
PART_MM = 5.0
PASSIVE = re.compile(r'^(R|C|L|FB)\d+$')
ANCHOR = re.compile(r'^(U|Q|J|D)\d+$')


def num(s):
    return int(re.sub(r'\D', '', s) or 0)


def build(pcb, groups, mech_refs, ds_refs, decaps):
    """pure on its inputs: returns (rows, ic_candidates)."""
    grp = {r: g['name'] for g in groups['groups'] for r in g['refs']}
    nets = {}
    for ref, fp in pcb.footprints.items():
        for p in fp.pads:
            if p.net_id > 0:
                nets.setdefault(p.net_id, {}).setdefault(ref, []).append(str(p.pad_number))
    names = {nid: n.name for nid, n in pcb.nets.items()}
    local = {nid: parts for nid, parts in nets.items()
             if names.get(nid) not in (None, '', 'GND') and sum(len(v) for v in parts.values()) <= LOCAL_MAX}
    skip = set(decaps) | set(ds_refs) | set(mech_refs)
    passives = sorted((r for r in pcb.footprints if PASSIVE.match(r) and r not in skip), key=lambda s: (s[0], num(s)))
    cand = {r: set() for r in pcb.footprints if re.match(r'^U\d+$', r)}
    for nid, parts in local.items():
        for a in parts:
            if a in cand:
                cand[a] |= {p for p in parts if PASSIVE.match(p)}
    rows, placed = [], {}
    for pr in passives:
        opts = [(a, nid, parts[pr], apads) for nid, parts in local.items() if pr in parts
                for a, apads in parts.items() if ANCHOR.match(a)]
        if not opts:
            continue
        a = sorted({o[0] for o in opts}, key=lambda x: (grp.get(x) != grp.get(pr), x.startswith('J'), num(x), x))[0]
        ppads = sorted({pd for o in opts if o[0] == a for pd in o[2]}, key=lambda s: (len(s), s))
        apads = sorted({pd for o in opts if o[0] == a for pd in o[3]}, key=lambda s: (len(s), s))
        placed[pr] = 0
        rows.append({'ref': pr, 'near': a, 'pads': {pr: ppads, a: apads}, 'max_mm': PIN_MM, 'basis': 'pad_edge',
                     'why': f'netlist: {pr} pad {",".join(ppads)} on the net of {a} pin {",".join(apads)} (plan v3: {PIN_MM:g} mm for a part named at a pin)',
                     'source_kind': 'netlist_pin'})
    for hop in range(1, MAX_HOPS + 1):
        new = []
        for pr in passives:
            if pr in placed:
                continue
            opts = [q for nid, parts in local.items() if pr in parts for q in parts if q != pr and placed.get(q) == hop - 1]
            if opts:
                new.append((pr, sorted(opts, key=lambda x: (grp.get(x) != grp.get(pr), num(x), x))[0]))
        for pr, q in new:
            placed[pr] = hop
            rows.append({'ref': pr, 'near': q, 'max_mm': PART_MM, 'basis': 'pad_edge',
                         'why': f'netlist: {pr} shares a local net with {q} ({hop} hop(s) from an anchor pin; KRT skill default {PART_MM:g} mm for a part named near a part)',
                         'source_kind': 'netlist_part'})
    return rows, {k: sorted(v, key=lambda x: (x[0], num(x))) for k, v in sorted(cand.items(), key=lambda kv: num(kv[0]))}


def main(argv):
    board, groups, mech, ds, out = argv[1:6]
    pcb = parse_kicad_pcb(board)
    groups = json.load(open(groups))
    mech_refs = [f['ref'] for f in json.load(open(mech))['fixed']]
    dsj = json.load(open(ds))
    dec = decap_view(pcb).decaps()
    rows, cand = build(pcb, groups, mech_refs, {r['ref'] for r in dsj['rows']}, dec)
    res = {'rows': rows, 'ic_candidates': cand, 'decaps': sorted(dec),
           'counts': {'netlist_pin': sum(1 for r in rows if r['source_kind'] == 'netlist_pin'),
                      'netlist_part': sum(1 for r in rows if r['source_kind'] == 'netlist_part'), 'decaps_soft': len(dec)}}
    json.dump(res, open(out, 'w'), indent=1)
    print(res['counts'], 'ICs with 0 passive candidates:', [k for k, v in cand.items() if not v])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
