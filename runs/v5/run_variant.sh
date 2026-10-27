#!/bin/sh
V=$1; D=/tmp/pcb-trials/timiq/v5/probe/tiny_$V; K=/tmp/pcb-trials/timiq/krt
$K/.venv/bin/python -X utf8 $K/py_placer/place_simple.py $D/tiny.kicad_pcb $D/out.kicad_pcb --groups $D/groups.json --intent $D/intent.json --seed 1 --json $D/out.json > $D/place.log 2>&1
echo "rc=$?" > $D/rc.txt
