#!/usr/bin/env python3
"""fence.py: draw and check a custom shield fence round each shielded block of a PLACED board (variant 3).

The circuit is placed first; a sheet-metal fence is drawn round a block afterwards. This script is the "afterwards":
from the placed board and the block list it computes each fence outline and gates the result.

    fence.py BOARD --blocks BLOCKS.json [--intent INTENT.json] [--json OUT.json] [--emit-gr OUT.kicad_pcb]
             [--wall 1.0] [--inner-clear 0.5] [--outer-clear 0.5] [--min-seg 3.0] [--ignore REF ...]

BLOCKS.json: {"<name>": {"members": ["C1", "U1", ...]}, ...}.  A run2_work/membership.json style entry
({"inside_F": [...]}) is read too. A block whose name is a footprint on the board (a can J7 standing in for the
fence on the human board) has that footprint ignored: it is the stand-in, not a foreign part.

GEOMETRY (all assumptions are flags; defaults in brackets):
  wall         [1.0 mm]  the fence's wall/pad-ring width. Taken from the human board's J7-J12 frames (24 pads, all 1.0 mm).
  inner-clear  [0.5 mm]  member body edge to the wall's inner edge.
  outer-clear  [0.5 mm]  wall's outer edge to any foreign part (and to another fence's wall).
  min-seg      [3.0 mm]  every straight segment of the outline is at least this long (sheet-metal flange / etch practice;
                         an ASSUMPTION, "about 3 mm" in the brief).
  The outline drawn is the wall CENTRE LINE. It is the bounding box of the members inflated by inner-clear + wall/2,
  with up to four rectangular notches carved from its corners wherever a notch >= min-seg x min-seg holds no member
  (so an L, a stepped or a Z shape hugs the block); no notch leaves a segment shorter than min-seg. Side notches (U
  shapes) are not carved.

CHECKS (per fence, exit 4 if any fails):
  members_inside   every member's F-face box lies inside the wall's inner edge
  ring_clear       no foreign part's F-face box touches the wall band or the outer-clear band
  no_foreign_inside  no non-member part's F-face box intersects the enclosed area
  fabricable       one simple rectilinear polygon, no holes, every segment >= min-seg
  fence_clearance  the fence is clear of every other fence's wall + clearance
  on_board         the fence's outer edge is inside the board bounds and clear of every hole keep-out of the intent
  A part is on the F face when it sits on F.Cu, or is through-hole (its drilled-pad box). B-face SMD parts are
  not under the lid; they are listed (b_under) but never fail a fence.
REPORT: nets crossing each fence (a net with a pad on a member and a pad on a non-member): signal / power / ground.

Exit 0 pass, 4 a check failed, 2 usage or unreadable input.
"""
import argparse, json, math, os, re, sys
from dataclasses import dataclass, field

KRT = os.environ.get('KRT_ROOT', '/tmp/pcb-trials/timiq/krt')
EPS = 1e-6
AREA_EPS = 1e-4          # mm2: touching edges are not an overlap


# ----------------------------------------------------------------------------------------------- board model
@dataclass
class Part:
    ref: str
    side: str                       # 'F' / 'B'
    rect: tuple                     # own-side box (x0, y0, x1, y1)
    tht_rect: tuple = None
    has_tht: bool = False
    nets: set = field(default_factory=set)
    pads: list = field(default_factory=list)      # (net, x, y) of every netted pad

    def front_rect(self):
        """The box the part presents on the F face, or None (a B-face SMD part)."""
        if self.side == 'F':
            return self.rect
        return self.tht_rect if self.has_tht else None


@dataclass
class Board:
    parts: dict
    bounds: tuple = None
    containers: set = field(default_factory=set)
    holes: list = field(default_factory=list)      # (name, cx, cy, r)


def load_board(path, intent=None):
    sys.path[:0] = [os.path.join(KRT, 'py_router'), os.path.join(KRT, 'py_placer')]
    from kicad_parser import parse_kicad_pcb
    from placement import legality
    p = parse_kicad_pcb(path)
    gl = legality.graded_parts_from_file(p, path)
    parts = {}
    for g in gl:
        fp = p.footprints[g.ref]
        nets = {pd.net_name for pd in fp.pads if pd.net_name}
        pads = [(pd.net_name, pd.global_x, pd.global_y) for pd in fp.pads if pd.net_name]
        parts[g.ref] = Part(g.ref, g.side, tuple(g.rect), tuple(g.tht_rect) if g.tht_rect else None, g.has_tht, nets, pads)
    b = Board(parts, tuple(p.board_info.board_bounds) if p.board_info.board_bounds else None,
              set(legality.container_refs(p, gl, path)))
    if intent:
        for k in json.load(open(intent, encoding='utf-8')).get('keepouts', []):
            if k.get('circle'):
                cx, cy, r = k['circle']
                b.holes.append((k.get('name', 'keepout'), cx, cy, r))
    return b


# ----------------------------------------------------------------------------------------------- geometry
def _shapely():
    global box, Polygon, MultiPolygon, Point, unary_union
    from shapely.geometry import box, Polygon, MultiPolygon, Point   # noqa: F401
    from shapely.ops import unary_union                               # noqa: F401


def _norm(poly, nd=4):
    """Round to 0.1 um and drop collinear vertices."""
    from shapely import set_precision
    q = set_precision(poly, 10 ** -nd)
    return q.simplify(0)


def fabricable(poly, min_seg, tol=1e-3):
    """(ok, [reasons]) for a fence outline: one simple rectilinear polygon, no holes, every segment >= min_seg."""
    why = []
    if poly.geom_type != 'Polygon':
        return False, [f'not one polygon ({poly.geom_type})']
    if not poly.is_valid:
        why.append('self-intersecting')
    if poly.interiors:
        why.append(f'{len(list(poly.interiors))} hole(s)')
    pts = list(poly.simplify(0).exterior.coords)[:-1]
    n = len(pts)
    short = []
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        if abs(dx) > tol and abs(dy) > tol:
            why.append(f'diagonal segment ({x0:.3f},{y0:.3f})-({x1:.3f},{y1:.3f})')
        ln = math.hypot(dx, dy)
        if ln < min_seg - tol:
            short.append(round(ln, 3))
    if short:
        why.append(f'{len(short)} segment(s) shorter than {min_seg} mm: {short}')
    return not why, why


def _corner_candidates(poly_bounds, rects, corner, L):
    """Maximal empty rectangles anchored at one corner of the bounding box: (w, h) pairs, each leaving at least L of the
    two box sides they start on."""
    X0, Y0, X1, Y1 = poly_bounds
    W, H = X1 - X0, Y1 - Y0
    cx, cy, sx, sy = corner
    xs = {W - L}
    for r in rects:
        for x in (r[0], r[2]):
            d = (x - cx) * sx
            if L - EPS <= d <= W - L + EPS:
                xs.add(d)
    out = []
    for w in sorted(xs):
        if w < L - EPS or w > W - L + EPS:
            continue
        xa, xb = sorted((cx, cx + sx * w))
        hmax = H - L
        for r in rects:
            if min(xb, r[2]) - max(xa, r[0]) <= EPS:
                continue
            dy = (r[1] - cy) if sy > 0 else (cy - r[3])
            hmax = min(hmax, dy)
        if hmax >= L - EPS:
            out.append((w, hmax))
    return out


def centre_line(member_rects, inner_clear, wall, min_seg, carve=True):
    """The wall centre line round the members (a shapely Polygon) and the notches carved from the bounding box."""
    _shapely()
    d = inner_clear + wall / 2.0
    rects = [(r[0] - d, r[1] - d, r[2] + d, r[3] + d) for r in member_rects]
    X0 = min(r[0] for r in rects); Y0 = min(r[1] for r in rects)
    X1 = max(r[2] for r in rects); Y1 = max(r[3] for r in rects)
    poly = box(X0, Y0, X1, Y1)
    cuts = []
    if not carve:
        return poly, cuts
    corners = [(X0, Y0, 1, 1), (X1, Y0, -1, 1), (X0, Y1, 1, -1), (X1, Y1, -1, -1)]
    used = set()
    for _ in range(4):
        best = None
        for ci, c in enumerate(corners):
            if ci in used:
                continue
            for w, h in _corner_candidates((X0, Y0, X1, Y1), rects, c, min_seg):
                xa, xb = sorted((c[0], c[0] + c[2] * w))
                for hh in sorted({h, *[min_seg * k for k in range(1, 60) if min_seg * k < h]}, reverse=True):
                    if hh < min_seg - EPS:
                        continue
                    ya, yb = sorted((c[1], c[1] + c[3] * hh))
                    cut = box(xa, ya, xb, yb)
                    newp = _norm(poly.difference(cut))
                    ok, _ = fabricable(newp, min_seg)
                    if ok:
                        if best is None or cut.area > best[0]:
                            best = (cut.area, ci, cut, newp)
                        break          # the largest valid height for this width
        if best is None:
            break
        _, ci, cut, poly = best
        used.add(ci)
        cuts.append(cut.bounds)
    return poly, cuts


def rings(centre, wall, outer_clear):
    inner = centre.buffer(-wall / 2.0, join_style=2)
    outer = centre.buffer(wall / 2.0, join_style=2)
    clear = centre.buffer(wall / 2.0 + outer_clear, join_style=2)
    return inner, outer, clear


def _area(a, b):
    return a.intersection(b).area


def net_kind(name):
    leaf = (name or '').split('/')[-1].lower()
    if re.match(r'^(a|d|p)?gnd|^vss', leaf):
        return 'ground'
    if re.match(r'^(a?gnd|dgnd|pgnd|vcc|vdd|vss|vee|vbus|vin|vout|vref|pwr|\+|-|\d)', leaf):
        return 'power'
    return 'signal'


def mst_crossings(pts_in, pts_out):
    """Prim's minimum spanning tree over one net's pads (Euclidean); (crossing edges, their total length in mm), where a
    crossing edge joins a member pad to a non-member pad. An airwire estimate of the wires that must cross the wall."""
    pts = [(x, y, True) for x, y in pts_in] + [(x, y, False) for x, y in pts_out]
    n = len(pts)
    if n < 2 or not pts_in or not pts_out:
        return 0, 0.0
    best = [math.inf] * n
    frm = [-1] * n
    done = [False] * n
    best[0] = 0.0
    cross, length = 0, 0.0
    for _ in range(n):
        u = min((i for i in range(n) if not done[i]), key=lambda i: best[i])
        done[u] = True
        if frm[u] >= 0 and pts[u][2] != pts[frm[u]][2]:
            cross += 1
            length += best[u]
        for v in range(n):
            if not done[v]:
                d = math.hypot(pts[u][0] - pts[v][0], pts[u][1] - pts[v][1])
                if d < best[v]:
                    best[v], frm[v] = d, u
    return cross, length


# ----------------------------------------------------------------------------------------------- the check
def check_fences(board, blocks, wall=1.0, inner_clear=0.5, outer_clear=0.5, min_seg=3.0, ignore=(), carve=True, centres=None):
    """blocks {name: [member refs]} -> report dict. Pure function of the model (the tests call it directly).
    `centres` {name: shapely Polygon}: check these hand-drawn wall centre lines instead of computing them."""
    _shapely()
    parts = board.parts
    skip = set(ignore) | set(board.containers) | {n for n in blocks if n in parts}
    rep = {'params': dict(wall=wall, inner_clear=inner_clear, outer_clear=outer_clear, min_seg=min_seg, carve=carve),
           'fences': {}, 'problems': []}
    geo = {}
    for name, refs in blocks.items():
        missing = [r for r in refs if r not in parts]
        mem = [r for r in refs if r in parts]
        front = {r: parts[r].front_rect() for r in mem}
        mrects = [v for v in front.values() if v]
        back_members = [r for r in mem if not front[r]]
        if not mrects:
            rep['problems'].append(f'{name}: no member has an F-face box')
            continue
        if centres and name in centres:
            centre, cuts = centres[name], []
        else:
            centre, cuts = centre_line(mrects, inner_clear, wall, min_seg, carve)
        inner, outer, clear = rings(centre, wall, outer_clear)
        geo[name] = dict(centre=centre, inner=inner, outer=outer, clear=clear, members=set(mem))
        rep['fences'][name] = dict(n_members=len(refs), missing=missing, back_members=back_members, cuts=[list(map(lambda v: round(v, 3), c)) for c in cuts],
                                   centre=[[round(x, 3), round(y, 3)] for x, y in list(centre.simplify(0).exterior.coords)[:-1]],
                                   area_inner=round(inner.area, 2), area_outer=round(outer.area, 2), area_clear=round(clear.area, 2),
                                   bbox_area_outer=round(box(*outer.bounds).area, 2))
    for name, g in geo.items():
        f = rep['fences'][name]
        # fabricable
        ok, why = fabricable(g['centre'], min_seg)
        f['fabricable'] = {'ok': ok, 'why': why}
        # members inside (their F-face box inside the inner edge)
        out_m = []
        for r in sorted(g['members']):
            fr = parts[r].front_rect()
            if fr and box(*fr).difference(g['inner']).area > AREA_EPS:
                out_m.append(r)
        f['members_inside'] = {'ok': not out_m, 'inside': len(g['members']) - len(out_m) - len(f['back_members']) - len(f['missing']),
                               'of': len(g['members']) - len(f['back_members']), 'outside': out_m}
        # foreign parts
        inside, ring, b_under = [], [], []
        for r, pt in parts.items():
            if r in g['members'] or r in skip:
                continue
            fr = pt.front_rect()
            if fr is None:
                if box(*pt.rect).intersects(g['inner']) and _area(box(*pt.rect), g['inner']) > AREA_EPS:
                    b_under.append(r)
                continue
            bx = box(*fr)
            if _area(bx, g['inner']) > AREA_EPS:
                inside.append(r)
            elif _area(bx, g['clear']) > AREA_EPS:
                ring.append(r)
        f['no_foreign_inside'] = {'ok': not inside, 'foreign': sorted(inside)}
        f['ring_clear'] = {'ok': not ring, 'in_ring': sorted(ring)}
        f['b_under'] = sorted(b_under)
        # other fences
        clash = sorted(o for o, h in geo.items() if o != name and _area(g['outer'], h['clear']) > AREA_EPS)
        f['fence_clearance'] = {'ok': not clash, 'clashes': clash}
        # board and holes
        why = []
        if board.bounds:
            bx0, by0, bx1, by1 = board.bounds
            ox0, oy0, ox1, oy1 = g['outer'].bounds
            if ox0 < bx0 - EPS or oy0 < by0 - EPS or ox1 > bx1 + EPS or oy1 > by1 + EPS:
                why.append('outside the board bounds')
        for hn, cx, cy, rad in board.holes:
            if g['outer'].distance(Point(cx, cy)) < rad - EPS:
                why.append(f'reaches hole keep-out {hn}')
        f['on_board'] = {'ok': not why, 'why': why}
        # nets crossing
        nets_in = set().union(*[parts[r].nets for r in g['members']])
        nets_out = set().union(*[p.nets for r, p in parts.items() if r not in g['members'] and r not in skip])
        cross = sorted(nets_in & nets_out)
        kinds = {'signal': [], 'power': [], 'ground': []}
        for n in cross:
            kinds[net_kind(n)].append(n)
        wc = {'signal': [0, 0.0], 'power': [0, 0.0], 'ground': [0, 0.0]}
        for n in cross:
            pin = [(x, y) for r in g['members'] for (nn, x, y) in parts[r].pads if nn == n]
            pout = [(x, y) for r, p in parts.items() if r not in g['members'] and r not in skip for (nn, x, y) in p.pads if nn == n]
            c, ln = mst_crossings(pin, pout)
            k = net_kind(n)
            wc[k][0] += c
            wc[k][1] += ln
        f['wall_crossings'] = {k: {'edges': v[0], 'length_mm': round(v[1], 1)} for k, v in wc.items()}
        f['nets_crossing'] = {'total': len(cross), 'signal': len(kinds['signal']), 'power': len(kinds['power']),
                              'ground': len(kinds['ground']), 'signal_nets': kinds['signal'], 'power_nets': kinds['power'],
                              'ground_nets': kinds['ground']}
        f['pass'] = all(f[k]['ok'] for k in ('fabricable', 'members_inside', 'no_foreign_inside', 'ring_clear', 'fence_clearance', 'on_board'))
    rep['pass'] = (not rep['problems']) and bool(geo) and all(f.get('pass') for f in rep['fences'].values())
    tot = rep['fences'].values()
    rep['totals'] = {'fences': len(geo), 'pass': sum(1 for f in tot if f.get('pass')),
                     'members_inside': sum(f['members_inside']['inside'] for f in tot if 'members_inside' in f),
                     'members': sum(f['members_inside']['of'] for f in tot if 'members_inside' in f),
                     'foreign_inside': sum(len(f['no_foreign_inside']['foreign']) for f in tot if 'no_foreign_inside' in f),
                     'ring_violations': sum(len(f['ring_clear']['in_ring']) for f in tot if 'ring_clear' in f),
                     'area_outer': round(sum(f['area_outer'] for f in tot), 2), 'area_inner': round(sum(f['area_inner'] for f in tot), 2),
                     'area_clear': round(sum(f['area_clear'] for f in tot), 2),
                     'nets_crossing_signal': sum(f['nets_crossing']['signal'] for f in tot if 'nets_crossing' in f),
                     'nets_crossing_power': sum(f['nets_crossing']['power'] for f in tot if 'nets_crossing' in f),
                     'wall_crossings_signal': sum(f['wall_crossings']['signal']['edges'] for f in tot if 'wall_crossings' in f),
                     'wall_crossing_signal_mm': round(sum(f['wall_crossings']['signal']['length_mm'] for f in tot if 'wall_crossings' in f), 1)}
    rep['_geo'] = geo
    return rep


# ----------------------------------------------------------------------------------------------- io
def read_blocks(path):
    d = json.load(open(path, encoding='utf-8'))
    out = {}
    for k, v in d.items():
        if isinstance(v, list):
            out[k] = list(v)
        elif 'members' in v:
            out[k] = list(v['members'])
        elif 'inside_F' in v:
            out[k] = list(v['inside_F'])
        else:
            raise SystemExit(f'{path}: block {k!r} has no "members" (or "inside_F") list')
    return out


def emit_gr(board_path, out_path, rep, layer='Dwgs.User'):
    """A copy of the board with each fence's centre line as a gr_poly on `layer` (and its name as gr_text)."""
    t = open(board_path, encoding='utf-8').read()
    add = []
    for i, (name, f) in enumerate(sorted(rep['fences'].items())):
        pts = ' '.join(f'(xy {x} {y})' for x, y in f['centre'])
        add.append(f'\t(gr_poly (pts {pts}) (stroke (width 0.3) (type solid)) (fill no) (layer "{layer}") '
                   f'(uuid "00000000-0000-4000-8000-{i + 1:012d}"))')
    end = t.rstrip().rfind(')')
    open(out_path, 'w', encoding='utf-8').write(t[:end].rstrip('\n') + '\n' + '\n'.join(add) + '\n' + t[end:])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('board')
    ap.add_argument('--blocks', required=True)
    ap.add_argument('--intent', help='hole keep-outs (circle rows) are read from it')
    ap.add_argument('--json')
    ap.add_argument('--emit-gr', help='write a copy of the board with the fences drawn on Dwgs.User')
    ap.add_argument('--wall', type=float, default=1.0)
    ap.add_argument('--inner-clear', type=float, default=0.5)
    ap.add_argument('--outer-clear', type=float, default=0.5)
    ap.add_argument('--min-seg', type=float, default=3.0)
    ap.add_argument('--fences', help='JSON {name: [[x, y], ...]}: check these hand-drawn wall centre lines instead of computing them')
    ap.add_argument('--no-carve', action='store_true', help='plain bounding-box fences')
    ap.add_argument('--ignore', nargs='*', default=[], help='refs never counted as foreign')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args(argv)
    try:
        blocks = read_blocks(a.blocks)
        board = load_board(a.board, a.intent)
    except (OSError, ValueError, KeyError) as e:
        print(f'fence: cannot read inputs: {e}', file=sys.stderr)
        return 2
    centres = None
    if a.fences:
        _shapely()
        centres = {k: Polygon(v) for k, v in json.load(open(a.fences, encoding='utf-8')).items()}
    rep = check_fences(board, blocks, a.wall, a.inner_clear, a.outer_clear, a.min_seg, a.ignore, not a.no_carve, centres)
    geo = rep.pop('_geo')
    rep['board'] = a.board
    if a.json:
        json.dump(rep, open(a.json, 'w'), indent=1)
    if a.emit_gr:
        emit_gr(a.board, a.emit_gr, rep)
    if not a.quiet:
        print(f'{"name":10} {"mem":>7} {"ok":>3} {"inside":>6} {"ring":>4} {"fab":>3} {"clr":>3} {"brd":>3} {"outer mm2":>9} {"inner mm2":>9} {"sig":>4} {"pwr":>4} {"gnd":>4}')
        for n, f in sorted(rep['fences'].items()):
            mi = f['members_inside']
            print(f'{n:10} {mi["inside"]:>3}/{mi["of"]:<3} {"Y" if f["pass"] else "N":>3} {len(f["no_foreign_inside"]["foreign"]):>6} '
                  f'{len(f["ring_clear"]["in_ring"]):>4} {"Y" if f["fabricable"]["ok"] else "N":>3} {"Y" if f["fence_clearance"]["ok"] else "N":>3} '
                  f'{"Y" if f["on_board"]["ok"] else "N":>3} {f["area_outer"]:>9} {f["area_inner"]:>9} '
                  f'{f["nets_crossing"]["signal"]:>4} {f["nets_crossing"]["power"]:>4} {f["nets_crossing"]["ground"]:>4}')
            for k, lab in (('no_foreign_inside', 'foreign inside'), ('ring_clear', 'in ring')):
                v = f[k].get('foreign') or f[k].get('in_ring')
                if v:
                    print(f'    FAIL {lab}: {" ".join(v)}')
            if f['members_inside']['outside']:
                print(f'    FAIL members outside: {" ".join(f["members_inside"]["outside"])}')
            if not f['fabricable']['ok']:
                print(f'    FAIL fabricable: {f["fabricable"]["why"]}')
            if not f['fence_clearance']['ok']:
                print(f'    FAIL fence clearance: {f["fence_clearance"]["clashes"]}')
            if not f['on_board']['ok']:
                print(f'    FAIL on board: {f["on_board"]["why"]}')
        for pr in rep['problems']:
            print('FAIL:', pr)
        t = rep['totals']
        print(f'fence: {"PASS" if rep["pass"] else "FAIL"}: {t["pass"]}/{t["fences"]} fences pass, members inside {t["members_inside"]}/{t["members"]}, '
              f'foreign inside {t["foreign_inside"]}, ring violations {t["ring_violations"]}, outer area {t["area_outer"]} mm2')
    return 0 if rep['pass'] else 4


if __name__ == '__main__':
    sys.exit(main())
