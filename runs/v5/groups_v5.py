#!/usr/bin/env python3
"""groups_v5.py : plan v5 groups of TimIQ (Infinionist 10-27). Pure, no I/O; imported by build_inputs.py and the tests.

Each shield can is ONE KRT group `can<J>` (J7..J12): its members (cans.json) + optional parts + the anchor marker + the fixed SMA connectors of its sheets, `side: "F"` (KRT's group
side: every part of the group stands on the front, under the can; skill 3.3 "give a group a side only to put all its parts on that face"), NO `flippable`. Plan v3/v4 used the
schematic sheets as groups, but a sheet spans two cans (the DAC sheet is in J9 and J12, U3 of the PLL sheet is in J8), so a group `side` could not say "under the can".
Everything else keeps its sheet group (`digital`); the panel LED D1 with its driver R1/Q1 (outside the cans) is group `status_led`.
"""
import re


def _refkey(r):
    m = re.match(r'^([A-Za-z]+)(\d+)$', r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)


def can_groups(cans, sheet_groups, anchors, fixed_refs, exclude):
    """-> (groups, notes): the can groups in can order, the sheet groups that are not can sheets (unchanged), and `status_led`.
    cans: cans.json (members, optional, anchor_marker, sheets); sheet_groups: groups.json's sheet groups (after the shields group was dropped); anchors: plan_v3.ANCHORS.
    Raises AssertionError when the new groups are not a partition of the old ones (every old ref once; only the markers are new)."""
    by_name = {g['name']: g for g in sheet_groups}
    sheet2can = {s: can for can, c in cans.items() for s in c['sheets']}
    out, seen = [], {}
    for can, c in cans.items():
        sheets = [by_name[s] for s in c['sheets']]
        refs = list(c['members']) + list(c.get('optional') or [])
        mk = (c.get('anchor_marker') or {}).get('ref')
        if mk:
            refs.append(mk)
        for s in sheets:        # the fixed SMA connectors of the sheet (J1, J2 in pll; J3, J4 in dividers) stay with the can group; the old sheet markers are the new ones
            refs += [r for r in s['refs'] if r in fixed_refs and r not in refs and not re.match(r'^MK\d+$', r)]
        near = []
        for s in sheets:
            for n in s.get('near') or []:
                m = 'can' + sheet2can[n] if n in sheet2can else n
                if m != 'can' + can and m not in near:
                    near.append(m)
        g = {'name': f'can{can}', 'role': sheets[0].get('role'), 'refs': refs, 'anchor': anchors[can]['ics'][0], 'near': near, 'side': 'F',
             'why': f"shield can {can} (sheet(s) {', '.join(c['sheets'])}): one group, every part on the front under the can (side F), none flippable; {anchors[can]['why']}"}
        out.append(g)
        for r in refs:
            seen.setdefault(r, []).append(g['name'])
    # templates: the sheet group's rows go to the can group that holds the chip
    for s in sheet_groups:
        for t in s.get('templates') or []:
            chip = t.get('chip')
            home = [g for g in out if chip in g['refs']]
            if s['name'] in sheet2can:
                assert len(home) == 1, f"template chip {chip} of sheet {s['name']} is in no can group"
                home[0].setdefault('templates', []).append(t)
    rest = []
    for s in sheet_groups:
        if s['name'] in sheet2can:
            continue
        g = dict(s)
        g['near'] = [('can' + sheet2can[n]) if n in sheet2can else n for n in (s.get('near') or [])]
        g.pop('flippable', None)
        out.append(g)
        for r in g['refs']:
            seen.setdefault(r, []).append(g['name'])
    old = {r for s in sheet_groups for r in s['refs']}
    left = sorted((r for r in old if r not in seen and r not in exclude), key=_refkey)
    assert not left, f'refs of the sheet groups in no new group: {left}'
    ex = sorted((r for r in exclude if r in old), key=_refkey)
    if ex:
        out.append({'name': 'status_led', 'role': 'interface', 'refs': ex, 'near': ['digital'],
                    'why': 'panel status LED D1 with its driver R1/Q1: outside the cans (the human has all three beside the SMAs); no zone, free'})
        for r in ex:
            seen.setdefault(r, []).append('status_led')
    dup = {r: v for r, v in seen.items() if len(v) > 1}
    assert not dup, f'refs in two groups: {dup}'
    new_refs = set(seen)
    extra = sorted(r for r in new_refs - old if not re.match(r'^MK\d+$', r))
    assert not extra, f'refs in the new groups that no sheet group had: {extra}'
    return out, {'sheet2can': sheet2can, 'excluded': ex}
