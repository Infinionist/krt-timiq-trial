#!/bin/bash
# run_seeds.sh : TimIQ v5, KRT skill plan-pcb-placement §3.6-3.7 as written, plus the post checks. NOT run by the builder (lead starts it).
#   place_simple      default 12 seeds (6 scattered, 6 clustered), --jobs 3                     -> seeds/s<S>.kicad_pcb, s<S>.json, s<S>.log, judge.json
#   judge_seeds       the 6 seeds judge.json names, fast route (route_diff/route.py at --quick 2, added by judge_seeds), --jobs 3
#   best 3 candidates (judge_seeds' ranking): reattach.py (cans J7-J12 back, option (d)) -> seeds/c<S>.kicad_pcb, then check_assembly
#                     --baseline, check_floorplan --intent, designer_check.py, render_placement PNG (seeds/c<S>.png)
# Every step appends to seeds/run.log (its own output in seeds/<step>.log). Hard steps (place, judge, reattach) stop the script at once
# (nonzero); the post checks of a candidate are all run and counted, and the script exits 1 at the end if any failed.
# Not routed past the screen: no --confirm (add `judge_seeds.py ... --confirm close` by hand if the NOTE says seeds are within the spread).
# Cores: --jobs 3 for both (single-threaded processes). Est. wall time: placing ~1.0-1.5 h, judging ~10 min, post checks ~5 min.
set -euo pipefail
V5=/tmp/pcb-trials/timiq/v5
K=/tmp/pcb-trials/timiq/krt
PY=$K/.venv/bin/python
S=$V5/seeds
JOBS=${JOBS:-3}
[ "$JOBS" -le 12 ] || { echo "JOBS=$JOBS: 20-core box, 12 at most" >&2; exit 2; }
[ ! -e "$S/judge.json" ] || { echo "$S/judge.json exists: a run is already here (move seeds/ aside)" >&2; exit 2; }
mkdir -p "$S"
LOG=$S/run.log
say() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"; }
# step NAME CMD... : run in $K, output to seeds/NAME.log, tail appended to run.log; returns the command's exit code
step() {
  local name=$1; shift
  say "START $name: $*"
  local rc=0
  ( cd "$K" && "$@" ) > "$S/$name.log" 2>&1 || rc=$?
  tail -n 15 "$S/$name.log" | cut -c1-300 >> "$LOG"
  say "END   $name rc=$rc"
  return $rc
}
hard() { step "$@" || { say "FAILED (hard): $1"; exit 1; }; }
FAILS=0
soft() { step "$@" || { say "FAILED (soft): $1"; FAILS=$((FAILS+1)); }; }

# 0. the gate must still pass on the inputs; stage the placing inputs
hard gate "$PY" -X utf8 "$V5/gate.py"
hard stage "$PY" -X utf8 py_router/copy_board.py "$V5/fixed.kicad_pcb" "$S/fixed.kicad_pcb"
cp "$V5/intent.json" "$V5/groups.json" "$S/"
cp /tmp/pcb-trials/timiq/run/judge_chain.txt "$S/judge_chain.txt"   # run 1's chain (route_diff on the DAC I/Q nets, then route.py, 8 layers)
# intent for the reattached boards: the can keep-outs also allow the can footprints J7-J12 and BOX1 (they are not on the placing board)
python3 - "$S" <<'PYEOF'
import json, sys
s = sys.argv[1]
it = json.load(open(s + '/intent.json'))
for k in it['keepouts']:
    if k.get('name', '').startswith('can-J'):
        k['allow'] = list(k['allow']) + ['J7', 'J8', 'J9', 'J10', 'J11', 'J12', 'BOX1']
json.dump(it, open(s + '/intent_reattached.json', 'w'), indent=1)
PYEOF
hard baseline_cans "$PY" -X utf8 "$V5/reattach.py" "$S/fixed.kicad_pcb" "$S/fixed_cans.kicad_pcb"

# 3.6 place: default seeds (6 scattered + 6 clustered), judge.json names the 6 to judge
rc=0
step place "$PY" -X utf8 py_placer/place_simple.py "$S/fixed.kicad_pcb" "$S/s{seed}.kicad_pcb" \
    --groups "$S/groups.json" --intent "$S/intent.json" --jobs "$JOBS" --json "$S/s{seed}.json" || rc=$?
# exit 4 = a seed left a part illegal / a declared pose refused / an edge oversubscribed: the input's to fix (skill §3.6), stop and report
[ "$rc" -eq 0 ] || { say "place_simple exit $rc: see $S/place.log and $S/judge.json (skill §3.6: fix the input or repair by hand)"; exit 1; }
[ -s "$S/judge.json" ] || { say "no judge.json"; exit 1; }

# 3.7 fast-route the judged seeds (judge_seeds adds --quick 2 to route.py and every route_diff.py step)
hard judge "$PY" -X utf8 py_placer/judge_seeds.py "$S/judge.json" --chain "$S/judge_chain.txt" --intent "$S/intent.json" --jobs "$JOBS"
TOP=$(python3 - "$S/judge.log" <<'PYEOF'
import json, sys
l = [x for x in open(sys.argv[1]) if x.startswith('JSON_SUMMARY: ')]
r = json.loads(l[-1].split('JSON_SUMMARY: ', 1)[1])['ranking']
print(' '.join(str(s) for s in r[:3]))
PYEOF
)
[ -n "$TOP" ] || { say "judge_seeds ranked no seed"; exit 1; }
say "top candidates (judge_seeds ranking): $TOP"

# candidates: reattach the cans, then the post checks (all run, failures counted)
for c in $TOP; do
  B=$S/c$c.kicad_pcb
  hard reattach_$c "$PY" -X utf8 "$V5/reattach.py" "$S/s$c.kicad_pcb" "$B"
  soft check_assembly_$c "$PY" -X utf8 py_tools/check_assembly.py "$B" --baseline "$S/fixed_cans.kicad_pcb" --json "$S/c$c.assembly.json"
  soft check_floorplan_$c "$PY" -X utf8 py_tools/check_floorplan.py "$B" --intent "$S/intent_reattached.json"
  soft designer_check_$c "$PY" -X utf8 "$V5/designer_check.py" "$B" --intent "$S/intent_reattached.json" --baseline "$S/fixed_cans.kicad_pcb" --json "$S/c$c.designer.json"
  soft render_$c "$PY" -X utf8 py_tools/render_placement.py "$B" -o "$S/c$c.png"
done
say "DONE: candidates $TOP, $FAILS failed post check(s); PNGs $S/c<S>.png; ranking in $S/judge.log"
[ "$FAILS" -eq 0 ] || exit 1
