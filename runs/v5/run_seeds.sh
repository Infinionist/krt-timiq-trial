#!/bin/bash
# run_seeds.sh : TimIQ v5 (plan v5), KRT skill plan-pcb-placement §3.6-3.7 as written, plus the post checks. NOT run by the builder (the lead starts it, after Infinionist has seen floorplan.png).
#   gate              (hard) gate.py must PASS: fit proof (fill table: every zone under the limit), faces, power supergroup, pre-flight legality of every fixed part.
#   place_simple      3 seeds: --scattered 0 --clustered 1 --anchored 2 (plan v5, Infinionist 10-27 call 4), --judge 3 (all three), --jobs 3   -> seeds/s<S>.kicad_pcb, s<S>.json, s<S>.log, judge.json
#                     Why anchored 2 + clustered 1, no scattered: an anchored seed starts each group round the point its wiring prefers (KRT: "each group started round the point its wiring
#                     prefers", opt-in): Infinionist's location suggestion, done the KRT way, for the 12 power groups and `digital`, with no tile. Two of them differ by KRT's own per-seed weight
#                     noise (simple_anneal ANCHORED spread). The clustered seed (groups gathered round one random point) is the stock fallback on boards where one big IC dominates and keeps
#                     a start that does not depend on the wiring guess. Scattered seeds start every part at a random place, which is what strewed the power parts in run v4 (3 scattered +
#                     3 clustered, all six illegal); with 3 seeds there is no room for them. KRT's own caveat holds: over 10 corpus boards anchored beat the default on 2, lost on 3.
#   place exit 4      is tolerated when judge.json names at least one seed (seeds with an illegal part are never named); it counts as one failed (soft) step.
#   NO SEED JUDGED   when judge.json names none (every seed left a part illegal): the seed with the lowest final.cost is forced through
#                     judge_seeds.py --seeds <S> (routing anyway, Infinionist 10-27 call 4): the skill's 3.6 "no seed can be judged" case 2 (a different part in each seed = the anneal's miss)
#                     or case 1 (the same part in every seed = the input's): the script prints which, from the seeds' `illegal` lists, and the run exits 1 at the end either way.
#   judge_seeds       the seeds judge.json names (or the forced one), fast route (route_diff/route.py at --quick 2, added by judge_seeds), --jobs 3
#   top candidates (judge_seeds' ranking, up to 3): reattach.py (cans J7-J12 back, option (d)) -> seeds/c<S>.kicad_pcb, then check_assembly --baseline, check_floorplan --intent,
#                     designer_check.py (members must stand on F), render_placement PNG (seeds/c<S>.png)
# Every step appends to seeds/run.log (its own output in seeds/<step>.log). Hard steps (gate, stage, place without any seed, judge, reattach) stop the script at once (nonzero);
# the post checks of a candidate are all run and counted, and the script exits 1 at the end if any failed.
# Not routed past the screen: no --confirm (add `judge_seeds.py ... --confirm close` by hand if the NOTE says seeds are within the spread).
# Cores: --jobs 3 for both (single-threaded processes). Est. wall time: placing ~0.7-1.0 h (run v4: 6 seeds in parallel 42 min), judging ~10 min, post checks ~5 min.
set -euo pipefail
V5=/tmp/pcb-trials/timiq/v5
K=/tmp/pcb-trials/timiq/krt
PY=$K/.venv/bin/python
S=$V5/seeds
JOBS=${JOBS:-3}   # plan v5: 3 seeds (0 scattered, 1 clustered, 2 anchored), 3 jobs
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
# intent for the reattached boards: written by build_inputs.py (the can keep-outs also allow the cans J7-J12 and BOX1, which are not on the placing board;
# overlap_waivers for every can over its members and optional parts)
cp "$V5/intent_reattached.json" "$S/intent_reattached.json"
hard baseline_cans "$PY" -X utf8 "$V5/reattach.py" "$S/fixed.kicad_pcb" "$S/fixed_cans.kicad_pcb"

# 3.6 place: 3 seeds (seed 0 clustered, seeds 1-2 anchored: clustered are numbered after the scattered ones, anchored after the clustered), judge.json names the legal ones
rc=0
step place "$PY" -X utf8 py_placer/place_simple.py "$S/fixed.kicad_pcb" "$S/s{seed}.kicad_pcb" \
    --groups "$S/groups.json" --intent "$S/intent.json" --scattered 0 --clustered 1 --anchored 2 --judge 3 --jobs "$JOBS" --json "$S/s{seed}.json" || rc=$?
# exit 4 = a seed left a part illegal / a declared pose refused / an edge oversubscribed: seeds with an illegal part are not named in judge.json (skill §3.6)
[ -s "$S/judge.json" ] || { say "place_simple exit $rc and no judge.json: see $S/place.log"; exit 1; }
FORCED=""
NAMED=$(python3 - "$S/judge.json" <<'PYEOF'
import json, sys
print(' '.join(str(s) for s in json.load(open(sys.argv[1])).get('judge') or []))
PYEOF
)
if [ "$rc" -ne 0 ]; then
  say "place_simple exit $rc (counts as one failed step); judge.json names: [${NAMED:-none}]"
  FAILS=$((FAILS+1))
fi
JUDGE_SEEDS=""
if [ -z "$NAMED" ]; then
  # skill 3.6 "When no seed can be judged": force the cheapest seed (lowest final.cost) through the judge anyway (Infinionist 10-27 call 4), and say which of the two causes it looks like
  FORCED=$(python3 - "$S" <<'PYEOF'
import glob, json, os, re, sys
S = sys.argv[1]
rows = []
for f in sorted(glob.glob(os.path.join(S, 's*.json'))):
    m = re.match(r's(\d+)\.json$', os.path.basename(f))
    if not m or not os.path.exists(os.path.join(S, f's{m.group(1)}.kicad_pcb')):
        continue
    d = json.load(open(f))
    rows.append((d['final']['cost'], int(m.group(1)), d.get('illegal') or []))
rows.sort()
if not rows:
    sys.exit(3)
common = set(rows[0][2])
for _c, _s, ill in rows[1:]:
    common &= set(ill)
sys.stderr.write('forced: seed %d (cost %.0f); %d part(s) illegal in EVERY seed %s (the input\'s: skill 3.6 case 1); per seed illegal counts %s\n'
                 % (rows[0][1], rows[0][0], len(common), sorted(common)[:12], {s: len(i) for _c, s, i in rows}))
print(rows[0][1])
PYEOF
) || { say "no seed placement to force"; exit 1; }
  say "judge.json names no seed: forcing seed $FORCED (lowest final.cost) through judge_seeds --seeds (routing anyway)"
  JUDGE_SEEDS="--seeds $FORCED"
fi

# 3.7 fast-route the judged seeds (judge_seeds adds --quick 2 to route.py and every route_diff.py step)
hard judge "$PY" -X utf8 py_placer/judge_seeds.py "$S/judge.json" --chain "$S/judge_chain.txt" --intent "$S/intent.json" --jobs "$JOBS" $JUDGE_SEEDS
TOP=$(python3 - "$S/judge.log" <<'PYEOF'
import json, sys
l = [x for x in open(sys.argv[1]) if x.startswith('JSON_SUMMARY: ')]
r = json.loads(l[-1].split('JSON_SUMMARY: ', 1)[1])['ranking']
print(' '.join(str(s) for s in r[:3]))
PYEOF
)
[ -n "$TOP" ] || { say "judge_seeds ranked no seed"; exit 1; }
say "top candidates (judge_seeds ranking)${FORCED:+, FORCED seed $FORCED}: $TOP"
if [ -n "$FORCED" ]; then FAILS=$((FAILS+1)); fi   # a forced seed is never DONE: it carries an illegal part; the post checks below say what

# candidates: reattach the cans, then the post checks (all run, failures counted)
for c in $TOP; do
  B=$S/c$c.kicad_pcb
  hard reattach_$c "$PY" -X utf8 "$V5/reattach.py" "$S/s$c.kicad_pcb" "$B"
  soft check_assembly_$c "$PY" -X utf8 py_tools/check_assembly.py "$B" --baseline "$S/fixed_cans.kicad_pcb" --intent "$S/intent_reattached.json" --json "$S/c$c.assembly.json"
  soft check_floorplan_$c "$PY" -X utf8 py_tools/check_floorplan.py "$B" --intent "$S/intent_reattached.json"
  soft designer_check_$c /usr/bin/python3 "$V5/designer_check.py" "$B" --intent "$S/intent_reattached.json" --baseline "$S/fixed_cans.kicad_pcb" --json "$S/c$c.designer.json"
  soft render_$c "$PY" -X utf8 py_tools/render_placement.py "$B" -o "$S/c$c.png"
done
say "DONE: candidates $TOP${FORCED:+ (seed $FORCED forced: no seed was judgeable)}, $FAILS failed step(s)/post check(s); PNGs $S/c<S>.png; ranking in $S/judge.log"
[ "$FAILS" -eq 0 ] || exit 1
