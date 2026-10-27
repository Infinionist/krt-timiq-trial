#!/usr/bin/env bash
# render.sh BOARD OUT.png  : F.Cu+B.Cu+F.Silkscreen+Edge.Cuts+Dwgs.User (fences) -> PNG. BOARD already carries the fences (fence.py --emit-gr).
set -euo pipefail
B=$1; O=$2; T=$(mktemp -d /tmp/pcb-trials/timiq/v3/render_XXXX)
kicad-cli pcb export svg "$B" -o "$T/o.svg" --layers "F.Cu,B.Cu,F.Silkscreen,Edge.Cuts,Dwgs.User" --black-and-white --exclude-drawing-sheet --page-size-mode 2 >/dev/null
rsvg-convert -w 2400 -b white "$T/o.svg" -o "$O"
rm -rf "$T"
