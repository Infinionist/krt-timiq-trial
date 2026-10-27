#!/usr/bin/env python3
"""gate.py : the pre-placement gate of TimIQ plan v2 step 2 (a script decides, no model).

PASS (exit 0) only when ALL hold; otherwise prints what is missing and exits 1 (2 on a usage or tool error):
  1. check_floorplan --plan-only: 0 errors                       (KRT)
  2. check_groups: 0 errors                                      (KRT)
  3. every IC (a U* reference on the board) is covered by one of (netlist rows count: an IC with no datasheet is covered by them):
       - a templates[] row in the intent whose anchor is the IC,
       - a proximity[] row in the intent naming the IC as ref or near (datasheet row or netlist row),
       - a written skip in the groups file: templates[] entry {chip: IC, skip: "<reason>"} or {chip: IC, kind: "none", why: "<reason>"}
         whose reason is real: >= 25 characters, not one of the excuses plan v2 rejects ("not fetched", "time cap", "4h15",
         "held by the decap rule", "held by decap rule", "left to the group"), AND (when netrows.json is present) the IC has no passive
         on its local nets at all (netrows.json ic_candidates == 0): a skip never hides an IC the netlist could serve.
  4. every shield can (cans.json, option (d): the cans are NOT on the placing board) has: both faces' member blocks 'can<J>_F' / 'can<J>_B' in
     the intent with the can's interior zone, the face as side and exactly the cans.json refs; a keep-out 'can-<J>' (in the intent) allowing
     exactly those members plus the can's 'optional' refs (allowed inside, not members); and no can footprint (J7-J12) on the placing board.

usage: gate.py [--board B] [--intent I] [--groups G] [--cans C] [--netrows N] [--json OUT]
Defaults are the files in /tmp/pcb-trials/timiq/v5/.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KRT = '/tmp/pcb-trials/timiq/krt'
PY = KRT + '/.venv/bin/python'
BAD_REASON = [r'not fetched', r'time cap', r'4h15', r'held by (the )?decap', r'left to the group', r'within the time']
MIN_REASON = 25


def krt(args):
    r = subprocess.run([PY, '-X', 'utf8'] + args, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def summary(text):
    for line in text.splitlines():
        if line.startswith('JSON_SUMMARY:'):
            return json.loads(line[len('JSON_SUMMARY:'):])
    return None


def ics_on_board(board):
    t = open(board, encoding='utf-8').read()
    return sorted(set(re.findall(r'\(property "Reference" "(U\d+)"', t)), key=lambda s: int(s[1:]))


def reason_problem(reason):
    if not isinstance(reason, str) or len(reason.strip()) < MIN_REASON:
        return f'reason shorter than {MIN_REASON} characters'
    for pat in BAD_REASON:
        if re.search(pat, reason, re.I):
            return f'reason is one plan v2 rejects (matches "{pat}")'
    return None


def coverage(ics, intent, groups, candidates=None):
    """candidates: {ic: [passives on its local nets]} (netrows.json). An IC is covered when it is a template anchor or named in a proximity row,
    or when one of its candidates is claimed by a proximity row (either end of the passive) or is a template member."""
    """returns {ic: ('template'|'proximity'|'skip' or None, detail)}."""
    tmpl = {t.get('anchor') for t in intent.get('templates', [])}
    prox = {}
    for p in intent.get('proximity', []):
        for r in (p.get('ref'), p.get('near')):
            prox.setdefault(r, 0)
            prox[r] += 1
    skips, bad_skips = {}, {}
    for g in groups.get('groups', []):
        for t in g.get('templates', []) or []:
            chip = t.get('chip')
            if not chip:
                continue
            reason = t.get('skip') if t.get('skip') else (t.get('why') if t.get('kind') == 'none' else None)
            if reason is None:
                continue
            prob = reason_problem(reason)
            (bad_skips if prob else skips)[chip] = prob or reason
    claimed = {p.get('ref') for p in intent.get('proximity', [])} | {m.get('ref') for t in intent.get('templates', []) for m in t.get('members', [])}
    out = {}
    for ic in ics:
        if ic in tmpl:
            out[ic] = ('template', 'intent templates[] row')
        elif ic in prox:
            out[ic] = ('proximity', f'{prox[ic]} proximity row(s)')
        elif candidates is not None and any(c in claimed for c in candidates.get(ic, ())):
            out[ic] = ('proximity', f"claims its passive(s) {sorted(c for c in candidates[ic] if c in claimed)[:4]}")
        elif ic in skips and candidates is not None and candidates.get(ic):
            out[ic] = (None, f'skip rejected: {len(candidates[ic])} passive(s) sit on its local nets (netrows.json) and none is claimed; a skip cannot hide them')
        elif ic in skips:
            out[ic] = ('skip', skips[ic][:70])
        elif ic in bad_skips:
            out[ic] = (None, f'skip rejected: {bad_skips[ic]}')
        else:
            out[ic] = (None, 'no template row, no proximity row, no written skip')
    return out


def ics_all_refs(board):
    t = open(board, encoding='utf-8').read()
    return set(re.findall(r'\(property "Reference" "([^"]+)"', t))


def cans_problems(cans, intent, board_refs):
    """{can/face or can: problem}: see check 4 in the module doc."""
    bad = {}
    blocks = {b.get('name'): b for b in intent.get('blocks', [])}
    kos = {k.get('name'): k for k in intent.get('keepouts', [])}
    for can, c in cans.items():
        members = []
        if can in board_refs:
            bad[f'{can}/board'] = 'the can footprint is on the placing board (option (d): it must be off, see reattach.py)'
        for face in ('F', 'B'):
            refs = c.get('refs', {}).get(face)
            b = blocks.get(f'can{can}_{face}')
            if refs == 'TODO' or refs is None or not isinstance(refs, list):
                bad[f'{can}/{face}'] = 'member refs are TODO'
                continue
            members += refs
            if not refs:
                if b is not None:
                    bad[f'{can}/{face}'] = 'cans.json has no members on this face but the intent has a block'
                continue
            if b is None:
                bad[f'{can}/{face}'] = 'refs given in cans.json but no block in the intent (rerun build_inputs.py)'
            elif sorted(b.get('refs') or []) != sorted(refs):
                bad[f'{can}/{face}'] = 'block refs differ from cans.json'
            elif b.get('side') != face:
                bad[f'{can}/{face}'] = f"block side {b.get('side')!r}, expected {face}"
            elif [round(v, 3) for v in (b.get('zone') or [])] != [round(v, 3) for v in c['zone']]:
                bad[f'{can}/{face}'] = 'block zone differs from the can interior'
        k = kos.get(f'can-{can}')
        if k is None:
            bad[f'{can}/keepout'] = f'no keep-out can-{can} in the intent'
        elif sorted(k.get('allow') or []) != sorted(members + list(c.get('optional') or [])):
            bad[f'{can}/keepout'] = 'keep-out allow list differs from the can members + optional parts'
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--board', default=HERE + '/fixed.kicad_pcb')
    ap.add_argument('--intent', default=HERE + '/intent.json')
    ap.add_argument('--groups', default=HERE + '/groups.json')
    ap.add_argument('--cans', default=HERE + '/cans.json')
    ap.add_argument('--netrows', default=HERE + '/netrows.json')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(argv)
    for f in (a.board, a.intent, a.groups):
        if not os.path.exists(f):
            print(f'gate: missing input {f}', file=sys.stderr)
            return 2
    res = {'checks': {}, 'missing': {}}
    fails = []

    rc, txt = krt([KRT + '/py_tools/check_floorplan.py', a.board, '--intent', a.intent, '--plan-only', '--allow-unplaced'])
    s = summary(txt)
    if s is None:
        print('gate: check_floorplan --plan-only gave no JSON_SUMMARY:\n' + txt[-800:], file=sys.stderr)
        return 2
    n = s.get('plan_errors')
    res['checks']['plan_only_errors'] = n
    if n != 0:
        fails.append(f'check_floorplan --plan-only: {n} error(s)')
        res['missing']['plan_only'] = [l.strip() for l in txt.splitlines() if '[error' in l.lower()][:20]

    rc, txt = krt([KRT + '/py_tools/check_groups.py', a.board, '--groups', a.groups, '--intent', a.intent])
    s = summary(txt)
    if s is None:
        print('gate: check_groups gave no JSON_SUMMARY:\n' + txt[-800:], file=sys.stderr)
        return 2
    res['checks']['check_groups_errors'] = s.get('errors')
    if s.get('errors') != 0:
        fails.append(f'check_groups: {s.get("errors")} error(s)')
        res['missing']['groups'] = [l.strip() for l in txt.splitlines() if 'ERROR' in l][:20]

    intent = json.load(open(a.intent))
    groups = json.load(open(a.groups))
    ics = ics_on_board(a.board)
    cands = None
    if os.path.exists(a.netrows):
        cands = json.load(open(a.netrows)).get('ic_candidates')
    cov = coverage(ics, intent, groups, cands)
    miss = {ic: d for ic, (k, d) in cov.items() if k is None}
    res['checks']['ics'] = len(ics)
    res['checks']['ics_uncovered'] = len(miss)
    res['missing']['ics'] = miss
    if miss:
        fails.append(f'{len(miss)} of {len(ics)} ICs have no template row, proximity row or valid skip')

    cans_missing = {}
    if os.path.exists(a.cans):
        cans = json.load(open(a.cans))
        cans_missing = cans_problems(cans, intent, ics_all_refs(a.board))
    else:
        cans_missing['cans.json'] = 'missing'
    res['checks']['cans_problems_count'] = len(cans_missing)
    res['missing']['cans'] = cans_missing
    if cans_missing:
        fails.append(f'{len(cans_missing)} can problem(s)')

    res['pass'] = not fails
    print('GATE ' + ('PASS' if not fails else 'FAIL'))
    for f in fails:
        print('  FAIL:', f)
    if miss:
        print('  ICs missing (template row / proximity row / valid skip):')
        for ic, d in miss.items():
            print(f'    {ic}: {d}')
    if cans_missing:
        print('  can problems:')
        for k, d in cans_missing.items():
            print(f'    {k}: {d}')
    for k in ('plan_only', 'groups'):
        for l in res['missing'].get(k, []):
            print(f'    {k}: {l}')
    print('  ok: ' + ', '.join(f'{ic}={k}' for ic, (k, d) in cov.items() if k))
    if a.json:
        json.dump(res, open(a.json, 'w'), indent=1)
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
