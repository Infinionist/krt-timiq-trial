# krt-timiq-trial

A placement trial of KiCadRoutingTools (KRT) v0.23.7 (commit db056e03) on the CERN TimIQ RF board.
@edgehero suggested the board. The work was done by a designer (Infinionist) driving Claude Code.
The board has 465 parts, 8 layers, 6 shield cans (J7-J12) and sits in a Hammond 1590Q lid.

This is raw working material, not a polished report. Point your own model at it.
Start with `notes/timiq.md`, then `runs/v6/REPORT.md`.

v6 is the run done the skill's way: the model reads the schematic, gets the physical facts and the
designer's intent, and runs the skill's rounds (3, 3 and 12 seeds). The earlier runs were our own
scripted variants and show where our setup went wrong.

Board source (CERN open hardware): https://gitlab.com/ohwr/project/timiq/timiq-hw

## Folders

- `notes/`: feedback notes for KRT (`timiq.md`: gaps, workarounds, where we leaned on the human board,
  results) and plans (`PLAN.md`, `PLAN-v2.md`).
- `scripts/`: small helper scripts shared by several runs.
- `runs/run1/`: first attempt, KRT's skill driven by Claude Opus with an empty design brief. 12 seeds, judge,
  final board with 557 blocking nets after routing.
- `runs/run2/`: second attempt. Plan v2 (see `notes/PLAN-v2.md`), prompt, inputs, and the can/hole/membership work files.
- `runs/v2/`: placer-only variant with our KRT patch. Scripts, intent, seeds, renders, human-board render.
- `runs/v3/`: loose anchor zones per can, courtyards synthesized, flippable faces. All 12 seeds illegal
  (our input bugs: a fixed LED in a hole keep-out, DAC bigger than its zone, overlapping zones). KRT flagged
  them only after 4 h of placing.
- `runs/v4/`: tight power strip and cans placed inside fixed zones, 6 seeds of 42 min. All 6 illegal
  (15-25 parts with no legal pose, mostly power). Our tiles were too tight.
- `runs/v5/`: holds `seeds-run1` (v5-1: all 282 can members inside their can, not DONE: 76 proximity misses,
  power entry split from regulators), `seeds-v4`, `seeds-run2` and `seeds` (v5b: power as loose groups, ICs locked
  on F; 3 seeds, all illegal, 7-9 parts with no legal pose). `cmp/` has the human-board comparison renders
  (human vs seed vs routed seed). `movie/` has the 3D placement movie.
- `runs/v6/`: the skill as written. `REPORT.md`, `final.kicad_pcb` (+ `.kicad_pro`, `final_intent.json`),
  `groups.json`, rounds `r1`/`r2`/`r3` (seed reports, logs, judge files, renders, best board per round),
  `best_*` renders, quick-route renders, `movie_r1..r3/placed_3d.mp4`, `ledger.jsonl`, start board, build scripts.
  Round 3: 6 of 12 seeds legal with 0 floorplan errors, the first legal placement of this board. Kept seed 7:
  buildable with BOX1 waivers, quick route 88 blocking (39 unrouted, 49 broken). Not DONE by the skill's table.

## What was trimmed

- No vendor datasheets (copyright) and no KRT clone. Get KRT v0.23.7 from its own repo.
- Route working dirs (`s*_route/`) were dropped except `runs/v6/r3/s7_route`.
- Only the best few seed boards of each round or run are kept. The seed `.json` reports and logs are all there.
- `*.kicad_prl` files and movie frame directories (`placed_movie3d/`) were dropped; the `.mp4` files are kept.
- `runs/v6/preflight_r1.txt` was over 5 MB in the original; it keeps its first and last 300 lines only.
- The name of the designer was replaced with `Infinionist` and home paths with `~`.

## Honest limits

The runs say as much about our setup as about KRT. The cans were taken off the board as a workaround (KRT has no
way to place parts inside a fixed can). J7-J10 poses, can membership and hole clearances follow the human board.
See "Where we cheated or leaned on the human board" in `notes/timiq.md`.
