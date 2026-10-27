import sys, json
sys.path.insert(0,'/tmp/pcb-trials/timiq/v2/krt/py_placer'); import _path
from kicad_parser import parse_kicad_pcb
from placement import legality, shields as sh, heights as H
b = parse_kicad_pcb('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
parts = {g.ref: g for g in legality.graded_parts_from_file(b)}
d = json.load(open('work/intent_v2.json'))
for row in d['shields']:
    fp = b.footprints[row['can']]
    pose = (fp.x, fp.y, 0.0)
    rows = []
    for wall in (0.0, 0.5):
        inner, outer, _ring = sh.boxes_local(fp, wall)
        I = H.to_board(inner, pose)
        rows.append(I)
    print(row['can'], 'inner0', [round(v,2) for v in rows[0]], 'outer', [round(v,2) for v in H.to_board(outer,pose)])
    worst = []
    for r in row['members']:
        q = parts[r].rect
        ov0 = max(rows[0][0]-q[0], rows[0][1]-q[1], q[2]-rows[0][2], q[3]-rows[0][3])
        ov5 = max(rows[1][0]-q[0], rows[1][1]-q[1], q[2]-rows[1][2], q[3]-rows[1][3])
        # pad copper
        pr = [legality.pad_rect(p) for p in b.footprints[r].pads]
        px0 = min(x[0] for x in pr); py0 = min(x[1] for x in pr); px1 = max(x[2] for x in pr); py1 = max(x[3] for x in pr)
        pv0 = max(rows[0][0]-px0, rows[0][1]-py0, px1-rows[0][2], py1-rows[0][3])
        worst.append((ov5, ov0, pv0, r, parts[r].source))
    worst.sort(reverse=True)
    print('  members over wall0.5:', sum(1 for w in worst if w[0] > 1e-6), ' over wall0 (occupancy):', sum(1 for w in worst if w[1] > 1e-6), ' pad copper over inner0:', sum(1 for w in worst if w[2] > 1e-6))
    print('  worst', [(round(w[0],2), round(w[1],2), round(w[2],2), w[3]) for w in worst[:5]])
