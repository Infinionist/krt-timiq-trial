#!/bin/sh
# pp.sh LOG args...  : run place_pose, keep full output in LOG, print exit code + key JSON bits
LOG=$1; shift
K=/tmp/pcb-trials/timiq/krt
$K/.venv/bin/python -X utf8 $K/py_placer/place_pose.py "$@" > "$LOG" 2>&1
RC=$?
echo "exit=$RC"
grep -E "^(REFUSED|refus|FORCE|wrote|WROTE)|height_pairs|cover|zone_containment|NOT |no worse|no_worse" "$LOG" | cut -c1-300 | head -20
grep '^JSON_SUMMARY' "$LOG" | sed 's/^JSON_SUMMARY: //' | python3 -c "
import sys,json
d=json.loads(sys.stdin.read())
for k in ('written','no_worse','legal','refused','reason','courtyard_error_pairs_after','height_pairs_new','height_pairs_after','zone_findings'):
    if k in d: print(k,'=',str(d[k])[:300])
print('keys:',[k for k in d if 'height' in k or 'cover' in k or 'zone' in k])
"
exit $RC
