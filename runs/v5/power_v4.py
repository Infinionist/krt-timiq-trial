#!/usr/bin/env python3
"""power_v4.py : the pure parts of TimIQ plan v4's power section (Infinionist 10-27).
Imported by build_inputs.py and the tests; no I/O. NETS = {net: [(ref, pad)]} of the placing board.

Groups (all by the netlist, three calls named):
  pw_in     J6 + the caps on nets that touch a J6 pin (the pre-filter caps C143-C145, C148-C150)
  pw_<br>   a branch: its filter inductors (an L whose far net feeds regulators) + the caps on that feed rail that are not a regulator's input cap
  pw_<U>    one per regulator: the regulator + every part on a net that only this regulator (and its own parts) touches (output rail caps, NR, feedback R/C)
            + its input cap (a REG_INPUT_FP ceramic on the shared feed rail; which regulator it serves is not in the netlist: nearest regulator on the human board = CHEAT 3)
  leftover  anything else (listed, never silently dropped)
"""
import math
import re

REG_INPUT_FP = 'SOLEIL-1210'     # call 1: a regulator's input cap is the 1210 ceramic on the shared feed rail (count checked == number of regulators on that rail)
FILL = 0.45                      # call 2: members' courtyard area / (2 x zone area), both faces, at most this (gate checks 0.5)
GAP = 0.0


def _pas(ref):
    return re.match(r'^(C|R|L|FB)\d+$', ref) is not None


def split_groups(nets, power_refs, regs, filters, fixed_in, fp_of, hpos):
    """-> (groups {name: {'refs': [...], 'kind': ..., ...}}, leftover [ref]). hpos = {ref: (x, y)} human board, ONLY to pick which regulator a shared-rail input cap serves."""
    by_ref = {}
    for n, pads in nets.items():
        for r, _p in pads:
            by_ref.setdefault(r, set()).add(n)
    refs = set(power_refs)
    regset = set(regs)
    reg_nets = {n for n, pads in nets.items() if n != 'GND' and {r for r, _ in pads} & regset}
    shared = {n for n in reg_nets if len({r for r, _ in nets[n]} & regset) >= 2 or ({r for r, _ in nets[n]} & (set(filters) | set(fixed_in)))}
    groups, taken = {}, set()

    def take(name, kind, members, **kw):
        members = [m for m in members if m in refs and m not in taken]
        taken.update(members)
        g = groups.setdefault(name, {'refs': [], 'kind': kind})
        g['refs'] += members
        g.update(kw)

    # pw_in: caps on any net that touches a fixed input connector pin
    inn = {n for n, pads in nets.items() if n != 'GND' and {r for r, _ in pads} & set(fixed_in)}
    take('pw_in', 'input', sorted(r for r in refs if r.startswith('C') and by_ref[r] & inn), anchor=sorted(fixed_in)[0])
    # branches: a filter's far net = the one that feeds regulators
    feed_of = {}
    for f in filters:
        fn = [n for n in by_ref[f] if n in reg_nets and n != 'GND']
        feed_of[f] = fn[0] if fn else None
    # branch id by the sign of the rail: 24V / -24V share one branch ("pm24"); 7V5 is its own: the branch is the union of filters whose feed rails feed the same
    # regulator FAMILY (regulators whose input nets are feed rails of these filters). Here: filters feeding rails with a common prefix after stripping '-' form a branch.
    br = {}
    for f, n in feed_of.items():
        br.setdefault(n.lstrip('-'), []).append(f)
    inputs = {}
    for r in regs:
        ins = [n for n in by_ref[r] if n in shared and n in feed_of.values()]
        inputs[r] = ins[0] if ins else None
    bulk, in_cap = {}, {}
    for rail in set(feed_of.values()):
        caps = sorted(c for c in refs if c.startswith('C') and by_ref[c] == {rail, 'GND'})
        serves = [r for r in regs if inputs[r] == rail]
        ic = [c for c in caps if fp_of[c] == REG_INPUT_FP]
        assert len(ic) == len(serves), (rail, ic, serves)
        bulk[rail] = [c for c in caps if c not in ic]
        # CHEAT 3: pair input caps with regulators by the human board's nearest-first assignment (greedy by distance)
        pairs = sorted(((math.dist(hpos[c], hpos[r]), c, r) for c in ic for r in serves))
        used_c, used_r = set(), set()
        for d, c, r in pairs:
            if c in used_c or r in used_r:
                continue
            used_c.add(c); used_r.add(r); in_cap[r] = c
    for key, fl in sorted(br.items()):
        rails = sorted({feed_of[f] for f in fl})
        take('pw_' + key.lower(), 'branch', sorted(fl) + [c for rl in rails for c in bulk[rl]], filters=sorted(fl), rails=rails)
    # regulators
    for r in regs:
        own = {n for n in by_ref[r] if n != 'GND' and n not in shared}
        mem = [r] + sorted((p for p in refs if p not in regset and p not in taken and by_ref[p] & own), key=lambda s: (s[0], int(s[1:])))
        if r in in_cap:
            mem.append(in_cap[r])
        take('pw_' + r, 'regulator', mem, reg=r, rail_in=inputs[r], own_nets=sorted(own))
    left = sorted(refs - taken, key=lambda s: (s[0], int(s[1:])))
    return groups, left


def pin_rows(nets, reg_group, pin_mm):
    """rows {ref, near, pads, max_mm, basis, why} from each non-regulator member to its regulator's pins: pads on a net that touches the regulator (not GND)."""
    reg = reg_group['reg']
    rpads = {}
    for n, pads in nets.items():
        if n == 'GND':
            continue
        for r, p in pads:
            if r == reg:
                rpads.setdefault(n, []).append(p)
    rows = []
    for m in reg_group['refs']:
        if m == reg:
            continue
        mp = {}
        for n, pads in nets.items():
            if n == 'GND' or n not in rpads:
                continue
            for r, p in pads:
                if r == m:
                    mp.setdefault(n, []).append(p)
        if not mp:
            continue
        # prefer the net where the regulator has the fewest pins (the tightest pin), then name order
        n = sorted(mp, key=lambda k: (len(rpads[k]), k))[0]
        rows.append({'ref': m, 'near': reg, 'pads': {m: sorted(mp[n], key=lambda s: (len(s), s)), reg: sorted(rpads[n], key=lambda s: (len(s), s))},
                     'max_mm': pin_mm, 'basis': 'pad_edge',
                     'why': f'plan v4 power group {reg}: {m} pad(s) {",".join(mp[n])} on net {n} with {reg} pin(s) {",".join(rpads[n])} ({pin_mm:g} mm pad edge)'})
    return rows


# ---------------------------------------------------------------- layout
def loads_centroid_x(nets, rail_nets, power_set, place_x):
    """(mean x, n) over the consumer parts on rail_nets that are not in the power block; place_x(ref) -> x or None (fixed part, its can centre, or its group's anchor connector)."""
    xs = [place_x(r) for n in rail_nets for r, _p in nets.get(n, ()) if r not in power_set]
    xs = [x for x in xs if x is not None]
    return (sum(xs) / len(xs), len(xs)) if xs else (None, 0)


def zone_area(refs, dims):
    return sum(dims[r][0] * dims[r][1] for r in refs)


def overlap(a, b):
    w, h = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def layout(groups, dims, side_of, order_key, strip, j6_rect, obstacles, fill=FILL, min_w=10.0, margin=1.0):
    """-> {block name: {'zone': [x0,y0,x1,y1], 'refs': [...], 'group': name, 'lost_mm2': float, 'fill': float}}. Columns outward from J6 on each side:
    column 0 = the side's pre-filter caps (top half) over its branch filter group (bottom half); then the regulators in order_key order, two to a column (stacked), a single
    last one full height. Half height = (strip height / 2). side_of(group) -> 'L' | 'R'; order_key(reg group) -> sortable (nearest J6 first)."""
    x0, y0, x1, y1 = strip
    H = y1 - y0
    h2 = H / 2.0
    out = {}

    def tile(name, refs, gname, x_a, x_b_dir, top, full=False):
        """place a tile starting at x_a growing in x_b_dir (+1 right, -1 left); returns its far edge."""
        if not refs:
            return x_a
        h = H if full else h2
        ya = y0 if (full or top) else y0 + h2
        A = zone_area(refs, dims)
        mx = max(max(dims[r]) for r in refs)
        w = max(A / (2 * fill) / h, mx + margin, min_w if full else 0)
        for _ in range(3):
            xa, xb = (x_a, x_a + w) if x_b_dir > 0 else (x_a - w, x_a)
            z = [round(xa, 3), round(ya, 3), round(xb, 3), round(ya + h, 3)]
            lost = sum(overlap(z, o) for o in obstacles)
            w2 = max(w, (A / (2 * fill) + lost) / h)
            if abs(w2 - w) < 1e-6:
                break
            w = w2
        xa, xb = (x_a, x_a + w) if x_b_dir > 0 else (x_a - w, x_a)
        z = [round(xa, 3), round(ya, 3), round(xb, 3), round(ya + h, 3)]
        lost = sum(overlap(z, o) for o in obstacles)
        out[name] = {'zone': z, 'refs': list(refs), 'group': gname, 'lost_mm2': round(lost, 2), 'fill': round(A / (2 * ((z[2] - z[0]) * (z[3] - z[1]) - lost)), 3)}
        return xb if x_b_dir > 0 else xa

    for sd, d in (('R', 1), ('L', -1)):
        edge = (j6_rect[2] + 1.0) if d > 0 else (j6_rect[0] - 1.0)
        brs = [g for g, v in groups.items() if v['kind'] == 'branch' and side_of(g) == sd]
        ins = [r for r in groups['pw_in']['refs'] if side_of(('in', r)) == sd]
        regs = sorted((g for g, v in groups.items() if v['kind'] == 'regulator' and side_of(g) == sd), key=order_key)
        b_refs = [r for g in brs for r in groups[g]['refs']]
        e0 = tile(f'pw_in_{sd}', ins, 'pw_in', edge, d, True)
        e1 = tile('pw_' + '_'.join(g[3:] for g in brs) if brs else f'pw_br_{sd}', b_refs, brs[0] if brs else '', edge, d, False)
        cur = e0 if d > 0 and e0 > e1 else (e1 if d > 0 else min(e0, e1)) if (ins or b_refs) else edge
        cur = max(e0, e1) if d > 0 else min(e0, e1)
        i = 0
        while i < len(regs):
            if i + 1 < len(regs):
                a = tile('pw_' + regs[i][3:], groups[regs[i]]['refs'], regs[i], cur, d, True)
                b = tile('pw_' + regs[i + 1][3:], groups[regs[i + 1]]['refs'], regs[i + 1], cur, d, False)
                cur = max(a, b) if d > 0 else min(a, b)
                i += 2
            else:
                cur = tile('pw_' + regs[i][3:], groups[regs[i]]['refs'], regs[i], cur, d, True, full=True)
                i += 1
    return out
