# Builds groups.json from the schematic sheets/blocks board_context read (464 parts: too many to list by hand).
import json, sys
c = json.load(open('ctx.json'))
fixed = {f['ref'] for f in json.load(open('intent.json'))['fixed_poses']}
sheet_group = {'TOP/PLL': 'pll', 'TOP/IQ modulator': 'iqmod', 'TOP/Frequency mixers': 'mixers',
               'TOP/Frequency dividers': 'dividers', 'TOP/ADC': 'adc', 'TOP/DAC': 'dac',
               'TOP/DAC Interface': 'dac_if', 'TOP/digital interface': 'digital'}
psu = {}
for b in 'B40 B46 B53 B41 B47 B49 B56 B57'.split(): psu[b] = 'power_in'
for b in 'B26 B27 B28 B29 B30 B31 B32 B33 B34 B35 B36 B37 B38 B39 B42 B43 B44 B45'.split(): psu[b] = 'ldo_pos'
for b in 'B48 B50 B51 B52 B54 B58 B59 B60'.split(): psu[b] = 'ldo_neg'
manual = {'C110': 'adc', 'C111': 'adc', 'C112': 'adc', 'C113': 'adc', 'R116': 'adc', 'R118': 'adc',
          'R123': 'adc', 'R124': 'adc', 'R83': 'dividers', 'J6': 'power_in'}
for j in 'J7 J8 J9 J10 J11 J12'.split(): manual[j] = 'shields'
G = {}
for p in c['parts']:
    r = p['ref']; s = p.get('schematic') or {}
    if r in manual: g = manual[r]
    elif r in fixed and not r.startswith('J'): continue
    elif s.get('sheet') == 'TOP/PSU': g = psu[s['block']]
    else: g = sheet_group[s['sheet']]
    G.setdefault(g, []).append(r)
meta = {
 'pll': dict(role='core', anchor='U1', near=['iqmod', 'mixers', 'dividers'],
   why='LMX2541 PLL/VCO (U1) with its supply ferrites and decaps, the 108 MHz VCXO U2, splitter U3, loop filter, lock LED D1/Q1, ref-in SMA J1 and ext-VCO SMA J2 (PLL sheet)'),
 'iqmod': dict(role='rf', anchor='U16', near=['pll', 'mixers', 'dac_if'],
   why='HMC1097 IQ modulator U16 with splitter U17 and its coupling/bypass caps (IQ modulator sheet); its I/Q baseband comes from dac_if'),
 'mixers': dict(role='rf', anchor='U23', near=['iqmod', 'pll', 'adc'],
   why='PMA2-43LN+ amps U21/U22 with bias tees, GAT-5 pad U23, QCN-34 quadrature splitter U24, splitter U25, SIM-73L mixers U26/U27 (Frequency mixers sheet); IF out goes to the ADC'),
 'dividers': dict(role='rf', anchor='U19', near=['pll', 'digital'],
   why='three HMC705 dividers U18-U20 with their decaps and config resistors, divider outputs to SMA J3/J4 (Frequency dividers sheet); R83 (no symbol) is U19 config pull'),
 'adc': dict(role='analog', anchor='U29', near=['mixers', 'digital'],
   why='ADS8694 ADC U29, its LTC6655 ref U30 and OPA2209 Butterworth front end U28 (ADC sheet); C110-C113, R116, R118, R123, R124 have no symbol but sit on U28/U29 filter nets'),
 'dac': dict(role='analog', anchor='U4', near=['dac_if', 'digital'],
   why='LTC2758 dual DAC U4 with its reference buffers U5/U6/U7/U8 and output amps U9-U11 (DAC sheet)'),
 'dac_if': dict(role='analog', anchor='U14', near=['dac', 'iqmod'],
   why='LTC6655 refs U12/U13 and LT6600 differential filters U14/U15 that drive the IQ modulator I/Q inputs (DAC Interface sheet)'),
 'digital': dict(role='interface', anchor='J5', near=['dac', 'adc', 'dividers'],
   why='80-pin QSH board-to-board connector J5 (back) with the LVDS receivers/drivers U31/U32/U34/U38 and LV4T125 level shifters U33/U35/U36/U37 (digital interface sheet)'),
 'power_in': dict(role='power', anchor='J6', near=['ldo_pos', 'ldo_neg'],
   why='6-pin Molex power entry J6 with its three NFM41 EMI filters L12-L14, bulk Al caps and test points TP1-TP9 (PSU sheet blocks B40/B41/B46/B47/B49/B53/B56/B57)'),
 'ldo_pos': dict(role='power', anchor='U41', near=['power_in'],
   why='five TPS7A4700 positive LDOs U39-U43, their input/output caps and status-LED resistors (PSU sheet); the LEDs D2-D8 are declared at fixed poses top-left'),
 'ldo_neg': dict(role='power', anchor='U44', near=['power_in'],
   why='two TPS7A3301 negative LDOs U44/U45 with their feedback dividers, caps and LED resistors (PSU sheet)'),
 'shields': dict(role='mechanical', anchor='J7',
   why='six BMI-S-204-F shield frames: the placer cannot put parts inside a can (it is a solid body to it), so they are grouped on their own and placed where they fit'),
}
groups = []
for g, refs in G.items():
    m = dict(meta[g]); m['name'] = g; m['refs'] = sorted(refs)
    groups.append({k: m[k] for k in ['name', 'role', 'refs', 'anchor', 'near', 'why'] if k in m})
json.dump({'schema': 1, 'groups': groups}, open('groups.json', 'w'), indent=1)
for g in groups: print(g['name'], len(g['refs']))
