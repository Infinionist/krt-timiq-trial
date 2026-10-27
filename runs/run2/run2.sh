#!/usr/bin/env bash
# TimIQ RF KRT placement trial, RUN 2 (shield cans J7-J12 off the board during placement, restored by helpers/cans.py).
# Same model, flags, backstop and capture as run.sh; its own folder (run2/), prompt (prompt2.md), session file and logs.
# Prepared 2026-10-26, NOT STARTED by the setup.
#
#   bash /tmp/pcb-trials/timiq/run2.sh --print    print the exact command and the environment, run nothing
#   bash /tmp/pcb-trials/timiq/run2.sh --check    preflight only (no model call), then exit
#   bash /tmp/pcb-trials/timiq/run2.sh            preflight, then the run (foreground; start it as a background job)
#
# What it does, in order: preflight (all by script) -> stage gate -> fence_audit create -> cheat watcher ->
# `claude -p` (stream-json to run/stream.jsonl, stderr to run.stderr.log, exit code to run.exit) -> post checks.
# It is built the way krt/kicad_routing_plugin/placement_run.py + ai_backend.ClaudeBackend.build_cmd build the
# placement-tab launch (-p, --output-format stream-json --verbose, --allowedTools PLACEMENT_ALLOWED_TOOLS, --add-dir
# <workdir>, --model), with edgehero's capture rules (staging/teammate_prompt.md, launch_board.sh) in prompt.md.
# Runs under `claude` on the subscription: ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN are unset, claude-api is not used.
# To resume after a crash or a usage-limit stop:  claude -p --resume $(cat run2.session) "Continue from STATE.md." (same flags)
# Usage check: at about 30 min in, `claude-api --status` / the usage page; the run is capped by the prompt at 4 h 15 min.
set -uo pipefail

T=/tmp/pcb-trials/timiq
WT=$T/krt
RUN=$T/run2
MODEL=opus
BACKSTOP=280m            # prompt cap is 4h15 from FIRST_CMD (report included); this only kills a stuck run
PROMPT_FILE=$T/prompt2.md
ALLOWED='Bash,Read,Glob,Grep,Write,Edit,WebSearch,WebFetch,Agent,Task,TodoWrite,Monitor'   # = placement_run.PLACEMENT_ALLOWED_TOOLS
EXPECT_KRT=db056e03
MODE=${1:-run}

# environment of the run (children inherit it)
export PATH="$WT/.venv/bin:$PATH"                       # python3 = krt/.venv (3.12), as the prompt says
export CLAUDE_HOOKS_OFF=1                               # Infinionist's hooks (budget notes, hold) must not steer this run
export ENABLE_CLAUDEAI_MCP_SERVERS=false                # no claude.ai connectors in the run
export KICAD_ROUTE_TRACE=1                              # edgehero: records route events beside each board; no copper change
export KRT_DATASHEET_DIR=$RUN/datasheets                # ai_backend.DATASHEET_DIR_ENV; the prompt says mv it to old/ at the end
export PYTHONDONTWRITEBYTECODE=1                        # keep the checkout clean for the cheat watcher
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL

CLAUDE=$(type -P claude || true)
SESSION=${SESSION_ID:-$(cat /proc/sys/kernel/random/uuid)}

# the command, as an array (prompt read from prompt.md at launch)
build_cmd() {
  CMD=(timeout --signal=TERM --kill-after=120 "$BACKSTOP"
       "$CLAUDE" -p "$(cat "$PROMPT_FILE")"
       --output-format stream-json --verbose
       --allowedTools "$ALLOWED"
       --add-dir "$RUN"
       --model "$MODEL"
       --setting-sources project,local                  # not Infinionist's user settings: no hooks, no global CLAUDE.md; krt/.claude project settings + skills stay
       --strict-mcp-config                              # no MCP servers at all
       --session-id "$SESSION")
}

if [ "$MODE" = "--print" ]; then
  echo "cwd:    $WT"
  echo "env:    PATH=$WT/.venv/bin:\$PATH CLAUDE_HOOKS_OFF=1 ENABLE_CLAUDEAI_MCP_SERVERS=false KICAD_ROUTE_TRACE=1 KRT_DATASHEET_DIR=$KRT_DATASHEET_DIR PYTHONDONTWRITEBYTECODE=1 (ANTHROPIC_API_KEY/AUTH_TOKEN/BASE_URL unset)"
  echo "stdin:  /dev/null    stdout: $RUN/stream.jsonl    stderr: $T/run2.stderr.log    exit code: $T/run2.exit"
  echo "command:"
  echo "  timeout --signal=TERM --kill-after=120 $BACKSTOP $CLAUDE -p \"\$(cat $PROMPT_FILE)\" \\"
  echo "    --output-format stream-json --verbose --allowedTools '$ALLOWED' \\"
  echo "    --add-dir $RUN --model $MODEL --setting-sources project,local --strict-mcp-config --session-id <fresh uuid>"
  echo "prompt: $PROMPT_FILE ($(wc -c < "$PROMPT_FILE") bytes, sha256 $(sha256sum "$PROMPT_FILE" | cut -d' ' -f1)); first line:"
  head -c 220 "$PROMPT_FILE"; echo " ..."
  exit 0
fi

fail() { echo "PREFLIGHT FAIL: $*" >&2; exit 3; }
note() { echo "preflight ok: $*"; }

preflight() {
  [ -n "$CLAUDE" ] && [ -x "$CLAUDE" ] || fail "claude not on PATH"
  case "$CLAUDE" in *claude-api*) fail "claude resolves to claude-api";; esac
  note "claude = $CLAUDE ($("$CLAUDE" --version 2>&1 | head -1))"
  "$CLAUDE" auth status 2>&1 | grep -q '"authMethod": "claude.ai"' || fail "claude is not logged in with the claude.ai subscription"
  note "subscription login (claude.ai)"
  command -v timeout >/dev/null || fail "no timeout"
  for f in "$PROMPT_FILE" "$WT/.venv/bin/python3" "$WT/rust_router/grid_router.so" \
           "$WT/.claude/skills/plan-pcb-placement/SKILL.md" "$WT/.claude/skills/plan-pcb-routing/SKILL.md" \
           "$WT/.claude/skills/analyze-power-nets/SKILL.md" "$WT/.claude/skills/plan-pcb-placement/scripts/grade.py" \
           "$WT/.claude/skills/plan-pcb-placement/scripts/measure.py" "$WT/py_placer/converge.py" "$WT/py_placer/judge_seeds.py" \
           "$WT/py_placer/place_simple.py" "$WT/py_placer/place_pose.py" "$WT/py_router/copy_board.py" \
           "$WT/tests/stress/run_watch.py" "$T/film_wt/tests/stress/fence_audit.py" "$T/_truth/human_stripped.kicad_pcb" \
           "$WT/wk/gpm/_staging/stage_gate.py" /usr/bin/kicad-cli /usr/bin/python3; do
    [ -e "$f" ] || fail "missing $f"
  done
  note "referenced paths exist"
  "$WT/.venv/bin/python3" -c "import sys; sys.path.insert(0,'$WT/rust_router'); import grid_router, numpy, scipy, shapely" 2>/dev/null \
    || fail "krt venv cannot import grid_router/numpy/scipy/shapely"
  note "venv imports (grid_router, numpy, scipy, shapely)"
  [ "$(git -C "$WT" rev-parse --short=8 HEAD)" = "$EXPECT_KRT" ] || fail "krt HEAD is not $EXPECT_KRT"
  [ -z "$(git -C "$WT" status --porcelain --untracked-files=no)" ] || fail "krt has tracked changes"
  note "krt at $EXPECT_KRT, no tracked changes"
  (cd "$RUN" && sha256sum -c --quiet "$T/inputs2.sha256") || fail "run inputs differ from inputs2.sha256"
  note "run inputs match inputs2.sha256 (board, pro, brief, mechanical.json, intent.json, 11 sheets, sym-lib-table, rescue lib)"
  # run 2: the shield-can helper works on this board (restore -> parse -> check), and the pile carries no fence
  mkdir -p "$T/watch2"; CT=$(mktemp -d "$T/watch2/cans_selftest.XXXXXX")
  "$WT/.venv/bin/python3" - "$CT" <<'PY' || fail "cans.py selftest could not write its dummy cans.json"
import json, sys
d = {c: {"cx": 150 + 40 * (i % 3), "cy": 100 + 40 * (i // 3), "rot": r, "circuit": []} for i, (c, r) in enumerate(zip(["J7","J8","J9","J10","J11","J12"], [0, 90, 180, 270, 0, 90]))}
json.dump(d, open(sys.argv[1] + "/cans.json", "w"))
PY
  [ "$(grep -cP '^\t\(footprint ' "$RUN/TimIQ_RF.kicad_pcb")" = 458 ] || fail "run2 board should carry 458 footprints (the pile without J7-J12)"
  "$WT/.venv/bin/python3" -B -X utf8 "$RUN/helpers/cans.py" restore "$RUN/TimIQ_RF.kicad_pcb" "$CT/r.kicad_pcb" --cans "$CT/cans.json" >/dev/null || fail "cans.py restore failed on the run2 board"
  [ "$(grep -cP '^\t\(footprint ' "$CT/r.kicad_pcb")" = 464 ] || fail "restored board should carry 464 footprints"
  "$WT/.venv/bin/python3" -B -X utf8 "$RUN/helpers/cans.py" check "$CT/r.kicad_pcb" --cans "$CT/cans.json" >/dev/null || fail "cans.py check failed on the restored selftest board"
  "$WT/.venv/bin/python3" -B -X utf8 "$RUN/helpers/cans.py" restore "$CT/r.kicad_pcb" "$CT/r2.kicad_pcb" --cans "$CT/cans.json" >/dev/null 2>&1 && fail "cans.py restore must refuse a board that already carries the fences (must-fail)"
  rm -rf "$CT"
  note "cans.py: restore -> 464 footprints -> check passes; restoring twice is refused"

  if [ "${RESUME:-0}" != 1 ]; then
    for m in STATE.md stream.jsonl ledger.jsonl DONE REPORT_DONE delivered.kicad_pcb .fence-manifest.json; do
      [ ! -e "$RUN/$m" ] || fail "$RUN/$m exists: the run was already started (set RESUME=1 to resume, or move run2/ aside)"
    done
    note "run folder is fresh"
  fi
  [ "${SKIP_TRUST_CHECK:-0}" = 1 ] || "$WT/.venv/bin/python3" - <<'PY' || fail "workspace trust for $WT not accepted yet: Infinionist opens claude once in $WT and accepts the trust prompt (or SKIP_TRUST_CHECK=1)"
import json, os, sys
p = json.load(open(os.path.expanduser('~/.claude.json'))).get('projects', {}).get('/tmp/pcb-trials/timiq/krt') or {}
sys.exit(0 if p.get('hasTrustDialogAccepted') else 1)
PY
  note "workspace trust accepted for $WT"
  "$WT/.venv/bin/python3" -B -X utf8 "$WT/wk/gpm/_staging/stage_gate.py" "$RUN" TimIQ_RF --human "$T/_truth/human_stripped.kicad_pcb" --json "$T/_truth/gate_preflight2.json" \
    >"$T/gate_preflight2.log" 2>&1 || { cat "$T/gate_preflight2.log" >&2; fail "stage gate does not pass"; }
  note "stage gate: $(head -c 160 "$T/gate_preflight2.log")"
}

preflight
[ "$MODE" = "--check" ] && { echo "preflight passed; nothing started"; exit 0; }

mkdir -p "$KRT_DATASHEET_DIR" "$T/watch2"
START=$(date -Is)
{ echo "start=$START"; echo "session=$SESSION"; echo "model=$MODEL"; echo "krt=$(git -C "$WT" rev-parse HEAD)"; echo "claude=$("$CLAUDE" --version 2>&1 | head -1)"; } > "$T/run2.meta"
echo "$SESSION" > "$T/run2.session"

# edgehero's launch_board.sh: fence record of the starting files against the human placement, then the cheat watcher
"$WT/.venv/bin/python3" -B -X utf8 "$T/film_wt/tests/stress/fence_audit.py" --control "$T/_truth/human_stripped.kicad_pcb" --workdir "$RUN" --mode create 2>&1 \
  | grep -v '^WARNING' | tail -3 | tee "$T/watch2/fence_create.txt"
[ "${PIPESTATUS[0]}" = 0 ] || { echo "fence_audit create failed (a leak, or an error): not starting" >&2; exit 4; }

( cd "$WT" || exit 1
  nohup "$WT/.venv/bin/python3" -X utf8 tests/stress/run_watch.py cheats --workdir "$RUN" --done "$RUN/DONE" \
    --report-done "$RUN/REPORT_DONE" --report-wait 0 > "$T/watch2/cheats.log" 2>&1 &
  echo $! > "$T/watch2/cheats.pid" )
# NOT started: `run_watch.py bugs`. It scans *.jsonl in the workdir, so it would read run/stream.jsonl (which quotes every tool
# output) and flood itself with its own quotes. TOOL_GAPS.md and the stream cover the same ground.

build_cmd
cd "$WT"
"${CMD[@]}" > "$RUN/stream.jsonl" 2> "$T/run2.stderr.log" < /dev/null
RC=$?
echo "$RC" > "$T/run2.exit"
echo "end=$(date -Is)" >> "$T/run2.meta"
echo "exit=$RC" >> "$T/run2.meta"

# post checks (no model calls)
[ -s "$T/watch2/cheats.pid" ] && kill "$(cat "$T/watch2/cheats.pid")" 2>/dev/null
"$WT/.venv/bin/python3" -B -X utf8 "$T/film_wt/tests/stress/fence_audit.py" --control "$T/_truth/human_stripped.kicad_pcb" --workdir "$RUN" --mode audit \
  > "$T/watch2/fence_audit.txt" 2>&1
(cd "$RUN" && sha256sum -c "$T/inputs2.sha256" > "$T/watch2/inputs_recheck.txt" 2>&1; echo "inputs_recheck_exit=$?" >> "$T/watch2/inputs_recheck.txt")
git -C "$WT" status --porcelain --untracked-files=no > "$T/watch2/krt_git_status.txt"
echo "run finished: exit $RC (see $T/run2.meta, $T/run2.stderr.log, $RUN/stream.jsonl)"
exit "$RC"
