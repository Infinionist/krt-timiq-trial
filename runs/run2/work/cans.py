#!/usr/bin/env python3
"""Shield-can helper for the TimIQ placement run (J7..J12, BMI-S-204-F fences).

WHY THIS EXISTS. KRT seats every part on the box its footprint occupies. A shield-can fence draws no courtyard, so
its box is its pad ring's bounding box (and its silk): a solid rectangle. place_simple therefore never puts a part
under a can (KRT's own README, "Shield cans": a can is solid today). A can only works if the circuit sits INSIDE
its wall. So during placement the six fences are NOT on the board; you choose where each can goes, write that down
in cans.json, and this script
  * declare : writes the wall keep-outs, the inner-area block and the overlap waivers for each can into your intent,
  * restore : puts the six fences back on a board at the poses in cans.json (before any routing or scoring),
  * check   : the pass/fail gate: every listed part inside its can, nothing on a wall, cans on the board.

cans.json (you write it; poses are the CAN CENTRE, rot in 0/90/180/270; "circuit" = refs or globs of the parts
that sit under that can, F-side parts only count -- the lid covers the front face):

  {"J7":  {"cx": 150.0, "cy": 120.0, "rot": 0, "circuit": ["<ref>", "<glob>", ...]},
   "J8":  {...}, ... "J12": {...}}

Subcommands (python3 -X utf8 cans.py <cmd> ...):
  geometry                              print the fence's outer box, wall width, inner box (local, rot 0)
  declare --cans cans.json --intent IN --out OUT --board BOARD   (BOARD = fixed.kicad_pcb; sets the overlap waivers)
  restore IN_BOARD OUT_BOARD --cans cans.json
  check BOARD --cans cans.json [--intent INTENT] [--strangers] [--json PATH]      exit 0 pass, 4 fail
  strip IN_BOARD OUT_BOARD --save FOOTPRINTS      (staging only: lifts J7..J12 out of a board)
"""
import argparse, fnmatch, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
KRT = os.environ.get('KRT_ROOT', '/tmp/pcb-trials/timiq/krt')
FOOTPRINTS = os.path.join(HERE, 'can_footprints.sexp')
CANS = ['J7', 'J8', 'J9', 'J10', 'J11', 'J12']
WALL = 1.0            # wall width = the fence's pad ring width (all 24 pads are 1.0 mm thick)
ROTS = (0, 90, 180, 270)
# Local (rot 0) geometry about the footprint origin (pad 1 centre). Filled by _local_geometry() and asserted
# against the footprints in can_footprints.sexp, so a changed fence cannot be used with stale numbers.
LOCAL_OUTER = (-1.65, -32.3, 31.15, 0.5)


# ----------------------------------------------------------------------------------------- s-expression text
def _footprint_span(text, ref):
    i = text.find('(property "Reference" "%s"' % ref)
    if i < 0:
        return None
    j = text.rfind('\n\t(footprint', 0, i) + 1
    d, k = 0, j
    while True:
        c = text[k]
        if c == '(':
            d += 1
        elif c == ')':
            d -= 1
            if d == 0:
                return j, k + 1
        k += 1


def _at_re():
    return re.compile(r'(\(footprint "[^"]*"\s*\n\t\t\(layer "[^"]*"\)\s*\n\t\t\(uuid "[^"]*"\)\s*\n\t\t)\(at [^)]*\)')


def _read_blocks():
    t = open(FOOTPRINTS, encoding='utf-8').read()
    out = {}
    for ref in CANS:
        sp = _footprint_span(t, ref)
        if sp is None:
            raise SystemExit(f'{FOOTPRINTS} lacks {ref}')
        out[ref] = t[sp[0]:sp[1]]
    return out


def _local_pads(block):
    pads = []
    for m in re.finditer(r'\(pad "([^"]+)" smd rect\s*\(at ([-\d.]+) ([-\d.]+)\)\s*\(size ([-\d.]+) ([-\d.]+)\)', block):
        n, x, y, w, h = m.group(1), *(float(v) for v in m.groups()[1:])
        pads.append((n, x, y, w, h))
    return pads


def local_geometry():
    """(outer, inner) boxes in the fence's local frame, from the saved footprints; asserts all six agree."""
    boxes = set()
    for ref, b in _read_blocks().items():
        pads = _local_pads(b)
        if len(pads) != 24:
            raise SystemExit(f'{ref}: expected 24 smd rect pads, found {len(pads)}')
        boxes.add((round(min(x - w / 2 for _, x, y, w, h in pads), 4), round(min(y - h / 2 for _, x, y, w, h in pads), 4),
                   round(max(x + w / 2 for _, x, y, w, h in pads), 4), round(max(y + h / 2 for _, x, y, w, h in pads), 4)))
    if len(boxes) != 1:
        raise SystemExit(f'the six fences do not share one pad box: {boxes}')
    o = boxes.pop()
    return o, (o[0] + WALL, o[1] + WALL, o[2] - WALL, o[3] - WALL)


def _xf(rot, ox, oy):
    c, s = {0: (1, 0), 90: (0, 1), 180: (-1, 0), 270: (0, -1)}[rot % 360]
    return lambda lx, ly: (ox + lx * c + ly * s, oy - lx * s + ly * c)


def _box(f, b):
    xs, ys = zip(f(b[0], b[1]), f(b[2], b[3]))
    return (min(xs), min(ys), max(xs), max(ys))


def can_boxes(spec):
    """{'origin': (x,y), 'outer': box, 'inner': box, 'walls': [4 boxes]} in board coordinates for one cans.json entry."""
    o, i = local_geometry()
    rot = int(spec['rot']) % 360
    if rot not in ROTS or float(spec['rot']) != rot:
        raise SystemExit(f'rot must be one of {ROTS}, got {spec["rot"]}')
    # centre of the outer box (local) maps to (cx, cy): solve the origin
    lcx, lcy = (o[0] + o[2]) / 2, (o[1] + o[3]) / 2
    ax, ay = _xf(rot, 0.0, 0.0)(lcx, lcy)
    ox, oy = spec['cx'] - ax, spec['cy'] - ay
    f = _xf(rot, ox, oy)
    walls_local = [(o[0], o[1], o[2], o[1] + WALL), (o[0], o[3] - WALL, o[2], o[3]),
                   (o[0], o[1] + WALL, o[0] + WALL, o[3] - WALL), (o[2] - WALL, o[1] + WALL, o[2], o[3] - WALL)]
    return {'origin': (round(ox, 4), round(oy, 4)), 'rot': rot, 'outer': _box(f, o), 'inner': _box(f, i),
            'walls': [_box(f, w) for w in walls_local]}


def load_cans(path):
    d = json.load(open(path, encoding='utf-8'))
    bad = [k for k in d if k not in CANS]
    if bad:
        raise SystemExit(f'cans.json: unknown can(s) {bad}; the cans are {CANS}')
    for k, v in d.items():
        for key in ('cx', 'cy', 'rot'):
            if key not in v:
                raise SystemExit(f'cans.json {k}: missing "{key}"')
    return d


# ----------------------------------------------------------------------------------------- subcommands
def cmd_geometry(a):
    o, i = local_geometry()
    print(f'fence (BMI-S-204-F), local frame, rot 0, origin = pad 1 centre, y down:')
    print(f'  outer pad-ring box  {o}   -> {o[2]-o[0]:.3f} x {o[3]-o[1]:.3f} mm')
    print(f'  wall width          {WALL} mm (the pad ring; the can wall sits on it, no part may touch it)')
    i = tuple(round(v, 3) for v in i)
    print(f'  inner (under lid)   {i}   -> {i[2]-i[0]:.3f} x {i[3]-i[1]:.3f} mm')
    print('  the lid covers the F face only; a B-side part under a can is not shielded by it.')
    print('  poses in cans.json are the can CENTRE (cx, cy), rot 0/90/180/270.')


def _globs(circuit, refs):
    out = []
    for g in circuit:
        hit = [r for r in refs if fnmatch.fnmatchcase(r, g)]
        if not hit:
            print(f'WARNING: circuit entry {g!r} matches no part on the board', file=sys.stderr)
        out += hit
    return sorted(set(out), key=lambda r: (re.sub(r'\d+', '', r), int(re.sub(r'\D', '', r) or 0)))


def _board_refs(board):
    t = open(board, encoding='utf-8').read()
    refs = {}
    for m in re.finditer(r'\n\t\(footprint "[^"]*"\s*\n\t\t\(layer "([^"]*)"\)', t):
        e = t.find('(property "Reference" "', m.end())
        r = re.match(r'\(property "Reference" "([^"]+)"', t[e:e + 80])
        if r:
            refs[r.group(1)] = m.group(1)
    return refs


def cmd_declare(a):
    cans = load_cans(a.cans)
    intent = json.load(open(a.intent, encoding='utf-8'))
    refs_side = _board_refs(a.board) if a.board else {}
    intent['keepouts'] = [k for k in intent.get('keepouts', []) if not str(k.get('name', '')).startswith('can-')]
    intent['blocks'] = [b for b in intent.get('blocks', []) if not str(b.get('name', '')).startswith('can:')]
    rows = []
    for ref, spec in sorted(cans.items(), key=lambda kv: CANS.index(kv[0])):
        g = can_boxes(spec)
        for n, w in enumerate(g['walls'], 1):
            intent['keepouts'].append({'name': f'can-{ref}-wall{n}', 'rect': [round(v, 4) for v in w], 'sides': ['F'], 'allow': ['BOX1', 'J*'],
                                       'why': f'wall of shield can {ref}: nothing sits on the fence wall'})
        circuit = spec.get('circuit') or []
        members = _globs(circuit, list(refs_side)) if refs_side else list(circuit)
        if refs_side:
            back = [r for r in members if refs_side.get(r) != 'F.Cu']
            if back:
                print(f'NOTE {ref}: {back} are B-side: the lid does not cover them, left out of the zone', file=sys.stderr)
            members = [r for r in members if refs_side.get(r) == 'F.Cu']
        if not members:
            print(f'NOTE {ref}: no F-side circuit listed: only the wall keep-outs are declared', file=sys.stderr)
            continue
        blk = {'name': f'can:{ref}', 'refs': members, 'zone': [round(v, 4) for v in g['inner']], 'side': 'F',
               'exclusive': False, 'tolerance_mm': 0.0,   # an exclusive zone clashes with BOX1, a frame the size of the board
               'why': f'under shield can {ref}: the circuit the lid covers, inside the wall'}
        intent['blocks'].append(blk)
        rows.append((ref, len(members)))
    # A restored board has parts under the lids. KRT's baseline gate (check_assembly/board_score/judge_seeds --baseline)
    # refuses a part that MOVED into another's closed silk body, and a fence's silk outline is such a body. Waive the
    # can-over-part pairs by name, for every F-side part except the declared mechanical ones (a can over an LED or a
    # connector stays an error). Pad clearance, pad shorts and hole clearance stay absolute (a waiver is about bodies).
    intent['overlap_waivers'] = [w for w in intent.get('overlap_waivers', []) if not str(w.get('why', '')).startswith('under a shield can:')]
    if refs_side:
        fixed = {f['ref'] for f in intent.get('fixed_poses', [])}
        under = sorted((r for r, sd in refs_side.items() if sd == 'F.Cu' and r not in fixed and r not in CANS),
                       key=lambda r: (re.sub(r'\d+', '', r), int(re.sub(r'\D', '', r) or 0)))
        for ref in sorted(cans):
            intent['overlap_waivers'] += [{'pair': [ref, r], 'why': 'under a shield can: a fence draws no courtyard; a part may sit under its lid'}
                                          for r in under]
    json.dump(intent, open(a.out, 'w', encoding='utf-8'), indent=2)
    print(f'declare: {len(cans)} can wall set(s) ({4*len(cans)} keep-outs), {len(intent["overlap_waivers"])} overlap waivers, blocks: ' + ', '.join(f'can:{r} ({n} parts)' for r, n in rows))


def cmd_restore(a):
    cans = load_cans(a.cans)
    missing = [c for c in CANS if c not in cans]
    if missing:
        raise SystemExit(f'cans.json lacks {missing}: all six cans must be placed')
    t = open(a.inp, encoding='utf-8').read()
    for c in CANS:
        if _footprint_span(t, c) is not None:
            raise SystemExit(f'{a.inp} already carries {c}: restore runs on a placement board without the fences')
    blocks = _read_blocks()
    add = []
    for c in CANS:
        g = can_boxes(cans[c])
        ox, oy = g['origin']
        rot = g['rot']
        b = blocks[c]
        new, n = _at_re().subn(lambda m: m.group(1) + f'(at {ox:g} {oy:g}' + (f' {rot:g}' if rot else '') + ')', b, count=1)
        if n != 1:
            raise SystemExit(f'{c}: cannot set the pose in the saved footprint')
        if rot:   # KiCad stores a pad's angle as the TOTAL angle, footprint rotation included
            new, npad = re.subn(r'(\(pad "[^"]+" smd rect\s*\(at [-\d.]+ [-\d.]+)\)', lambda m: m.group(1) + f' {rot:g})', new)
            if npad != 24:
                raise SystemExit(f'{c}: expected 24 pads to turn, found {npad}')
        add.append(new)
    end = t.rstrip().rfind(')')
    out = t[:end].rstrip('\n') + '\n' + '\n'.join(add) + '\n' + t[end:]
    open(a.out, 'w', encoding='utf-8').write(out)
    pro = os.path.splitext(a.inp)[0] + '.kicad_pro'
    if os.path.exists(pro):
        import shutil
        shutil.copyfile(pro, os.path.splitext(a.out)[0] + '.kicad_pro')
    print(f'restore: {a.out} = {a.inp} + {len(add)} fences at the poses in {a.cans}')


def cmd_strip(a):
    t = open(a.inp, encoding='utf-8').read()
    saved = []
    for c in CANS:
        sp = _footprint_span(t, c)
        if sp is None:
            raise SystemExit(f'{c} not on {a.inp}')
        b = t[sp[0]:sp[1]]
        b, n = _at_re().subn(lambda m: m.group(1) + '(at 0 0)', b, count=1)
        saved.append((sp, b))
    for sp, _ in sorted(saved, reverse=True):
        t = t[:sp[0]] + t[sp[1] + 1:]
    open(a.out, 'w', encoding='utf-8').write(t)
    if a.save:
        open(a.save, 'w', encoding='utf-8').write('\n'.join(b for _, b in saved) + '\n')
    pro = os.path.splitext(a.inp)[0] + '.kicad_pro'
    if os.path.exists(pro):
        import shutil
        shutil.copyfile(pro, os.path.splitext(a.out)[0] + '.kicad_pro')
    print(f'strip: removed {CANS} from {a.inp} -> {a.out}')


def _rect_hit(a, b, eps=1e-9):
    return min(a[2], b[2]) - max(a[0], b[0]) > eps and min(a[3], b[3]) - max(a[1], b[1]) > eps


def cmd_check(a):
    sys.path[:0] = [os.path.join(KRT, 'py_router'), os.path.join(KRT, 'py_placer')]
    from kicad_parser import parse_kicad_pcb
    from placement import legality
    cans = load_cans(a.cans)
    p = parse_kicad_pcb(a.board)
    gl = legality.graded_parts_from_file(p, a.board)
    graded = {g.ref: g for g in gl}
    containers = set(legality.container_refs(p, gl, a.board))   # BOX1: a frame the whole board sits inside
    problems = []
    bounds = p.board_info.board_bounds
    geo = {c: can_boxes(cans[c]) for c in CANS if c in cans}
    for c, g in geo.items():
        o = g['outer']
        if bounds and (o[0] < bounds[0] or o[1] < bounds[1] or o[2] > bounds[2] or o[3] > bounds[3]):
            problems.append(f'{c}: the can ({o[0]:.1f},{o[1]:.1f})-({o[2]:.1f},{o[3]:.1f}) leaves the board {tuple(bounds)}')
    for i, c in enumerate(CANS):
        for d in CANS[i + 1:]:
            if c in geo and d in geo and _rect_hit(geo[c]['outer'], geo[d]['outer']):
                problems.append(f'{c} and {d} overlap')
    if a.intent:
        it = json.load(open(a.intent, encoding='utf-8'))
        fixed = {f['ref'] for f in it.get('fixed_poses', [])}
        for k in it.get('keepouts', []):
            if k.get('circle') is None or str(k.get('name', '')).startswith('can-'):
                continue
            cx, cy, rad = k['circle']
            for c, g in geo.items():
                o = g['outer']
                dx, dy = max(o[0] - cx, 0, cx - o[2]), max(o[1] - cy, 0, cy - o[3])
                if math.hypot(dx, dy) < rad:
                    problems.append(f'{c} reaches into keep-out {k["name"]}')
        for c, g in geo.items():
            for ref in sorted(fixed):
                if ref in graded and ref not in containers and p.footprints[ref].layer == 'F.Cu' and _rect_hit(graded[ref].rect, g['outer']):
                    problems.append(f'{c} covers the declared part {ref}')
    refs_in = {c: _globs(cans[c].get('circuit') or [], list(p.footprints)) for c in geo}
    for c, g in geo.items():
        for ref, gp in graded.items():
            if ref in CANS or ref in containers or p.footprints[ref].layer != 'F.Cu':
                continue
            r = gp.rect
            if any(_rect_hit(r, w) for w in g['walls']):
                problems.append(f'{ref} sits on the wall of {c}')
        for ref in refs_in[c]:
            fp = p.footprints.get(ref)
            if fp is None or fp.layer != 'F.Cu':
                continue
            r = graded[ref].rect
            ib = g['inner']
            if not (r[0] >= ib[0] - 1e-6 and r[1] >= ib[1] - 1e-6 and r[2] <= ib[2] + 1e-6 and r[3] <= ib[3] + 1e-6):
                problems.append(f'{ref} is listed under {c} but its box is not inside the wall')
        if a.strangers:
            for ref, gp in graded.items():
                if ref in CANS or ref in containers or ref in refs_in[c] or p.footprints[ref].layer != 'F.Cu':
                    continue
                r = gp.rect
                ib = g['inner']
                if _rect_hit(r, ib):
                    problems.append(f'{ref} is under {c} but not listed in its circuit')
    res = {'board': a.board, 'cans': {c: {'circuit_n': len(refs_in[c]), 'inner': [round(v, 3) for v in geo[c]['inner']]} for c in geo},
           'problems': problems, 'pass': not problems}
    if a.json:
        json.dump(res, open(a.json, 'w'), indent=1)
    for pr in problems:
        print('FAIL:', pr)
    print(f'cans check: {"PASS" if not problems else "FAIL"} ({len(problems)} problem(s), {len(geo)} can(s))')
    return 0 if not problems else 4


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('geometry')
    d = sp.add_parser('declare'); d.add_argument('--cans', required=True); d.add_argument('--intent', required=True)
    d.add_argument('--out', required=True); d.add_argument('--board')
    r = sp.add_parser('restore'); r.add_argument('inp'); r.add_argument('out'); r.add_argument('--cans', required=True)
    c = sp.add_parser('check'); c.add_argument('board'); c.add_argument('--cans', required=True); c.add_argument('--json'); c.add_argument('--intent', help='also check the cans against the intent: hole keep-outs and declared parts')
    c.add_argument('--strangers', action='store_true', help='also fail for an unlisted F-side part under a lid')
    s = sp.add_parser('strip'); s.add_argument('inp'); s.add_argument('out'); s.add_argument('--save')
    a = ap.parse_args()
    rc = {'geometry': cmd_geometry, 'declare': cmd_declare, 'restore': cmd_restore, 'check': cmd_check, 'strip': cmd_strip}[a.cmd](a)
    sys.exit(rc or 0)


if __name__ == '__main__':
    main()
