import sys, re
sys.path.insert(0,'/tmp/pcb-trials/timiq/run2_work')
import cans
src, dst = sys.argv[1], sys.argv[2]
t = open(src).read()
for spec in sys.argv[3:]:
    ref, x, y = spec.split(',')
    a, b = cans._footprint_span(t, ref)
    blk = t[a:b]
    new, n = re.subn(r'(\(layer "[^"]*"\)\s*\n\t\t\(uuid "[^"]*"\)\s*\n\t\t\(at )([-\d.]+) ([-\d.]+)', lambda m: f'{m.group(1)}{x} {y}', blk, count=1)
    assert n == 1, ref
    t = t[:a] + new + t[b:]
open(dst, 'w').write(t)
import shutil, os
shutil.copyfile(os.path.splitext(src)[0] + '.kicad_pro', os.path.splitext(dst)[0] + '.kicad_pro')
