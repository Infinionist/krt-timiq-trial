#!/usr/bin/env python3
"""table.py SCORE.json ... : the score table, one column per board."""
import json, sys
rows = [json.load(open(p)) for p in sys.argv[1:]]
def g(r, *k):
    for x in k:
        r = r.get(x) if isinstance(r, dict) else None
    return r
spec = [('members inside', lambda r: f"{g(r,'fence','totals','members_inside')}/{g(r,'fence','totals','members')}"),
 ('fences passing', lambda r: f"{g(r,'fence','totals','pass')}/{g(r,'fence','totals','fences')}"),
 ('foreign parts inside', lambda r: g(r,'fence','totals','foreign_inside')),
 ('ring violations', lambda r: g(r,'fence','totals','ring_violations')),
 ('fence-fence/board/hole fails', lambda r: sum((not b['fence_clearance']) + (not b['on_board']) for b in r['fence']['per_block'].values())),
 ('fabricable', lambda r: f"{sum(b['fabricable'] for b in r['fence']['per_block'].values())}/6"),
 ('floorplan errors', lambda r: g(r,'floorplan','errors')),
 ('overlap mm2 (floorplan)', lambda r: g(r,'floorplan','overlap_area')),
 ('assembly buildable', lambda r: g(r,'assembly','buildable')),
 ('HPWL mm (check_floorplan)', lambda r: g(r,'floorplan','hpwl')),
 ('wire mm / crossings (placer model)', lambda r: f"{g(r,'model','wire_mm')} / {g(r,'model','crossings')}"),
 ('signal nets crossing fences', lambda r: g(r,'fence','totals','nets_crossing_signal')),
 ('signal wall-crossing MST edges', lambda r: g(r,'fence','totals','wall_crossings_signal')),
 ('signal wall-crossing length mm', lambda r: g(r,'fence','totals','wall_crossing_signal_mm')),
 ('fence area outer total mm2', lambda r: g(r,'fence','totals','area_outer')),
 ('fence area inner total mm2', lambda r: g(r,'fence','totals','area_inner'))]
print(f"{'':36}" + ''.join(f"{r['label']:>16}" for r in rows))
for n, f in spec:
    print(f"{n:36}" + ''.join(f"{str(f(r)):>16}" for r in rows))
print('area outer per block: ' )
for b in ['J7','J8','J9','J10','J11','J12']:
    print(f"  {b:34}" + ''.join(f"{g(r,'fence','per_block',b,'area_outer'):>16}" for r in rows))
