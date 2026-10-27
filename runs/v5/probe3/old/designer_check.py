#!/usr/bin/env python3
"""designer_check.py BOARD : the "designer check" of TimIQ plan v2, one PASS/FAIL line per check (a script decides, no model).
Exit 0 only if every check passes; 1 if any fails; 2 on a usage or tool error.

  assembly   check_assembly says buildable (with --baseline and --intent as the placement loop calls it; `--baseline none` for a
             board that is nobody's placement run, such as the human board). --waive A/B,... names pairs accepted as the only
             blocking items (the human board's C20/R16).
  floorplan  check_floorplan --intent: 0 errors
  members    every member of every can (cans.json: refs per face) sits on its face with its pad box inside the can zone (+ --zone-tol);
             no other part has its centre inside a can zone on the same face
  band       no top-side (F) part touches a wall-band keep-out of the brief (allow lists honoured)
  box        every can present (J7-J12) lies inside the box rectangle
  window     J7-J10 are at their cans_poses.json poses (option (d); mechanical.json for older runs) and each overlaps the lid window (fractions printed)
  holes      no part's pad box is closer to a hole centre than its keep-out radius (holes.json; the part's allow list honoured)
  far        passives more than --far-mm (10) pad-edge from the nearest IC pin they serve: count <= --max-far

usage: designer_check.py BOARD [--intent I] [--baseline B|none] [--waive A/B,..] [--cans C] [--holes H] [--brief BR] [--mech M] [--poses P]
                         [--max-far N] [--far-mm D] [--zone-tol T] [--json OUT]
Run with the system python3 (pcbnew); KRT's tools are called through its venv.
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KRT = '/tmp/pcb-trials/timiq/krt'
PY = KRT + '/.venv/bin/python'
# facts (FACTS 1, 6): box 120 x 120 at BOX1's origin; lid window
BOX = (124.2124, 94.9478, 244.2124, 214.9478)
WINDOW = (150.21, 148.95, 212.21, 190.95)
HUMAN_FAR = 36          # this script's own count on the human board (netlist-served pins, pad edge, all faces); plan v2 quoted 17 for bottom passives by centre distance


def load_board(path):
    import pcbnew
    fd = os.dup(2)
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
    try:
        b = pcbnew.LoadBoard(path)
    finally:
        os.dup2(fd, 2)
    return pcbnew, b


def parts_of(pcbnew, b):
    mm = pcbnew.ToMM
    out = {}
    for f in b.GetFootprints():
        ref = f.GetReference()
        pads = []
        for p in f.Pads():
            bb = p.GetBoundingBox()
            pads.append((mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom()), p.GetNetname(), p.GetNumber()))
        pos = f.GetPosition()
        box = None
        if pads:
            box = (min(p[0] for p in pads), min(p[1] for p in pads), max(p[2] for p in pads), max(p[3] for p in pads))
        out[ref] = {'face': 'B' if f.IsFlipped() else 'F', 'x': mm(pos.x), 'y': mm(pos.y), 'rot': f.GetOrientationDegrees(), 'pads': pads, 'box': box}
    return out


def inter_area(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def rect_gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def krt(args):
    r = subprocess.run([PY, '-X', 'utf8'] + args, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def summary(text):
    for line in text.splitlines():
        if line.startswith('JSON_SUMMARY:'):
            return json.loads(line[len('JSON_SUMMARY:'):])
    return None


class Report:
    def __init__(self):
        self.rows = []

    def add(self, name, ok, detail):
        self.rows.append((name, bool(ok), detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name:9s} {detail}")

    @property
    def ok(self):
        return all(r[1] for r in self.rows)


def check_assembly(rep, board, intent, baseline, waive):
    out = board + '.designer_ca.json'
    cmd = [KRT + '/py_tools/check_assembly.py', board, '--json', out]
    if intent:
        cmd += ['--intent', intent]
    if baseline and baseline != 'none':
        cmd += ['--baseline', baseline]
    rc, txt = krt(cmd)
    if not os.path.exists(out):
        print('designer_check: check_assembly produced no JSON:\n' + txt[-600:], file=sys.stderr)
        sys.exit(2)
    d = json.load(open(out))
    os.remove(out)
    pairs = {'/'.join(sorted((p['a'], p['b']))) for p in d.get('blocking_pairs', [])}
    other = {k: (len(d[k]) if isinstance(d.get(k), list) else d.get(k)) for k in
             ('courtyard_blocking_gating_pairs', 'courtyard_error_gating_pairs', 'silk_enclosed_gating_pairs', 'own_pad_gating_pairs',
              'locked_contact_pairs', 'coincident_origin_groups', 'graphic_pad_gating_pairs', 'testpoint_covered_gating_pairs')}
    other = {k: v for k, v in other.items() if v}
    other['containment_blocking'] = d.get('containment_blocking') or 0
    other['body_edge_band_gating'] = d.get('body_edge_band_gating') or 0
    other = {k: v for k, v in other.items() if v}
    waived = {'/'.join(sorted(w.split('/'))) for w in waive}
    if d.get('buildable'):
        rep.add('assembly', True, f"buildable (baseline {baseline or 'none'})")
    elif pairs and pairs <= waived and not other:
        rep.add('assembly', True, f"NOT buildable only on waived pair(s) {sorted(pairs)} (baseline {baseline or 'none'})")
    else:
        rep.add('assembly', False, f"NOT BUILDABLE: blocking {sorted(pairs)[:6]}{'...' if len(pairs) > 6 else ''} other gates {other} (baseline {baseline or 'none'})")


def check_floorplan(rep, board, intent):
    if not intent:
        rep.add('floorplan', False, 'no --intent given')
        return
    rc, txt = krt([KRT + '/py_tools/check_floorplan.py', board, '--intent', intent])
    s = summary(txt)
    if s is None:
        print('designer_check: check_floorplan gave no JSON_SUMMARY:\n' + txt[-600:], file=sys.stderr)
        sys.exit(2)
    n = s.get('errors')
    rep.add('floorplan', n == 0, f"{n} error(s) {s.get('violations_by_rule', {}) if n else ''}".strip())


def check_members(rep, parts, cans_file, tol):
    cans = json.load(open(cans_file))
    member_of = {}
    todo = []
    for can, c in cans.items():
        for face in ('F', 'B'):
            refs = c['refs'].get(face)
            if not isinstance(refs, list):
                todo.append(f'{can}/{face}')
                continue
            for r in refs:
                member_of[r] = (can, face)
    if todo:
        rep.add('members', False, f"member refs not declared (TODO): {', '.join(todo)}")
        return
    bad = []
    for r, (can, face) in member_of.items():
        p = parts.get(r)
        z = cans[can]['zone']
        if p is None:
            bad.append(f'{r}: not on the board')
        elif p['face'] != face:
            bad.append(f'{r}: on {p["face"]}, declared {face}')
        elif p['box'] is None or not (p['box'][0] >= z[0] - tol and p['box'][1] >= z[1] - tol and p['box'][2] <= z[2] + tol and p['box'][3] <= z[3] + tol):
            bad.append(f'{r}: outside {can} zone')
    intr = []
    for r, p in parts.items():
        if r in member_of or r in cans or r.startswith(('J7', 'J8', 'J9', 'J10', 'J11', 'J12')):
            continue
        for can, c in cans.items():
            z = c['zone']
            if z[0] <= p['x'] <= z[2] and z[1] <= p['y'] <= z[3] and p['face'] in ('F', 'B') and any(p['face'] == f and isinstance(c['refs'].get(f), list) for f in ('F', 'B')):
                intr.append(f'{r}@{p["face"]} in {can}')
    rep.add('members', not bad and not intr,
            f"{len(member_of) - len(bad)}/{len(member_of)} members in their can on their face; {len(intr)} intruder(s)"
            + (f"; e.g. {(bad + intr)[:4]}" if bad or intr else ''))


def check_band(rep, parts, brief):
    ko = [k for k in json.load(open(brief)).get('keepouts', []) if k.get('kind') == 'enclosure_wall_band']
    hits = []
    for r, p in parts.items():
        if p['face'] != 'F' or p['box'] is None:
            continue
        for k in ko:
            if r in (k.get('allow') or ()):
                continue
            if inter_area(p['box'], k['rect']) > 1e-6:
                hits.append(f"{r} in {k['name']}")
    rep.add('band', not hits, f"{len(hits)} top-side part(s) in the wall band" + (f": {hits[:6]}" if hits else ''))


def check_box(rep, parts):
    out = []
    n = 0
    for c in ('J7', 'J8', 'J9', 'J10', 'J11', 'J12'):
        p = parts.get(c)
        if not p or not p['box']:
            continue
        n += 1
        b = p['box']
        if not (b[0] >= BOX[0] and b[1] >= BOX[1] and b[2] <= BOX[2] and b[3] <= BOX[3]):
            out.append(c)
    rep.add('box', not out and n > 0, f"{n} can(s) checked, outside the box: {out}")


def check_window(rep, parts, mech, poses_file=None):
    m = {f['ref']: f for f in json.load(open(mech))['fixed']}
    if poses_file and os.path.exists(poses_file):      # option (d): the cans are not in mechanical.json, their poses are in cans_poses.json
        m.update({r: {'x': p['x'], 'y': p['y'], 'rot': p['rot']} for r, p in json.load(open(poses_file)).items()})
    bad, fr = [], {}
    for c in ('J7', 'J8', 'J9', 'J10'):
        p = parts.get(c)
        if p is None:
            bad.append(f'{c}: missing')
            continue
        f = m.get(c)
        if f and (abs(p['x'] - f['x']) > 0.01 or abs(p['y'] - f['y']) > 0.01 or abs(((p['rot'] - f['rot']) + 180) % 360 - 180) > 0.5 or p['face'] != 'F'):
            bad.append(f'{c}: moved off its mechanical.json pose')
        b = p['box']
        a = inter_area(b, WINDOW)
        fr[c] = round(a / ((b[2] - b[0]) * (b[3] - b[1])), 2)
        if a <= 0:
            bad.append(f'{c}: not under the window')
    rep.add('window', not bad, f"overlap fraction of each can with the window {fr}" + (f"; {bad}" if bad else ''))


def check_holes(rep, parts, holes_file):
    holes = json.load(open(holes_file))
    bad = []
    worst = None
    for h in holes:
        for r, p in parts.items():
            if r in h['allow'] or p['box'] is None:
                continue
            d = rect_gap((h['x'], h['y'], h['x'], h['y']), p['box'])
            slack = d - h['radius']
            if worst is None or slack < worst[0]:
                worst = (round(slack, 3), h['name'], r)
            if slack < -1e-6:
                bad.append(f"{r} {-slack:.2f} mm inside {h['name']}")
    rep.add('holes', not bad, f"{len(holes)} holes, {len(bad)} part(s) inside a keep-out circle; tightest slack {worst}" + (f"; {bad[:5]}" if bad else ''))


def served_pins(parts):
    """{passive: [(ic, pad index)]}: IC pins on the passive's non-GND nets, and through local nets (<= 5 pads, no IC pin) of other
    passives, up to 3 hops (same definition as the v4 bench)."""
    nets = {}
    for r, p in parts.items():
        for i, pad in enumerate(p['pads']):
            if pad[4]:
                nets.setdefault(pad[4], []).append((r, i))
    ispas = lambda r: re.match(r'^[RCL]\d+$', r) is not None
    pas_nets = {r: [pad[4] for pad in p['pads'] if pad[4] and pad[4] != 'GND'] for r, p in parts.items() if ispas(r)}
    ic_on = {n: [(r, i) for r, i in pl if r.startswith('U')] for n, pl in nets.items()}
    out = {}
    for r in pas_nets:
        pins, seen_n, seen_p = [], set(), {r}
        frontier = [(n, 0) for n in pas_nets[r]]
        while frontier:
            n, hop = frontier.pop()
            if n in seen_n:
                continue
            seen_n.add(n)
            if ic_on.get(n):
                pins += ic_on[n]
                continue
            if hop >= 3 or len(nets[n]) > 5:
                continue
            for q, _ in nets[n]:
                if q in seen_p or q not in pas_nets:
                    continue
                seen_p.add(q)
                frontier += [(m, hop + 1) for m in pas_nets[q]]
        out[r] = sorted(set(pins))
    return out


def check_far(rep, parts, far_mm, max_far):
    sv = served_pins(parts)
    far, n = [], 0
    for r, pins in sv.items():
        if not pins:
            continue
        n += 1
        d = min(rect_gap(parts[r]['box'], parts[ic]['pads'][i][:4]) for ic, i in pins)
        if d > far_mm:
            far.append((r, round(d, 1)))
    far.sort(key=lambda t: -t[1])
    rep.add('far', len(far) <= max_far, f"{len(far)} of {n} passives are > {far_mm:g} mm pad-edge from their IC pin (limit {max_far}); worst {far[:5]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board')
    ap.add_argument('--intent', default=HERE + '/intent.json')
    ap.add_argument('--baseline', default=HERE + '/fixed.kicad_pcb', help="board the run started from, or 'none'")
    ap.add_argument('--waive', default='', help='A/B,C/D : pairs accepted as the only blocking items')
    ap.add_argument('--cans', default=HERE + '/cans.json')
    ap.add_argument('--holes', default=HERE + '/holes.json')
    ap.add_argument('--brief', default=HERE + '/fixed.design-brief.json')
    ap.add_argument('--mech', default=HERE + '/mechanical.json')
    ap.add_argument('--poses', default=HERE + '/cans_poses.json', help='can poses (option (d)); overrides mechanical.json for J7-J12')
    ap.add_argument('--max-far', type=int, default=HUMAN_FAR)
    ap.add_argument('--far-mm', type=float, default=10.0)
    ap.add_argument('--zone-tol', type=float, default=0.5)
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    if not os.path.exists(a.board):
        print(f'designer_check: no such board {a.board}', file=sys.stderr)
        return 2
    for f in (a.cans, a.holes, a.brief, a.mech):
        if not os.path.exists(f):
            print(f'designer_check: missing {f}', file=sys.stderr)
            return 2
    pcbnew, b = load_board(a.board)
    parts = parts_of(pcbnew, b)
    rep = Report()
    print(f'designer_check {a.board}')
    check_assembly(rep, a.board, a.intent, a.baseline, [w for w in a.waive.split(',') if w])
    check_floorplan(rep, a.board, a.intent)
    check_members(rep, parts, a.cans, a.zone_tol)
    check_band(rep, parts, a.brief)
    check_box(rep, parts)
    check_window(rep, parts, a.mech, a.poses)
    check_holes(rep, parts, a.holes)
    check_far(rep, parts, a.far_mm, a.max_far)
    print('DESIGNER CHECK ' + ('PASS' if rep.ok else 'FAIL') + f"  ({sum(1 for r in rep.rows if r[1])}/{len(rep.rows)})")
    if a.json:
        json.dump([{'check': n, 'pass': o, 'detail': d} for n, o, d in rep.rows], open(a.json, 'w'), indent=1)
    return 0 if rep.ok else 1


if __name__ == '__main__':
    sys.exit(main())
