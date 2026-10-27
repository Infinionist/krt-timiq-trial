# KRT feedback notes: TimIQ RF placement (living notes; source for a future KRT issue/discussion, D-048: Infinionist OKs text)

Board: CERN TimIQ RF (8L, 465 parts, 6 shield cans J7-J12 inside a Hammond 1590Q lid, lid window over J7-J10).
KRT stock v0.23.7 (db056e03). Lead: Claude Opus; Infinionist = experienced designer driving the calls.

## How Infinionist drives placement (his method, to compare with KRT's loop)
- Mechanical and design intent first: cans J7-J10 fixed under the lid window; J11/J12 placed in a floorplan he reviews.
- Can membership by FUNCTION, not schematic sheet: DAC output buffers into the DAC-IF can, LO splitter into the
  mixer can, RF-exit passives optional (in J10 or outside). Same calls the original designer made, because they fit.
- In each can: put the main IC (or the bulk of the circuit) near the centre, biased toward where critical signals
  enter/leave; then build around it, squeeze, push, nudge to fit. Anchor is a starting point, not a rule.
- Protect critical paths (RF, LO, DAC/ADC analog) over pure wire length; power entry ordered filter -> regulator.
- Decaps: as close as possible to their own pin, smallest value nearest; soft, may move out. Larger parts top side,
  an IC may go bottom where it makes sense.
- Group first, then place groups (Infinionist 10-27): hand placement starts by grouping the LOGICAL circuits, finer than
  "all power": the input section, each filter stage, each regulator with its own parts. Then each group is pulled to its
  logical spot (input next to the connector, a regulator next to the parts it supplies). The human TimIQ board does
  exactly this: J6 mid-strip, 7V5 LDO chain to the right, +/-24V chain to the left, each regulator a tight cluster.
- Reviews the floorplan render before any seeds; reviews top seeds by image.

## What we ran into (KRT gaps or friction)
1. Shield cans: no stock way to place parts INSIDE a fixed can. covers[] without a model = solid; overlap_waivers[]
   quiet check_assembly but the placer's seat gate (quench.candidate_valid) ignores them; courtyards_overlap ignore
   still leaves zone_containment errors. (Already reported in part: issues on mount holes/shields; see 1455/1456.)
2. --decaps-from <reference> arms only max_pin_distance (8.16 mm here), not per-cap limits, when the reference has
   caps beyond 5 mm (34/122). No setting for "smallest value nearest the pin".
3. Library with no courtyards (458/465): KRT falls back to pad bbox and silk bodies never gate -> parts placed over
   other parts' bodies. A courtyard synthesis step (or a warning that blocks) would help.
4. No anchor/centroid preference for a block's main IC; it drifts to zone edges toward its external nets.
5. A fixed container (BOX1, board-sized) trips user keep-outs unless listed in allow.
6. No floorplanner: zones must be drawn by hand (fine, but the skill should say so up front).
7. Runtime: 465 parts, 12 seeds: 9-74 min per seed on one core each (74 min wall on 12 cores).
8. Proximity rows without pads: priced over shared-net legs, graded on closest pair (KRT warns; mismatch).
9. No "near a point" preference: a soft anchor needs a small block zone with tolerance_mm (we used 55% of the can, 1 mm).
10. keep_away is graded and priced by the router only; the placer ignores it. emc_roles proposals came back all "unknown".
11. No face preference cost: "larger parts on top" can only be the starting face; place_simple flips a part only when it
    has no room on its side. Infinionist 10-27: suggest adjustable face settings (per part class or size: prefer top, allow
    bottom, cost weight), and explain the SMT assembly practice behind them: heavy and tall parts on one side, bottom side
    light parts only (reflow, no drop-off), avoid shadowing for wave/selective solder, fewer bottom parts = cheaper second
    pass. KRT may not know these practices; R9-decide-candidates-assembly.yaml has the draft rules.
12. Long links (SMA notch to can, 25-35 mm) can't be proximity rows; we used the anchor shift instead.

13. Power floorplan: Infinionist 10-27 would make the power zone tighter; a placer needs power-path guidance (current per rail,
    loads, filter->regulator->load order, loop area) to do that itself. No KRT input carries currents today.
14. Zone fit is only known after placing: plan-only checks zones but not that each zone's parts (courtyards + spacing)
    fit in it. Run v4 spent 4.2 core-hours to learn the power tiles were too tight.
16. Run v6 (Infinionist 10-27): the placer kept the cans' regions well even with the cans gone, but nothing knew about the 1590Q
    lid, which fits over the cans and dictates where some parts go (a keep-in/keep-out). KRT can express it (block zones,
    keep-outs), but the skill never asks about enclosure or lid constraints. Worth checking whether a mechanism belongs there.
15. Face choice inside a zone: with faces free, the anneal put most can members and the big ICs on the bottom (gap 11).

## What we did (workarounds / deviations from KRT's loop, each with its reason)
- Cans OFF the placing board; each can = blocks[] zone (F and B) + keep-out allowing only its members; cans put back
  after placing (reattach.py). Reason: gap 1. Deviation: yes.
- Floorplan review by Infinionist before seeds; a coverage gate (every IC has template/rows/valid skip). Deviation: ours.
- Pin proximity rows from the netlist (2.0 mm pin / 5.0 mm part, skill defaults; loosened to 3.0 mm after run 1).
- Plan v3 (10-27): courtyards synthesized, loose anchor zones per can, power zone, emc_roles/keep_away + ordered RF
  chains, flippable faces with big parts top.

## Where we cheated or leaned on the human board (be honest in any post)
- J7-J10 poses are the human's (Infinionist's design-intent call: under the lid window).
- J11/J12 poses: lead's floorplan, reasoned from net counts, but it matches the human's choice.
- Hole clearances reduced to what the human board clears at 3 holes (FIX7, J5-2, BOX1-5).
- --decaps-from read the human layout (limits only, no poses).
- Run 1 kept every part on its human face (dropped in v3).
- Can membership overrides match the human's (stated as such).
- Designer check compares against human-board counts (far passives, proximity) as the target.

## Results so far
- Run v5-1 (10-26): all 282 can members inside their can on their face; 0 wall-band, box, hole violations. Not DONE:
  76 proximity misses at 2.0 mm (human: 182), power entry split from regulators (100-130 mm vs 20-37), body overlaps
  (no courtyards), ICs at can edges, left-edge scatter. Infinionist's read: placed for wire length, not to protect critical paths.
- Run v3 (10-27): all 12 seeds illegal. Our input bugs (fixed LED in a hole keep-out; DAC U4 bigger than its anchor
  zone; anchor zones overlapping can zones). KRT flagged all three, but only after 4 h of placing: a pre-flight check
  (plan-only) that every fixed part is legal and every block's largest part fits its zone would have caught them in seconds.
  Better than run 1: power parts kept together, no left-edge scatter.
- Run v4 (10-27, 6 seeds, 42 min each on 6 cores; Infinionist predicted a fail, power section too tight): all 6 illegal,
  exit 4, so no judge/route. Per seed 15-25 parts with no legal pose, almost all power (L12-L14, U39-U45, J6 caps), plus
  U4 (DAC, J12 anchor) in 4 of 6. check_floorplan 160-197 errors per seed: proximity 123-155, zone_containment 14-25
  (power tiles: most spills 0.01-2.6 mm, a few 8-12 mm; our tiles had tolerance 0), decap distance 6-22, keep_away 2-10.
  Seed 3 post-checked by hand (reattach + designer_check): cans PASS (282/282 members, 0 intruders, band, box, window,
  holes); FAIL assembly (U13 under the J9 frame), far passives 29 (limit 28), 117/286 pin rows missed (WARN), 2 of 7
  anchor pulls missed (U11 7.9 mm, U20 9.5 mm). Faces: 166 can members on B vs 116 on F, big ICs (U29, U9, U15, U16) on B.
  Power strip: regulators not clustered with their caps (R157 31 mm from U44, L13 29 mm from J6), U45 pushed out of the strip.
  Lesson (ours): tiles sized at ~0.45 fill with zero tolerance and no slack for courtyards are too tight; KRT's answer
  (no legal pose) is right, but it took 42 min per seed to say so; a plan-only fit check per zone would say it in seconds.
- Run v5b (10-27, Infinionist asked for one more try: power as loose groups + supergroup, can ICs/RF/big parts locked F, 40 small passives
  flippable inside J7/J8/J12, fill proven by script <= 0.65; 3 seeds 1 clustered + 2 anchored, 27 min on 3 cores): all 3
  illegal again, 7-9 parts each with no legal pose, now mostly ICs in the full cans (U2, U4, U5, U10, U15, U23; U1, U11;
  U3, U27, U8). Fill 0.65 is above KRT's 0.55 "crowded": our fit gate's limit was too loose for big ICs. Forced quick route
  of seed 0: 104 joins needed, 265 blocking. Post checks: cans PASS (282/282 in their can, 27 on B, every IC F), band, box,
  window PASS; FAIL assembly (5 blocking, R66/R75/R76/R79/U1), floorplan 11 errors (zone_containment 7), hole (C145 0.9 mm
  into FIX6), far passives 42 (limit 28; power entry L13 58 mm from U43); 162/271 pin rows missed; LO/PLL net 1.33 mm from a
  digital net (keep_away 3 mm). Better than v4: power regulators clustered with their caps, groups compact, no scatter.
  Movie (make-3d-movie, seed 1 re-placed): 7 illegal, all parts boxes (no 3D model lookup).
  Lesson: the human board fits only because it uses both faces under each can far more (97 of 279 on B); a fit limit
  should come from KRT's own crowding line, and the run should stop at the gate, not after placing.

## Run v5b vs the human board (lead, 10-27; Infinionist to add his own after a closer look)
- Totals: ratsnest 7937 mm vs human 6237 (+27%); crossings 1746 vs 1250 (+40%). Renders: /tmp/pcb-trials/timiq/v5/cmp/.
- Faces under cans (F/B): human J7 33/24, J8 36/9, J9 32/12, J10 19/28, J11 26/9, J12 26/15 (97 on B, every IC F);
  seed 0 J7 52/0, J8 41/12, J9 44/0, J10 52/0, J11 35/0, J12 36/15 (27 on B). KRT flips a flippable part only when the
  front has no room, so J7 kept all 12 of its flippable parts on F and packed the can. Our setup was too tight (Infinionist
  10-27). Gap for KRT: no way to say "decaps go behind their IC on B" or "prefer B for small passives here", only "may
  flip if stuck" (gap 11).
- Matched channels: the human mirrors the I/Q chains (J9: U11/U13/U15 beside U10/U12/U14; J8 a grid of U23-U27), ICs
  square to the signal flow, passives in rows along can walls (J10 attenuator rows). The seed packs each can into a blob,
  rotations arbitrary, no symmetry. No KRT input says "these two channels are copies, place them mirrored".
- Power: in the movie (group colours) each regulator is its own tight cluster; in the plain render it reads as random
  because the groups touch, rotations vary and the order filter -> regulator -> load is lost (L13 58 mm from U43).
  Human: regulators in a row along the top, caps in neat arrays per regulator.
- Digital: human lines U31-U38 up beside J5 in rows; the seed rotates and scatters them, with long fans to J5.
- Quick route (judge, --quick 2): 42 nets unrouted and 46 broken, mostly SPI/control from the digital side to the PLL,
  ADC and DAC cans. With the cans packed and no gaps between them, there were no channels between cans.
- Honest limits of this trial: scripted one pass of the skill (no model looking at seeds and adjusting), cans off the
  board (workaround), our fit limit too loose, faces set by us. Results say as much about our setup as about KRT.

## Run v6: the skill as written, model reads the schematic, design intent given (10-27)
- Report and boards: /tmp/pcb-trials/timiq/v6/REPORT.md. Cans removed, physical facts + Infinionist's intent only; 3 rounds
  (3, 3, 12 seeds); verifier, full route and full-level re-judge skipped (model budget).
- Round 3: 6 of 12 seeds legal with 0 floorplan errors; the first legal placement of this board. Kept seed 7: buildable
  (with BOX1 waivers), 133 warnings; quick route 88 blocking (39 unrouted, 49 broken), so not DONE by the skill's table.
- Gaps found: check_assembly gates on BOX1's corner posts and silk outline, which place_simple doesn't avoid, so no seed is
  buildable without waivers; J7/J8 circuits fit only with passives on B; no input for mirrored I/Q copies, power order
  beyond soft `near`, or chains across groups (a cross-group proximity row silently merges the groups); judge picks by
  quick route alone (s7 over s4 by 1 net, in the noise; s4 better by eye); nothing keeps non-can parts inside the enclosure
  (U33 outside); make_movie re-places the seed and differs from the kept board (443 of 458 parts).
