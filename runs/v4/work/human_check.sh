#!/bin/bash
# human_check.sh [intent] : check_floorplan on the human board with the v4 intent + brief
I=${1:-/tmp/pcb-trials/timiq/v4/in/intent_v4.json}
cd /tmp/pcb-trials/timiq/v2/krt
/tmp/pcb-trials/timiq/krt/.venv/bin/python -X utf8 py_tools/check_floorplan.py /tmp/pcb-trials/timiq/v4/in/human.kicad_pcb --intent $I --json /tmp/pcb-trials/timiq/v4/work/human_check.json --allow-routed > /tmp/pcb-trials/timiq/v4/work/human_check.txt 2>&1
echo exit $?
