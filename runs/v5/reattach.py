#!/usr/bin/env python3
"""reattach.py BOARD OUT [--side cans_side.json] [--poses cans_poses.json] : put the shield cans J7-J12 back on a placed board
(TimIQ v5 option (d): the cans are off the placing board; run this before check_assembly / routing).

Exit 0: every can re-attached at its pose and verified in OUT (re-read: ref, pose, face, every pad net name used on the board).
Exit 1: a refusal, nothing written: a can already on BOARD, a pad net the board does not have, a pose that did not survive.
Exit 2: usage / unreadable input.
KiCad 10 boards carry net names only (no id table), so a can's pad nets re-attach by name (GND for the cans)."""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cans_io  # noqa: E402
import add_courtyards  # noqa: E402


def reattach(text, side, poses, margin=0.25):
    """(new text, problems). problems empty = fine. A can with no courtyard gets one (add_courtyards, `margin` mm; None/0 = leave it), as every
    other footprint of the placing board does (plan v3 item 1)."""
    probs = []
    fps = {r: (s, e) for s, e, r in cans_io.scan_footprints(text)}
    nets = cans_io.net_names(text)
    blocks = []
    for ref in sorted(side, key=lambda r: int(r[1:])):
        if ref in fps:
            probs.append(f'{ref} is already on the board')
            continue
        blk = side[ref]
        p = poses[ref]
        blk = cans_io.set_pose(blk, p['x'], p['y'], p['rot'])
        if margin:
            blk = add_courtyards.with_courtyard(blk, margin) or blk

        for name in sorted(set(re.findall(r'\(net "([^"]*)"\)', blk))):
            if name and name not in nets:
                probs.append(f'{ref}: pad net "{name}" is not used on the target board')
        blocks.append('\t' + blk if not blk.startswith('\t') else blk)
    if probs:
        return text, probs
    i = text.rstrip().rfind(')')
    new = text[:i].rstrip('\n') + '\n' + '\n'.join(blocks) + '\n' + text[i:]
    return new, []


def verify(text, side, poses):
    probs = []
    fps = {r: text[s:e] for s, e, r in cans_io.scan_footprints(text)}
    for ref, p in poses.items():
        if ref not in fps:
            probs.append(f'{ref} missing after reattach')
            continue
        x, y, rot, face = cans_io.footprint_pose(fps[ref])
        if abs(x - p['x']) > 1e-6 or abs(y - p['y']) > 1e-6 or abs(rot - p['rot']) > 1e-6 or face != p['face']:
            probs.append(f'{ref} pose ({x},{y},{rot},{face}) != declared ({p["x"]},{p["y"]},{p["rot"]},{p["face"]})')
    return probs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board')
    ap.add_argument('out')
    ap.add_argument('--side', default=HERE + '/cans_side.json')
    ap.add_argument('--poses', default=HERE + '/cans_poses.json')
    ap.add_argument('--courtyard-margin', type=float, default=0.25, help='mm; a can without a courtyard gets one (0 = leave the cans as they are)')
    a = ap.parse_args(argv)
    try:
        text = open(a.board, encoding='utf-8').read()
        side = json.load(open(a.side))
        poses = json.load(open(a.poses))
    except (OSError, ValueError) as e:
        print(f'reattach: unreadable input: {e}', file=sys.stderr)
        return 2
    if set(side) != set(poses):
        print(f'reattach: side file {sorted(side)} and poses file {sorted(poses)} name different cans', file=sys.stderr)
        return 1
    new, probs = reattach(text, side, poses, a.courtyard_margin)
    if not probs:
        probs = verify(new, side, poses)
    if probs:
        for p in probs:
            print('REFUSED: ' + p, file=sys.stderr)
        return 1
    open(a.out, 'w', encoding='utf-8').write(new)
    print(f'reattached {len(side)} can(s): {", ".join(sorted(side, key=lambda r: int(r[1:])))} -> {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
