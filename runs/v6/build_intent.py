#!/usr/bin/env python3
"""v6: write groups.json, the brief's keep_away, emit the intent with KRT, then add the designer's intent to it:
can blocks (zone = can interior, exclusive), assembly both faces, chain proximity rows inside each can group, severity.proximity warn.
Inputs: ctx.json (board_context), v5/cans.json (Infinionist's can membership + can interior rects; the human faces in it are NOT used)."""
import json, collections, subprocess, re, sys
V6, K = '/tmp/pcb-trials/timiq/v6', '/tmp/pcb-trials/timiq/krt'
PY = K + '/.venv/bin/python'
ctx = json.load(open(V6 + '/ctx.json'))
cans = json.load(open('/tmp/pcb-trials/timiq/v5/cans.json'))
P = {p['ref']: p for p in ctx['parts']}
nets = {}          # ref -> {net: [pads]}
netparts = collections.defaultdict(set)
for p in ctx['parts']:
    d = collections.defaultdict(list)
    for pads in p['pads_by_face'].values():
        for pd in pads:
            d[pd['net']].append(pd['pad'])
    nets[p['ref']] = dict(d)
    for n in d: netparts[n].add(p['ref'])
RAILS = {'GND', '', '3V3_1', '3V3_2', '5V_1', '5V_2', '-5V', '15V', '-15V', '7V5', '24V', '-24V'}
def is_rail(n): return n in RAILS or len(netparts[n]) > 6
def npads(r): return sum(len(v) for v in nets[r].values())
def fp(r): return P[r]['footprint'].split(':')[-1]
def small_passive(r): return re.match(r'(R|C|L)\d', r) and re.search(r'0603|0805|0402', fp(r))

# ---- can groups (membership: Infinionist's cans.json, F and B lists merged; faces not used) ----
CAN_GROUP = {'J7': 'pll', 'J8': 'lo_mix_iq', 'J9': 'dac_if', 'J10': 'dividers', 'J11': 'adc', 'J12': 'dac'}
CAN_ANCHOR = {'J7': 'U1', 'J8': 'U16', 'J9': 'U14', 'J10': 'U19', 'J11': 'U29', 'J12': 'U4'}
CAN_CONN = {'J7': ['J1'], 'J8': ['J2'], 'J10': ['J3', 'J4']}
CAN_WHY = {'J7': 'PLL can: LMX2541 synthesizer U1, VCXO reference U2, its loop filter, supply ferrites and decaps; J1 the 352 MHz reference input SMA',
           'J8': 'LO splitter U3 + IQ modulator U16/U17 + mixer chain U21-U27 (PMA2 amps, GAT-5 attenuator, QCN-34 hybrid, SIM-73L mixers); J2 the external LO SMA',
           'J9': 'DAC interface: DAC output op-amps U10/U11, references U12/U13, LT6600 I/Q filters U14/U15 into the IQ modulator',
           'J10': 'frequency dividers U18-U20 (HMC705) with their strap resistors and decaps; J3/J4 the divided-output SMAs',
           'J11': 'ADC can: ADS8694 U29 with its OPA2209 driver U28 (2nd order Butterworth) and 4.096 V reference U30',
           'J12': 'DAC can: LTC2758 dual DAC U4 with its op-amps U5-U9, gain/offset resistors and decaps'}
groups, used = [], set()
for can, g in CAN_GROUP.items():
    c = cans[can]
    refs = sorted(set(c['refs']['F']) | set(c['refs']['B']) | set(c.get('optional') or []))
    used |= set(refs) | set(CAN_CONN.get(can, []))
    groups.append({'name': g, 'role': 'signal', 'refs': CAN_CONN.get(can, []) + refs, 'anchor': CAN_ANCHOR[can],
                   'why': CAN_WHY[can] + f'. Members = shield can {can} (Infinionist\'s membership, v5/cans.json); placed in the can interior (intent block zone).'})
DIG = [r for r in P if P[r].get('sheet') == 'digital']
# digital sheet: every part whose schematic sheet is digital.kicad_sch
sheet_of = {}
for s in ctx['schematic']['sheets']:
    f = s.get('file') or s.get('name')
    for b in s.get('blocks', []):
        for r in b['refs']: sheet_of[r] = f
    for r in s.get('loose', s.get('alone', [])) or []: sheet_of[r] = f
for s in ctx['schematic']['sheets']:
    f = s.get('file') or ''
    for k in s:
        if isinstance(s[k], list) and k not in ('blocks', 'notes'):
            for x in s[k]:
                if isinstance(x, str) and x in P: sheet_of.setdefault(x, f)
dig = sorted(r for r, f in sheet_of.items() if 'digital' in f and r not in used)
if 'J5' not in dig: dig = ['J5'] + dig
groups.append({'name': 'digital', 'role': 'interface', 'refs': dig, 'anchor': 'J5',
               'why': 'digital interface sheet: LVDS receivers/drivers U31/U32/U34/U38 and level buffers U33/U35-U37 with their resistors and decaps, on the J5 board-to-board header (intent 7: next to J5, short fans)'})
used |= set(dig)
groups.append({'name': 'pll_status', 'role': 'ui', 'refs': ['D1', 'Q1', 'R1'], 'anchor': 'D1', 'near': ['pll'],
               'why': 'PLL-lock LED D1 with its driver FET Q1 and resistor R1 (drawn block B67); kept out of the PLL can by Infinionist\'s membership'})
used |= {'D1', 'Q1', 'R1'}
# ---- power (intent 4): input, one group per filter stage, one per regulator with its own parts ----
PW = {
 'pw_in':   (['J6', 'TP4', 'TP5', 'TP6', 'TP7', 'TP8', 'TP9'], 'J6', [], 'power entry J6 with its ground test points TP4-TP9'),
 'pw_7v5':  (['L12', 'C143', 'C148', 'C155', 'C162', 'TP1'], 'L12', ['pw_in'], '7V5 input filter: NFM41 L12, bulk C143 + C148 before, C155 + C162 after, TP1'),
 'pw_24v':  (['L13', 'C144', 'C149', 'C156', 'C163', 'TP2'], 'L13', ['pw_in'], '+24V input filter: L13, C144 + C149, C156 + C163, TP2'),
 'pw_n24v': (['L14', 'C145', 'C150', 'C157', 'C164', 'TP3'], 'L14', ['pw_in'], '-24V input filter: L14, C145 + C150, C157 + C164, TP3'),
 'reg_5v1':  (['U39', 'C139', 'C141', 'C146', 'C151', 'C153', 'C158', 'C160', 'D2', 'R154'], 'U39', ['pw_7v5', 'dividers', 'digital'], 'TPS7A4700 7V5 -> 5V_1 (dividers, digital buffers): input C139, NR C141, outputs C146/C151/C153/C158/C160, rail LED D2 + R154'),
 'reg_5v2':  (['U40', 'C140', 'C142', 'C147', 'C152', 'C154', 'C159', 'C161', 'D3', 'R155'], 'U40', ['pw_7v5', 'dac', 'dac_if', 'adc'], 'TPS7A4700 7V5 -> 5V_2 (DAC, DAC IF, ADC, mixers): input C140, NR C142, outputs, LED D3 + R155'),
 'reg_3v3a': (['U41', 'C165', 'C170', 'C175', 'C180', 'C183', 'C188', 'C193', 'D4', 'R160'], 'U41', ['pw_7v5', 'pll'], 'TPS7A4700 7V5 -> 3V3_1 (PLL): input C165, NR C170, outputs, LED D4 + R160'),
 'reg_3v3b': (['U42', 'C166', 'C171', 'C176', 'C181', 'C184', 'C189', 'C194', 'D5', 'R161'], 'U42', ['pw_7v5', 'adc', 'digital'], 'TPS7A4700 7V5 -> 3V3_2 (ADC, digital): input C166, NR C171, outputs, LED D5 + R161'),
 'reg_15v':  (['U43', 'C167', 'C172', 'C177', 'C182', 'C185', 'C190', 'C195', 'D6', 'R162'], 'U43', ['pw_24v', 'dac', 'dac_if'], 'TPS7A4700 24V -> 15V (DAC op-amps): input C167, NR C172, outputs, LED D6 + R162'),
 'reg_m5v':  (['U44', 'C168', 'C173', 'C178', 'R156', 'R157', 'C186', 'C191', 'C196', 'C198', 'C200', 'D7', 'R163'], 'U44', ['pw_n24v', 'dac', 'dac_if', 'adc'], 'TPS7A3301 -24V -> -5V: input C168, NR C173, feedback R156/R157 + C178, outputs, LED D7 + R163'),
 'reg_m15v': (['U45', 'C169', 'C174', 'C179', 'R158', 'R159', 'C187', 'C192', 'C197', 'C199', 'C201', 'D8', 'R164'], 'U45', ['pw_n24v', 'dac', 'dac_if'], 'TPS7A3301 -24V -> -15V: input C169, NR C174, feedback R158/R159 + C179, outputs, LED D8 + R164'),
}
for name, (refs, anc, near, why) in PW.items():
    g = {'name': name, 'role': 'power', 'refs': refs, 'anchor': anc, 'why': why}
    if near: g['near'] = near
    groups.append(g); used |= set(refs)
mech = {'FIX%d' % i for i in range(1, 9)} | {'BOX1'}
left = sorted(set(P) - used - mech)
print('unassigned:', left)
# ---- faces (intent 6): small passives flippable; in RF cans only decaps (cap with one pad on GND, >= 1 nF) ----
RF = {'pll', 'lo_mix_iq', 'dividers'}
RF_PARTS = {'U3', 'U16', 'U17', 'U21', 'U22', 'U23', 'U24', 'U25', 'U26', 'U27', 'J1', 'J2', 'J3', 'J4'}
def on_rf_net(r):
    # round 3: an RF part is a passive on an auto-named signal net touching an RF chip or SMA, or on the LO/IQ/mixer/PLL-out named nets
    for n in nets[r]:
        if is_rail(n): continue
        if any(k in n for k in ('PLLout', 'IQout', 'MIXERout', 'PLL_OUT')): return True
        if n.startswith('Net-(') and (netparts[n] & RF_PARTS): return True
    return False
def is_decap(r):
    if not r.startswith('C') or 'GND' not in nets[r]: return False
    v = (P[r].get('value') or '').lower()
    return not re.match(r'\d+(\.\d+)?pf', v)
for g in groups:
    fl = [r for r in g['refs'] if small_passive(r) and (g['name'] not in RF or is_decap(r) or not on_rf_net(r))]
    if fl: g['flippable'] = fl
json.dump({'schema': 1, 'groups': groups}, open(V6 + '/groups.json', 'w'), indent=1)
print('groups', len(groups), 'flippable', sum(len(g.get('flippable', [])) for g in groups))
gof = {r: g['name'] for g in groups for r in g['refs']}
# ---- keep_away (intent 2): LO/PLL nets >= 3 mm from digital nets ----
def signal_nets(refs):
    return sorted({n for r in refs for n in nets[r] if not is_rail(n) and n not in RAILS})
pll_refs = [r for r in groups[0]['refs']]
lo_refs = ['U3', 'C20', 'R14', 'R16', 'R17', 'R165', 'J2', 'U16', 'U17', 'C63', 'C64', 'R70', 'R71', 'C70', 'R72', 'R73', 'C98', 'R100', 'U21', 'L8', 'C101', 'C108', 'L10', 'U23', 'U24', 'R108']
digi_ctl = re.compile(r'PLL_(DATA|CLK|LE|CE|LOCKED|ENC|END)', re.I)
lo_nets = [n for n in signal_nets(pll_refs + lo_refs) if not digi_ctl.search(n)]
dg_nets = signal_nets(dig)
brief = json.load(open(V6 + '/fixed.design-brief.json'))
esc = lambda L: ','.join(n.replace(' ', '?') for n in L)
brief['keep_away'] = [{'rule': esc(dg_nets) + ':' + esc(lo_nets) + ':3',
                       'why': 'designer intent 2: LO/PLL nets stay at least 3 mm from digital nets (digital = the digital-interface sheet nets; LO/PLL = PLL can signal nets and the LO path into the splitter, IQ modulator and mixer amps)'}]
json.dump(brief, open(V6 + '/fixed.design-brief.json', 'w'), indent=1)
print('keep_away', len(dg_nets), 'digital nets vs', len(lo_nets), 'LO/PLL nets')
# ---- emit (skill 3.2) ----
r = subprocess.run([PY, '-X', 'utf8', K + '/py_tools/check_floorplan.py', V6 + '/fixed.kicad_pcb', '--emit-intent', V6 + '/intent.json', '--allow-unplaced'],
                   cwd=K, capture_output=True, text=True)
open(V6 + '/emit.log', 'w').write(r.stdout + r.stderr); assert r.returncode == 0, r.stderr[-2000:]
it = json.load(open(V6 + '/intent.json'))
# ---- blocks: one per can, zone = can interior, exclusive ----
blocks = []
for can, g in CAN_GROUP.items():
    gr = next(x for x in groups if x['name'] == g)
    refs = [x for x in gr['refs'] if not x.startswith('J')]
    blocks.append({'name': 'can_' + can, 'refs': refs, 'zone': cans[can]['zone'], 'exclusive': True, 'tolerance_mm': 0.0,
                   'why': f'designer intent 1: the circuit under shield can {can} (removed for this run) sits in the can interior, isolated from the other circuits'})
it['blocks'] = blocks
it['assembly'] = {'sides': 'both', 'why': 'designer intent 6: ICs, RF parts and big parts on top; small passives may go on the bottom (groups[].flippable)'}
# ---- chain rows (intent 2, 5): inside each can group, each passive at the pin of the part it serves on each signal net ----
rows = []
for g in groups:
    if g['name'] not in CAN_GROUP.values(): continue
    members = set(g['refs'])
    for r in g['refs']:
        if r.startswith('J') or npads(r) > 3: continue
        for n, pads in nets[r].items():
            if is_rail(n): continue
            partners = [q for q in netparts[n] if q != r and q in members]
            if not partners: continue
            q = max(partners, key=lambda q: (npads(q), q))
            if npads(q) <= 3 and not q.startswith('J'):
                continue            # passive-to-passive links come from the other side when an IC is on the net
            rows.append({'ref': r, 'near': q, 'max_mm': 2.0, 'pads': {r: pads, q: nets[q][n]},
                         'why': f'designer intent 2/5: {r} on the signal path / at the pin it serves ({n}) of {q}, chain link inside group {g["name"]}'})
    # IC-to-IC direct links (ordered chain): two ICs on a 2-part signal net
    ics = [r for r in g['refs'] if npads(r) > 3 and not r.startswith('J')]
    for i, a in enumerate(ics):
        for b in ics[i + 1:]:
            sh = [n for n in nets[a] if n in nets[b] and not is_rail(n)]
            if sh:
                rows.append({'ref': b, 'near': a, 'max_mm': 5.0, 'basis': 'pad_edge', 'pads': {b: nets[b][sh[0]], a: nets[a][sh[0]]},
                             'why': f'designer intent 2: ordered chain {a} -> {b} share {sh[0]}, kept adjacent'})
# dedupe (ref, near)
seen, out = set(), []
for x in rows:
    k = (x['ref'], x['near'])
    if k in seen or (x['near'], x['ref']) in seen: continue
    seen.add(k); out.append(x)
it['proximity'] = it.get('proximity', []) + out
it['severity'] = dict(it.get('severity', {}), proximity='warn')
it['min_reader'] = max(it.get('min_reader', 0), 14)
json.dump(it, open(V6 + '/intent.json', 'w'), indent=1)
print('blocks', len(blocks), 'proximity rows', len(out))
