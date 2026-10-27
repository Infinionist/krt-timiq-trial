#!/usr/bin/env bash
# variant 4 placement on TimIQ: run 1's fixed board and groups (less the 'shields' group), intent_v4 (all known constraints)
cd /tmp/pcb-trials/timiq/v4
export PYTHONDONTWRITEBYTECODE=1
/tmp/pcb-trials/timiq/krt/.venv/bin/python -X utf8 /tmp/pcb-trials/timiq/v2/krt/py_placer/place_simple.py in/fixed.kicad_pcb "out/s{seed}.kicad_pcb" \
  --groups in/groups_v2.json --intent in/intent_v4.json --seeds ${SEEDS:-7,11} --clustered-seeds ${SEEDS:-7,11} --jobs 2 \
  --json "out/s{seed}.json" > out/place.log 2>&1
echo "exit $?" >> out/place.log
