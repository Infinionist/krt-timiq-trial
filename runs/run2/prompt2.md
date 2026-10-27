/plan-pcb-placement full /tmp/pcb-trials/timiq/run2/TimIQ_RF.kicad_pcb /tmp/pcb-trials/timiq/run2/intent.json — Work headless and unattended; never wait for user input. Use /tmp/pcb-trials/timiq/run2 as the working directory for ALL artifacts (groups.json, the intent, scores, renders, REPORT.md). Keep the seeds in /tmp/pcb-trials/timiq/run2/ with the skill's names (s<S>.kicad_pcb, s<S>.json, s<S>_route/, s<S>_fast.kicad_pcb, s<S>_fast.score.json): this GUI's candidates table reads them. Keep the converge ledger at /tmp/pcb-trials/timiq/run2/ledger.jsonl. Do not modify any file outside /tmp/pcb-trials/timiq/run2, and never edit TimIQ_RF.kicad_pcb in place. Read datasheets with WebSearch and WebFetch; a PDF datasheet reads better downloaded (curl) and opened with the Read tool, a few `pages` at a time, figures included. If you must save a downloaded file, save it only under $KRT_DATASHEET_DIR, which the orchestrator deletes after the run. If you dispatch a subagent, copy this sentence into its prompt verbatim: it must not modify any file outside /tmp/pcb-trials/timiq/run2 (a downloaded datasheet may go under $KRT_DATASHEET_DIR), must never edit TimIQ_RF.kicad_pcb in place, and must answer with a line beginning VERDICT= (never RESULT=, which this GUI reads as the run's own result line). At close-out write the final board to /tmp/pcb-trials/timiq/run2/final.kicad_pcb (with sibling final.kicad_pro) and the report to /tmp/pcb-trials/timiq/run2/REPORT.md. If a gate refuses because the board already carries routed copper, stop and report status "refused" instead of stripping copper. On a pile, check_floorplan's unplaced gate is not a refusal of this run: pass it --allow-unplaced, as the skill says. Record every milestone board in that ledger as you go (the skill's `converge.py record` step): this GUI shows the newest row as the run's progress. ## Trial rules (these add to the skill; where one conflicts with the lines above, these win)

You are running the `/plan-pcb-placement` skill (upstream KiCadRoutingTools main, v0.23.7) on ONE board, alone, start to finish: a pile of parts with no routing in, a finished board out, or a stop when one of the skill's stop rules fires. You are being measured: the result, the time and the tool problems you hit are the point. Work honestly. A clear "NOT DONE, here is why, here are the blockers" is a valid result; a fudged DONE is not.

### Paths

- The repo checkout (WT) is your working directory: `/tmp/pcb-trials/timiq/krt`. Every repo-relative path in the skill (`py_router/...`, `py_tools/...`, `py_placer/...`, `.claude/skills/...`) is relative to it.
- Your folder (the skill's `wk/<run>`): `/tmp/pcb-trials/timiq/run2`, called RUN below. Use the absolute path wherever the skill writes `wk/<run>`.
- Input board: `RUN/TimIQ_RF.kicad_pcb`, with its `.kicad_pro`, `TimIQ_RF.design-brief.json`, `mechanical.json` and `intent.json`. `helpers/cans.py` and `helpers/can_footprints.sexp` are given too (the shield cans, "Board facts" below). The schematic is beside it (`RUN/TimIQ_RF.kicad_sch` is the root, 10 more sheets, `sym-lib-table`, `TimIQ-RF_sch-rescue.lib`); `board_context.py` finds it by itself.
- `python3` on PATH is the repo's venv Python 3.12 (numpy, scipy, shapely, ortools). Use `python3 -X utf8`. Use `/usr/bin/kicad-cli` for KiCad's CLI.
- Net names start with `/`, so quote globs: `--nets '*'`.
- Run EVERY routing command of `judge_seeds.py` with `KICAD_ROUTE_TRACE=1` in its environment (it is already exported for this run; keep it).

### The invocation, and what it means

Your invocation is the equivalent of `/plan-pcb-placement full RUN/TimIQ_RF.kicad_pcb RUN/intent.json`: the skill's defaults, one pass of 12 seeds (6 scattered, 6 clustered), with the 6 the objective rates best judged by `py_placer/judge_seeds.py`. Anchored seeds are opt-in and not part of this test. Everything the skill says applies, through §3.9's `delivered.kicad_pcb`: the workflow including §3.5's datasheet templates, the stop rules, the verifier (one subagent, at most 3 calls), the ledger and REPORT.md.

You cannot invoke a skill from inside the skill, so follow every skill it names by hand, from its SKILL.md: `/plan-pcb-routing` (the full route, §3.8) and the `/analyze-power-nets` step it asks for. For each, write in REPORT.md that you followed it by hand.

**The intent you were given is read-only.** `intent.json` already compiles the design brief and `mechanical.json`, so do not emit another (§3.2: a given intent is the intent). Some skill steps write an intent: `waive_locked_overlaps.py`, `fit_template.py --write-intent`, an `overlap_waivers[]` or `proximity[]` row you add. Before the first of them, copy `intent.json` to `intent_run.json`, then use `intent_run.json` for every later step, placing, judging, scoring and the verifier included. REPORT.md lists every row you added to it, with the reason. `fixed.kicad_pcb` is a `copy_board.py` copy of the input board. Nothing in it is locked; the declared poses reach `place_simple` through the intent's `fixed_poses[]`.

### What you are given, and what you are not

- `mechanical.json` declares 22 parts at exact poses: BOX1, FIX1-FIX8 (mounting hardware), J1-J6 (connectors) and D2-D8 (LEDs). They are the user's stated mechanical requirements (the skill's §3.1 / `fixed_poses[]`). Every part, those included, starts in the pile and unlocked; a declared pose is a target the placer seats. Parts keep the side (F.Cu or B.Cu) they had; the pile flips nothing.
- Every other part is yours to place: the other connectors, the LED D1, every IC and passive. The six shield-can fences J7-J12 are yours to place too, by the procedure in "Board facts" below: they are not on the board you are given.
- The board outline is fixed (the skill never changes it). Board-wide pours are kept; their fills were removed.
- **EMC rows: none are given.** Do not invent limits. The user is not available. Proceed without `proximity[]` / `keep_away` rows, and say in REPORT.md that none were given and which of the skill's questions you therefore could not ask.
- **Any other choice the skill leaves to the user** (for example which of two locked parts to move): make it yourself and record it in REPORT.md as a judgment.
- **The user is not available during this run.** Never wait for input.

### Board facts: the six shield cans (J7-J12)

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

### Datasheets

- You may WebSearch / WebFetch / curl a part number's datasheet from a manufacturer's or distributor's site.
- You may NOT look up this board or its project: not its name, its repo, its schematic or layout images, OSHWLab, GitHub, GitLab or kicad.org pages about it, nor any other design that is this one under another name.
- A downloaded file is saved under `$KRT_DATASHEET_DIR` (= `RUN/datasheets`), one folder per part. At the end, per the skill's §6.4, `mv` `datasheets/` to `old/datasheets/` (never delete).

### Time (a hard cap)

- Before your first tool command, run `date -Is` and write `FIRST_CMD: <that time>` into `RUN/STATE.md`.
- The cap is **4 h 15 min from FIRST_CMD, report included.** Check `date -Is` at every milestone. At 3 h 30 min stop starting new placements, routes or experiments: finish what runs, pick the best board you have, and run the skill's close-out. By 4 h 15 min `delivered.kicad_pcb`, REPORT.md, TOOL_GAPS.md, the verdict files and both marker files must exist. If the board is not DONE, that is "NOT DONE", with the blockers named (which nets, which parts, what you tried, which stop rule fired). It is the expected outcome on a board this size; say so plainly.
- Keep `RUN/STATE.md` current at every milestone: the best board's path and sha256, its board_score, running jobs and their logs, what you try next. If your context is reset or you are resumed, read STATE.md and the ledger and CONTINUE. Never restart from the pile.
- **This is a headless run: your final reply ends the whole run, and every background job dies with it.** Never write the final reply while a job of yours is still running or before `REPORT_DONE` exists. Wait for a long job with the Monitor tool, or with bounded polls in Bash (`sleep` under 9 minutes per call), never by ending your turn. A background job is finished only when its log shows its exit line. Never write or assume a completion notice yourself. Never leave a background job unwatched for more than 20 minutes.

### Shell and machine rules

- **Never run `rm -r` or `rm -rf`, nor delete a directory.** To get rid of something, move it into `RUN/old/` with `mv`.
- Use `run_in_background` for any command that may exceed the tool's foreground timeout; a background job is killed at its own `timeout`.
- The machine is shared with other work. Caps: `place_simple --jobs 4`; `judge_seeds.py --jobs 3`; at most 3 routing processes of yours at once; never a judging route beside a placement of yours.
- **No `gh` write of any kind** (no issue, comment, PR, reaction), no `git commit`, `git push`, `git add` or `git checkout` in the checkout, no edit of any tracked repo file (tools, tests, docs, skills). `gh issue list --repo drandyhaas/KiCadRoutingTools --state all --search "<keywords>"` (read-only) is allowed for TOOL_GAPS.md; reading an issue's title is fine. Do not open issue bodies for issues that describe this board.
- If a tool is wrong, work around it with a script in `RUN/helpers/` and record the gap in TOOL_GAPS.md.
- Any subagent except the single verifier the skill specifies is not allowed.

### Not allowed

- **Reading** anything outside these places: `RUN/`, the checkout `/tmp/pcb-trials/timiq/krt` (except `wk/`, which is staging for the people who run you), `$KRT_DATASHEET_DIR`, system and Python library paths, KiCad's install (`/usr/share/kicad`, `/usr/lib/kicad*`). In particular do not read, list or open: anything else under `/tmp/pcb-trials/`, `/tmp/pcb-trials/timiq/` (everything beside `run2/` and `krt/`, including `run/`, the folder of an earlier attempt), `~/projects`, `~/.claude`, `/mnt/c`, `~/Downloads`, other checkouts or worktrees of KiCadRoutingTools, any copy of this design anywhere, git history of board files, and GitHub discussion #118.
- **Writing** outside `RUN/` (and `$KRT_DATASHEET_DIR`, which is inside it).
- **Editing** the design brief, `mechanical.json`, `intent.json`, `helpers/cans.py` or `helpers/can_footprints.sexp` you were given; their sha256 are re-checked.

### Files the orchestrator films and grades (keep them exactly)

- **The seeds stay where the skill puts them**, in `RUN/`: `s<S>.kicad_pcb/.json/.log`, `s<S>_route/`, `s<S>_fast.kicad_pcb` and `s<S>_fast.score.json`, plus `judge.json` and `judge_chain.txt`.
- **`RUN/placed_from/`** holds exactly the files the pass that produced your kept seed read: `fixed.kicad_pcb` (with its `.kicad_pro`, via `copy_board.py`), `groups.json`, `cans.json` and the intent file. Keep that intent file's own name.
- **Placing again** (a new pass of §3.6) overwrites the seeds. Before it, `mv` the previous pass's `s*` files, `judge.json`, `judge_chain.txt` and `placed_from/` into `RUN/old/pass<K>/`.
- **`RUN/CHOSEN.json`** has these keys: `"seed"` (S, the kept seed); `"start"` (`"scattered"` or `"clustered"`); `"pass"` (K); `"intent"` (the intent file the pass placed with); `"place_args"` (every `place_simple` argument of that pass beyond the input, OUT, `--groups`, `--intent`, `--jobs` and `--json`, e.g. `["--template-weight", "200"]`, or `[]`); `"after"` (every `place_pose` change you made after `place_simple`, or `[]`); `"cans"` (`"cans.json"`, the file the pass placed with). With it the kept seed can be re-filmed exactly.
- **The full route (§3.8) runs in `RUN/final_route/`.** Its input is a `copy_board.py` copy of your `final.kicad_pcb` (the kept placement) with the shield cans restored (`helpers/cans.py restore`, "Board facts" below), named `final_route/in.kicad_pcb`; say in REPORT.md that you restored them there. Export three variables for EVERY routing command of that chain: `REDO_RUNDIR=/tmp/pcb-trials/timiq/run2/final_route`, `REDO_MANIFEST=$REDO_RUNDIR/redo_commands.sh` and `KICAD_ROUTE_TRACE=1`. After the first step check that `final_route/redo_commands.sh` exists. The chain's last board is copied with `copy_board.py` to `RUN/routed.kicad_pcb`; that is the board §3.9 starts from. If you route the final board more than once, `mv` the old `final_route/` to `final_route_old<K>/` first, so `final_route/` holds the chain of the board you ship.
- **Ledger.** Record every milestone the skill names (§5 rule 6) with `py_placer/converge.py record`, `--parent` set to the board it was made from, in `RUN/ledger.jsonl`: the first legal placement; EVERY judged seed (`--rejected` for the ones you do not keep); the kept placement; the first routed board and each further fully routed board (`--kind completion`); the first DONE; the delivered board. Close it with one `record --final --stop-condition ...` row, as the skill says.

### Deliverables, all in RUN

1. `delivered.kicad_pcb` with its `.kicad_pro` (via `copy_board.py`; the skill's §3.9 filled board; if `fill_for_delivery` failed, copy the unfilled board there and say so), `DELIVERED.sha256` (the sha256 of delivered.kicad_pcb), `routed.kicad_pcb`, `final.kicad_pcb` (the kept placement, without the cans), `cans.json`, `groups.json`, the intent files, `CHOSEN.json`, `placed_from/`, `final_route/`. When the run ends NOT DONE these still exist: deliver the best board you have and say what it is.
2. `ledger.jsonl`, closed with `--final`.
3. `REPORT.md` with the skill's §6 sections. Also say: what you did by hand for each skill you followed inline; every row you added to the intent; that no EMC rows were given; every judgment you made for the user; the wall time from FIRST_CMD.
4. `TOOL_GAPS.md`: one section per tool problem you hit, ranked by how much it cost you. What counts: a tool that claimed something false, refused wrongly, crashed, hung, was silently wrong, or was missing so you had to write a helper; and problems with the SKILL's instructions (a step that does not work as written, or a missing step). Each section gives: the tool and command; what it claimed; what was true, with the measurement; a command that reproduces it from WT (copy the input board it needs into `RUN/repro/` so it still works afterwards); the result of a read-only `gh issue list --repo drandyhaas/KiCadRoutingTools --state all --search "<keywords>"`, naming any issue (open or closed) that already covers it.
5. The verifier's `verdict_*.txt` files, the `grade.py` output, and the `measure.py --self --evidence` output (§6.3).
6. Marker files: when the delivered board is frozen, create `RUN/DONE` containing one line, `sha256 <sha256 of delivered.kicad_pcb>` (create it for a NOT DONE board too: it names the board you ship); after REPORT.md and TOOL_GAPS.md are written, create `RUN/REPORT_DONE` (empty). Helper scripts go in `RUN/helpers/`, each one a TOOL_GAPS.md entry saying why the repo's tools were not enough (the given `helpers/cans.py` is not a gap: it is part of the trial's setup).

### The final reply (after REPORT_DONE exists)

Short summary only: DONE or NOT DONE; the delivered board's path and sha256; blocking / joins_needed / vias / copper_mm / segments; the stop rule that fired; the wall time from FIRST_CMD; the number of TOOL_GAPS entries and the top three in one line each. Then, as the instructions above require, one last line `RESULT={...}` whose `board` is `RUN/delivered.kicad_pcb` and whose `report` is `RUN/REPORT.md`. After the report, end your reply with exactly one line of the form RESULT=<compact single-line JSON> with this exact schema: {"status": "complete"|"residue"|"refused", "board": "<absolute path to the final board file>", "report": "<absolute path to REPORT.md, or null>", "blocking": <final board_score blocking count as an integer, or null>, "summary": "<one line>"}
