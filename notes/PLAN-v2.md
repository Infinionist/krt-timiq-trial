# TimIQ placement plan v2 (lead, 2026-10-26). Nothing runs until Infinionist OKs this page.

## What went wrong (run 1 against KRT's skill, read end to end)
- Design brief empty (`interfaces: []`): box, lid height, window, wall band, holes never declared. Skill: "declared facts win".
- `--decaps-from <human board>` not used: KRT's own way to arm decap limits when a placed reference exists. Run 1 then
  skipped templates "held by the decap rule", a rule that was off. That is the strung-out passives.
- 0 proximity rows; template skips written "not fetched within the time cap". No `--plan-only` check before placing.
- v2-v4 were placer-only variants with our patch: not KRT's loop. Stopped.

## Constraints: fact -> KRT key (stock) or GAP
| fact | KRT input |
|---|---|
| J1-J4 SMA, J5, J6, LEDs, FIX1-8, BOX1 | `fixed[]` in mechanical.json (as run 1) |
| J7-J10 cans under the lid window (Infinionist) | `fixed_poses[]` basis mechanical, human poses |
| can interiors (who sits under each can, F and B) | `blocks[]` zone = can interior rect, refs = that sheet's parts, side F/B |
| can frame over its members | `covers[]` (a fixed shield, underside ~5.5) or `overlap_waivers[]`: PROBE FIRST (step 1) |
| J11/J12 free | GAP: zones need a known rect. Option A: I place them in the floorplan, you approve. B: our patch |
| box interior, top-side wall band 2.75 mm | `keepouts[]` 4 band rects `sides: F`; bottom parts allowed (as human) |
| lid height 27.5 mm | `keepouts[]` box interior `max_height_mm` 27.5 |
| hole clearance 3.5 mm or human's (J5, BOX1, FIX) | `keepouts[]` circles (`add_rule_area --mounting-holes` is the no-op of KRT 1455) |
| decaps | `--decaps-from` the human board: limits only, per cap, never poses |
| support passives at a pin (chains) | `proximity[]` rows: datasheet where there is one, else netlist rows at 2.0 mm pin / 5.0 mm part (skill default) |
| RF chains U21/U22 PMA2-43LN+ | `templates[]` kind rf front end (datasheet Fig 1) |
| LMX2541 loop filter, HMC1097, HMC705, ADC/DAC | `proximity[]` from datasheet text (KRT kinds don't cover them) |
| faces | `assembly.sides: both`, every part keeps its human face (heavy parts stay top) |
| RF crossings at wall notches, 3V3_2 back notch | GAP for the placer: checked by the designer check |
| lid holes R2.2 inside J7/J10 | OPEN: what are they? |

## Loop: KRT place mode as written; deviations marked
1. Probe (CPU, minutes): one fixed can with members, `covers[]` vs waivers; pick the stock mechanism that works.
2. Brief + mechanical.json + emit with `--decaps-from`; groups = sheets (as run 1); datasheet rows and templates.
   Gate (script): `check_floorplan --plan-only` 0 errors, `check_groups` 0 errors, every IC has a template, rows or a
   skip with a reason that holds. DEVIATION: the coverage gate is ours; KRT relies on the agent.
3. DEVIATION: floorplan review: a render of zones and fixed parts goes to you before any seed.
4. place_simple default 12 seeds, judge 6, as a background script: no agent watching (that's where v4's tokens went).
5. Judge with KRT's fast route, then our designer check, then the PNGs for you.

## Designer check (script, pass/fail; the human board run through it = target)
check_assembly buildable; check_floorplan 0 errors; every member inside its can (F and B); no top part in the wall
band; cans inside the box, J7-J10 under the window; hole clearances; passive-to-pin gap distribution no worse than the
human's (count > 10 mm: human 17); RF chain parts toward their notch. Human fails check_assembly on C20/R16: noted, waived.

## For you
1. J11/J12: A (fixed in the floorplan, stock KRT) or B (free, our patch)? I recommend A.
2. Netlist rows at 2.0 mm pin / 5.0 mm part where no datasheet says: OK?
3. Decap limits from the human board (KRT's own way, limits not poses): OK?
4. Lid holes R2.2 in J7/J10: what do they hold?
5. Start after your weekly reset. Model work: me + one builder (brief/intent) + doc-reader (5 datasheets). CPU: ~2-4 h.

## Infinionist 10-26 answers
1 A (J11/J12 fixed in the floorplan, his review). 2 yes (2.0 pin / 5.0 part). 3 yes (--decaps-from human, limits only).
4 unknown ("not my board"): lid holes are in the lid, no board constraint; listed as an assumption. 5 start after the reset.

## Floorplan proposal for J11/J12 (lead, for Infinionist's review with a render)
Free room after J7-J10 (fixed): the top strip y 97.7..136.8 (above J9) and the left column x 127..166, y 97.7..157.9.
Signal nets (no power/GND): ADC sheet 6 to digital (near J5, right top), 2 to mixers (J8); DAC sheet 4 to digital, 2 to
DAC IF (J9). -> J12 (DAC) directly above J9, x 167-201 (feeds J9, nearest digital). J11 (ADC) in the left column next to
J7, y ~120-155 (closest to the mixers' 2 analog nets; leaves the top-left corner free for ADC drivers/reference).
Same 37.8 mm pitch as J7-J10 (3.4 mm courtyard gap). This matches the human's choice; reasons above, not copied.

## Step 1-2 results (builder, 10-26) and changes proposed (need Infinionist's OK)
- Probe: stock KRT cannot seat parts inside a fixed can. covers[] = solid; overlap_waivers[] only quiet check_assembly,
  the placer's seat gate ignores them. Proposal (d), stock KRT: leave J7-J12 off the placing board; each can = blocks[] zone
  for its members + keep-out allowing them; put the can footprints back before check_assembly/routing. Deviation, reported.
- --decaps-from arms only max_pin_distance 8.16 (human has 34/122 caps > 5 mm). Proposal: decaps get the 2.0 mm pin rows
  from answer 2 like other passives; keep KRT's 8.16 as the backstop.
- Lid height 27.5: not declared (336 parts have no height data). Proposal: designer check flags tall parts by script instead.
- FIX holes: clearance from the hole edge (Infinionist), not pad edge. Window: cans only partly under it (human too); check = overlap.
- Gate today FAIL: 42/45 ICs uncovered, can refs TODO. Next (CPU+lead): sheet -> can refs, netlist rows, then render.
- Infinionist 10-26 OK: 1 (d) yes. 2 decaps NOT hard: as close as possible, by pin, smallest value nearest, may move out
  (soft; 8.16 backstop). 3 height not a concern. 4 FIX from hole edge. "Go" -> builder: refs, rows, gate, render. No seeds.
- Infinionist 10-26 floorplan OK. Can membership != schematic sheets (note for write-up): like the original designer, U10/U11+C45-50+
  R50-57 (DAC sheet) -> J9; U3 (pll sheet) -> J8; C96,C97,R75,R76,R78,R79,R88,R89 optional (in J10 or outside); D1/R1/Q1 outside.
  Calls made because they made sense by function, same as the human. KRT wish: decap ordering (smallest nearest pin) style hint.

## Plan v3 (Infinionist OK 10-27) after seed run 1 (c2 best; review: path not protected, body overlaps, ICs at can sides,
## left-edge scatter, bottom ICs)
1. Courtyards for all footprints without one (458/465): body/silk outline + margin, before placing.
2. Anchor zone per can for its main IC: LOOSE (Infinionist: a starting point only), centred,
   biased toward the can's signal openings. Power zone near J6, ordered filter -> regulator -> output caps.
   Lead draws, render to Infinionist before seeds.
3. Critical paths: KRT emc_roles/keep_away rows + ordered chains for RF/LO paths (notch -> parts -> can opening).
4. Faces: not fixed to the human's. Larger parts top preferred; an IC may go bottom where it makes sense. Flippable.
5. Pin proximity rows 2.0 -> 3.0 mm. U3's passives (R14,R16,R17,R165,C20) move with U3 to J8.
6. Fixes: BOX1 allowed in can keep-outs; post-check waivers for can-over-member; designer check knows optional parts
   and skips LED resistors; far check reports filter->regulator.

## Run v3 result (10-27 00:31): FAILED, stopped, re-plan needs Infinionist's OK
- 12 seeds, ~2.3 h each under load (box ~30). place rc=4: every seed illegal; judge none.
- Input bugs the gate missed: (a) D2 (fixed LED) inside hole-FIX5-1 keep-out in every seed; (b) U4 does not fit
  canJ12_anchor (5.3 mm past south edge) -> "no legal pose for U4" in 11/12 seeds; (c) anchor zones overlap their can
  zone -> 6 intent_zone_overlap errors (KRT wants `exclusive` or no overlap).
- Best s5: 132 floorplan errors = 102 proximity (3 mm pin rows, human holds 104/244), 13 decap inferred, 6 zone overlap,
  5 keep_away, 2 keepout (D2, U34 at J5-1), 2 template, 2 containment.
- Better than run 1: power parts stay together in the top strip (filters with regulators); left-edge scatter gone.
- Proposed fixes (not applied): gate checks fixed parts vs keep-outs and anchor IC fits its anchor zone; anchor
  zone >= anchor courtyard + 2 mm, or a proximity row to the can centre instead of a zone; D2: human clearance at FIX5;
  pin rows graded as WARN; 6 seeds not 12.

## Plan v4 (builder 10-27, inputs in v5/; gate PASS, no seeds run)
- Changed: D2/hole clearances measured on the human board WITH courtyards; pre-flight (preflight_probe.py, KRT's own legality, 1.4 s) is gate check 7 with zone-fit, overlap, fill <= 0.5 and power-tile checks; power split into 11 pw_* tiles (pw_in_R/L, pw_7v5, pw_24v, pw_U39..U45; pw_misc has no zone) with 3 mm pin rows; designer_check grades pin-row and anchor-pull misses as WARN; 6 seeds.
- Anchors (Infinionist 10-27): NO anchor zone, nothing exclusive (exclusive pushes the IC's own decaps out). KRT has no pose hint for a movable part (only template poses, group `near`, `edge` hints; `--anchored` seeds solve centres from wiring), so option (b): a fixed marker MK7..MK12 (0.1 mm pad, 0.2 mm courtyard, in the anchor IC's group so no fold_followers move) at the can centre shifted by the exit vector, and one proximity row per anchor IC to it (basis body, 7 mm: KRT prices it, grades a miss as an error, we WARN). Nesting would only be `exclusive`; all 6 intent_zone_overlap warns are gone. Unverified: how hard the anneal pulls (not run).
- CHEAT list (taken from the human board): hole clearances FIX5-1 4.9 (D2), FIX6-1 4.6, FIX7-1 3.15, J5-2 2.325, BOX1-5 4.75; branch SIDES (7V5 right of J6, +-24V left); J6 position; which 1210 input cap serves which 7V5 regulator. LOGIC (netlist): branch / regulator groups, column order by loads centroid, filter -> regulator order, tile sizes from courtyard area / fill. Workaround, not a cheat: BOX1 0.2 mm point courtyard.
- KRT gaps: exclusive zones have no allow list (a fixed part such as BOX1 is refused in every one); a courtyard-less pin frame is graded on its pad box (= the whole box); a pad-less footprint is never placed or fixed (so a marker needs a pad); no dry-run for fixed-pose legality (we replicate place_simple up to the anneal); no pose hint for a movable part; `tolerance_mm` zones nest only via `exclusive`.
- Open: pw_U40's tile overlaps J5's courtyard (44 mm2) and the J5-2 hole circle: real fill about 0.56 vs the 0.45 the gate sees (it subtracts holes only). Not changed.
- Group-first inside cans (proposal, not built): KRT groups are the sheets already. Per can sub-circuit groups would keep them gathered: J7 PLL core U1 + loop filter + VCXO U2 + ferrites L1-L7; J8 IQ mod U16 + LO splitters/amp chains U21-U27; J9 op-amps U10/U11 + LT6600 U14/U15 + refs U12/U13; J10 divider chain U18-U20; J11 ADC U29 + driver U28 + ref U30; J12 DAC U4 + buffers U5-U9. Needs per-can ref lists from the schematic sheets.

## Plan v5 (builder 10-27, inputs in v5/; NO seeds run; gate FAILS on the can fill: stop and decide)
Infinionist's calls (10-27): no tight boxes; power = groups + loose location; every can group side F, nothing flippable inside; fit proven by script; 3 seeds; must-fail tests; render; this page.
- Fill table (gate.py prints it every run; fillcheck.py: member courtyards + KRT clearance 0.2 / usable area, single face; limit 0.65 = Infinionist's 0.6-0.65, TIGHT above 0.55 = KRT's
  CROWDED_UTILISATION; the zone tolerance is not counted as room):
  | zone | n | usable F mm2 | load F mm2 | fill | verdict |
  | canJ7 | 52 | 949 | 723 | 0.76 | FAIL |
  | canJ8 | 53 | 949 | 728 | 0.77 | FAIL |
  | canJ9 | 44 | 949 | 604 | 0.64 | TIGHT |
  | canJ10 | 47 (+8 optional, not counted) | 949 | 548 | 0.58 | TIGHT |
  | canJ11 | 35 | 949 | 437 | 0.46 | ok |
  | canJ12 | 51 | 949 | 750 | 0.79 | FAIL |
  | power_strip | 75 | 3929 | 2007 | 0.51 | ok (nothing flippable) |
  | free (all outside the cans) | 154 | 13954 | 3461 | 0.25 | ok |
  FINDING (stop condition of call 3): the members of J7, J8, J12 do NOT fit on F alone (0.76-0.79 > 0.65); J9 is 0.64. Nothing was moved to B. Numbers for the decision: shed 106 / 111 / 133 mm2
  (J7 / J8 / J12) to reach 0.65 = the 12 / 13 / 15 smallest R/C parts; or generated courtyard margin 0.25 -> 0.15 (the 457 courtyards we drew) gives J7 0.69, J8 0.69, J12 0.72 (still over);
  the human put 24 / 12 / 12 / 28 / 9 / 25 of the members on B under the can footprint. KRT's own plan check also warns: all-F board is 61 % covered (plan_board_crowded, > 55 %).
- Changes and reasons:
  1. cans: ONE KRT group per can (groups_v5.py, `side: F`, no flippable), block side F, tolerance_mm 0.0 (run v4: default 0.5 let U13 stand on the J9 frame pads; the gate checks tolerance 0).
  2. faces: every movable part starts on F (436, 178 turned from B); decide_faces.py lists a small passive flippable only where a non-can zone is over 0.55 on F: none (power 0.51, free 0.25).
  3. power: the 11 pw_* tiles are deleted. Groups kept (pw_in, pw_7v5, pw_24v, pw_U39..U45). ONE loose block `power_strip` (strip x 112-256.4, y 64-94.4, tolerance 4, not exclusive, no side).
     Location = group `near` hints + anchored seeds; rows only INSIDE a group (see KRT gap 1). pw_in's cap rows to J6 loosened 3 -> 10 mm (same group). L12-L14 -> J6 rows dropped (cross-group).
  4. rows: dropped R74->U17 (J10/J8), R115->U26, R116->U27 (J11/J8): ends in two cans, unsatisfiable in every seed; R157/R159 -> U44/U45 (LED series resistors follow their LED).
  5. gate: fill table, zone fit with keep-outs/fixed parts (U4 in J12 fits), faces, tile, supergroup, tolerance, unsatisfiable rows, KRT fold_followers (no row may move a part to another group);
     preflight_probe also returns rects/side/clearance and the anchored starts. designer_check: a can whose cans.json says side F fails any member on B.
  6. run_seeds.sh: `--scattered 0 --clustered 1 --anchored 2 --judge 3 --jobs 3` (anchored = the KRT location suggestion; scattered strewed the power parts in v4); no judge.json seed ->
     lowest final.cost forced through judge_seeds --seeds, then reattach + post checks + render; place exit 4 tolerated when a seed is named. Gate is step 0 (hard): it blocks the run now.
- KRT gaps (for the feedback notes): (1) a proximity row between two groups is a membership claim (grouping.fold_followers; the whole group follows when the subject is its anchor): plan v4's
  power rows folded 11 groups into one of 78 parts, and no loose group-to-group row exists (only `near` hints); (2) block tolerance default 0.5 puts parts on a fixed frame's pads; (3) no
  per-zone fill check at a limit (plan_zone_crowded only at 100 %); (4) anchored start ignores zones (it started power groups inside the cans); (5) netlist rows across cans are unsatisfiable by plan.
- Tests: tests/test_v5.py (KRT venv, 19 cases, all hold): can member flippable / on B / group or block without side F, pw_ tile, no supergroup, zone over the fill limit, U4 not fitting,
  fixed D2 illegal, can tolerance, unsatisfiable row, row folding groups, flippable rule. tests/test_scripts.py (v4 era) still names tiles / block side None / anchor counts: NOT yet updated
  (it must be brought to v5 before it is run as "the suite"; the old expectations fail by design).
- Render: v5/floorplan.png, v5/floorplan_bottom.png (everything on F: the bottom view shows only fixed B parts).

## Plan v5b (Infinionist 10-27: passives under cans may go bottom)
Rule (code: v5/faces_v5.py docstring, decide_faces.py, fillcheck.face_problems, gate check 7, designer_check `members`): inside each can every IC (U*), every RF-path part and every part with courtyard >= 20 mm2 stays on F, locked; small SMD passives (R, C, FB = ferrite bead; courtyard < 20 mm2) may go to B, only inside their own can's rect. KRT way (placement/faces.py): a group or block `side` DECLARES the face and overrides `flippable`, so a can with flips has NO group side and NO block side and lists them `flippable` in its group canJ<J> (all parts still START on F; place_simple keeps a part's face and flips a flippable one only where F has no room); a can that needs none keeps side F. cans.json carries the same list (`flippable`, no `side`) for designer_check. Choice: for a can over 0.65 on F, eligible parts, decaps serving only the can's own ICs first (KRT decap_view owners), then those serving some of them, then smallest courtyard, until F <= 0.65 and B <= 0.65. All eligible used up and still over: FAIL with the shortfall mm2 (limit not loosened).
RF-path rule (script, from the netlist; listed in v5/faces.json `rf_path`): a part with a pad on an RF net. RF nets (rails = GND or > 12 pads excluded): (1) victim nets of the intent keep_away rules (RF to SMA J1-J4, LO/PLL out, DAC I/Q, ADC inputs: 13 nets) + non-rail nets on an SMA pad; (2) non-rail nets of the passives named by the ordered RF chains (proximity rows `plan v3 chain`) and the template (PMA2-43LN+ front end) members, + non-rail nets joining two chain ICs; (3) series closure: a 2-pad passive on an RF net passes RF to its other net if that net is not a rail and has an IC or SMA pad. 53 RF nets, 97 RF-path parts board-wide; members with a pad on an RF net (ICs included): 12 (J7), 40 (J8), 14 (J9), 7 (J10), 8 (J11), 10 (J12) members.
Gate (python3 build_inputs.py, then KRT-python gate.py): GATE PASS. Fill table (single face, courtyard + 0.2 clearance / usable; F0 = nothing flipped, F / B = flippable parts flipped):
| zone | n | flippable | F0 | F | B | verdict |
| canJ7 | 52 | 12 | 0.76 | 0.65 (0.648) | 0.12 | TIGHT, ok |
| canJ8 | 53 | 13 (all 13 eligible) | 0.77 | 0.64 | 0.12 | TIGHT, ok |
| canJ9 | 44 | 0 (side F) | 0.64 | 0.64 | 0 | TIGHT, ok |
| canJ10 | 47 | 0 (side F) | 0.58 | 0.58 | 0 | TIGHT, ok |
| canJ11 | 35 | 0 (side F) | 0.46 | 0.46 | 0 | ok |
| canJ12 | 51 | 15 | 0.79 | 0.65 (0.647) | 0.14 | TIGHT, ok |
| power_strip | 75 | 0 | 0.51 | 0.51 | 0 | ok |
| free | 154 | 0 | 0.25 | 0.25 | 0 | ok |
Flips: J7 C1 C21 C4 C6 C8 C10-C15 C2 (5 serve its ICs' rails first); J8 C104 C106 C64-C69 C71 R108 R14 R71 R72; J12 C26-C36 C39-C41 C44 (11 of 15 serve its ICs). 40 parts in all. J8 has only 13 eligible (40 of its 53 members are ICs, RF-path or L): the margin is thin (0.643). Post-check (designer_check members, on a placed board): any non-flippable can member or any IC on B, or a flipped part whose pad box is outside its can rect, FAILS.
Tests: tests/test_v5.py (KRT venv, 44 cases, all hold; of the 19 v5 cases two were rewritten: "can member flippable" -> IC / RF-path / L / >= 20 mm2 / other-can / side-with-flippable must fail, and "the fill limit FAILS J7/J8/J12" -> it fails only when nothing is flippable). Mutation check: with ineligible_reason, board_face_problems, b_outside_problems, the shortfall or the side-override rule disabled the matching tests fail. Render: floorplan.png, floorplan_bottom.png. No seeds run.
