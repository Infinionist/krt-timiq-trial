#!/bin/bash
# 30-minute check-in: run state, errors, cheat watcher, usage. No model calls.
R=/tmp/pcb-trials/timiq/run
sleep "${1:-1800}"
echo "== $(date -Is) stream $(wc -l < $R/stream.jsonl) lines"
/usr/bin/python3 - <<'PY'
import json,collections
R='/tmp/pcb-trials/timiq/run/stream.jsonl'
tools=collections.Counter(); errs=[]; last=''; usage=None
for l in open(R):
    try: e=json.loads(l)
    except: continue
    if e.get('type')=='assistant':
        for c in e['message'].get('content',[]):
            if c.get('type')=='tool_use': tools[c['name']]+=1; last=json.dumps(c.get('input'))[:200]
            if c.get('type')=='text': lasttext=c['text'][:300]
        usage=e['message'].get('usage')
    if e.get('type')=='user':
        for c in e['message'].get('content',[]) if isinstance(e['message'].get('content'),list) else []:
            if c.get('is_error'): errs.append(str(c.get('content'))[:200])
print('tools',dict(tools)); print('errors',len(errs)); [print('  ',x) for x in errs[-5:]]
print('last tool',last); print('last usage',usage)
PY
echo "-- STATE.md"; head -30 $R/STATE.md 2>/dev/null
echo "-- cheats"; tail -5 /tmp/pcb-trials/timiq/watch/cheats.log 2>/dev/null
grep -c -i -E 'traceback' $R/*.log 2>/dev/null | grep -v ':0' | head
