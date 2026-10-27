#!/usr/bin/env python3
"""plan_v3.py : the pure parts of TimIQ plan v3 (anchors, power zone, chains, keep-away, faces). Imported by build_inputs.py and by the tests; no I/O of its own
beyond reading the boards it is handed. Tables first (every call written down with its reason), functions after.

Run with the system python3 (pcbnew)."""
import math
import re

# ---- item 2: anchors. One main IC (or pair) per can; the zone is a LOOSE start (Infinionist) ----
ANCHORS = {
    'J7': {'ics': ['U1'], 'why': 'LMX2541 PLL/VCO: the can is built around it (34 of the can\'s passives sit on its pins); the VCXO U2 follows it (row U2 near R13)'},
    'J8': {'ics': ['U16'], 'why': 'HMC1097 IQ modulator: main device of J8 (IQ mod sheet); the U21-U27 mixer chain follows by ordered chain rows'},
    'J9': {'ics': ['U10', 'U11'], 'why': 'DAC-output op-amp pair U10/U11: 8 + 8 passives on their local nets (DAC output stage C45-C50, R50-R57) against 6 + 6 on the LT6600 filters U14/U15 '
                                         '(netrows ic_candidates), so U10/U11 are the DAC IF circuit\'s centre'},
    'J10': {'ics': ['U20'], 'why': 'HMC705 divider U20: the last stage, the only one whose outputs (C96/C97) leave the can for SMAs J3/J4; U18 and U19 chain back from it'},
    'J11': {'ics': ['U29'], 'why': 'ADS8694 ADC: the can\'s main device (16 passives; the U28 driver and U30 reference serve it)'},
    'J12': {'ics': ['U4'], 'why': 'LTC2758 dual DAC: the can\'s main device (27 passives on its local nets)'},
}
ANCHOR_FRAC = 0.74         # zone side = 0.74 x the can interior side -> 55 % of the interior area (the plan asked for 50-60 %)
ANCHOR_MARGIN = 2.0        # plan v4: the anchor point is the centre of the room an anchor IC (courtyard + this much a side) leaves in the can, shifted toward the exit vector
ANCHOR_PULL_MM = 7.0       # plan v4 (Infinionist 10-27, no exclusive zones): the anchor IC's proximity row to its marker, body to body: a pull, not a wall (6-8 mm)
MARKER_PREFIX = 'MK'       # the fixed anchor markers MK7..MK12 (one per can J7..J12): a 0.2 mm point courtyard and one 0.1 mm pad (KRT ignores a pad-less part), no net, in the anchor IC's group

# ---- item 2: power zone near J6 ----
POWER_GROUPS = ['power_in', 'ldo_pos', 'ldo_neg']      # groups.json sheets: J6 filters, five positive and two negative LDOs, their caps
POWER_STRIP = [112.0, 64.0, 256.4, 94.4]       # plan v5: the ONE loose power supergroup zone = the top strip above the box across the board width (envelope x 109.2..259.2, y from 63.4; the
                                               # wall band starts at y 94.95): the human put the same 75 parts in the middle of it. Plan v4 packed 11 tiles into [134, 64, 252, 94.4].
POWER_ZONE = POWER_STRIP
POWER_TOL = 4.0            # plan v5: the supergroup's tolerance_mm ("generous": a part 4 mm out of the strip is not graded; the board edge above and the wall band below stop it anyway)
LOOSE_REG_FILTER_MM = 25.0 # plan v5: regulator -> the filter that feeds its rail (part row, pad edge); the human board has them up to 20.4 mm apart
LOOSE_J6_MM = 10.0         # plan v5: the input group's pin rows to J6 (C143-C145, C148-C150, L12-L14), 3 mm in plan v4, loose now
POWER_REGS = ['U39', 'U40', 'U41', 'U42', 'U43', 'U44', 'U45']
POWER_FILTERS = ['L12', 'L13', 'L14']                  # the three NFM41 power-entry filters at J6 pins 1, 3, 5
PART_MM = 5.0
PIN_MM = 3.0               # plan v3 item 5 (was 2.0)

# ---- item 5: parts that move into a can ----
U3_OVERRIDE = {'refs': ['R14', 'R16', 'R17', 'R165', 'C20'], 'can': 'J8',
               'reason': 'U3\'s own LO-splitter input network (C20 DC block from the J2 ext-VCO SMA, R165 shunt, R16/R17/R14 pad network): moves with U3 into J8 (plan v3 item 5)'}

# ---- item 3: ordered chains (part rows, link by link) inside ONE can; each (ref, near, why) ----
CHAINS = [
    ('J1 ref-in', [('R8', 'C3', 'R8 (shunt on the J1 net) sits at the DC block C3, as the human has it (3.9 mm from U1), not at the SMA'),
                   ]),
    ('J2 ext-VCO', [('R165', 'C20', 'R165 shunts the J2 net at the DC block C20 (item 5: with U3 in J8)'),
                    ]),
    ('VCXO', [('U2', 'R13', 'U2 reaches U1 through R13 (U2 pad 1 net C17-Pad1 -> R13 -> U1 pin 15 net): U2 follows R13, R13 follows U1 pin 15')]),
    ('LO to IQ mod', [('U3', 'C63', 'splitter U3 pin 9 -> C63 -> U16 pin 3 (the IQ modulator LO input)')]),
    ('IQ out to dividers', [('U17', 'C70', 'IQ modulator U16 pin 16 -> C70 -> splitter U17')]),
    ('LO to mixer branch A', [('U23', 'C108', 'U21 amp output -> C108 -> pad U23'),
                              ('U24', 'U23', 'U23 -> quadrature splitter U24 (direct net)'),
                              ('U26', 'U24', 'U24 pin 4 -> mixer U26 (direct net)'),
                              ('U27', 'U24', 'U24 pin 6 -> mixer U27 (direct net)')]),
    ('LO to mixer branch B', [('U17', 'C99', 'splitter U17 -> C99 -> amp U22'),
                              ('U25', 'C109', 'U22 amp output -> C109 -> splitter U25'),
                              ('U26', 'U25', 'U25 pin 7 -> mixer U26 (direct net)'),
                              ('U27', 'U25', 'U25 pin 9 -> mixer U27 (direct net)')]),
    ('divider chain', [('U19', 'C80', 'U18 -> C80/C81 -> U19'),
                       ('U20', 'C88', 'U19 -> C88/C89 -> U20 (the J10 anchor)')]),
    ('ADC driver', [('U28', 'R123', 'U28 output -> R123 -> U29 pin 16')]),
]
# existing rows the chains replace: a row that pins a shunt to the far-away SMA contradicts the chain (R8 / R165 sit at their DC blocks)
DROP_ROWS = [('R8', 'J1'), ('R165', 'J2')]

# ---- item 3: keep-away. Declared in the design brief (route.py prices it too) and compiled into the intent ----
KEEP_AWAY_GAP = 3.0        # KRT's own derived default (board_context emc_roles proposals use 3 mm = twice route.py's --keep-away-free)
SENSITIVE = {
    'RF to the SMA notches J1-J4': ['Net-(C3-Pad2)', 'Net-(C20-Pad1)', 'Net-(C96-Pad2)', 'Net-(C97-Pad2)'],
    'LO / PLL out': ['/TOP/PLL/PLL_IN', '/TOP/PLL/PLL_OUT', 'Net-(C20-Pad2)', '/TOP/IQ modulator/PLLout1', '/TOP/Frequency mixers/PLLout0'],
    'DAC I/Q outputs': ['/TOP/DAC Interface/DAC_I', '/TOP/DAC Interface/DAC_Q'],
    'ADC inputs': ['Net-(C110-Pad1)', 'Net-(C111-Pad1)'],
}
POWER_AGGRESSOR_NETS = ['24V', '-24V', '7V5', 'Net-(C143-Pad1)', 'Net-(C144-Pad1)', 'Net-(C145-Pad2)']   # the regulators' raw input rails and the entry-filter nodes
DIGITAL_CHIPS = ['U31', 'U32', 'U33', 'U34', 'U35', 'U36', 'U37', 'U38']        # LVDS receivers/drivers and level shifters; J5 is the other digital side
LOCAL_MAX = 12             # a net with more pads than this is a rail, not a signal


def knet(name):
    """a net name in route.py's keep-away syntax: no spaces (written '?', which the net matcher reads as any one character)."""
    return name.replace(' ', '?')


def digital_nets(nets):
    """{net: pads} of the digital side: every non-GND net on J5, and every local net (<= LOCAL_MAX pads) on U31-U38."""
    out = set()
    for n, pads in nets.items():
        if n == 'GND' or not n:
            continue
        refs = {r for r, _ in pads}
        if 'J5' in refs or (refs & set(DIGITAL_CHIPS) and len(pads) <= LOCAL_MAX):
            out.add(n)
    return sorted(out)


def keep_away_rules(nets, gap=KEEP_AWAY_GAP):
    """[(rule, why)]: digital -> sensitive, power input rails -> sensitive. Raises when a net named in the tables is not on the board or sits on both sides."""
    sens = sorted({n for v in SENSITIVE.values() for n in v})
    dig = digital_nets(nets)
    missing = [n for n in sens + POWER_AGGRESSOR_NETS if n not in nets]
    if missing:
        raise ValueError(f'keep-away nets not on the board: {missing}')
    both = set(sens) & (set(dig) | set(POWER_AGGRESSOR_NETS))
    if both:
        raise ValueError(f'nets on both sides of a keep-away rule: {sorted(both)}')
    what = '; '.join(f"{k}: {len(v)}" for k, v in SENSITIVE.items())
    rules = [(f"{','.join(knet(n) for n in dig)}:{','.join(knet(n) for n in sens)}:{gap:g}",
              f'digital side ({len(dig)} nets: every net of J5 and the local nets of U31-U38) away from the sensitive nets ({what}); gap {gap:g} mm is KRT\'s derived default'),
             (f"{','.join(knet(n) for n in POWER_AGGRESSOR_NETS)}:{','.join(knet(n) for n in sens)}:{gap:g}",
              f'regulator input rails and power-entry filter nodes ({", ".join(POWER_AGGRESSOR_NETS)}) away from the sensitive nets; gap {gap:g} mm')]
    return rules, sens, dig


# ---- anchors: zone placement ----
def _centre(r):
    return ((r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0)


def exit_vector(can, anchors, members_of, nets, pos_of, can_zone, place_of=None):
    """(vx, vy, n_places, detail): mean unit vector from the can centre toward where its signals go (components in -1..1). Places, not parts, are counted once:
    a fixed connector, another can, or a free part's group-anchor connector (place_of(ref) -> id or None; pos_of(place id) -> (x, y)). Weights: a net on the anchor IC
    that reaches a place 1.0, the same one hop further through a passive 0.5, a net on any other member of this can (one hop only) 0.25; a place keeps its largest weight."""
    cx, cy = _centre(can_zone)
    by_ref = {}
    for n, pads in nets.items():
        for r, _p in pads:
            by_ref.setdefault(r, []).append(n)
    pas = re.compile(r'^(R|C|L|FB)\d+$')
    place_of = place_of or (lambda r: members_of.get(r) or r)
    best = {}

    def note(q, w):
        pl = place_of(q)
        if pl is None or pl == can or pos_of(pl) is None:
            return
        if best.get(pl, (0, None))[0] < w:
            best[pl] = (w, q)

    own = {r for r, c in members_of.items() if c == can}
    for src, w1, hop2 in [(a, 1.0, True) for a in anchors] + [(m, 0.25, False) for m in sorted(own - set(anchors))]:
        for n in by_ref.get(src, ()):
            if n == 'GND' or len(nets[n]) > LOCAL_MAX:
                continue
            for r, _p in nets[n]:
                if r == src or r in own:
                    if not (hop2 and r != src and r in own and pas.match(r)):
                        continue
                if r != src and r not in own:
                    note(r, w1)
                if hop2 and pas.match(r):
                    for n2 in by_ref.get(r, ()):
                        if n2 == 'GND' or n2 == n or len(nets[n2]) > LOCAL_MAX:
                            continue
                        for q, _ in nets[n2]:
                            if q != r and q not in anchors and q not in own:
                                note(q, 0.5)
    vec = []
    for pl, (w, q) in best.items():
        x, y = pos_of(pl)
        d = math.hypot(x - cx, y - cy)
        if d > 1e-6:
            vec.append((w * (x - cx) / d, w * (y - cy) / d, w, f'{pl}:{w:g}'))
    tw = sum(v[2] for v in vec)
    if not tw:
        return 0.0, 0.0, 0, []
    return sum(v[0] for v in vec) / tw, sum(v[1] for v in vec) / tw, len(vec), sorted(v[3] for v in vec)


def anchor_zone(can_zone, v, frac=ANCHOR_FRAC):
    """the anchor zone: a rectangle of side frac x the interior, centred, shifted by v x the free room on each axis (at most flush with the wall)."""
    w, h = can_zone[2] - can_zone[0], can_zone[3] - can_zone[1]
    aw, ah = w * frac, h * frac
    cx, cy = _centre(can_zone)
    sx = max(-1.0, min(1.0, v[0])) * (w - aw) / 2.0
    sy = max(-1.0, min(1.0, v[1])) * (h - ah) / 2.0
    return [round(cx + sx - aw / 2, 3), round(cy + sy - ah / 2, 3), round(cx + sx + aw / 2, 3), round(cy + sy + ah / 2, 3)]


def anchor_point(can_zone, v, dims, margin=2.0, pair_gap=2.0):
    """plan v4 (no anchor zone): (x, y) of the anchor marker = the centre the old anchor zone had: the can centre shifted toward the exit vector v by at most the room
    the anchor ICs (courtyard + margin a side, side by side with pair_gap) leave in the interior. Raises ValueError when they do not fit the interior."""
    z = anchor_zone_v4(can_zone, v, dims, margin, pair_gap)
    return round((z[0] + z[2]) / 2, 3), round((z[1] + z[3]) / 2, 3)


def anchor_zone_v4(can_zone, v, dims, margin=2.0, pair_gap=2.0):
    """plan v4 fix 3: the anchor zone is the anchor IC's courtyard plus `margin` on every side (a square of side max(w, h) + 2 margin, so it holds the IC at either quarter turn;
    two anchor ICs side by side with pair_gap between), centred on the can centre shifted toward the exit vector v by at most the free room, kept inside the can interior.
    dims = [(w, h)] of the anchor ICs' courtyards. Raises ValueError when it cannot fit the interior."""
    ds = [max(w, h) for w, h in dims]
    aw = sum(ds) + pair_gap * (len(ds) - 1) + 2 * margin
    ah = max(ds) + 2 * margin
    w, h = can_zone[2] - can_zone[0], can_zone[3] - can_zone[1]
    if aw > w or ah > h:
        raise ValueError(f'anchor zone {aw:.1f} x {ah:.1f} does not fit the can interior {w:.1f} x {h:.1f}')
    cx, cy = _centre(can_zone)
    sx = max(-1.0, min(1.0, v[0])) * (w - aw) / 2.0
    sy = max(-1.0, min(1.0, v[1])) * (h - ah) / 2.0
    return [round(cx + sx - aw / 2, 3), round(cy + sy - ah / 2, 3), round(cx + sx + aw / 2, 3), round(cy + sy + ah / 2, 3)]


# ---- faces ----
def is_large(ref, area, min_area=20.0):
    """a part that should start on the front: courtyard body >= min_area mm2, or an IC, inductor or connector."""
    return area >= min_area or ref[0] in 'ULJ' and re.match(r'^[ULJ]\d+$', ref) is not None


# ---- power rows (item 2): J6 pin -> filter (the existing 3 mm pin rows), filter -> regulator input (5 mm part rows), regulator -> its caps (5 mm) ----
def power_rows(nets, hpos, power_refs):
    """[(row, kind)] kind 'filter->regulator' | 'regulator->cap'. hpos = {ref: (x, y)} of the human board, used only to ORDER regulators (nearest first) and to pick
    the regulator of a cap whose net reaches several."""
    regs = set(POWER_REGS)
    d = lambda a, b: math.hypot(hpos[a][0] - hpos[b][0], hpos[a][1] - hpos[b][1])
    rows = []
    for filt in POWER_FILTERS:
        outs = [n for n, p in nets.items() if n != 'GND' and filt in {r for r, _ in p} and {r for r, _ in p} & regs]
        todo = sorted({r for n in outs for r, _ in nets[n] if r in regs})
        prev = filt
        while todo:
            nxt = min(todo, key=lambda r: (d(prev, r), r))
            todo.remove(nxt)
            rows.append(({'ref': nxt, 'near': prev, 'max_mm': PART_MM, 'basis': 'pad_edge',
                          'why': f"plan v3 power chain: {nxt} is a regulator fed through {filt}'s output net ({', '.join(outs)}); "
                                 f"{'the filter itself' if prev == filt else 'the previous regulator of the chain'} is the link ({PART_MM:g} mm part row)"},
                         'filter->regulator'))
            prev = nxt
    j6 = {r for n, p in nets.items() if n != 'GND' for r, _ in p if 'J6' in {x for x, _ in p}}
    for c in sorted((r for r in power_refs if re.match(r'^C\d+$', r) and r not in j6), key=lambda s: int(s[1:])):
        cand = {}
        for n, p in nets.items():
            if n == 'GND' or c not in {r for r, _ in p}:
                continue
            for r, _ in p:
                if r in regs:
                    cand.setdefault(r, n)
        if not cand:
            continue
        reg = min(cand, key=lambda r: (d(c, r), r))
        rows.append(({'ref': c, 'near': reg, 'max_mm': PART_MM, 'basis': 'pad_edge',
                      'why': f'plan v3 power chain: {c} is on {cand[reg]} with regulator {reg} (input/output cap of its rail; nearest such regulator in the human layout): {PART_MM:g} mm part row'},
                     'regulator->cap'))
    return rows
