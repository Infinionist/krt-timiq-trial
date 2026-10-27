import pcbnew, json
mm = pcbnew.ToMM
b = pcbnew.LoadBoard('/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb')
hc = json.load(open('human_cans.json'))
out = {}
for can, rect in hc['rects'].items():
    out[can] = {'zone': [round(v, 4) for v in rect], 'refs': {'F': [], 'B': []}, 'why': 'REFERENCE: the human board membership (centre inside the can interior); self-test only, never an input to a placement'}
for ref, can in hc['inside'].items():
    f = b.FindFootprintByReference(ref)
    out[can]['refs']['B' if f.IsFlipped() else 'F'].append(ref)
for c in out:
    for k in 'FB': out[c]['refs'][k].sort()
json.dump(out, open('human_cans_ref.json', 'w'), indent=1)
print({c: (len(v['refs']['F']), len(v['refs']['B'])) for c, v in out.items()})
