#!/usr/bin/env python3
"""rowcheck.py : plan v5 row checks, pure python (no shapely, no pcbnew), used by build_inputs.py, gate.py and the tests.

unsatisfiable_rows(blocks, rows, fixed_rects)
    {(ref, near): problem}: a proximity row whose two ends can never be within max_mm: each end's region is its zoned block's rect grown by the block's tolerance, or its own rect
    when it is a fixed part, or nothing (free: no bound). The rect gap between the two regions is a lower bound of the parts' gap (parts stand inside their regions), so a gap above
    max_mm means no placement can hold the row. Plan v4's netlist rows R74->U17 (J10 / J8), R115->U26 and R116->U27 (J11 / J8) were such rows: three proximity errors in every seed.
claim_problems(groups, rows)  (KRT venv: placement.grouping)
    {ref: problem}: KRT's own fold_followers on the groups with the rows: every part a row moves into another group. A row between two groups is a membership CLAIM
    (place_simple does the same fold before it anneals): plan v4's power rows folded all 11 power groups into one group of 78 parts.
"""
import math


def _gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def regions(blocks, fixed_rects=None, default_tol=0.5):
    """{ref: (label, rect)} for every member of a zoned block (zone grown by tolerance) and every fixed part."""
    out = {}
    for r, rc in (fixed_rects or {}).items():
        out[r] = (r, list(rc))
    for b in blocks:
        z = b.get('zone')
        if not z:
            continue
        tol = b.get('tolerance_mm', default_tol)
        zr = [z[0] - tol, z[1] - tol, z[2] + tol, z[3] + tol]
        for r in b.get('refs') or []:
            out[r] = (b['name'], zr)
    return out


def unsatisfiable_rows(blocks, rows, fixed_rects=None):
    reg = regions(blocks, fixed_rects)
    bad = {}
    for row in rows:
        a, b = reg.get(row['ref']), reg.get(row['near'])
        if a and b and a[0] != b[0]:
            g = _gap(a[1], b[1])
            if g > row['max_mm'] + 1e-9:
                bad[(row['ref'], row['near'])] = f"ends in different regions ({a[0]}, {b[0]}) {g:.1f} mm apart, row limit {row['max_mm']:g} mm: no placement holds it"
    return bad


def claim_problems(groups, rows, krt='/tmp/pcb-trials/timiq/krt'):
    import sys
    for d in ('py_placer', 'py_router'):
        if krt + '/' + d not in sys.path:
            sys.path.insert(0, krt + '/' + d)
    from placement.grouping import fold_followers
    _out, moved = fold_followers(groups, rows)
    return {r: f'row moves {r} from group {f} to group {t} (a proximity row between groups is a membership claim)' for r, (f, t) in sorted(moved.items())}
