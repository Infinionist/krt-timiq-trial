# Copy a make_movie work dir and add each declared can's wall (cans[] fence bands, intent blocks fence_mm)
# as fixed boxes of the can's interior height, so render.mjs draws them. Placement data untouched.
import json, os, shutil, sys
src, dst, intent = sys.argv[1:4]
H = 6.0  # interior_height_mm from the brief (frame overall height)
os.makedirs(dst, exist_ok=True)
S = json.load(open(os.path.join(src, 'scene.json'))); T = json.load(open(os.path.join(src, 'timeline.json')))
I = json.load(open(intent)); walls = []
for b in I['blocks']:
    w = b.get('fence_mm')
    if not w: continue
    x0, y0, x1, y1 = b['zone']; n = b['name'].split(':')[1]
    for e, r in (('N', (x0 - w, y0 - w, x1 + w, y0)), ('S', (x0 - w, y1, x1 + w, y1 + w)),
                 ('W', (x0 - w, y0, x0, y1)), ('E', (x1, y0, x1 + w, y1))):
        cx, cy, hw, hh = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2, (r[2] - r[0]) / 2, (r[3] - r[1]) / 2
        walls.append(({'ref': f'CAN_{n}_{e}', 'side': b['side'], 'pads': [], 'court': [-hw, -hh, hw, hh],
                       'body': [-hw, -hh, hw, hh, H], 'color': [196, 200, 206], 'fixed': True, 'dnp': False}, (cx, cy)))
S['parts'] += [p for p, _ in walls]
S['key'].append({'rgb': [196, 200, 206], 'mark': 'solid', 'text': 'shield can walls (declared in cans[], not drawn on the board)'})
T['refs'] += [p['ref'] for p, _ in walls]
d = S['thickness']
for f in T['frames']:
    f['p'] = list(f['p']) + [[round(cx, 4), round(cy, 4), 0.0, d] for _, (cx, cy) in walls]
json.dump(S, open(os.path.join(dst, 'scene.json'), 'w')); json.dump(T, open(os.path.join(dst, 'timeline.json'), 'w'))
job = json.load(open(os.path.join(src, 'job.json')))
job.update(scene=os.path.join(dst, 'scene.json'), timeline=os.path.join(dst, 'timeline.json'), outDir=os.path.join(dst, 'frames'))
os.makedirs(job['outDir'], exist_ok=True); json.dump(job, open(os.path.join(dst, 'job.json'), 'w'))
print(len(walls), 'walls added;', len(T['frames']), 'frames')
