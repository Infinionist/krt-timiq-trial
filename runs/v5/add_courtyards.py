#!/usr/bin/env python3
"""add_courtyards.py IN OUT [--margin 0.25] [--skip REF,..] [--json REPORT] : give every footprint that has no courtyard one (TimIQ plan v3 item 1).

A footprint without an F.CrtYd/B.CrtYd shape falls back, in KRT, to its pad bounding box with NO margin (the plan-only warning "458 footprint(s)
have no courtyard"). This writes one rectangle per such footprint, on its own face (F.CrtYd for a front part, B.CrtYd for a back part):
    body   = bounding box of the part's outline graphics on its own face (silk + fab lines/circles/arcs/polys/rects), united with its pad boxes
             (an outline that stops short of a pad would otherwise leave a courtyard that does not enclose the copper; IPC courtyards enclose both),
             or the pad box alone when there is no outline,
    rect   = body grown by --margin on every side (default 0.25 mm: IPC-7351 nominal density level B courtyard excess for chip parts).
A footprint that already has any F.CrtYd / B.CrtYd item is NOT touched (its bytes stay identical). --skip names refs that never get one
(a container frame such as BOX1: a 120 mm courtyard over the whole box would overlap every part; KRT reads BOX1 as a pin frame instead).
Footprints with no pad and no outline graphics get none and are listed ("unmeasurable").
The text is edited, never re-saved through pcbnew (every other byte stays), as cans_io.py does. Coordinates are footprint-local (the file's own frame:
a pad's angle is absolute, so its local angle is angle - footprint angle).

Exit 0 : OUT written and re-read: every footprint not skipped/unmeasurable has a courtyard, every footprint that had one is byte-identical.
Exit 1 : the re-read check failed (nothing written).   Exit 2 : usage / unreadable input.
Prints one report line: footprints, already had one, added, skipped, unmeasurable, the margin."""
import argparse
import json
import math
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cans_io  # noqa: E402

NUM = r'([-\d.e+]+)'
OUTLINE_LAYERS = {'F': ('F.SilkS', 'F.Fab'), 'B': ('B.SilkS', 'B.Fab')}


def has_courtyard(blk):
    return re.search(r'\(layer "[FB]\.CrtYd"\)', blk) is not None


def _items(blk):
    """Top-level (depth 2) s-expression items of a footprint block as strings."""
    out = []
    depth = 0
    i, n = 0, len(blk)
    start = None
    while i < n:
        c = blk[i]
        if c == '"':
            i += 1
            while i < n and blk[i] != '"':
                i += 2 if blk[i] == '\\' else 1
        elif c == '(':
            depth += 1
            if depth == 2:
                start = i
        elif c == ')':
            if depth == 2 and start is not None:
                out.append(blk[start:i + 1])
                start = None
            depth -= 1
        i += 1
    return out


def _xy(s):
    return [(float(a), float(b)) for a, b in re.findall(r'\(xy ' + NUM + ' ' + NUM + r'\)', s)]


def body_box(blk):
    """(outline_box or None, pad_box or None, face) in footprint-local mm."""
    x, y, rot, face = cans_io.footprint_pose(blk)
    lay = OUTLINE_LAYERS[face]
    ox, oy = [], []
    px, py = [], []

    def add(lst_x, lst_y, pts):
        for a, b in pts:
            lst_x.append(a)
            lst_y.append(b)
    for it in _items(blk):
        kind = re.match(r'\((\w+)', it).group(1)
        lm = re.search(r'\(layer "([^"]+)"\)', it)
        if kind == 'pad':
            m = re.match(r'\(pad "[^"]*" \w+ \w+\s+\(at ' + NUM + ' ' + NUM + r'(?: ' + NUM + r')?\)\s+\(size ' + NUM + ' ' + NUM, it)
            if not m:
                continue
            cx, cy, ang, w, h = float(m.group(1)), float(m.group(2)), float(m.group(3) or 0.0), float(m.group(4)), float(m.group(5))
            if round((ang - rot) / 90.0) % 2:
                w, h = h, w
            add(px, py, [(cx - w / 2, cy - h / 2), (cx + w / 2, cy + h / 2)])
        elif kind.startswith('fp_') and lm and lm.group(1) in lay:
            lw = re.search(r'\(width ' + NUM + r'\)', it)
            half = float(lw.group(1)) / 2 if lw else 0.0
            pts = []
            if kind == 'fp_circle':
                c = re.search(r'\(center ' + NUM + ' ' + NUM + r'\)', it)
                e = re.search(r'\(end ' + NUM + ' ' + NUM + r'\)', it)
                if c and e:
                    r = math.hypot(float(e.group(1)) - float(c.group(1)), float(e.group(2)) - float(c.group(2)))
                    pts = [(float(c.group(1)) - r, float(c.group(2)) - r), (float(c.group(1)) + r, float(c.group(2)) + r)]
            elif kind in ('fp_line', 'fp_rect'):
                s = re.search(r'\(start ' + NUM + ' ' + NUM + r'\)', it)
                e = re.search(r'\(end ' + NUM + ' ' + NUM + r'\)', it)
                if s and e:
                    pts = [(float(s.group(1)), float(s.group(2))), (float(e.group(1)), float(e.group(2)))]
            elif kind == 'fp_arc':
                pts = [(float(a), float(b)) for a, b in re.findall(r'\((?:start|mid|end) ' + NUM + ' ' + NUM + r'\)', it)]
            elif kind in ('fp_poly', 'fp_curve'):
                pts = _xy(it)
            if pts:
                add(ox, oy, [(min(p[0] for p in pts) - half, min(p[1] for p in pts) - half), (max(p[0] for p in pts) + half, max(p[1] for p in pts) + half)])
    ob = (min(ox), min(oy), max(ox), max(oy)) if ox else None
    pb = (min(px), min(py), max(px), max(py)) if px else None
    return ob, pb, face


def courtyard_rect(blk, margin):
    """(face, (x0, y0, x1, y1)) footprint-local, or None when the footprint has neither outline nor pad."""
    ob, pb, face = body_box(blk)
    boxes = [b for b in (ob, pb) if b]
    if not boxes:
        return None
    r = (min(b[0] for b in boxes) - margin, min(b[1] for b in boxes) - margin, max(b[2] for b in boxes) + margin, max(b[3] for b in boxes) + margin)
    return face, tuple(round(v, 3) for v in r)


def courtyard_item(face, r):
    f = lambda v: f'{v:.3f}'.rstrip('0').rstrip('.')
    return ('\t\t(fp_rect\n\t\t\t(start ' + f(r[0]) + ' ' + f(r[1]) + ')\n\t\t\t(end ' + f(r[2]) + ' ' + f(r[3]) + ')\n'
            '\t\t\t(stroke\n\t\t\t\t(width 0.05)\n\t\t\t\t(type solid)\n\t\t\t)\n\t\t\t(fill no)\n'
            f'\t\t\t(layer "{face}.CrtYd")\n\t\t\t(uuid "{uuid.uuid4()}")\n\t\t)\n')


def with_courtyard(blk, margin=0.25):
    """The footprint block with a courtyard rectangle inserted before its first pad; the block itself when it already has one; None when it has
    neither outline nor pad to measure."""
    if has_courtyard(blk):
        return blk
    cy = courtyard_rect(blk, margin)
    if cy is None:
        return None
    item = courtyard_item(*cy)
    pos = blk.find('\n\t\t(pad ')
    if pos < 0:
        pos = blk.rfind('\n\t)')
    return blk[:pos + 1] + item + blk[pos + 1:]


def add_courtyards(text, margin=0.25, skip=()):
    """(new text, report dict). Pure on its inputs."""
    skip = set(skip)
    out, last = [], 0
    rep = {'footprints': 0, 'had': 0, 'added': [], 'skipped': [], 'unmeasurable': [], 'margin_mm': margin}
    for s, e, ref in cans_io.scan_footprints(text):
        rep['footprints'] += 1
        blk = text[s:e]
        if has_courtyard(blk):
            rep['had'] += 1
            continue
        if ref in skip:
            rep['skipped'].append(ref)
            continue
        new = with_courtyard(blk, margin)
        if new is None:
            rep['unmeasurable'].append(ref)
            continue
        out.append(text[last:s])
        out.append(new)
        last = e
        rep['added'].append(ref)
    out.append(text[last:])
    return ''.join(out), rep


POINT_HALF = 0.1


def point_courtyard(text, ref, half=POINT_HALF):
    """plan v4: text with a POINT courtyard (a 2*half mm square at the footprint origin, F.CrtYd) in footprint `ref` when it has none; the same text when it has one.
    For the pin frame BOX1: no courtyard made KRT grade it on its pad bounding box = the whole box, so every exclusive zone refused its declared pose (preflight_probe.py found
    it: KRT's exclusive zones have no allow list); a 0.2 mm point courtyard sits at the box corner, over no zone and no part. Raises KeyError when the ref is absent."""
    for s, e, r in cans_io.scan_footprints(text):
        if r == ref:
            blk = text[s:e]
            if has_courtyard(blk):
                return text
            pos = blk.find('\n\t\t(pad ')
            if pos < 0:
                pos = blk.rfind('\n\t)')
            return text[:s] + blk[:pos + 1] + courtyard_item('F', (-half, -half, half, half)) + blk[pos + 1:] + text[e:]
    raise KeyError(ref)


def marker_footprint(ref, x, y, half=POINT_HALF):
    """plan v4 (no anchor zones): the text of a marker footprint: one half x half mm pad (KRT never places or fixes a pad-less footprint), no net, a 2*half mm square courtyard on F.CrtYd at (x, y). A fixed part for KRT's proximity rows:
    an anchor IC is pulled to it (a proximity row, body basis) instead of being held in a zone."""
    return (f'\t(footprint "anchor:POINT"\n\t\t(layer "F.Cu")\n\t\t(uuid "{uuid.uuid4()}")\n\t\t(at {x:.4f} {y:.4f})\n'
            f'\t\t(property "Reference" "{ref}"\n\t\t\t(at 0 0 0)\n\t\t\t(layer "F.SilkS")\n\t\t\t(hide yes)\n\t\t\t(uuid "{uuid.uuid4()}")\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1 1)\n\t\t\t\t\t(thickness 0.15)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n'
            f'\t\t(property "Value" "anchor marker"\n\t\t\t(at 0 0 0)\n\t\t\t(layer "F.Fab")\n\t\t\t(hide yes)\n\t\t\t(uuid "{uuid.uuid4()}")\n'
            '\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1 1)\n\t\t\t\t\t(thickness 0.15)\n\t\t\t\t)\n\t\t\t)\n\t\t)\n'
            '\t\t(attr smd exclude_from_pos_files exclude_from_bom)\n'
            + courtyard_item('F', (-half, -half, half, half))
            + f'\t\t(pad "1" smd rect\n\t\t\t(at 0 0)\n\t\t\t(size {half:g} {half:g})\n\t\t\t(layers "F.Cu")\n\t\t\t(uuid "{uuid.uuid4()}")\n\t\t)\n' + '\t)\n')


def add_markers(text, markers):
    """text with a marker footprint per (ref, x, y) appended before the board's closing parenthesis; KeyError-free, but a ref already on the board is a ValueError."""
    have = {r for _s, _e, r in cans_io.scan_footprints(text)}
    for ref, _x, _y in markers:
        if ref in have:
            raise ValueError(f'{ref} is already on the board')
    last = max(e for _s, e, _r in cans_io.scan_footprints(text))
    i = text.index('\n', last) + 1               # the line after the last footprint
    return text[:i] + ''.join(marker_footprint(r, x, y) for r, x, y in markers) + text[i:]


def frame_courtyard_size(text, ref):
    """(w, h) of the F/B.CrtYd fp_rect of footprint `ref`, or None when it has none. Each fp_rect is cut out by paren counting (its stroke
    block nests two deep, which the old one-regex version could not follow, so it always returned None)."""
    for s, e, r in cans_io.scan_footprints(text):
        if r != ref:
            continue
        blk = text[s:e]
        for m in re.finditer(r'\(fp_rect\b', blk):
            depth, i = 0, m.start()
            while i < len(blk):
                depth += (blk[i] == '(') - (blk[i] == ')')
                i += 1
                if depth == 0:
                    break
            item = blk[m.start():i]
            if not re.search(r'\(layer "[FB]\.CrtYd"\)', item):
                continue
            g = re.search(r'\(start ' + NUM + ' ' + NUM + r'\)\s*\(end ' + NUM + ' ' + NUM + r'\)', item)
            if g:
                x0, y0, x1, y1 = (float(v) for v in g.groups())
                return abs(x1 - x0), abs(y1 - y0)
        return None
    return None


def verify(old, new, skip):
    """problems list: every footprint that had a courtyard is byte-identical; every other one (not skipped / unmeasurable) has one."""
    probs = []
    fo = {r: old[s:e] for s, e, r in cans_io.scan_footprints(old)}
    fn = {r: new[s:e] for s, e, r in cans_io.scan_footprints(new)}
    if set(fo) != set(fn):
        probs.append('footprint set changed')
    for r, b in fo.items():
        if has_courtyard(b):
            if fn.get(r) != b:
                probs.append(f'{r}: had a courtyard and was modified')
        elif r in skip:
            if fn.get(r) != b:
                probs.append(f'{r}: skipped but modified')
        elif r in fn and not has_courtyard(fn[r]) and courtyard_rect(b, 0.25) is not None:
            probs.append(f'{r}: still without a courtyard')
        elif r in fn and has_courtyard(fn[r]):
            # the other bytes of an edited footprint are unchanged: removing the one new item gives the old block back
            stripped = re.sub(r'\t\t\(fp_rect\n\t\t\t\(start [^\n]*\n\t\t\t\(end [^\n]*\n\t\t\t\(stroke\n\t\t\t\t\(width 0\.05\)\n\t\t\t\t\(type solid\)\n\t\t\t\)\n\t\t\t\(fill no\)\n\t\t\t\(layer "[FB]\.CrtYd"\)\n\t\t\t\(uuid "[^"]*"\)\n\t\t\)\n', '', fn[r])
            if stripped != b:
                probs.append(f'{r}: more than the courtyard changed')
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board')
    ap.add_argument('out')
    ap.add_argument('--margin', type=float, default=0.25)
    ap.add_argument('--skip', default='BOX1', help='comma list of refs that never get a courtyard (default BOX1, the pin frame)')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    try:
        text = open(a.board, encoding='utf-8').read()
    except OSError as e:
        print(f'add_courtyards: unreadable input: {e}', file=sys.stderr)
        return 2
    skip = [r for r in a.skip.split(',') if r]
    new, rep = add_courtyards(text, a.margin, skip)
    probs = verify(text, new, set(skip))
    if probs:
        for p in probs[:10]:
            print('REFUSED: ' + p, file=sys.stderr)
        return 1
    open(a.out, 'w', encoding='utf-8').write(new)
    if a.json:
        json.dump(rep, open(a.json, 'w'), indent=1)
    print(f"add_courtyards: {rep['footprints']} footprint(s): {rep['had']} already had a courtyard (untouched), {len(rep['added'])} added at margin "
          f"{a.margin:g} mm, {len(rep['skipped'])} skipped {rep['skipped']}, {len(rep['unmeasurable'])} unmeasurable {rep['unmeasurable']} -> {a.out}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
