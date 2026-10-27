#!/usr/bin/env bash
# render.sh BOARD OUT.png : F.Cu + B.Cu + F.Silkscreen + Edge.Cuts, board-cropped
set -e
tmp=$(mktemp -d /tmp/pcb-trials/timiq/v2/work/rnd.XXXX)
kicad-cli pcb export svg --layers F.Cu,B.Cu,F.Silkscreen,Edge.Cuts --mode-single --page-size-mode 2 -o $tmp/b.svg "$1" >/dev/null 2>&1
rsvg-convert -w 2400 -b white $tmp/b.svg -o "$2"
rm -rf $tmp
