#!/usr/bin/env python3
"""decide_faces.py BOARD GROUPS INTENT [--cans CANS] [--write] [--json OUT] [--limit L] : plan v5b (Infinionist 10-27). Run with KRT's venv python.

The rule is written in faces_v5.py (docstring): inside a can every IC, every RF-path part and every part with courtyard >= 20 mm2 stays on the FRONT, locked; its small SMD passives
(R, C, FB; courtyard < 20 mm2) may go to the BOTTOM, only inside their own can. Everything STARTS on the front (set_faces).

What this script decides (it measures with fillcheck.fill_table over the pre-flight probe: KRT's courtyards, clearance, fixed parts, keep-outs, with EVERY part on F):
  * a CAN whose front fill is over fillcheck.LIMIT (0.65): the eligible small passives are listed flippable, the decaps of the can's own ICs first (the human practice: caps behind
    their IC), then smallest first, until the front fill is <= LIMIT and the back fill is <= LIMIT. Eligible parts used up and the front still over: verdict FAIL with the shortfall in
    mm2 (the limit is never loosened). The can's group and block then carry NO `side` (a declared side overrides flippable in KRT) and cans.json gets `flippable`; a can that needs
    nothing keeps `side: F` everywhere.
  * a NON-can zone over `--limit` (default fillcheck.WARN) on its front face: as in plan v5, its smallest R/C parts (courtyard < 20 mm2) listed flippable until it is back at the limit.
With --write the groups, intent and cans files are rewritten (idempotent: the measure always starts from "every part on F"); --json gets the plan, the RF-path list and the table.
Exit 0: every can fits; 1: a can does not (verdict FAIL, shortfall printed; gate.py fails on it too); 2: tool error."""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fillcheck  # noqa: E402
import faces_v5  # noqa: E402


def neutral(groups, intent):
    """copies in which nothing is flippable and every can block is on F: the 'all parts on the front' state the plan is measured from."""
    g, i = json.loads(json.dumps(groups)), json.loads(json.dumps(intent))
    for x in g['groups']:
        x.pop('flippable', None)
    for b in i['blocks']:
        if str(b.get('name', '')).startswith('can'):
            b['side'] = 'F'
    return g, i


def decide(groups, intent, cans, probe, netinfo, owners, limit_can=fillcheck.LIMIT, limit_other=fillcheck.WARN):
    """Pure. -> {'verdict': 'PASS'|'FAIL', 'plans': {can: plan_can result}, 'picks': {zone: [ref]}, 'shortfall': {can: mm2}, 'rf': rf_path result, 'rows': table rows (before),
    'groups', 'intent', 'cans': rewritten copies}. groups/intent may already carry a previous decision: the measure starts from the neutral state."""
    g0, i0 = neutral(groups, intent)
    rows = fillcheck.fill_table(i0, g0, probe, limit_can)
    rf = faces_v5.rf_path(netinfo, i0)
    picks = {z: v for z, v in fillcheck.flippable_needed(rows, g0, probe, i0, limit_other).items()}
    new_g, new_i, new_c = json.loads(json.dumps(g0)), json.loads(json.dumps(i0)), json.loads(json.dumps(cans))
    by_name = {x['name']: x for x in new_g['groups']}
    blocks = {b['name']: b for b in new_i['blocks']}
    plans, short = {}, {}
    for row in rows:
        if row['kind'] != 'can':
            continue
        can = row['name'][3:]
        members = list(blocks[row['name']].get('refs') or [])
        ics = [r for r in members if r.startswith('U')]
        if row['fill'] > limit_can + 1e-9:
            plans[can] = faces_v5.plan_can(row, members, probe.get('dims') or {}, probe.get('clearance') or 0.0, limit_can, netinfo, rf['parts'], faces_v5.pref_ranks(owners, ics))
        else:
            plans[can] = {'picks': [], 'F0': row['fill_F0'], 'F': row['fill_F'], 'B': row['fill_B'], 'shortfall_mm2': 0.0, 'eligible': None, 'ineligible': {}}
        pl = plans[can]
        if pl['shortfall_mm2'] > 0:
            short[can] = pl['shortfall_mm2']
        grp = by_name.get(row['name'])
        if pl['picks']:
            if grp is not None:
                grp.pop('side', None)
                grp['flippable'] = list(pl['picks'])
            blocks[row['name']].pop('side', None)
            new_c[can].pop('side', None)
            new_c[can]['flippable'] = list(pl['picks'])
        else:
            if grp is not None:
                grp['side'] = 'F'
            blocks[row['name']]['side'] = 'F'
            new_c[can]['side'] = 'F'
            new_c[can].pop('flippable', None)
    chosen = sorted({r for v in picks.values() for r in v})
    for x in new_g['groups']:
        if x['name'].startswith('can'):
            continue
        fl = [r for r in x['refs'] if r in chosen]
        if fl:
            x['flippable'] = fl
    return {'verdict': 'FAIL' if short else 'PASS', 'plans': plans, 'picks': picks, 'shortfall': short, 'rf': rf, 'rows': rows, 'groups': new_g, 'intent': new_i, 'cans': new_c}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('board')
    ap.add_argument('groups')
    ap.add_argument('intent')
    ap.add_argument('--cans', default=HERE + '/cans.json')
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--json', default=None)
    ap.add_argument('--limit', type=float, default=fillcheck.WARN, help='limit for the zones that are not cans (default fillcheck.WARN)')
    ap.add_argument('--can-limit', type=float, default=fillcheck.LIMIT)
    a = ap.parse_args(argv)
    pj = tempfile.mktemp(suffix='.probe.json')
    r = subprocess.run([sys.executable, '-X', 'utf8', HERE + '/preflight_probe.py', a.board, a.groups, a.intent, '--out', pj], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(pj):
        print('decide_faces: preflight_probe failed:\n' + (r.stdout + r.stderr)[-800:], file=sys.stderr)
        return 2
    probe = json.load(open(pj))
    os.remove(pj)
    intent, groups, cans = json.load(open(a.intent)), json.load(open(a.groups)), json.load(open(a.cans))
    netinfo = faces_v5.board_netinfo(a.board)
    owners = faces_v5.decap_owners(a.board)
    res = decide(groups, intent, cans, probe, netinfo, owners, a.can_limit, a.limit)
    print('before (every part on F):')
    for line in fillcheck.format_table(res['rows']):
        print('  ' + line)
    for can, pl in res['plans'].items():
        print(f"  can{can}: F0 {pl['F0']:.2f} -> F {pl['F']:.2f} / B {pl['B']:.2f}; {len(pl['picks'])} flippable"
              + (f" ({pl['eligible']} eligible)" if pl['eligible'] is not None else '') + (f"; SHORTFALL {pl['shortfall_mm2']:.0f} mm2" if pl['shortfall_mm2'] else ''))
        if pl['picks']:
            print(f"    {' '.join(pl['picks'])}")
    n = sum(len(v) for v in res['picks'].values())
    print(f'decide_faces: {n} non-can part(s) listed flippable' + (''.join(f"\n  {z}: {v}" for z, v in res['picks'].items() if v)))
    print(f"decide_faces: {res['verdict']}" + (f" (cans over the limit with every eligible part flipped: {res['shortfall']})" if res['shortfall'] else ''))
    if a.write:
        json.dump(res['groups'], open(a.groups, 'w'), indent=1)
        json.dump(res['intent'], open(a.intent, 'w'), indent=1)
        json.dump(res['cans'], open(a.cans, 'w'), indent=1)
    if a.json:
        rf = res['rf']
        json.dump({'verdict': res['verdict'], 'limit': a.can_limit, 'rows_before': res['rows'], 'plans': res['plans'], 'flippable_other': res['picks'], 'shortfall_mm2': res['shortfall'],
                   'rf_path': {'rule': 'faces_v5.py docstring', 'nets': rf['nets'], 'parts': rf['parts']}}, open(a.json, 'w'), indent=1)
    return 0 if res['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
