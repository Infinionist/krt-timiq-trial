"""Sketches for the PMA2-43LN+ rf front ends, from the datasheet's Fig 1 (application circuit; the datasheet has no layout figure, so no
coordinates exist to copy): RF-IN pin 2 -> C1 DC block in series, L1 bias choke pin 2 -> bias node pin 1, C3 shunt at the bias node, R1 from the
bias node to Rb/C5; RF-OUT pin 7 -> C2 DC block in series, L2 choke from pin 7 to C4 shunt / R2 (0R) to VDD. Pads matched by net."""
import json, collections
ctx = json.load(open('/tmp/pcb-trials/timiq/v6/ctx.json'))
N = {}
for p in ctx['parts']:
    d = collections.defaultdict(list)
    for pads in p['pads_by_face'].values():
        for pd in pads: d[pd['net']].append(pd['pad'])
    N[p['ref']] = d
def pad(r, other):     # r's pad on the net shared with `other`
    return [pp for n, ps in N[r].items() for pp in ps if n in N[other] and n not in ('GND', '')]
def mk(U, c1, l1, c3, r1, c2, l2, c4, r2):
    m = lambda ref, partners, side, note, rot=None, reach=None: dict(
        {'ref': ref, 'pads': dict({ref: sorted({x for q in partners for x in pad(ref, q)})}, **{q: pad(q, ref) for q in partners}), 'side': side, 'note': note},
        **({'rot': rot} if rot is not None else {}), **({'reach': reach} if reach else {}))
    return {'anchor': U, 'kind': 'rf front end', 'source': 'Mini-Circuits PMA2-43LN+ datasheet, p4 Fig 1 Application and Characterization Circuit (no layout figure)',
            'members': [m(c1, [U], '+y', 'C1 DC block in series at RF-IN pin 2'),
                        m(l1, [U], '+y', 'L1 bias choke from RF-IN pin 2 to BIAS pin 1'),
                        m(c3, [U, l1], '+y', 'C3 shunt at the bias node (pin 1)'),
                        m(r1, [c3], '+y', 'R1 49.9R from the bias node toward Rb', reach=5),
                        m(c2, [U], '-y', 'C2 DC block in series at RF-OUT pin 7'),
                        m(l2, [U], '-y', 'L2 choke from RF-OUT pin 7 to the supply node'),
                        m(c4, [l2], '-y', 'C4 shunt at the choke supply node'),
                        m(r2, [l2], '-y', 'R2 0R from the choke node to VDD', reach=5)]}
s1 = mk('U21', 'C98', 'L8', 'C101', 'R103', 'C108', 'L10', 'C105', 'R106')
s2 = mk('U22', 'C99', 'L9', 'C103', 'R105', 'C109', 'L11', 'C107', 'R107')
for s, f in ((s1, 'sk_U21.json'), (s2, 'sk_U22.json')):
    json.dump(s, open('/tmp/pcb-trials/timiq/v6/' + f, 'w'), indent=1)
    for m_ in s['members']: print(s['anchor'], m_['ref'], m_['pads'])
