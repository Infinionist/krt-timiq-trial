import sys, collections
sys.path[:0]=['/tmp/pcb-trials/timiq/krt/py_router']
from kicad_parser import parse_kicad_pcb
p=parse_kicad_pcb('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
print(p.board_info.board_bounds)
by=collections.defaultdict(list)
for r,fp in p.footprints.items():
    by[(fp.footprint_name or '').split(':')[-1]].append(r)
for n,rs in sorted(by.items(), key=lambda kv:-len(kv[1])):
    print(len(rs), n, sorted(rs)[:8])
