# Independent wall check: every pad (conservative circle, radius = half its larger side) of every part
# against each can's 1.8 mm wall band on the can's face. Exits 1 if any pad touches a wall.
import json, math, re, sys
board, intent = sys.argv[1], sys.argv[2]
t = open(board).read(); I = json.load(open(intent))
starts = [m.start() for m in re.finditer(r'\n\t\(footprint "', t)] + [len(t)]
pads = []  # (ref, side, x, y, r)
for a, b in zip(starts, starts[1:]):
    s = t[a:b]
    ref = re.search(r'\(property "Reference" "([^"]+)"', s).group(1)
    side = re.search(r'\(layer "([FB])\.Cu"\)', s).group(1)
    at = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)', s)
    fx, fy, fa = float(at.group(1)), float(at.group(2)), math.radians(float(at.group(3) or 0))
    for p in re.finditer(r'\(pad "[^"]*" (\w+) \w+\s+\(at ([-\d.]+) ([-\d.]+)[^)]*\)\s+\(size ([-\d.]+) ([-\d.]+)\)', s):
        lx, ly = float(p.group(2)), float(p.group(3))
        x = fx + lx * math.cos(fa) + ly * math.sin(fa); y = fy - lx * math.sin(fa) + ly * math.cos(fa)
        layers = 'FB' if p.group(1) in ('thru_hole', 'np_thru_hole') else side
        pads.append((ref, layers, x, y, max(float(p.group(4)), float(p.group(5))) / 2))
bad = []; n = 0
for blk in I['blocks']:
    if not blk.get('fence_mm'): continue
    x0, y0, x1, y1 = blk['zone']; w = blk['fence_mm']; face = blk['side']; n += 1
    for ref, layers, x, y, r in pads:
        if ref == 'BOX1' or face not in layers: continue
        # inside outer box (zone grown by w) and not fully inside the interior
        if x + r > x0 - w and x - r < x1 + w and y + r > y0 - w and y - r < y1 + w and \
           not (x - r >= x0 and x + r <= x1 and y - r >= y0 and y + r <= y1):
            bad.append((blk['name'], ref, round(x, 2), round(y, 2)))
print(f"{len(pads)} pads, {n} can walls checked; pads on a wall: {len(bad)}")
for b in bad[:30]: print('  ', b)
sys.exit(1 if bad else 0)
