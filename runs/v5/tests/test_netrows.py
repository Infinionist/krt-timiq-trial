#!/usr/bin/env python3
"""Tests of netrows.build on a hand-made 8-part board (run with KRT's venv python)."""
import sys
sys.path.insert(0, '/tmp/pcb-trials/timiq/v5')
import netrows as N

fails = []
def expect(n, c):
    print(('ok    ' if c else 'FAIL  ') + 'netrows: ' + n)
    if not c: fails.append(n)

class P:
    def __init__(s, ref, num, net): s.component_ref, s.pad_number, s.net_id = ref, num, net
class FP:
    def __init__(s, pads): s.pads = pads
class Net:
    def __init__(s, name): s.name = name

# nets: 1 GND, 2 sig1 (U1.3, R1.1), 3 mid (R1.2, R2.1), 4 sig2 (R2.2, U2.1), 5 +3V3 (many pads)
fps = {'U1': FP([P('U1', '3', 2), P('U1', '1', 1)]), 'U2': FP([P('U2', '1', 4)]),
       'R1': FP([P('R1', '1', 2), P('R1', '2', 3)]), 'R2': FP([P('R2', '1', 3), P('R2', '2', 4)]),
       'C1': FP([P('C1', '1', 5), P('C1', '2', 1)]), 'C2': FP([P('C2', '1', 2), P('C2', '2', 1)]),
       'R9': FP([P('R9', '1', 3), P('R9', '2', 1)])}
for i in range(15): fps[f'X{i}'] = FP([P(f'X{i}', '1', 5)])
class PCB: pass
pcb = PCB(); pcb.footprints = fps
pcb.nets = {1: Net('GND'), 2: Net('sig1'), 3: Net('mid'), 4: Net('sig2'), 5: Net('+3V3')}
groups = {'groups': [{'name': 'g', 'refs': list(fps)}]}
rows, cand = N.build(pcb, groups, [], set(), {'C1'})
by = {r['ref']: r for r in rows}
expect('R1 on U1 pin 3 gets a 3.0 mm pin row with both pad lists', by['R1']['near'] == 'U1' and by['R1']['max_mm'] == 3.0 and by['R1']['pads'] == {'R1': ['1'], 'U1': ['3']})
expect('R2 (on U2 pin 1) gets its own pin row, not a chain row', by['R2']['near'] == 'U2' and by['R2']['max_mm'] == 3.0)
expect('C2 shunt on a signal net: a pin row on U1', by['C2']['near'] == 'U1' and 'pads' in by['C2'])
expect('R9 hangs on the mid net only: a 5.0 mm row near a part, no pads', by['R9']['max_mm'] == 5.0 and 'pads' not in by['R9'] and by['R9']['near'] in ('R1', 'R2'))
expect('MUST FAIL: the decap C1 gets no row (soft, the decap term holds it)', 'C1' not in by)
rows2, _ = N.build(pcb, groups, [], {'R1'}, {'C1'})
expect('MUST FAIL: a datasheet-row part gets no netlist row', 'R1' not in {r['ref'] for r in rows2})
expect('ic_candidates lists the passives on the IC local nets', cand['U1'] == ['C2', 'R1'] and cand['U2'] == ['R2'])
print('NETROWS ' + ('FAILED: ' + ', '.join(fails) if fails else 'ALL HOLD'))
sys.exit(1 if fails else 0)
