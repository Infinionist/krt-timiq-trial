#!/usr/bin/env python3
"""v3 inputs: run 2's intent (+ run 1's templates) and a groups file with one FENCE group per shielded block.

Block list = F-face members of the human board's cans (run2_work/membership.json; used here as the block list for the
experiment only). Each fence group takes its members out of the sheet group they were in; the remaining parts keep their
groups. Each fence group is `apart` from every other group (place_simple keeps groups' nearest courtyards APART_MM = 3 mm
apart, softly): that gap is the ring around the block.
"""
import json, sys
IN = '/tmp/pcb-trials/timiq/v3/in/'
mem = json.load(open(IN + 'membership.json'))
base = json.load(open(IN + 'groups_base.json'))
cans = ['J7', 'J8', 'J9', 'J10', 'J11', 'J12']
owner = {r: g['name'] for g in base['groups'] for r in g['refs']}
fence_of = {}
for c in cans:
    for r in mem[c]['inside_F']:
        assert r in owner, r
        fence_of[r] = 'fence_' + c
groups, fences = [], []
for g in base['groups']:
    keep = [r for r in g['refs'] if r not in fence_of]
    if not keep:
        continue
    h = dict(g); h['refs'] = keep
    if h.get('anchor') not in keep:
        h.pop('anchor', None)
    if h.get('templates'):
        h['templates'] = [t for t in h['templates'] if t['chip'] in keep]
        if not h['templates']:
            h.pop('templates')
    groups.append(h)
names = [g['name'] for g in groups] + ['fence_' + c for c in cans]
for c in cans:
    refs = sorted(mem[c]['inside_F'], key=lambda r: (r.rstrip('0123456789'), int(''.join(ch for ch in r if ch.isdigit()))))
    from_g = {}
    for r in refs:
        from_g[owner[r]] = from_g.get(owner[r], 0) + 1
    near = [g for g, n in sorted(from_g.items(), key=lambda kv: -kv[1]) if n >= 4 and any(x['name'] == g for x in groups)]
    chip = [r for r in refs if r.startswith('U')][0]
    f = {'name': 'fence_' + c, 'role': 'shield', 'refs': refs, 'anchor': chip, 'near': near,
         'apart': [n for n in names if n != 'fence_' + c],
         'why': f'block of the custom shield fence {c}-position: the F-face parts the human board has under can {c}; the placer keeps a ring round it (apart {3} mm from every other group)'}
    groups.append(f)
# a ref in the base templates lists must still resolve: done above. Write.
json.dump({'schema': 1, 'groups': groups}, open(IN + 'groups_v3a.json', 'w'), indent=1)
# intent: run 2's, plus run 1's templates
it = json.load(open('/tmp/pcb-trials/timiq/run2/intent.json'))
r1 = json.load(open('/tmp/pcb-trials/timiq/run/intent_run.json'))
it['templates'] = r1['templates']
it['min_reader'] = max(it.get('min_reader', 0), r1.get('min_reader', 0))
json.dump(it, open(IN + 'intent_v3.json', 'w'), indent=1)
print({g['name']: len(g['refs']) for g in groups})
