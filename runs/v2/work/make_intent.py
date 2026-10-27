"""v2 intent = run 1's intent_run.json + shields[] (human membership, F face only) [+ heights rows]."""
import sys, json
sys.path.insert(0,'/tmp/pcb-trials/timiq/v2/krt/py_placer'); import _path
from kicad_parser import parse_kicad_pcb
out = sys.argv[1]; under = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
b = parse_kicad_pcb('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
m = json.load(open('/tmp/pcb-trials/timiq/v2/human_members.json'))
d = json.load(open('/tmp/pcb-trials/timiq/run/intent_run.json'))
d['min_reader'] = max(d.get('min_reader', 0), 16)
rows = []
for can, refs in m.items():
    rows.append({'can': can, 'underside_mm': under, 'wall_clearance_mm': 0.2,
                 'members': [r for r in refs if b.footprints[r].layer == 'F.Cu'],
                 'source': 'experiment: members = the F-face parts inside the human board\'s can (membership taken from the human map); lid height assumed'})
d['shields'] = rows
json.dump(d, open(out, 'w'), indent=1)
print(sum(len(r['members']) for r in rows), 'members in', len(rows), 'cans')
