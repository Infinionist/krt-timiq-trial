import sys, re
sys.path.insert(0, '/tmp/pcb-trials/timiq/v5')
import cans_io
p = '/tmp/pcb-trials/timiq/v6/start.kicad_pcb'
t = open(p, encoding='utf-8').read()
leds = ['D%d' % i for i in range(2, 9)]
for k, ref in enumerate(leds):
    for s, e, r in cans_io.scan_footprints(t):
        if r == ref:
            blk = t[s:e]
            m = re.search(r'\n\t\t\(at ([-\d.]+) ([-\d.]+)( [-\d.]+)?\)', blk)
            nb = blk[:m.start()] + f'\n\t\t(at {196 + 3 * k} 362{m.group(3) or ""})' + blk[m.end():]
            t = t[:s] + nb + t[e:]
            print(ref, m.group(0).strip(), '->', 196 + 3 * k, 362)
            break
open(p, 'w', encoding='utf-8').write(t)
