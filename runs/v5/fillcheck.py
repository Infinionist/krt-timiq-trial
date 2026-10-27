#!/usr/bin/env python3
"""fillcheck.py : plan v5 fit proof (Infinionist 10-27). Pure functions, no I/O; run with KRT's venv python (shapely). Imported by gate.py and the tests.

For every zone of the intent (a can interior, the power supergroup) and for the free region outside the cans:

    fill = (sum over the members on a face of (w + c) x (h + c)) / (usable area of that face)

  (w, h)   the part's courtyard rect as KRT grades it (preflight_probe.py 'dims': KRT's own state.parts[ref].rect(), generated courtyards included)
  c        KRT's own legality clearance for the board (0.2 mm, probe 'clearance'): the "with clearance" currency of KRT's plan_zone_crowded rule, so a pair of
           parts needs its two courtyards plus c between them. Every part is counted this way: no extra "spacing" fudge.
  usable   the zone rect minus what is not the members' to use on that face: keep-outs that apply to that face and do not allow all the members (mounting holes,
           wall band, other cans), the courtyards of the fixed parts standing there (J6, J5, the LEDs), cut to the board envelope minus the edge clearance.
           The zone's tolerance is NOT counted as room (it is a safety margin for the grade, not area the parts may rely on).

Faces. A block with `side` puts all its members on that face. Otherwise a member stands on the face it has on the placing board (probe 'side'), unless a
group lists it `flippable`: then it may take either. Plan v5b (Infinionist 10-27; the rule is written in faces_v5.py): a can's small passives may be listed flippable. A listed part
is counted on the BACK:
    fill F  = loadF / usableF                   (every flippable part flipped: the front the placer is left with)
    fill B  = (loadB + flex) / usableB          (every flippable part flipped: inside the can rect, minus what stands there already)
    fill    = max(fill F, fill B)               (fill F0 = (loadF + flex) / usableF is the front with nothing flipped, for the table)
The verdict is against LIMIT (0.65), a number Infinionist gave (0.6-0.65 for a single face) and the lead's rule of thumb for what an annealer legalises with fixed shapes; above
WARN (0.55) = KRT's own CROWDED_UTILISATION (placement/options.py: "typically <= 0.55 to route") the row is flagged TIGHT. Nothing here moves a part: it only measures.
"""
import math

LIMIT = 0.65
WARN = 0.55
SMALL_PASSIVE_MM2 = 20.0       # a passive below this courtyard area may be listed flippable when the fit needs it (plan v5, Infinionist 10-27 call 2)


def _box(r):
    from shapely.geometry import box
    return box(r[0], r[1], r[2], r[3])


def _circle_box(c):
    return _box([c[0] - c[2], c[1] - c[2], c[0] + c[2], c[1] + c[2]])


def keepout_geom(k):
    """a keep-out as a shapely geometry: a rect, or a circle (the real circle, 64 segments)."""
    if k.get('rect'):
        return _box(k['rect'])
    if k.get('circle'):
        from shapely.geometry import Point
        c = k['circle']
        return Point(c[0], c[1]).buffer(c[2], 32)
    return None


def obstacles(face, members, intent, probe):
    """[shapely geom]: what is not the members' to use on `face`: keep-outs that apply to that face and do not allow all the members, and the courtyards of the fixed
    parts standing on that face (not the members themselves, the point markers MK*, nor BOX1, the pin frame over the whole box)."""
    mem = set(members)
    cut = []
    for k in intent.get('keepouts') or []:
        if face not in (k.get('sides') or ['F', 'B']):
            continue
        if mem and mem <= set(k.get('allow') or []):
            continue
        g = keepout_geom(k)
        if g is not None:
            cut.append(g)
    rects, sides = probe.get('rects') or {}, probe.get('side') or {}
    for r in probe.get('fixed') or []:
        if r in mem or r.startswith('MK') or r == 'BOX1' or r not in rects:
            continue
        if sides.get(r, 'F') != face:
            continue
        cut.append(_box(rects[r]))
    return cut


def base_geom(zone, intent, probe, edge_clearance=None):
    """the zone rect (None: the whole envelope) cut to the envelope minus the board edge clearance."""
    env = (intent.get('envelope') or {}).get('rect')
    ec = probe.get('edge_clearance') if edge_clearance is None else edge_clearance
    ec = 0.5 if ec is None else ec
    base = _box(zone) if zone else None
    if env:
        e = _box([env[0] + ec, env[1] + ec, env[2] - ec, env[3] - ec])
        base = e if base is None else base.intersection(e)
    assert base is not None, 'no zone and no envelope'
    return base


def usable_geom(zone, face, members, intent, probe, edge_clearance=None):
    """shapely geometry of the usable room of `zone` on `face` for `members` (see the module doc). zone=None: the envelope (the free region)."""
    from shapely.ops import unary_union
    base = base_geom(zone, intent, probe, edge_clearance)
    cut = obstacles(face, members, intent, probe)
    return base.difference(unary_union(cut)) if cut else base


def member_loads(block, groups, probe):
    """(loadF, loadB, flex, n, detail): mm2 with clearance of the members that must be on F, on B, and that may go either way."""
    dims, sides = probe.get('dims') or {}, probe.get('side') or {}
    c = probe.get('clearance') or 0.0
    flex_refs = {r for g in (groups or {}).get('groups', []) for r in (g.get('flippable') or [])}
    fixed_side = block.get('side') if block.get('side') in ('F', 'B') else None
    lf = lb = fx = 0.0
    missing = []
    for r in block.get('refs') or []:
        if r not in dims:
            missing.append(r)
            continue
        a = (dims[r][0] + c) * (dims[r][1] + c)
        if fixed_side:
            if fixed_side == 'F':
                lf += a
            else:
                lb += a
        elif r in flex_refs:
            fx += a
        elif sides.get(r, 'F') == 'F':
            lf += a
        else:
            lb += a
    return lf, lb, fx, len(block.get('refs') or []), missing


def verdict(fill, limit=LIMIT, warn=WARN):
    return 'FAIL' if fill > limit + 1e-9 else ('TIGHT' if fill > warn + 1e-9 else 'ok')


def row_for(name, kind, block, zone, groups, intent, probe, limit=LIMIT):
    lf, lb, fx, n, missing = member_loads(block, groups, probe)
    refs = block.get('refs') or []
    uf = usable_geom(zone, 'F', refs, intent, probe).area
    ub = usable_geom(zone, 'B', refs, intent, probe).area
    ratio = lambda load, use: (load / use if use > 0 else math.inf) if load else 0.0
    fill_f0 = ratio(lf + fx, uf)
    fill_f = ratio(lf, uf)                  # the flippable parts all on the back
    fill_b = ratio(lb + fx, ub)             # ... and the back with them
    fill = max(fill_f, fill_b)
    nflex = len({r for g in (groups or {}).get('groups', []) for r in (g.get('flippable') or [])} & set(refs))
    return {'name': name, 'kind': kind, 'n': n, 'zone_mm2': round(((zone[2] - zone[0]) * (zone[3] - zone[1])) if zone else 0.0, 1), 'usable_F_mm2': round(uf, 1), 'usable_B_mm2': round(ub, 1),
            'load_F_mm2': round(lf, 1), 'load_B_mm2': round(lb, 1), 'flex_mm2': round(fx, 1), 'n_flex': nflex, 'fill_F0': round(fill_f0, 3), 'fill_F': round(fill_f, 3), 'fill_B': round(fill_b, 3),
            'fill': round(fill, 3), 'limit': limit, 'status': verdict(fill, limit),
            'face': block.get('side') or ('F' if not lb and not fx else 'F/B' if lb or fx else 'F'), 'missing': missing}


def fill_table(intent, groups, probe, limit=LIMIT, free_refs=None):
    """[row]: one per zoned block, plus the 'free' row (every non-fixed part that is a member of no can block, on the envelope minus the can keep-outs, holes, band
    and fixed parts). free_refs: override the free members (tests)."""
    rows = []
    zoned = [b for b in intent.get('blocks', []) if b.get('zone') and b.get('refs')]
    for b in zoned:
        kind = 'can' if b['name'].startswith('can') else 'power' if b['name'].startswith('power') else 'zone'
        rows.append(row_for(b['name'], kind, b, b['zone'], groups, intent, probe, limit))
    in_can = {r for b in zoned if b['name'].startswith('can') for r in b['refs']}
    fixed = set(probe.get('fixed') or [])
    if free_refs is None:
        free_refs = [r for r in (probe.get('dims') or {}) if r not in in_can and r not in fixed]
    # the can keep-outs allow their members only: for the free parts they are cut by usable_geom already (the free parts are not in their allow lists)
    rows.append(row_for('free (everything outside the cans)', 'free', {'refs': free_refs}, None, groups, intent, probe, limit))
    return rows


def fill_problems(intent, groups, probe, limit=LIMIT):
    """{block: problem}: every row over the limit. (The old plan v4 both-faces 0.5 check is gone: single face, with clearance, usable area.)"""
    bad = {}
    for r in fill_table(intent, groups, probe, limit):
        if r['status'] == 'FAIL':
            bad[r['name']] = (f"fill F {r['fill_F']:.2f} / B {r['fill_B']:.2f} (flippable parts flipped; front with none flipped {r['fill_F0']:.2f}) > {limit:g} ({r['n']} parts, {r.get('n_flex', 0)} flippable, load F {r['load_F_mm2']:.0f} / B {r['load_B_mm2']:.0f} / flippable {r['flex_mm2']:.0f} mm2 with clearance, "
                              f"usable F {r['usable_F_mm2']:.0f} / B {r['usable_B_mm2']:.0f} mm2)")
    return bad


def format_table(rows):
    """the fill table: per zone the front fill with nothing flipped (F0), the front (F) and the back (B) with the flippable parts flipped, and the verdict on the larger of F and B."""
    out = [f"{'zone':34s} {'face':4s} {'n':>3s} {'flip':>4s} {'usable F':>8s} {'usable B':>8s} {'load F':>7s} {'load B':>7s} {'F0':>5s} {'F':>5s} {'B':>5s} {'limit':>5s}  verdict"]
    for r in rows:
        out.append(f"{r['name'][:34]:34s} {r['face']:4s} {r['n']:3d} {r.get('n_flex', 0):4d} {r['usable_F_mm2']:8.0f} {r['usable_B_mm2']:8.0f} {r['load_F_mm2']:7.0f} {r['load_B_mm2'] + r['flex_mm2']:7.0f} "
                   f"{r['fill_F0']:5.2f} {r['fill_F']:5.2f} {r['fill_B']:5.2f} {r['limit']:5.2f}  {r['status']}")
    return out


# ---------------------------------------------------------------- the face rules (Infinionist 10-27 call 2)
def face_problems(intent, groups, probe, cans, large_mm2=SMALL_PASSIVE_MM2, netinfo=None, rf_parts=None):
    """{key: problem}. The v5b face rule (faces_v5.py docstring). For every can:
      * its group can<J> lists no part flippable  -> the group AND the block have side F (KRT: a declared side overrides flippable, so a can that is pinned says F);
      * its group lists parts flippable           -> the group and the block have NO side, every listed part is a member of the can, a small SMD passive (R, C, FB; courtyard
        < large_mm2) and not RF-path (netinfo + rf_parts: faces_v5.rf_path; without them only the class and size are checked), and cans.json says the same list;
      * no part of the can is flippable in another group, and every member starts on F on the placing board.
    Outside the cans: a big part (U, L, J, or a courtyard >= large_mm2) is not flippable and not on B."""
    import faces_v5
    bad = {}
    gby = {g['name']: g for g in groups.get('groups', [])}
    flex = {}
    for g in groups.get('groups', []):
        for r in g.get('flippable') or []:
            flex.setdefault(r, []).append(g['name'])
    side = probe.get('side') or {}
    dims = probe.get('dims') or {}
    ni = netinfo or {'values': {}, 'nets': {}, 'footprints': {}}
    blocks = {b.get('name'): b for b in intent.get('blocks', [])}
    in_can = set()
    for can, c in cans.items():
        members = list(c.get('members') or [])
        in_can |= set(members)
        g = gby.get(f'can{can}')
        b = blocks.get(f'can{can}')
        flips = list((g or {}).get('flippable') or [])
        if g is None:
            bad[f'{can}/group'] = f'no group can{can} in groups.json (a can is one KRT group)'
        else:
            if flips:
                if g.get('side') is not None:
                    bad[f'{can}/group-side'] = f"group can{can} lists {len(flips)} part(s) flippable and has side {g.get('side')!r}: a declared side overrides flippable in KRT (placement/faces.py)"
            elif g.get('side') != 'F':
                bad[f'{can}/group-side'] = f"group can{can} has side {g.get('side')!r}, not 'F' (it lists nothing flippable: members must stand on top, under the can)"
            miss = sorted(set(members) - set(g.get('refs') or []))
            if miss:
                bad[f'{can}/group-refs'] = f'{len(miss)} member(s) not in group can{can}: {miss[:6]}'
        if b is None:
            bad[f'{can}/block-side'] = f'no block can{can}'
        elif flips and b.get('side') is not None:
            bad[f'{can}/block-side'] = f"block can{can} has side {b.get('side')!r} but its group lists {len(flips)} part(s) flippable (a block side overrides flippable)"
        elif not flips and b.get('side') != 'F':
            bad[f'{can}/block-side'] = f"block can{can} has side {b.get('side')!r}, not 'F'"
        if sorted(c.get('flippable') or []) != sorted(flips) or (c.get('side') == 'F') == bool(flips):
            bad[f'{can}/cans-json'] = f"cans.json says side {c.get('side')!r}, flippable {len(c.get('flippable') or [])}; the group lists {len(flips)} flippable (designer_check reads cans.json)"
        for r in flips:
            if r not in members:
                bad[f'{can}/flippable/{r}'] = f'{r} is listed flippable in can{can} but is not a member of the can (a bottom part must belong to its own can)'
                continue
            why = faces_v5.ineligible_reason(r, ni, dims, rf_parts, large_mm2)
            if why and not (why == 'no courtyard size' and not dims):
                bad[f'{can}/flippable/{r}'] = f'{r} must stay on the front, locked, and is listed flippable: {why}'
        for r in members:
            others = [n for n in flex.get(r, []) if n != f'can{can}']
            if others:
                bad[f'{can}/flippable/{r}'] = f'can member {r} is listed flippable in another group {others}'
            if side.get(r) == 'B':
                bad[f'{can}/on-B/{r}'] = f'can member {r} stands on B on the placing board (every part starts on the front)'
    fixed = set(probe.get('fixed') or [])
    for r, a in ((r, dims[r][0] * dims[r][1]) for r in dims):
        if r in in_can or r in fixed:
            continue
        big = a >= large_mm2 or r[0] in 'ULJ'
        if big and r in flex:
            bad[f'outside/flippable/{r}'] = f'big part {r} ({a:.0f} mm2) is listed flippable in {flex[r]}'
        if big and side.get(r) == 'B':
            bad[f'outside/on-B/{r}'] = f'big part {r} ({a:.0f} mm2) stands on B on the placing board'
    return bad


def tile_problems(intent):
    """{name: problem}: no power tile (a pw_* block with a zone): power is groups + one loose supergroup (Infinionist 10-27 call 1)."""
    return {f"tile/{b['name']}": 'a pw_* power tile with a zone (plan v5 deletes them: power = groups, location by loose rows / anchored seeds, at most one loose supergroup zone)'
            for b in intent.get('blocks', []) if str(b.get('name', '')).startswith('pw_') and b.get('zone')}


def zone_problems(intent, cans):
    """{key: problem}: can interior blocks have tolerance 0 (a part must stand fully inside the can: a 0.5 mm default tolerance let U13 stand on the J9 frame pads),
    no block of the intent is exclusive, the supergroup (power*) has a generous tolerance and no side."""
    bad = {}
    blocks = {b.get('name'): b for b in intent.get('blocks', [])}
    for can in cans:
        b = blocks.get(f'can{can}')
        if b is not None and b.get('tolerance_mm') != 0.0:
            bad[f'{can}/tolerance'] = f"block can{can} tolerance_mm {b.get('tolerance_mm')!r}: must be 0.0 (the default 0.5 puts parts on the can's frame pads: run v4 U13 on J9)"
    return bad


def pose_exists(zone, w, h, cut):
    """True when a w x h box has a position inside `zone` clear of every obstacle geometry in `cut` (each grown by its bounding box: exact for rects, conservative for circles).
    The centre must lie in the zone shrunk by the half box, outside every obstacle's bbox grown by the half box."""
    from shapely.geometry import box as sbox
    from shapely.ops import unary_union
    if w > zone[2] - zone[0] + 1e-9 or h > zone[3] - zone[1] + 1e-9:
        return False
    centres = sbox(zone[0] + w / 2, zone[1] + h / 2, zone[2] - w / 2, zone[3] - h / 2)
    grown = [sbox(g.bounds[0] - w / 2, g.bounds[1] - h / 2, g.bounds[2] + w / 2, g.bounds[3] + h / 2) for g in cut if not g.is_empty]
    free = centres.difference(unary_union(grown)) if grown else centres
    # a degenerate (zero-area) free set is a pose too: the box exactly fills the zone
    return (not free.is_empty) and (free.area > 1e-6 or centres.area <= 1e-9 or free.length > 0)


def fit_problems(intent, probe):
    """{block/ref: problem}: for every zoned block, each member's box (courtyard united with its pad-copper box) has a pose in the USABLE room of its zone on its face at
    some quarter turn. A can whose keep-outs, holes or fixed parts leave no pose for U4 (run v3: 5.3 mm past the zone) fails here, by name, before any seed."""
    bad = {}
    dims, pads, rects, sides = probe.get('dims') or {}, probe.get('padbox') or {}, probe.get('rects') or {}, probe.get('side') or {}
    for b in intent.get('blocks', []):
        z = b.get('zone')
        if not z or not b.get('refs'):
            continue
        face_of = lambda r: b['side'] if b.get('side') in ('F', 'B') else sides.get(r, 'F')
        cuts = {f: obstacles(f, b['refs'], intent, probe) for f in ('F', 'B')}
        for r in b['refs']:
            if r not in dims:
                bad[f"{b['name']}/{r}"] = 'no courtyard dimensions for this member (not on the board?)'
                continue
            w, h = dims[r]
            if r in pads and r in rects:       # union with the pad box: a pad that reaches past the courtyard needs that room too
                a, p = rects[r], pads[r]
                w, h = max(a[2], p[2]) - min(a[0], p[0]), max(a[3], p[3]) - min(a[1], p[1])
            if not (pose_exists(z, w, h, cuts[face_of(r)]) or pose_exists(z, h, w, cuts[face_of(r)])):
                bad[f"{b['name']}/{r}"] = (f'box {w:.2f} x {h:.2f} mm (courtyard + pads) has no pose in the usable room of zone '
                                           f'{z[2] - z[0]:.2f} x {z[3] - z[1]:.2f} mm on {face_of(r)} at either quarter turn')
    return bad


def flippable_needed(rows, groups, probe, intent, limit=WARN, small_mm2=SMALL_PASSIVE_MM2):
    """Which small passives must be listed flippable, decided by the fill, not by taste (Infinionist 10-27 call 2).
    For every row over `limit` that is not a can (cans are F only, never flippable): the smallest SMD passives (R, C, FB; courtyard < small_mm2) of its members, smallest first,
    until the F-side fill with them on B is back to `limit` or the B side would pass it. Returns {block name: [ref]} (empty when nothing needs it)."""
    out = {}
    dims = probe.get('dims') or {}
    c = probe.get('clearance') or 0.0
    for r in rows:
        if r['kind'] == 'can' or r['fill'] <= limit:
            continue
        blocks = {b.get('name'): b for b in intent.get('blocks', [])}
        refs = (blocks.get(r['name']) or {}).get('refs') if r['kind'] != 'free' else None
        if refs is None:
            continue
        cands = sorted((x for x in refs if x[0] in 'RC' and dims.get(x) and dims[x][0] * dims[x][1] < small_mm2), key=lambda x: (dims[x][0] * dims[x][1], x))
        loadF, uF = r['load_F_mm2'], max(r['usable_F_mm2'], 1e-9)
        loadB, uB = r['load_B_mm2'], max(r['usable_B_mm2'], 1e-9)
        pick = []
        for x in cands:
            if loadF / uF <= limit:
                break
            a = (dims[x][0] + c) * (dims[x][1] + c)
            if (loadB + a) / uB > limit:
                break
            loadF -= a
            loadB += a
            pick.append(x)
        out[r['name']] = pick
    return out
