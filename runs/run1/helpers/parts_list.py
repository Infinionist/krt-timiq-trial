# Compact one-line-per-part table from board_context --json (its --md is 5000 lines).
import sys, json
c = json.load(open(sys.argv[1]))
for p in sorted(c['parts'], key=lambda p: ((p.get('schematic') or {}).get('sheet') or '~', (p.get('schematic') or {}).get('block') or '', p['ref'])):
    s = p.get('schematic') or {}
    print(f"{(s.get('sheet') or '-'):24s} {(s.get('block') or '-'):5s} {p['ref']:6s} {p['side']} {p['footprint'][:34]:34s} {str(p.get('value'))[:40]} body={p['body_mm']}")
