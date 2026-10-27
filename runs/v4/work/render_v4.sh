#!/usr/bin/env bash
# render_v4.sh BOARD OUT.png : F.Cu + B.Cu + F.Silkscreen + B.Silkscreen + Edge.Cuts (+ F/B.Fab for ref labels), board-cropped
set -e
tmp=$(mktemp -d /tmp/pcb-trials/timiq/v4/work/rnd.XXXX)
kicad-cli pcb export svg --layers F.Cu,B.Cu,F.Silkscreen,B.Silkscreen,Edge.Cuts --mode-single --page-size-mode 2 -o $tmp/b.svg "$1" >/dev/null 2>&1
rsvg-convert -w 3000 -b white $tmp/b.svg -o "$2"
rm -rf $tmp
