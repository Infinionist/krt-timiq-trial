#!/usr/bin/env python3
"""set_faces.py IN OUT --front REF[,REF..] [--front-file F.json] : stand the named parts on the FRONT face (TimIQ plan v3 item 4). Run with KRT's venv python.

KRT's own writer (`placement.writer.write_placed_output`, `new_side`) mirrors a back part to the front at its own x/y/rotation: pad layers, graphics, text,
courtyard. A part already on the front is not touched. This is the START face only: place_simple keeps every part on the face it has and flips a part
named `flippable` in the groups file only when it has no room there (placement/faces.py), so "larger parts on top" is "start on top, flipped last".
Exit 0: written, and re-read: every named ref is on F, every other footprint is byte-identical. Exit 1: refused (an unknown ref, or the re-read failed).
Exit 2: usage."""
import argparse
import json
import os
import sys

KRT = '/tmp/pcb-trials/timiq/krt'
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for d in ('py_router', 'py_placer'):
    sys.path.insert(0, KRT + '/' + d)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board')
    ap.add_argument('out')
    ap.add_argument('--front', default='')
    ap.add_argument('--front-file', default=None, help='json list of refs')
    a = ap.parse_args(argv)
    refs = [r for r in a.front.split(',') if r]
    if a.front_file:
        refs += json.load(open(a.front_file))
    refs = sorted(set(refs))
    import cans_io
    from placement.writer import write_placed_output
    text = open(a.board, encoding='utf-8').read()
    fps = {r: text[s:e] for s, e, r in cans_io.scan_footprints(text)}
    unknown = [r for r in refs if r not in fps]
    if unknown:
        print(f'REFUSED: not on the board: {unknown}', file=sys.stderr)
        return 1
    moves = []
    for r in refs:
        x, y, rot, face = cans_io.footprint_pose(fps[r])
        if face == 'B':
            moves.append({'reference': r, 'new_x': x, 'new_y': y, 'new_rotation': rot % 360.0, 'new_side': 'F'})
    write_placed_output(a.board, a.out, moves)
    new = open(a.out, encoding='utf-8').read()
    nf = {r: new[s:e] for s, e, r in cans_io.scan_footprints(new)}
    probs = [f'{r}: still on the back' for r in refs if cans_io.footprint_pose(nf[r])[3] != 'F']
    moved = {m['reference'] for m in moves}
    probs += [f'{r}: changed but not asked' for r in fps if r not in moved and nf.get(r) != fps[r]]
    if set(nf) != set(fps):
        probs.append('footprint set changed')
    if probs:
        for p in probs[:10]:
            print('REFUSED: ' + p, file=sys.stderr)
        os.remove(a.out)
        return 1
    print(f'set_faces: {len(refs)} named, {len(moves)} turned from B to F, {len(refs) - len(moves)} already on F -> {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
