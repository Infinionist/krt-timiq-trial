#!/usr/bin/env bash
# usage: run_place.sh TAG GROUPS INTENT SEEDS [extra place_simple args...]
set -uo pipefail
TAG=$1; G=$2; I=$3; SEEDS=$4; shift 4
V=/tmp/pcb-trials/timiq/v3; K=/tmp/pcb-trials/timiq/krt
mkdir -p $V/out/$TAG
export PYTHONDONTWRITEBYTECODE=1
cd $V/out/$TAG
exec nice -n 10 $K/.venv/bin/python -X utf8 $K/py_placer/place_simple.py $V/in/fixed.kicad_pcb "$V/out/$TAG/s{seed}.kicad_pcb" \
  --groups $G --intent $I --seeds $SEEDS --jobs 2 --json "$V/out/$TAG/s{seed}.json" "$@"
