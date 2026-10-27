#!/usr/bin/env python3
"""capture_rules2.md = capture_rules.md (run 1) adapted for run 2: run2 paths, the shield-can procedure, hole keep-outs."""
import re
t = open('/tmp/pcb-trials/timiq/capture_rules.md', encoding='utf-8').read()
def sub(old, new):
    global t
    assert old in t, old[:70]
    t = t.replace(old, new, 1)
t = re.sub(r'/tmp/pcb-trials/timiq/run\b', '/tmp/pcb-trials/timiq/run2', t)
sub("`mechanical.json` and `intent.json`. The schematic is beside it",
    "`mechanical.json` and `intent.json`. `helpers/cans.py` and `helpers/can_footprints.sexp` are given too (the shield cans, \"Board facts\" below). The schematic is beside it")
sub("- Every other part is yours to place: the other connectors, the shield frames, the LED D1, every IC and passive.",
    "- Every other part is yours to place: the other connectors, the LED D1, every IC and passive. The six shield-can fences J7-J12 are yours to place too, by the procedure in \"Board facts\" below: they are not on the board you are given.")
sub("each one a TOOL_GAPS.md entry saying why the repo's tools were not enough.",
    "each one a TOOL_GAPS.md entry saying why the repo's tools were not enough (the given `helpers/cans.py` is not a gap: it is part of the trial's setup).")
sub("(everything beside `run/` and `krt/`)", "(everything beside `run2/` and `krt/`, including `run/`, the folder of an earlier attempt)")
sub("**Editing** the design brief, `mechanical.json` or `intent.json` you were given; their sha256 are re-checked.",
    "**Editing** the design brief, `mechanical.json`, `intent.json`, `helpers/cans.py` or `helpers/can_footprints.sexp` you were given; their sha256 are re-checked.")
sub("`\"after\"` (every `place_pose` change you made after `place_simple`, or `[]`). With it",
    "`\"after\"` (every `place_pose` change you made after `place_simple`, or `[]`); `\"cans\"` (`\"cans.json\"`, the file the pass placed with). With it")
sub("`groups.json` and the intent file. Keep that intent file's own name.",
    "`groups.json`, `cans.json` and the intent file. Keep that intent file's own name.")
sub("Its input is a `copy_board.py` copy of your `final.kicad_pcb` (the kept placement), named `final_route/in.kicad_pcb`.",
    "Its input is a `copy_board.py` copy of your `final.kicad_pcb` (the kept placement) with the shield cans restored (`helpers/cans.py restore`, \"Board facts\" below), named `final_route/in.kicad_pcb`; say in REPORT.md that you restored them there.")
sub("`final.kicad_pcb` (the kept placement), `groups.json`,", "`final.kicad_pcb` (the kept placement, without the cans), `cans.json`, `groups.json`,")
facts = '''### Board facts: the six shield cans (J7-J12)

| J7-J12 are six RF shield-can fences, all the same part: a square ring of 24 GND pads, 32.8 mm outside, a 1.0 mm wall, 30.8 x 30.8 mm inside. The lid covers the front face only.
| Each can covers its inner area. Circuits that need shielding go inside a can. Nothing goes on the wall. A can with no circuit under it is pointless: if you leave one empty, say why in REPORT.md.
| The cans are free to place: you choose where each one goes, which circuits go inside it and how they are arranged. Nothing about this is given.
| KRT treats a fence as a solid body (its README, "Shield cans"), so no part can be seated under one. To work around that the fences are NOT on the board you are given. They come back after placement, at the poses you choose.

How it works, all by `python3 -X utf8 RUN/helpers/cans.py <command>` (`--help` for each; `geometry` prints the fence's dimensions):

1. Early, before you place (after you have read the schematic and chosen your groups), decide the six cans and write `RUN/cans.json`: `{"J7": {"cx": ..., "cy": ..., "rot": 0, "circuit": ["<ref>", "<glob>", ...]}, ...}`. `cx`, `cy` is the can's centre, `rot` is 0/90/180/270, `circuit` lists refs or globs of the parts that sit under that can. All six cans must be in the file. A B-side part is not covered by the lid and is left out of the zone with a note.
2. Copy `intent.json` to `intent_run.json` (as above), then run `cans.py declare --cans RUN/cans.json --intent RUN/intent_run.json --out RUN/intent_run.json --board RUN/fixed.kicad_pcb`. Per can it writes four wall keep-outs (F side), one block `can:<J>` whose zone is the can's inner area, and `overlap_waivers` pairs (each can with each F-side part that is not a declared mechanical part: about 1,500 rows, so that KRT's baseline gate accepts a part standing under a lid; pad, hole and keep-out rules stay absolute). These are rows you added to the intent: say so in REPORT.md once, do not list them one by one. Place with that intent.
3. After placing, `cans.py check <board> --cans RUN/cans.json --intent RUN/intent_run.json` is the pass/fail gate for the cans: every listed part inside its wall, nothing on a wall, the cans on the board and apart, clear of the hole keep-outs and of the declared mechanical parts. Exit 0 or 4. A kept placement must pass it. (`--strangers` also lists unlisted F-side parts under a lid, which is allowed.)
4. Before ANY routing or scoring of a placement, put the fences back: `cans.py restore <placement.kicad_pcb> <out.kicad_pcb> --cans RUN/cans.json`. Use it as the first line of the judging chain (`python3 -X utf8 RUN/helpers/cans.py restore {in} {out} --cans RUN/cans.json`) and to build `final_route/in.kicad_pcb`. The board you restore must not already carry J7-J12. The seeds, the placement boards and `final.kicad_pcb` stay without the cans; `routed.kicad_pcb` and `delivered.kicad_pcb` carry them.
5. If you change a can's pose or circuit, rewrite `cans.json`, run `declare` again and place again (a new pass).
6. A restored board has parts under the lids. The waivers from step 2 make KRT's grades accept that (a fence draws no courtyard, and its pads are its only copper); the `check` above is the check for the wall. Do not "fix" those pairs.

Mounting holes: the intent already carries six keep-out circles (`hole-J5-*`, `hole-BOX1-*`) around the 4.35 mm holes of J5 and the 4.0 mm holes of BOX1. They are given facts; do not move or remove them.

'''
sub("### Datasheets\n", facts + "### Datasheets\n")
open('/tmp/pcb-trials/timiq/capture_rules2.md', 'w', encoding='utf-8').write(t)
print('capture_rules2.md', len(t), 'chars')
