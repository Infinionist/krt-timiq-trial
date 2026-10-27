#!/usr/bin/env python3
"""calibrate_holes.py : per mounting hole, the circle keep-out radius = HOLE radius (drill / 2) + clearance. The clearance is measured from
the HOLE EDGE (Infinionist 10-26), not the pad edge: 3.5 mm unless the HUMAN board (check_floorplan's own keepout metric: the part's rect /
tht_rect against the circle) is closer, then the human's. Writes holes.json. Measures with concentric test circles from the hole edge
outward, one check_floorplan run on the human board. `radius_for` is the pure rule (tests/test_scripts.py)."""
import json, subprocess, sys, math
K = '/tmp/pcb-trials/timiq/krt'
HUMAN = '/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb'
H = json.load(open('/tmp/pcb-trials/timiq/v5/holes_human.json'))
# plan v4 fix 2: the fixed status LEDs D2-D8 are NOT allowed inside a hole circle (run v3: D2 stood inside hole-FIX5-1's 3.5 mm clearance in every seed). They count as
# human parts like any other, so the circle is cut back to where the human board has them (as for FIX7, J5-2 and BOX1-5).
FIXED = set(f['ref'] for f in json.load(open('/tmp/pcb-trials/timiq/run/mechanical.json'))['fixed'] if not f['ref'].startswith('D')) | {'J7', 'J8', 'J9', 'J10', 'J11', 'J12'}
STEP = 0.05
DEFAULT = 3.5
HUMAN_CY = '/tmp/pcb-trials/timiq/v5/t2/human_cy.kicad_pcb'


def human_with_courtyards():
    """plan v4 fix 2: the placing board carries courtyards for every footprint (add_courtyards.py, margin 0.25, plan v3 item 1) and KRT's keep-out reads the
    courtyard, so the human's clearance must be measured on the human board WITH the same courtyards, else D2 (a THT LED, no courtyard on the human board)
    reads further from the hole than it stands on the placing board."""
    import os
    os.makedirs(os.path.dirname(HUMAN_CY), exist_ok=True)
    r = subprocess.run([K + '/.venv/bin/python', '-X', 'utf8', K + '/py_router/copy_board.py', HUMAN, HUMAN_CY], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run([sys.executable, '/tmp/pcb-trials/timiq/v5/add_courtyards.py', HUMAN_CY, HUMAN_CY + '.tmp', '--margin', '0.25', '--skip', 'BOX1'], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    os.replace(HUMAN_CY + '.tmp', HUMAN_CY)
    return HUMAN_CY


def radius_for(drill, reach, default=DEFAULT, step=STEP):
    """keep-out radius from the hole centre. reach = smallest tested radius at which a non-allowed human part already hits (None: none).
    The clearance counts from the hole edge (drill / 2), never from the pad edge."""
    hole_r = drill / 2
    r0 = hole_r + default
    if reach is None:
        return round(r0, 3)
    return round(max(hole_r, min(r0, reach - step)), 3)


def run(keepouts, tag):
    it = {'schema': 1, 'kind': 'floorplan-intent', 'units': 'mm', 'min_reader': 15, 'keepouts': keepouts}
    p = f'/tmp/pcb-trials/timiq/v5/t2/cal_{tag}.json'
    json.dump(it, open(p, 'w'))
    r = subprocess.run([K + '/.venv/bin/python', '-X', 'utf8', K + '/py_tools/check_floorplan.py', human_with_courtyards(), '--intent', p, '--json', p + '.out'],
                       capture_output=True, text=True)
    d = json.load(open(p + '.out'))
    viol = [v for v in d.get('violations', []) if v.get('rule') == 'keepout']
    return viol


def hole_r(h):
    return h['drill'] / 2


def main():
    rows = []
    test = []
    for h in H:
        name = f"hole-{h['host']}-{h['pad'] or ('1' if h['y'] > 120 else '2')}"
        h['name'] = name
        n = int(DEFAULT / STEP) + 1
        for i in range(n + 1):
            rad = round(hole_r(h) + i * STEP, 3)
            test.append({'name': f'{name}@{rad}', 'circle': [h['x'], h['y'], rad], 'sides': ['F', 'B'], 'allow': [h['host']]})
    viol = run(test, 'all')
    hit = {}
    for v in viol:
        nm = v['measured']['keepout']; ref = v['ref']
        name, rad = nm.split('@'); rad = float(rad)
        hit.setdefault(name, {}).setdefault(ref, []).append(rad)
    out = []
    for h in H:
        name = h['name']; hr = hole_r(h)
        refs = hit.get(name, {})
        # fixed parts inside the circle are the plan's (allowed), the rest are the human's closest parts
        fixed_in = sorted(r for r in refs if r in FIXED)
        free = {r: min(v) for r, v in refs.items() if r not in FIXED}   # smallest tested radius that already hits = the part's reach
        rad = radius_for(h['drill'], min(free.values()) if free else None)
        nearest = min(free, key=free.get) if free else None
        clear = round(rad - hr, 3)
        out.append(dict(name=name, host=h['host'], x=h['x'], y=h['y'], drill=h['drill'], pad_d=h['pad_d'], hole_gap_human=h['gap_hole_edge'],
                        radius=rad, clearance_from_hole_edge=clear, default=DEFAULT, human_limited=clear < DEFAULT - 1e-9, nearest_human_part=nearest,
                        allow=sorted(set([h['host'], 'BOX1']) | set(fixed_in)) if h['host'] != 'BOX1' else sorted(set(['BOX1']) | set(fixed_in))))
    for o in out: print(o['name'], 'drill', o['drill'], 'r', o['radius'], 'clear(hole edge)', o['clearance_from_hole_edge'], 'limited' if o['human_limited'] else '', o['nearest_human_part'] or '', 'allow', o['allow'])
    json.dump(out, open('/tmp/pcb-trials/timiq/v5/holes.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
