#!/usr/bin/env python3
"""render_floorplan.py [--out PNG_PREFIX] : the floorplan picture for Infinionist's review (plan v3), NO placement involved. System python3 (pcbnew) + rsvg-convert.
Draws, from the v5 inputs only (cans.json, intent.json, holes.json, mechanical.json, the brief's keep_away rules, fixed.kicad_pcb):
  - board outline, the box (Hammond 1590Q), wall band (top view), lid window, mounting-hole keep-outs (radius and drill);
  - the six shield cans: footprint box (thin dotted), interior zone = member block (solid, labelled with sheet and member count);
  - the anchor marker of each can (plan v4, Infinionist 10-27: no anchor zone, nothing exclusive): a cross at the biased can centre with a dashed 7 mm pull circle, labelled with the anchor IC(s);
  - plan v5 (Infinionist 10-27): NO power tiles. The ONE loose power supergroup zone power_strip (the top strip above the box, dashed, its tolerance band lighter) and, per power group
    (pw_in, pw_7v5, pw_24v, pw_U39..pw_U45), a ring (anchored seed 1) and a diamond (anchored seed 2) at the point KRT's anchored start solves for that group from its wiring
    (preflight_probe.py "anchored": simple_anneal._anchors, nothing placed): the location suggestion Infinionist asked for. Each can: FRONT only, with its fill (gate fill table);
  - fixed parts (grey boxes, J1-J6 and the panel LEDs);
  - keep_away groups in two colours: AGGRESSOR (digital side + regulator input rails, magenta) and VICTIM (the sensitive RF / LO / DAC / ADC nets, teal):
    fixed parts on them are outlined (J5 digital, J6 power rails = aggressor; J1-J4 SMAs = victim), each can carries an A/V count chip, and a side panel
    lists, per can, the aggressor and victim parts inside it;
  - a legend.
Writes <prefix>.png (top view: with the wall band) and <prefix>_bottom.png (bottom view: no wall band; plan v5: every movable part stands on F, so only the fixed B parts show).
Needs gate.out.json (python3 gate.py --json gate.out.json, KRT venv: the fill table and the anchored starts) beside it.
(KRT's render_placement draws poses and keep-out circles of a PLACED board; it has no layer for a block zone, so this is SVG by hand.)"""
import argparse
import json
import os
import re
import subprocess
import sys

V5 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, V5)
import plan_v3  # noqa: E402
SC = 6.0                                  # px per mm
X0, Y0, X1, Y1 = 106.0, 54.0, 262.0, 236.0
PANEL = 420                               # px of side panel to the right of the board area
LEGEND = 218                              # px of legend below
BOX = (124.2124, 94.9478, 244.2124, 214.9478)
BAND = 2.75
WINDOW = (150.21, 148.95, 212.21, 190.95)
COL = {'J7': '#4c78a8', 'J8': '#f58518', 'J9': '#54a24b', 'J10': '#b279a2', 'J11': '#8c6d31', 'J12': '#17becf'}
AGG, VIC = '#c2185b', '#00695c'           # keep_away aggressor (magenta) / victim (dark teal): used for nothing else
POWER = '#f9a825'                         # regulator tiles pw_U39..pw_U45
POWER_BR = '#e65100'                      # input / branch tiles pw_in*, pw_7v5, pw_24v
FONT = 'DejaVu Sans, sans-serif'


def px(x, y):
    return (x - X0) * SC, (y - Y0) * SC


def rect(r, **kw):
    x, y = px(r[0], r[1])
    a = ' '.join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{(r[2]-r[0])*SC:.1f}" height="{(r[3]-r[1])*SC:.1f}" {a}/>'


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;')


def text(x, y, s, size=11, fill='#222', anchor='start', weight='normal', raw=False, halo=False):
    px_, py_ = (x, y) if raw else px(x, y)
    return f'<text x="{px_:.1f}" y="{py_:.1f}" font-family="{FONT}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}"{' stroke="#fff" stroke-width="3.5" stroke-opacity="0.9" paint-order="stroke" stroke-linejoin="round"' if halo else ''}>{esc(s)}</text>'


def chip(x, y, label, fill, stroke, color, size=11):
    """a small rounded label at board mm (x, y) (top-left)."""
    x_, y_ = px(x, y)
    w = 7.0 * len(label) * size / 11 + 8
    return (f'<rect x="{x_:.1f}" y="{y_:.1f}" width="{w:.1f}" height="{size+7}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            + text(x_ + 4, y_ + size + 1, label, size, color, weight='bold', raw=True))


def compress(refs):
    """['R2','R3','R4','R7','C1'] -> 'C1 R2-R4 R7' (same prefix, consecutive numbers)."""
    by = {}
    for r in refs:
        m = re.match(r'^([A-Z]+)(\d+)$', r)
        by.setdefault(m.group(1) if m else r, []).append(int(m.group(2)) if m else 0)
    out = []
    for p in sorted(by):
        ns = sorted(by[p])
        i = 0
        while i < len(ns):
            j = i
            while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
                j += 1
            out.append(f'{p}{ns[i]}' if j == i else f'{p}{ns[i]}-{p}{ns[j]}' if j > i + 1 else f'{p}{ns[i]} {p}{ns[j]}')
            i = j + 1
    return ' '.join(out)


def wrap(s, n):
    lines, cur = [], ''
    for w in s.split(' '):
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    return lines + ([cur] if cur else [])


def load():
    """(outline pts, fixed part boxes, aggressor/victim parts per rule) from the board and the brief."""
    import pcbnew
    import designer_check as dc
    b = pcbnew.LoadBoard(V5 + '/fixed.kicad_pcb')
    ps = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(ps, True)
    o = ps.Outline(0)
    outline = [(pcbnew.ToMM(o.CPoint(i).x), pcbnew.ToMM(o.CPoint(i).y)) for i in range(o.PointCount())]
    mech = json.load(open(V5 + '/mechanical.json'))['fixed']
    boxes = {}
    for f in mech:
        if f['ref'].startswith(('FIX', 'BOX', plan_v3.MARKER_PREFIX)):
            continue
        bb = b.FindFootprintByReference(f['ref']).GetBoundingBox(False)
        boxes[f['ref']] = tuple(pcbnew.ToMM(v) for v in (bb.GetX(), bb.GetY(), bb.GetRight(), bb.GetBottom()))
    parts = dc.parts_of(pcbnew, b)
    sides = dc.keep_away_sides(parts, V5 + '/fixed.design-brief.json')
    agg = sorted({r for sd in sides for v in sd['agg'].values() for r, _p in v})
    vic = sorted({r for sd in sides for v in sd['vic'].values() for r, _p in v})
    return outline, boxes, agg, vic, sides


def fcol(status):
    return {'FAIL': '#c62828', 'TIGHT': '#ef6c00', 'ok': '#2e7d32'}.get(status, '#333')


def build(side, cans, holes, boxes, outline, power, agg, vic, sides, gate, parts):
    W, H = (X1 - X0) * SC + PANEL, (Y1 - Y0) * SC + LEGEND
    bw = (X1 - X0) * SC
    fill = {r['name']: r for r in gate['fill_table']}
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" viewBox="0 0 {W:.0f} {H:.0f}">',
         '<rect width="100%" height="100%" fill="#ffffff"/>',
         '<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#8d6e63" stroke-width="2"/></pattern></defs>']
    pts = ' '.join(f'{px(x, y)[0]:.1f},{px(x, y)[1]:.1f}' for x, y in outline)
    o.append(f'<polygon points="{pts}" fill="#f7f7f2" stroke="#777" stroke-width="1.5"/>')
    o.append(rect(BOX, fill='none', stroke='#222', stroke_width=2.5))
    if side == 'F':
        for r in ((BOX[0], BOX[1], BOX[2], BOX[1] + BAND), (BOX[0], BOX[3] - BAND, BOX[2], BOX[3]),
                  (BOX[0], BOX[1] + BAND, BOX[0] + BAND, BOX[3] - BAND), (BOX[2] - BAND, BOX[1] + BAND, BOX[2], BOX[3] - BAND)):
            o.append(rect(r, fill='url(#hatch)', fill_opacity=0.6, stroke='none'))
    o.append(rect(WINDOW, fill='#1f77b4', fill_opacity=0.06, stroke='#1f77b4', stroke_width=2, stroke_dasharray='10,5'))
    o.append(text(WINDOW[0] + 1, WINDOW[1] - 1.0, 'lid window', 12, '#1f77b4'))
    late = []
    # the loose power supergroup (plan v5): ONE zone, dashed, tolerance band lighter; drawn on the top view only (everything is on F)
    sg = power['zone']
    tol = power['tol']
    if side == 'F':
        o.append(rect([sg[0] - tol, sg[1] - tol, sg[2] + tol, sg[3] + tol], fill=POWER, fill_opacity=0.06, stroke=POWER, stroke_width=1, stroke_dasharray='3,4'))
        o.append(rect(sg, fill=POWER, fill_opacity=0.12, stroke=POWER_BR, stroke_width=3, stroke_dasharray='14,7'))
        fr = fill.get('power_strip', {})
        late.append(text(sg[0] + 16.0, sg[3] - 3.2, f"power_strip: ONE loose supergroup, {power['n']} parts in {power['ngroups']} groups, tolerance {tol:g} mm, not exclusive", 12, '#5d3a00', 'start', 'bold', halo=True))
        late.append(text(sg[0] + 16.0, sg[3] - 0.9, f"front-face fill {fr.get('fill', 0):.2f} (limit {fr.get('limit', 0):g}); nothing flippable. Rings / diamonds: where KRT's anchored seeds 1 / 2 start each group", 10, '#5d3a00', halo=True))
        for gname, fam in power['groups'].items():
            colr = {'in': '#6d4c41', '7v5': '#e65100', '24v': '#6a1b9a'}[fam]
            for sd, shape in (('1', 'ring'), ('2', 'diamond')):
                for a_ in (gate.get('anchored') or {}).get(sd, []):
                    if a_['group'] != gname:
                        continue
                    x, y = px(a_['x'], a_['y'])
                    x = min(max(x, 4), bw - 4)
                    y = min(max(y, 4), (Y1 - Y0) * SC - 4)
                    if shape == 'ring':
                        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="#fff" fill-opacity="0.8" stroke="{colr}" stroke-width="3"/>')
                    else:
                        o.append(f'<path d="M{x:.1f} {y-9:.1f}L{x+9:.1f} {y:.1f}L{x:.1f} {y+9:.1f}L{x-9:.1f} {y:.1f}Z" fill="#fff" fill-opacity="0.8" stroke="{colr}" stroke-width="3"/>')
                    late.append(text((x / SC) + X0 + 1.4, (y / SC) + Y0 + 0.6, gname.replace('pw_', ''), 9, colr, 'start', 'bold', halo=True))
    # cans
    A_set, V_set = set(agg), set(vic)
    for can, c in cans.items():
        col = COL[can]
        members = set(c['members'])
        nA, nV = len(members & A_set), len(members & V_set)
        fr = fill.get(f'can{can}', {})
        o.append(rect(c['bbox'], fill='none', stroke=col, stroke_width=1.2, stroke_dasharray='2,3'))
        o.append(rect(c['zone'], fill=col, fill_opacity=0.14, stroke=(fcol(fr.get('status')) if side == 'F' and fr.get('status') == 'FAIL' else col), stroke_width=3))
        mk = c['anchor_marker']
        mx, my = px(mk['x'], mk['y'])
        o.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="{c["anchor_max_mm"] * SC:.1f}" fill="none" stroke="{col}" stroke-width="3" stroke-dasharray="12,6"/>')
        o.append(f'<path d="M{mx-9:.1f} {my:.1f}H{mx+9:.1f}M{mx:.1f} {my-9:.1f}V{my+9:.1f}" stroke="{col}" stroke-width="3"/>')
        o.append(text(mk['x'] + 0.9, my / SC + Y0 - 0.9, mk['ref'], 10, col, 'start', 'bold', halo=True))
        cx = c['zone'][0] + 1.0                             # labels in a left corner of the can interior, on the side away from the marker's pull circle
        cy = c['zone'][1] if mk['y'] >= (c['zone'][1] + c['zone'][3]) / 2 else c['zone'][3] - 17.8
        o.append(text(cx, cy + 3.0, f"{can}  {' + '.join(c['sheets'])}", 15, '#111', 'start', 'bold', halo=True))
        nfl = len(c.get('flippable') or [])
        o.append(text(cx, cy + 5.6, f"group can{can}: {len(c['members'])} members, " + (f"{nfl} small passives may go to B (rest locked on F)" if nfl else 'all on F (side F)') + (f" (+{len(c['optional'])} opt.)" if c['optional'] else ''), 10, '#333', 'start', halo=True))
        o.append(text(cx, cy + 8.0, (f"fill F {fr.get('fill_F', 0):.2f} (no flip {fr.get('fill_F0', 0):.2f}) / B {fr.get('fill_B', 0):.2f}  limit {fr.get('limit', 0):g}  {fr.get('status', '')}" if nfl
                                     else f"front fill {fr.get('fill', 0):.2f} / {fr.get('limit', 0):g}  {fr.get('status', '')}"), 13 if not nfl else 11, fcol(fr.get('status')), 'start', 'bold', halo=True))
        o.append(text(cx, cy + 10.2, f"anchor {' '.join(c['anchors'])}, pull to {mk['ref']} <= {c['anchor_max_mm']:g} mm (soft)", 9, col, 'start', halo=True))
        o.append(chip(c['zone'][0] + 1.0, c['zone'][3] - 4.0, f'A {nA}', '#fce4ec', AGG, AGG, 10))
        o.append(chip(c['zone'][0] + 8.0, c['zone'][3] - 4.0, f'V {nV}', '#e0f2f1', VIC, VIC, 10))
        o.append(text(c['bbox'][0] + 0.8, c['bbox'][1] + 1.6, f"{can} box {c['bbox'][2]-c['bbox'][0]:.1f}x{c['bbox'][3]-c['bbox'][1]:.1f}", 9, col))
    for h in holes:
        x, y = px(h['x'], h['y'])
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{h["radius"]*SC:.1f}" fill="#ff7f0e" fill-opacity="0.12" stroke="#ff7f0e" stroke-width="2" stroke-dasharray="5,3"/>')
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{h["drill"]/2*SC:.1f}" fill="#fff" stroke="#333" stroke-width="1.5"/>')
        o.append(text(h['x'], h['y'] + h['radius'] + 2.0, f"{h['name'].replace('hole-', '')} r{h['radius']:.2f}", 9, '#a65500', 'middle'))
    for ref, bb in boxes.items():
        if parts[ref]['face'] != side:
            continue
        stroke, sw = ('#222', 1)
        if ref in A_set:
            stroke, sw = AGG, 4
        elif ref in V_set:
            stroke, sw = VIC, 4
        o.append(rect(bb, fill='#555', fill_opacity=0.35, stroke=stroke, stroke_width=sw))
        lab = ref + (' (aggressor)' if ref in A_set else ' (victim)' if ref in V_set else '') + (' [on B]' if side == 'B' else '')
        cxm, lyy, anc = (bb[0] + bb[2]) / 2, bb[1] - 0.6, 'middle'
        if sg[0] <= cxm <= sg[2] and sg[1] <= lyy <= sg[3]:       # the default label spot is inside the supergroup strip: put it on the box
            lyy = (bb[1] + bb[3]) / 2
        o.append(text(cxm, lyy, lab, 10, stroke if sw > 1 else '#222', anc, 'bold' if sw > 1 else 'normal', halo=True))
    o += late
    o.append(text(222.0, 132.0, 'digital: J5 + U31-U38', 10, AGG, 'end', 'bold'))
    o.append(text(222.0, 134.4, '(group digital, free)', 9, AGG, 'end'))
    if side == 'B':
        o.append(text((X0 + X1) / 2, Y0 + 14.0, 'Nothing is placed on the back at the start:', 20, '#555', 'middle', 'bold', halo=True))
        o.append(text((X0 + X1) / 2, Y0 + 19.0, f"all {gate['n_movable']} movable parts start on F; only the {sum(len(c.get('flippable') or []) for c in cans.values())} small passives listed flippable "
                       f"({', '.join(f'{k} {len(c.get('flippable') or [])}' for k, c in cans.items() if c.get('flippable'))}) may end on B, inside their own can", 13, '#555', 'middle', halo=True))
    # side panel: the fill table, the faces rule, the power groups
    ox = bw + 14
    y = 24
    o.append(text(ox, y, 'Fit proof before any seed (gate.py)', 15, '#111', raw=True, weight='bold'))
    y += 16
    o.append(text(ox, y, 'fill = courtyards + clearance / usable; F / B shown', 10, '#555', raw=True))
    y += 20
    for r in gate['fill_table']:
        o.append(text(ox, y, r['name'].replace(' (everything outside the cans)', ' (all outside cans)')[:26], 11, '#111', raw=True))
        o.append(f'<rect x="{ox + 170}" y="{y-10}" width="110" height="11" fill="#eee" stroke="#bbb"/>')
        o.append(f'<rect x="{ox + 170}" y="{y-10}" width="{min(r["fill"], 1.0) * 110:.0f}" height="11" fill="{fcol(r["status"])}" fill-opacity="0.8"/>')
        o.append(f'<path d="M{ox + 170 + r["limit"] * 110:.1f} {y-12}V{y+3}" stroke="#000" stroke-width="2"/>')
        o.append(text(ox + 288, y, f"{r['fill_F']:.2f}/{r['fill_B']:.2f} {r['status']}", 11, fcol(r['status']), raw=True, weight='bold'))
        y += 17
    o.append(text(ox, y + 3, f"bar = larger of F / B; tick = limit {gate['limit']:g}; TIGHT > 0.55", 9, '#555', raw=True))
    y += 26
    o.append(text(ox, y, 'Faces', 13, '#111', raw=True, weight='bold'))
    y += 15
    for ln in wrap(f"Plan v5b (Infinionist 10-27). Every can is ONE KRT group. Inside a can every IC, every RF-path part and every part with courtyard >= 20 mm2 stays on F, locked; its small "
                   f"passives (R, C, FB) may go to B, only inside their own can. A can that needs flips has no group or block side (a side overrides flippable in KRT) and lists them: "
                   f"{', '.join(f'{k} {len(c['flippable'])}' for k, c in cans.items() if c.get('flippable'))}. "
                   f"Cans that fit keep side F. All {gate['n_movable']} movable parts start on F; nothing outside the cans is flippable.", 64):
        o.append(text(ox, y, ln, 10, '#333', raw=True))
        y += 12.5
    y += 10
    o.append(text(ox, y, 'Power groups (KRT groups; no tiles)', 13, '#111', raw=True, weight='bold'))
    y += 15
    for gname, info in power['info'].items():
        o.append(text(ox, y, f"{gname}: {info['n']} parts" + (f", {info['what']}" if info['what'] else ''), 10, '#333', raw=True))
        y += 12.5
    y += 6
    for ln in wrap('Location is loose: `near` hints between groups (pw_U* near their branch, branch near pw_in), rows only INSIDE a group (a row between groups is a membership claim in KRT), '
                   'the power_strip zone, and the anchored seeds.', 64):
        o.append(text(ox, y, ln, 10, '#555', raw=True))
        y += 12.5
    # legend
    ly = (Y1 - Y0) * SC + 20
    o.append(text(10, ly, f"TimIQ floorplan (plan v5b), {'TOP (F)' if side == 'F' else 'BOTTOM (B), not mirrored'} view. No placement: the cans are OFF the placing board. Every movable part starts on F.", 12, '#111', raw=True, weight='bold'))
    items = [('rect', dict(fill=COL['J7'], fill_opacity=0.25, stroke=COL['J7'], stroke_width=3), 'can interior = member block on F (tolerance 0); red outline = over the fill limit'),
             ('rect', dict(fill='none', stroke=COL['J7'], stroke_width=3, stroke_dasharray='12,6'), 'anchor marker MK<n> (cross) and its 7 mm pull circle (dashed): the can main IC is pulled to it, soft'),
             ('rect', dict(fill='none', stroke=COL['J7'], stroke_width=1.2, stroke_dasharray='2,3'), 'can footprint box 34.4 mm (keep-out)'),
             ('rect', dict(fill=POWER, fill_opacity=0.2, stroke=POWER_BR, stroke_width=3, stroke_dasharray='14,7'), 'power_strip: the ONE loose power supergroup zone (lighter dashed = its tolerance band)'),
             ('circ', dict(fill='#fff', stroke='#e65100', stroke_width=3), 'ring / diamond: where anchored seed 1 / 2 start a power group (brown input, orange 7V5, purple +-24V)'),
             ('rect', dict(fill='#555', fill_opacity=0.35, stroke='#222', stroke_width=1), 'fixed parts (J1-J6, panel LEDs); FIX and BOX1 not drawn'),
             ('circ', dict(fill='#ff7f0e', fill_opacity=0.2, stroke='#ff7f0e', stroke_width=2, stroke_dasharray='5,3'), 'hole keep-out (from the hole edge); white disc = drill'),
             ('rect', dict(fill='url(#hatch)', fill_opacity=0.6, stroke='none'), 'wall band 2.75 mm (top view only)'),
             ('rect', dict(fill='#1f77b4', fill_opacity=0.08, stroke='#1f77b4', stroke_width=2, stroke_dasharray='10,5'), 'lid window'),
             ('rect', dict(fill='#fce4ec', stroke=AGG, stroke_width=3), 'keep_away AGGRESSOR (digital side; regulator input rails): outline / chip A n'),
             ('rect', dict(fill='#e0f2f1', stroke=VIC, stroke_width=3), 'keep_away VICTIM (RF to SMA, LO/PLL, DAC I/Q, ADC inputs): outline / chip V n')]
    for i, (kind, attrs, label) in enumerate(items):
        cx_, cy_ = 10 + (i % 2) * (bw / 2 + 120), ly + 22 + (i // 2) * 28
        a = ' '.join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
        o.append(f'<rect x="{cx_}" y="{cy_}" width="34" height="16" {a}/>' if kind == 'rect' else f'<circle cx="{cx_+17}" cy="{cy_+8}" r="9" {a}/>')
        o.append(text(cx_ + 44, cy_ + 12, label, 11, '#222', raw=True))
    o.append('</svg>')
    return '\n'.join(o)


WHAT = {'pw_in': 'J6 + 6 pre-filter caps', 'pw_7v5': 'L12 + bulk caps', 'pw_24v': 'L13 L14 + bulk caps'}


def power_info():
    """{zone, tol, n, ngroups, groups {name: family}, info {name: {n, what}}} for the supergroup block and the pw_* groups of groups.json."""
    its = json.load(open(V5 + '/intent.json'))['blocks']
    sg = [b for b in its if b['name'] == 'power_strip'][0]
    g = json.load(open(V5 + '/groups.json'))['groups']
    pw = [x for x in g if x['name'].startswith('pw_') and x['name'] != 'pw_misc']
    fam = {}
    for x in pw:
        if x['name'] in ('pw_in',):
            fam[x['name']] = 'in'
        elif x['name'] in ('pw_7v5',) or any(n == 'pw_7v5' for n in (x.get('near') or [])):
            fam[x['name']] = '7v5'
        else:
            fam[x['name']] = '24v'
    info = {x['name']: {'n': len([r for r in x['refs'] if r != 'J6']), 'what': WHAT.get(x['name'], 'regulator + its caps')} for x in pw}
    return {'zone': sg['zone'], 'tol': sg.get('tolerance_mm', 0.5), 'n': len(sg['refs']), 'ngroups': len(pw), 'groups': fam, 'info': info}


def svgs(gate_json=V5 + '/gate.out.json'):
    """{suffix: svg text} for the top and bottom views."""
    import designer_check as dc
    import pcbnew
    cans = json.load(open(V5 + '/cans.json'))
    holes = json.load(open(V5 + '/holes.json'))
    gate = json.load(open(gate_json))
    gate.setdefault('limit', gate['fill_table'][0]['limit'])
    outline, boxes, agg, vic, sides = load()
    b = pcbnew.LoadBoard(V5 + '/fixed.kicad_pcb')
    parts = dc.parts_of(pcbnew, b)
    gate['n_movable'] = gate.get('n_movable') or len([r for r in parts if parts[r]['face'] == 'F' and r not in {f['ref'] for f in json.load(open(V5 + '/mechanical.json'))['fixed']}])
    power = power_info()
    return {suffix: build(side, cans, holes, boxes, outline, power, agg, vic, sides, gate, parts) for side, suffix in (('F', ''), ('B', '_bottom'))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=V5 + '/floorplan')
    ap.add_argument('--gate', default=V5 + '/gate.out.json', help='gate.py --json output (fill table, anchored starts)')
    a = ap.parse_args()
    for suffix, svg in svgs(a.gate).items():
        sp = f'{a.out}{suffix}.svg'
        open(sp, 'w').write(svg)
        subprocess.run(['rsvg-convert', '-o', f'{a.out}{suffix}.png', sp], check=True)
        os.remove(sp)
        print('wrote', f'{a.out}{suffix}.png')


if __name__ == '__main__':
    main()
