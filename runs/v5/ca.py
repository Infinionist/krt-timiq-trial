#!/usr/bin/env python3
"""ca.py BOARD BASELINE [INTENT] [--refs J7,U1,...]: run check_assembly --baseline, print the gate summary
and every gating/advisory pair that names one of --refs (default J7)."""
import sys, json, subprocess, os, argparse
ap=argparse.ArgumentParser(); ap.add_argument('board'); ap.add_argument('baseline'); ap.add_argument('--intent'); ap.add_argument('--refs',default='J7'); ap.add_argument('--tag',default=None)
a=ap.parse_args()
refs=set(a.refs.split(','))
tag=a.tag or os.path.splitext(os.path.basename(a.board))[0]
out=os.path.join(os.path.dirname(os.path.abspath(a.board)),tag+'.ca.json')
K='/tmp/pcb-trials/timiq/krt'
cmd=[K+'/.venv/bin/python','-X','utf8',K+'/py_tools/check_assembly.py',a.board,'--baseline',a.baseline,'--json',out]
if a.intent: cmd+=['--intent',a.intent]
r=subprocess.run(cmd,capture_output=True,text=True)
open(out.replace('.json','.log'),'w').write(r.stdout+r.stderr)
d=json.load(open(out))
print('exit',r.returncode,'verdict',d['verdict'],'blocking',d['blocking'],'advisory',d['advisory'],'courtyard_blocking',d['courtyard_blocking'],
      'containment_blocking',d['containment_blocking'],'height_pairs',len(d['height_pairs']),'silk_enclosed_gating',len(d['silk_enclosed_gating_pairs']),
      'pad_conflicts',d['pad_conflicts'])
def has(p): return any(r in str(p) for r in refs) if False else False
def names(p):
    return p if isinstance(p,str) else json.dumps(p)[:300]
for key in ('blocking_pairs','courtyard_blocking_gating_pairs','courtyard_error_gating_pairs','silk_enclosed_gating_pairs','height_pairs','containments','own_pad_gating_pairs','coincident_origin_groups'):
    v=d.get(key) or []
    mine=[p for p in v if any(('"%s"'%r in json.dumps(p)) for r in refs)]
    print(f'{key}: total {len(v)}, naming {sorted(refs)}: {len(mine)}')
    if key=='containments':
        import collections
        c=collections.Counter((p['kind'],p['gate_exempt'] or 'GATES',p['waived']) for p in mine)
        print('    by (kind,gate_exempt,waived):',dict(c))
    else:
        for p in mine[:8]: print('   ',names(p))
if len(sys.argv)>0:
    import re
    for line in open(out.replace('.json','.log')):
        if re.search(r'GATE|COURTYARD BLOCKING|BLOCKING',line) and any(r+' ' in line or ' '+r in line for r in refs): print('LOG',line.rstrip()[:240])
