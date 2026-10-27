#!/usr/bin/env bash
# variant 2 placement on TimIQ: run 1's fixed board and groups (less the 'shields' group), intent + shields[]
cd /tmp/pcb-trials/timiq/v2
export PYTHONDONTWRITEBYTECODE=1
/tmp/pcb-trials/timiq/krt/.venv/bin/python -X utf8 krt/py_placer/place_simple.py run/fixed.kicad_pcb "out/s{seed}.kicad_pcb" \
  --groups run/groups_v2.json --intent run/intent_v2.json --seeds 7,11 --clustered-seeds 7,11 --jobs 2 \
  --json "out/s{seed}.json" > out/place.log 2>&1
echo "exit $?" >> out/place.log
