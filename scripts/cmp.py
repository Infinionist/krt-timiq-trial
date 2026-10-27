import xml.etree.ElementTree as ET, pcbnew, re
D='/tmp/pcb-trials/timiq/guisch/'
r=ET.parse(D+'n.xml').getroot()
comps={c.get('ref'):c for c in r.find('components')}
sc={k for k in comps if not re.match(r'#(PWR|FLG)',k)}
nets={n.get('name'):[(x.get('ref'),x.get('pin')) for x in n] for n in r.find('nets')}
b=pcbnew.LoadBoard('/tmp/pcb-trials/timiq/work/TimIQ_RF.kicad_pcb')
fp={f.GetReference() for f in b.GetFootprints()}
bn={}
for f in b.GetFootprints():
  for p in f.Pads():
    if p.GetNetname(): bn.setdefault(p.GetNetname(),[]).append((f.GetReference(),p.GetNumber()))
print('sch comps',len(comps),'non-power',len(sc),'board fps',len(fp))
print('sch nets',len(nets),'board nets',len(bn))
print('sch only',sorted(sc-fp)); print('board only',sorted(fp-sc))
norm=lambda s:s.lstrip('/')
def key(n): return frozenset(n)
bset={key(v):k for k,v in bn.items()}
mm=[(k,bset[key(v)]) for k,v in nets.items() if key(v) in bset and norm(k)!=norm(bset[key(v)])]
print('same pins, different name',len(mm),mm[:6])
print('sch nets with no board match',sum(1 for v in nets.values() if key(v) not in bset and len(v)>1))
