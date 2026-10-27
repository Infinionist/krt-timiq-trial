import json, collections, sys
c = json.load(open('/tmp/pcb-trials/timiq/v6/ctx.json'))
sch = c.get('schematic', {})
sheet_of = {}
for s in sch.get('sheets', []) if isinstance(sch.get('sheets'), list) else []:
    for b in s.get('blocks', []):
        for r in b.get('refs', []): sheet_of[r] = s.get('file', s.get('name'))
    for r in s.get('refs', []) or []: sheet_of.setdefault(r, s.get('file', s.get('name')))
netparts = collections.defaultdict(set)
rows = []
for p in c['parts']:
    nets = {}
    for face, pads in p['pads_by_face'].items():
        for pd in pads:
            nets.setdefault(pd['net'], []).append(pd['pad'] + (':' + pd['pinfunction'] if pd['pinfunction'] else ''))
    for n in nets: netparts[n].add(p['ref'])
    rows.append((p['ref'], p.get('value'), p['footprint'].split(':')[-1][:28], p['body_mm'], nets))
GND = {'GND', ''}
for ref, val, fp, body, nets in rows:
    ns = ' '.join(f"{n}({len(netparts[n])})" for n in nets if n not in GND)
    print(f"{ref:6} {str(val)[:18]:18} {fp:28} {body[0]:.1f}x{body[1]:.1f} {sheet_of.get(ref,'?')[:10]:10} {ns}")
