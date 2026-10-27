#!/usr/bin/env python3
"""cans_io.py : text-level footprint surgery for TimIQ v5 option (d): the six shield cans J7-J12 are NOT on the placing board.

  strip   BOARD OUT SIDE POSES [--refs J7,..]   remove the can footprints from BOARD (written to OUT); SIDE (json) keeps each footprint's
                                                s-expression, POSES (json) the pose it must be re-attached at. Poses come from --pose-board
                                                (default: the human layout) so J11/J12 are the lead's floorplan.
  (re-attaching is reattach.py)

The text is edited, never re-saved through pcbnew, so every other byte of the board stays as it was."""
import argparse
import json
import re
import sys

HUMAN = '/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb'
CANS = ['J7', 'J8', 'J9', 'J10', 'J11', 'J12']


def scan_footprints(text):
    """[(start, end, ref)] of every top-level (depth 1) footprint block. String-aware paren matching."""
    out = []
    depth = 0
    i = 0
    n = len(text)
    start = None
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == '\\' else 1
        elif c == '(':
            depth += 1
            if depth == 2 and text.startswith('(footprint', i):
                start = i
        elif c == ')':
            if depth == 2 and start is not None:
                blk = text[start:i + 1]
                m = re.search(r'\(property "Reference" "([^"]*)"', blk)
                out.append((start, i + 1, m.group(1) if m else None))
                start = None
            depth -= 1
        i += 1
    return out


def footprint_pose(blk):
    """(x, y, rot, face) of a footprint block: its own first (at ..) after the uuid, and its layer."""
    head = blk[:blk.find('(pad') if '(pad' in blk else len(blk)]
    m = re.search(r'\(at ([-\d.e]+) ([-\d.e]+)(?: ([-\d.e]+))?\)', head)
    lay = re.search(r'\(layer "([^"]+)"\)', head)
    return float(m.group(1)), float(m.group(2)), float(m.group(3) or 0.0), ('B' if lay and lay.group(1).startswith('B.') else 'F')


def set_pose(blk, x, y, rot):
    """The block with its footprint (at ..) replaced. Only the first (at ..) (the footprint's own) is touched."""
    def n(v):
        return f'{v:.6f}'.rstrip('0').rstrip('.') or '0'
    new = f'(at {n(x)} {n(y)} {n(rot)})' if rot else f'(at {n(x)} {n(y)})'
    out, n = re.subn(r'\(at [-\d.e]+ [-\d.e]+(?: [-\d.e]+)?\)', new, blk, count=1)
    if n != 1:
        raise ValueError('no (at ..) in footprint block')
    return out


def net_names(text):
    """The set of net names the board uses (KiCad 10 files carry names only: (net "NAME") on pads, zones and tracks; no id table)."""
    return set(re.findall(r'\(net "([^"]*)"\)', text))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('strip')
    s.add_argument('board'); s.add_argument('out'); s.add_argument('side'); s.add_argument('poses')
    s.add_argument('--refs', default=','.join(CANS))
    s.add_argument('--pose-board', default=HUMAN)
    a = ap.parse_args(argv)
    refs = a.refs.split(',')
    text = open(a.board, encoding='utf-8').read()
    ptext = open(a.pose_board, encoding='utf-8').read()
    pose_of = {r: footprint_pose(ptext[s0:e0]) for s0, e0, r in scan_footprints(ptext) if r in refs}
    fps = scan_footprints(text)
    have = {r: (s0, e0) for s0, e0, r in fps if r in refs}
    miss = [r for r in refs if r not in have]
    if miss or any(r not in pose_of for r in refs):
        print(f'strip: missing from board {miss}, from pose board {[r for r in refs if r not in pose_of]}', file=sys.stderr)
        return 2
    side, poses = {}, {}
    for r in refs:
        blk = text[have[r][0]:have[r][1]]
        x, y, rot, face = pose_of[r]
        side[r] = set_pose(blk, x, y, rot)
        poses[r] = {'x': x, 'y': y, 'rot': rot, 'face': face}
    for r in sorted(refs, key=lambda r: -have[r][0]):
        s0, e0 = have[r]
        # also eat the whitespace before the block so no blank line is left
        while s0 > 0 and text[s0 - 1] in ' \t':
            s0 -= 1
        if s0 > 0 and text[s0 - 1] == '\n':
            s0 -= 1
        text = text[:s0] + text[e0:]
    open(a.out, 'w', encoding='utf-8').write(text)
    json.dump(side, open(a.side, 'w'), indent=1)
    json.dump(poses, open(a.poses, 'w'), indent=1)
    print(f'stripped {len(refs)} can footprint(s) -> {a.out}; side {a.side}; poses {a.poses}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
