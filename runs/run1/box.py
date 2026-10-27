import re
t=open('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb').read()
i=t.find('(footprint "SOLEIL:1590Q"') 
if i<0: i=t.find('1590Q')
print(i)
# find the footprint form containing BOX1
m=[m.start() for m in re.finditer(r'\(footprint ',t)]
for s in m:
    seg=t[s:s+60000]
    if '"BOX1"' in seg[:3000]:
        # find end by paren match
        d=0
        for k,ch in enumerate(seg):
            if ch=='(': d+=1
            elif ch==')':
                d-=1
                if d==0: break
        body=seg[:k+1]
        print(len(body))
        print(re.findall(r'\(layer "?([\w.]+)"?\)',body).__len__())
        from collections import Counter
        print(Counter(re.findall(r'\((fp_\w+)[^\n]*?\(layer "?([\w.]+)"?\)',body)))
        for pm in re.finditer(r'\(pad [^\n]*',body): print(pm.group(0)[:200])
        print(body[:600])
        break
# board-level Edge.Cuts
print(len(re.findall(r'\(gr_(?:line|arc)[^\n]*Edge.Cuts',t)))
