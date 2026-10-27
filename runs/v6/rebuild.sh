#!/bin/sh
# v6 input pipeline: groups + brief keep_away + emit + designer intent, then the PMA2 templates (skill 3.3-3.5)
K=/tmp/pcb-trials/timiq/krt; V6=/tmp/pcb-trials/timiq/v6
/usr/bin/python3 $V6/build_intent.py || exit 1
python3 - <<'PY'
import json
p='/tmp/pcb-trials/timiq/v6/groups.json'; g=json.load(open(p))
for x in g['groups']:
    if x['name']=='lo_mix_iq':
        x['templates']=[{'chip':'U21','kind':'rf front end','why':'PMA2-43LN+ gain block in the LO path: DC blocks, bias choke and shunt caps of its datasheet Fig 1'},
                        {'chip':'U22','kind':'rf front end','why':'PMA2-43LN+ gain block in the IQ path: same circuit as U21'}]
    if x['name']=='pll':
        x['templates']=[{'chip':'U1','kind':'none','why':'LMX2541 PLL/VCO: L1-L7 are BLM18 supply ferrite beads, not a switching stage; its passives are held by the chain/pin rows'}]
json.dump(g,open(p,'w'),indent=1)
PY
for U in U21 U22; do env -C $K .venv/bin/python -X utf8 py_tools/fit_template.py $V6/fixed.kicad_pcb --sketch $V6/sk_$U.json --render $V6/fit_$U.png --intent $V6/intent.json --write-intent $V6/intent.json > $V6/fit_$U.log 2>&1 || exit 2; done
python3 - <<'PY'
import json
p='/tmp/pcb-trials/timiq/v6/intent.json'; it=json.load(open(p))
mem={m['ref'] for t in it.get('templates',[]) for m in t['members']}
it['proximity']=[r for r in it['proximity'] if r['ref'] not in mem]
json.dump(it,open(p,'w'),indent=1); print('templates',len(it['templates']),'rows',len(it['proximity']),'keepouts',len(it.get('keepouts',[])))
PY
