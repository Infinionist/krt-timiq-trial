#!/usr/bin/env python3
"""human_reference.py : reference numbers of the HUMAN board for the plan v3 inputs (far passives, proximity rows at 2/3/5 mm, filter-regulator, keep_away). System python3.
Writes human_reference.json next to it. Standalone: exit 0 when written."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import designer_check as dc
H = '/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb'
pc, b = dc.load_board(H)
P = dc.parts_of(pc, b)
it = json.load(open(HERE + '/intent.json'))
out = {}
far, n, leds = dc.far_list(P, 10.0)
far_all = dc.far_list({k: dict(v, fp='') for k, v in P.items()}, 10.0)       # no LED exclusion
out['far'] = {'far_mm': 10.0, 'far_count': len(far), 'measured': n, 'led_resistors_left_out': leds, 'count_without_led_exclusion': len(far_all[0]), 'worst': far[:8]}
def pad_gap(a, b_, pa, pb):
    pads_a = [p for p in P[a]['pads'] if p[5] in pa] or P[a]['pads']
    pads_b = [p for p in P[b_]['pads'] if p[5] in pb] or P[b_]['pads']
    return min(dc.rect_gap(x[:4], y[:4]) for x in pads_a for y in pads_b)
pin, part = [], []
for r in it['proximity']:
    if r['ref'] not in P or r['near'] not in P:
        continue
    if r.get('pads'):
        pin.append(pad_gap(r['ref'], r['near'], r['pads'].get(r['ref'], []), r['pads'].get(r['near'], [])))
    else:
        part.append(pad_gap(r['ref'], r['near'], [], []))
def dist(v, lims):
    return {f'<= {l:g} mm': sum(1 for x in v if x <= l + 1e-9) for l in lims} | {'rows': len(v), 'median': round(sorted(v)[len(v)//2], 2), 'max': round(max(v), 1)}
out['proximity_pin_rows'] = dist(pin, (2.0, 3.0, 5.0))
out['proximity_part_rows'] = dist(part, (5.0, 10.0))
info = {}
rep = dc.Report.__new__(dc.Report); rep.rows = []; rep.infos = []
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    dc.info_filter_regulator(rep, P)
    ka = dc.keep_away_readings(P, HERE + '/fixed.design-brief.json')
out['filter_regulator'] = rep.infos[0][2]
out['keep_away'] = ka
json.dump(out, open(HERE + '/human_reference.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'keep_away'}, indent=1)[:2500])
for k in ka: print(k['index'], k['label'], k['min_mm'], k['inside'], k['by_group'])
