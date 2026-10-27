#!/usr/bin/env bash
# gpm staging for one board (ported from gp14, from fa10's stage_board.sh; macOS).
#   bash wk/gpm/_staging/stage_board.sh NN STEM "SRC.kicad_pcb" [derive_decl args...]
# Run from the campaign worktree root (krt-gpm). Writes wk/gpm/_truth/STEM/ (the
# answer key) and wk/gpm/NN_STEM/ (the teammate's folder). Every step's output is in
# _truth/STEM/stage.log.
set -euo pipefail
WT=/tmp/pcb-trials/timiq/krt
export PATH="$WT/.venv/bin:$PATH"
NN=$1; STEM=$2; SRC=$3; shift 3
T=/tmp/pcb-trials/timiq/_truth; B=/tmp/pcb-trials/timiq/run; S=$WT/wk/gpm/_staging
FILM_WT=/tmp/pcb-trials/timiq/film_wt
mkdir -p "$T" "$B"
exec > >(tee "$T/stage.log") 2>&1
PY="python3 -B -X utf8"
echo "== 0 worktree $(git -C $WT rev-parse --short HEAD), source $SRC"
echo "== 1 copy source"
$PY $WT/py_router/copy_board.py "$SRC" "$T/human.kicad_pcb"
echo "== 2 strip copper (segments, arcs, vias, fills, teardrops, tuning patterns)"
$PY $WT/tests/stress/strip_copper_only.py "$T/human.kicad_pcb" "$T/human_stripped.kicad_pcb"
echo "== 2b strip board text, drawings off Edge.Cuts, padless artwork"
$PY $S/strip_drawings.py "$T/human_stripped.kicad_pcb"
echo "== 3 pile (every part with pads moved south of the outline, every lock removed)"
$PY $WT/.claude/skills/plan-pcb-placement/scripts/make_unplaced.py "$T/human_stripped.kicad_pcb" "$B/$STEM.kicad_pcb"
$PY - "$B/$STEM.kicad_pcb" "$FILM_WT/tests/stress" <<'EOF'
import json, sys
sys.path.insert(0, sys.argv[2])
from stage_unaided import sanitize_staged_project
print('sanitize:', json.dumps(sanitize_staged_project(sys.argv[1]), default=str)[:600])
EOF
echo "== 3a strip pad-level locks (KiCad 6 locks pads one by one; make_unplaced leaves them)"
$PY $S/strip_pad_locks.py "$B/$STEM.kicad_pcb"
echo "== 3b sanitize the pile (local zones under 25 %, text angles)"
$PY $S/sanitize_pile.py "$B/$STEM.kicad_pcb"
echo "== 4 declarations (rule fa10-decl-v1)"
$PY $S/derive_decl.py "$T/human_stripped.kicad_pcb" --stem "$STEM" --out "$B" --json-out "$T/decl.json" "$@"
# TRIAL ADAPTATION: no fixed[] decisions staged; the rule's output is parked outside the run folder
[ -f "$B/mechanical.json" ] && mv "$B/mechanical.json" "$T/rule_mechanical.json"
MECH=(); [ -f "$B/mechanical.json" ] && MECH=(--mechanical "$B/mechanical.json") || MECH=(--no-mechanical)
echo "== 5a validate on the human board"
$PY $WT/py_tools/check_floorplan.py "$T/human_stripped.kicad_pcb" --brief "$B/$STEM.design-brief.json" "${MECH[@]}" \
    --emit-intent "$T/human_intent.json" --decaps-from "$T/human_stripped.kicad_pcb" || echo "EMIT-ON-HUMAN exit $?"
$PY $WT/py_tools/check_floorplan.py "$T/human_stripped.kicad_pcb" --intent "$T/human_intent.json" --brief "$B/$STEM.design-brief.json" \
    "${MECH[@]}" --require-brief-coverage --json "$T/human_grade.json" || echo "GRADE-ON-HUMAN exit $?"
echo "== 5b emit the run intent on the pile"
$PY $WT/py_tools/check_floorplan.py "$B/$STEM.kicad_pcb" --emit-intent "$B/intent.json" --allow-unplaced \
    --decaps-from "$T/human_stripped.kicad_pcb" || echo "EMIT-ON-PILE exit $?"
$PY $S/redact_intent.py "$B/intent.json"
echo "== 6 record"
$PY - "$T" "$B" "$STEM" "$SRC" <<'EOF'
import hashlib, json, os, sys
T, B, stem, src = sys.argv[1:]
def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest() if os.path.exists(p) else None
def sha_crlf(p):
    t = open(p, 'rb').read().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    return hashlib.sha256(t).hexdigest()
files = {n: sha(os.path.join(B, n)) for n in sorted(os.listdir(B)) if os.path.isfile(os.path.join(B, n))}
json.dump({'stem': stem, 'source': src, 'source_sha256': sha(src), 'source_sha256_crlf': sha_crlf(src),
           'inputs': files}, open(os.path.join(T, 'stage.json'), 'w'), indent=2)
print(json.dumps(files, indent=1))
EOF
echo "== 7 gate"
$PY $S/stage_gate.py "$B" "$STEM" --human "$T/human_stripped.kicad_pcb" --json "$T/gate.json"
