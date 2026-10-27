#!/usr/bin/env python3
"""mk_tiny_intent.py VARIANT : build probe/tiny_<V>/ (board, brief, mechanical, intent, groups) for the step-1 probe.
V in C (control: nothing), A (covers[J7]+heights), B (overlap_waivers J7 x members), D (no J7 at all: zone control), E (courtyards_overlap=ignore in .kicad_pro), F (E plus overlap_waivers)."""
import json, os, shutil, subprocess, sys
V = sys.argv[1]
P = '/tmp/pcb-trials/timiq/v5/probe'
K = '/tmp/pcb-trials/timiq/krt'
D = f'{P}/tiny_{V}'
os.makedirs(D, exist_ok=True)
for ext in ('kicad_pcb', 'kicad_pro'):
    shutil.copy(f'{P}/tiny/tiny.{ext}', f'{D}/tiny.{ext}')
if V in ('E', 'F'):
    pro = json.load(open(f'{D}/tiny.kicad_pro'))
    pro['board']['design_settings']['rule_severities']['courtyards_overlap'] = 'ignore'
    json.dump(pro, open(f'{D}/tiny.kicad_pro', 'w'), indent=2)
if V == 'D':
    import pcbnew
    bd = pcbnew.LoadBoard(f'{D}/tiny.kicad_pcb'); bd.Remove(bd.FindFootprintByReference('J7')); pcbnew.SaveBoard(f'{D}/tiny.kicad_pcb', bd)
mem = json.load(open(f'{P}/tiny/tiny.kicad_pcb.members.json'))
faces = mem['faces']
F = sorted(r for r, s in faces.items() if s == 'F')
B = sorted(r for r, s in faces.items() if s == 'B')
if V != 'D': json.dump({'schema': 1, 'fixed': [{'ref': 'J7', 'x': 131.6648, 'y': 190.96, 'rot': 0.0,
          'reason': 'probe: Infinionist 10-26, J7-J10 fixed at the human pose under the lid window'}]},
          open(f'{D}/mechanical.json', 'w'), indent=1)
brief = {'schema': 1, 'kind': 'design-brief', 'units': 'mm', 'board': 'tiny.kicad_pcb', 'interfaces': []}
if V == 'A':
    brief['covers'] = [{'connector': 'J7', 'side': 'F', 'axis_deg': 0, 'width_mm': 32, 'length_mm': 31.5, 'offset_mm': -15.9,
                        'underside_mm': 5.5, 'removable': False,
                        'source': 'probe: Laird BMI-S-204-F frame 32x32x6 (FACTS 10, web); fixed shield'}]
    brief['heights'] = [{'ref': r, 'height_mm': 0.9, 'source': 'probe guess (not a datasheet)'} for r in F]
json.dump(brief, open(f'{D}/tiny.design-brief.json', 'w'), indent=1)
def run(args, log):
    r = subprocess.run([f'{K}/.venv/bin/python', '-X', 'utf8'] + args, capture_output=True, text=True)
    open(log, 'w').write(r.stdout + r.stderr)
    return r.returncode
rc = run([f'{K}/py_tools/check_floorplan.py', f'{D}/tiny.kicad_pcb', '--emit-intent', f'{D}/intent.json', '--allow-unplaced'], f'{D}/emit.log')
print('emit rc', rc)
it = json.load(open(f'{D}/intent.json'))
zone = [131.01, 159.66, 161.81, 190.46]
it['blocks'] = [b for b in it.get('blocks', [])]
it['blocks'] += [
    {'name': 'canJ7_F', 'refs': F, 'zone': zone, 'side': 'F', 'why': 'probe: members under can J7, top'},
    {'name': 'canJ7_B', 'refs': B, 'zone': zone, 'side': 'B', 'why': 'probe: members under can J7, bottom'}]
if V in ('B', 'F'):
    it['overlap_waivers'] = [{'pair': ['J7', r], 'why': 'probe: member sits inside the fixed can frame J7'} for r in F]
json.dump(it, open(f'{D}/intent.json', 'w'), indent=1)
json.dump({'schema': 1, 'groups': [{'name': 'pll', 'role': 'core', 'refs': F + B + ([] if V == 'D' else ['J7']), 'anchor': 'U1', 'why': 'probe: PLL sheet parts of can J7'}]},
          open(f'{D}/groups.json', 'w'), indent=1)
print('F', len(F), 'B', len(B), 'intent keys', sorted(it.keys()))
