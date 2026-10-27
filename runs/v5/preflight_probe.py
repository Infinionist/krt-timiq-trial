#!/usr/bin/env python3
"""preflight_probe.py BOARD GROUPS INTENT [--out JSON] : the dry legality probe of TimIQ plan v4 (fix 1). Run with KRT's venv python.

Runs place_simple's own set-up (main(): faces, declared poses, seat_state/build, the fixed-pose check against every part that stays where it is, the too-big check)
and stops at the first call of the anneal (simple_anneal.scatter raises Stop). Nothing is placed or written. KRT's own predicate decides:
  refused  {ref: [reasons]}   a declared (fixed) pose KRT refuses: keep-out, hole clearance, exclusive zone, courtyard / pad clash with another stay-put part, outline
  too_big  [ref]              a movable part that does not fit the usable board area at either quarter turn
  dims     {ref: [w, h]}      the courtyard rect of every part as KRT grades it (state.parts[ref].rect()), used by gate.py's zone-fit checks
  rects    {ref: [x0, y0, x1, y1]}  that rect at the seated pose (plan v5: the fixed parts are the obstacles of a zone's usable area)
  padbox   {ref: [x0, y0, x1, y1]}  the pad-copper box of every part with pads at the seated pose (plan v5: reach of a pad past the courtyard)
  side     {ref: 'F'|'B'}     the face each part stands on after the declared faces were applied
  fixed    [ref]              the parts that stay where they are (not movable)
  clearance, edge_clearance   KRT's own legality knobs for this board (mm)
  anchored {seed: [{group, n, x, y}]}  plan v5: where KRT's ANCHORED start would put each group (simple_anneal._anchors: the least-squares solve toward the fixed parts and groups
           a group is wired to, with that seed's weights) for the anchored seeds of run_seeds.sh (1 and 2): a look at the location suggestion before any seed runs. Nothing is placed.
Exit 0 when it reached the anneal (the JSON is written), 2 when place_simple refused to start (message printed)."""
import argparse
import contextlib
import io
import json
import os
import re
import sys

KRT = '/tmp/pcb-trials/timiq/krt'
sys.path.insert(0, KRT + '/py_placer')
sys.path.insert(0, KRT + '/py_router')
sys.path.insert(0, KRT + '/py_tools')


class Stop(Exception):
    pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('board')
    ap.add_argument('groups')
    ap.add_argument('intent')
    ap.add_argument('--out', default=None)
    ap.add_argument('--anchored-seeds', default='1,2', help='seeds whose anchored start is solved (run_seeds.sh: --scattered 0 --clustered 1 --anchored 2 -> seeds 1, 2)')
    a = ap.parse_args(argv)
    import place_simple
    from placement import simple_anneal
    cap = {}

    def stop(model, movable, **kw):
        cap['model'] = model
        cap['movable'] = list(movable)
        raise Stop()

    simple_anneal.scatter = stop
    # the state is built inside main(); hook the seat_state call to keep it
    from placement import edge_seat
    real = edge_seat.seat_state

    def seat(*args, **kw):
        s = real(*args, **kw)
        cap['state'] = s
        return s

    edge_seat.seat_state = seat
    buf = io.StringIO()
    tmp = os.path.join('/tmp', f'preflight_{os.getpid()}.kicad_pcb')
    rc = None
    with contextlib.redirect_stdout(buf):
        try:
            rc = place_simple.main([a.board, tmp, '--groups', a.groups, '--intent', a.intent, '--seed', '0'])
        except Stop:
            rc = 'stop'
    out = buf.getvalue()
    if rc != 'stop':
        print('preflight_probe: place_simple did not reach the anneal (rc %r):\n%s' % (rc, out[-1500:]), file=sys.stderr)
        return 2
    refused = {}
    for m in re.finditer(r"WARNING: (\S+)'s declared pose is not legal: (.*)", out):
        refused[m.group(1)] = [s.strip() for s in m.group(2).split(';')]
    too_big = re.findall(r'WARNING: (\S+) \([\d.]+ x [\d.]+ mm\) does not fit in the usable area', out)
    st = cap['state']
    dims = {}
    for r, p in st.parts.items():
        x0, y0, x1, y1 = p.rect()
        dims[r] = [round(x1 - x0, 3), round(y1 - y0, 3)]
    rects, padbox, side = {}, {}, {}
    for r, p in st.parts.items():
        x0, y0, x1, y1 = p.rect()
        rects[r] = [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]
        pb = p.padbox()
        if pb is not None:
            padbox[r] = [round(pb[0], 4), round(pb[1], 4), round(pb[2], 4), round(pb[3], 4)]
        side[r] = p.side
    movable = set(cap['movable'])
    anchored = {}
    try:
        import random
        model = cap['model']
        grp_of = {r: n for n, members in model.groups for r in members}
        inner = tuple(model.state.usable)
        for sd in [int(s) for s in a.anchored_seeds.split(',') if s]:
            rng = random.Random(sd)
            for _r in cap['movable']:            # scatter() draws x and y per movable part before the anchored solve: replay them so the weights are the seed's own
                rng.uniform(0, 1)
                rng.uniform(0, 1)
            nodes, centres = simple_anneal._anchors(model, cap['movable'], rng, inner)
            anchored[str(sd)] = [{'group': grp_of.get(m[0]), 'n': len(m), 'x': round(float(c[0]), 2), 'y': round(float(c[1]), 2)} for m, c in zip(nodes, centres) if len(m) > 1]
    except Exception as ex:      # a reading for the render, never a reason to stop the probe
        anchored = {'error': repr(ex)}
    res = {'refused': refused, 'too_big': too_big, 'dims': dims, 'movable': cap['movable'], 'rects': rects, 'padbox': padbox, 'side': side,
           'fixed': sorted(r for r in st.parts if r not in movable), 'clearance': getattr(st, 'clearance', None),
           'edge_clearance': getattr(st, 'board_edge_clearance', None), 'anchored': anchored}
    if a.out:
        json.dump(res, open(a.out, 'w'))
    print(json.dumps({'refused': refused, 'too_big': too_big, 'n_parts': len(dims)}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
