#!/bin/bash
# Resume the TimIQ run after a usage-limit stop. Usage: resume.sh "<new deadline, e.g. 2026-10-27T03:10-05:00>"
T=/tmp/pcb-trials/timiq; RUN=$T/run; WT=$T/krt
SESSION=$(cat $T/run.session); DL="${1:?new deadline}"
MSG="You were stopped by a usage limit, not by anything you did. The time you were stopped does not count: your new hard deadline (report included) is $DL; stop starting new work 45 min before it. First: date -Is, re-read RUN/STATE.md and TOOL_GAPS.md, check which of your background jobs still exist (ps) and which finished (their logs), then continue the skill from where you were. All earlier rules still hold. Note the pause and the resume time in STATE.md."
cd "$WT" || exit 1
export CLAUDE_HOOKS_OFF=1 ENABLE_CLAUDEAI_MCP_SERVERS=false KICAD_ROUTE_TRACE=1 KRT_DATASHEET_DIR=$RUN/datasheets PYTHONDONTWRITEBYTECODE=1
timeout --signal=TERM --kill-after=120 280m /usr/local/bin/claude -p "$MSG" --resume "$SESSION" --output-format stream-json --verbose \
  --allowedTools 'Bash,Read,Glob,Grep,Write,Edit,WebSearch,WebFetch,Agent,Task,TodoWrite,Monitor' --add-dir "$RUN" --model opus \
  --setting-sources project,local --strict-mcp-config >> "$RUN/stream.jsonl" 2>> "$T/run.stderr.log"
echo "resume exit $? $(date -Is)" | tee -a $T/run.resumes
