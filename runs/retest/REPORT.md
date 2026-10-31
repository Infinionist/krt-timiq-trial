# TimIQ_RF -- /plan-pcb-placement `place` -- REPORT

**Status: residue.** The placement is DONE-clean (buildable, 0 floorplan errors, nothing off the outline,
mechanical poses held, every can member inside its can), but its route is not clean: the full judging route
of the kept placement leaves 2 nets open (board_score blocking 7, joins_needed 3), and the `--quick 2`
screen route leaves 65. Both remaining blockers measure PASSABLE on the placement (routing findings, below).

Final board: `final.kicad_pcb` (+ `final.kicad_pro`), sha256 `262415a6cca5d3cdd977d984ff779ffdd581897c01ff9a6ca5eef5aac13866fe`
= seed 3's placement (`s3.kicad_pcb`) with the reference labels tidied (silk only). `groups.json`, `intent.json` beside it.

| place-mode DONE condition | measured | met |
|---|---|---|
| `check_assembly --baseline fixed.kicad_pcb` buildable | buildable (blocking 0) | yes |
| `check_floorplan --intent` 0 errors | 0 errors, 19 warnings (10 intent_zone_overlap: my centre zones nest in the can zones; 2 link; 5 proximity; 2 replicate) | yes |
| no pad / graphic / keep-out copper off the outline | grade.py: done true; check_assembly: no oob pad copper gating | yes |
| mechanical facts (15 fixed poses, cans) | seated by fixed_poses; can blocks graded clean by check_floorplan | yes |
| fast route with no blocking net | `s3_fast` (`--quick 2`): blocking 65 (25 unrouted + 40 broken, poured nets not counted), joins 74; `s3_full` (full route): board_score **blocking 7** (unrouted 4, broken 3), joins_needed 3; quick_score of the same board: blocking 1 | **no** |

`grade.py --mode place`: `{"done": true, "assembly_verdict": "buildable (blocking 0)", "floorplan_errors": 0}` (it grades the placement, not a route).

board_score of the full judging route `s3_full.kicad_pcb`: blocking_by {unrouted 4, broken 3, drc 0, undersized 0,
floorplan 0, assembly 0, drc_via_in_paste 0}; **vias 782, copper_mm 7815.85, segments 5564**. Ungraded (UNEXAMINED): diff_pairs, impedance, length, net_widths.
board_score of the unrouted placement itself (`final.kicad_pcb`): blocking 551 (every net unrouted, as placed).

## Groups and judgement calls (`groups.json`, 21 groups)

All 443 movable parts are in exactly one group (`check_groups`: 0 errors). The 15 mechanical parts
(FIX1-8, J1-J6, BOX1) are seated by `fixed_poses[]` (compiled from `mechanical.json`), not locked.

| group | anchor | parts | why / judgement |
|---|---|---|---|
| can_J7_pll | U1 | 52 + J1 | the brief's J7 row (PLL sheet: LMX2541 U1, VCXO U2, loop filter, ferrites L1-L7); J1 (352 MHz ref SMA) joins it, fixed |
| can_J8_lo_mixers | U16 | 53 + J2 | the brief's J8 row (splitter U3, IQ modulator U16, splitter U17, gain blocks U21/U22, attenuator U23, hybrid U24, splitter U25, mixers U26/U27); J2 fixed |
| can_J9_iq_filters | U14 | 44 | J9 row: DAC output amps U10/U11, references U12/U13, I/Q filters U14/U15 |
| can_J10_dividers | U19 | 55 + J3, J4 | J10 row: HMC705 chain U18->U19->U20, strap resistors; J3/J4 fixed |
| can_J11_adc | U29 | 35 | J11 row: OPA2209 U28 -> ADS8694 U29, ref U30 |
| can_J12_dac | U4 | 51 | J12 row: LTC2758 U4 and its reference/I-V amps |
| psu_in | J6 | J6 + TP4-TP9 | power entry (7V5, +24V, -24V) and the GND test points drawn beside it |
| filt_7v5 / filt_24v / filt_n24v | L12 / L13 / L14 | 6 each | each NFM41 EMI filter with its input bulk, output caps and test point (schematic blocks B40/B41, B46/B47, B53/B49) |
| reg_5v1, reg_5v2, reg_3v3_1, reg_3v3_2, reg_15v | U39..U43 | 10 each | each TPS7A4700 LDO with its input cap, NR cap, output caps and power LED (schematic blocks) |
| reg_n5v, reg_n15v | U44, U45 | 13 each | each TPS7A3301 with its feedback divider, caps and LED |
| dig_spi | J5 | 17 | LVDS rx U32 + shifter U33 (ADC/DAC SPI), LVDS tx U38, at board-to-board connector J5 (fixed, B side) |
| dig_pll_ctl | U31 | 10 | LVDS rx U31 (PLL control) + buffer U35 (DAC MISO) |
| dig_div_ctl | U34 | 24 | LVDS rx U34 + shifters U36/U37 and their dividers (frequency-divider control) |
| lock_led | D1 | 3 | PLL lock LED D1, driver Q1, R1 (PLL sheet, outside the can) |

Judgement calls:
- **One group per shield can**, its main IC the anchor: the brief's `cans[]` rows already decide which parts
  share a can; splitting a can into sub-groups adds nothing the can's zone does not hold.
- **C155/C162, C156/C163, C157/C164** (filter output caps on 7V5/24V/-24V) stay in their filter's group:
  the schematic draws them in the filter blocks with the test points. `check_groups` WARNs that they are
  exempt from the decap rule; that is right for a filter's output bulk.
- **R151** (DAC_MISO pull-up) stays in dig_pll_ctl with its buffer U35 (2 links to the DAC can, 1 to its group): it is the buffer's output pull-up.
- `flippable` lists the SMD passives of the PSU and digital groups (no Al electrolytics, no 1210s, no LEDs),
  per designer intent 6 ("small passives may go on the bottom") and `assembly.sides: both`.
- Templates: U1 is recorded `kind: none` (L1-L7 are BLM18 ferrite beads on supply pins, not a switching
  inductor); U21/U22 (PMA2-43LN+ gain blocks) are `rf front end` candidates recorded with `skip` -- see Deviations.

## The user's (designer's) placement instructions -- how each was written, and where it differed from a prior

| # | instruction | written as | prior it differed from / which was followed |
|---|---|---|---|
| 1 | six cans by function, members inside on the listed face | the brief's `cans[]` (given), compiled by `--emit-intent` into `can:Jn:F/B` blocks (zone, side, `fence_mm` 1.8 on F), keep-outs and a 6.0 mm height keep-out per can | placement-lessons: "groups place a board, not regions" -- the user's regions were followed (3.4c) |
| 2 | RF/analog paths first with ordered chains; LO/PLL >= 3 mm from digital | 8 `chains[]` in signal order (PLL ref, LO->mixer LO, LO->IQ mod->IQ, divider chain, DAC I/Q out, DAC, ADC), 3 mm stage gap (my default: no distance stated); the keep_away is the brief's (given) -- graded by check_floorplan and read by the routers; the placer prices it (`keep_away priced: 1 rule over 132 parts`); groups dig_* carry `apart` from the three LO cans | followed |
| 3 | I/Q copies mirrored if expressible | NOT expressible: `replicate[]` is a translated copy only. Declared two `replicate[].channels` rows (U14/U15, U10/U11 with their passives) so the grade reports them; `place_pose replicate --intent` was REFUSED on the kept seed (it would put C43 4.74 mm outside can J12's zone, an ERROR) | the mirror was not expressible; the copies stay as annealed (grade warns, see below) |
| 4 | input, each filter, each regulator its own group; filter -> regulator -> loads | 11 power groups (above); 7 `chains[]` `power_<reg>`: [J6] -> [filter group] -> [regulator group] -> [its load ICs], `max_mm` [10, 25, 45] (my defaults: no distance stated); `rails[]` names every supply so the rails are priced as rails | skill prior: "a regulator that makes a rail for several groups is in the power group by its entry, near only its entry"; the user's per-regulator groups and order were followed |
| 5 | decaps at their own pin, smallest nearest (soft) | place_simple's decap term; no limit armed (`dispositions.rules.decap_distance` says why: soft, no distance given) | followed as soft |
| 6 | ICs, RF and big parts on top; small passives may go on the bottom | a zoneless `blocks[]` `top_face_ics` with `side: F` for U33-U37, U39, U40, U41, U43, L13, C144, C156 (on B in the pile); `flippable` for SMD passives | the pile had these ICs on B (the human layout's choice); the user was followed |
| 7 | digital next to J5 | J5 is dig_spi's anchor; dig_pll_ctl and dig_div_ctl `near` dig_spi; 3 `links[]` digital ICs -> J5 within 10 mm (my default) | followed |
| 8 | anchors are starting points; main IC central | `blocks[]` `center:J7/J8/J10/J11/J12` (U1, U16, U19, U29, U4) each held to the can's central 16 x 16 mm; J9 (two matched I/Q pairs) has no single main IC and got none | followed |

## Enclosure, covers and declared heights

- Asked (headless: the answer was given in the task): Hammond 1590Q box; its lid fits over the cans; six BMI-S-204-F
  frames (wall 1.8 mm, zone = interior) at the brief's zones; no other height limit.
- Declared, all from the given brief: `cans[]` (6 rows, `interior_height_mm` 6.0, Laird BLS catalog p12), `heights[]`
  (174 rows, every lid-face member's height from its datasheet), `keepouts[]` box-post-1..4 (enclosure posts).
- No covers (no card/module socket on the board). Nothing declared conservatively by me.

## Intent additions (on top of the given intent; script `work/make_intent.py`, original kept as `work/intent.given.json`)

`min_reader` 19; `top_face_ics` and `center:*` blocks; 15 `chains[]`; 3 `links[]`; `rails[]`; 2 `replicate[]`;
7 `proximity[]` rows at the skill's no-one-to-ask default 2.0 mm (L8, L10 at U21; L9, L11 at U22 -- bias/output
chokes; C18, R15, C19 -- PLL loop filter at U1), graded warn by `severity.proximity`; `legality_budget`
{overlap_area 0, oob_count 0} (3.4c: the cans are the user's regions, an overfull zone is an error);
`dispositions.rules` for `decap_distance` and `zone_exclusive`; `BOX1` added to every `can:*` keep-out's `allow`.

OWED answers (the emit's roster): `decap_distance` -> dispositioned (designer 5 is soft, no distance);
`legality` -> armed (`legality_budget`). `zone_exclusive` -> dispositioned (the brief does not make the cans exclusive; the fence keeps the wall band clear).

## Placement and judging

- `place_simple` 12 seeds (6 scattered 0-5, 6 clustered 6-11), 221500 moves per anneal, `--jobs 12`. Every seed legal,
  floorplan 0, assembly 0 (judge.json). Exit 4 only for BOX1's `refused` (tool gap 1). Seeds 0, 3 and 10
  re-annealed once after a courtyard pair (U4/U9, U23/U24, U22/U25).
  Costs: s7 10251, s11 10488, s2 10647, s3 11341, s1 11425, s8 11529, s5 11744, s9 11846, s10 12030, s4 12390, s6 12439, s0 14503.
- Judged (the 6 cheapest): 7, 11, 2, 3, 1, 8, chain `judge_chain.txt` (route_diff on the LVDS/IQ pairs, then route.py
  over all 8 layers, layer costs 1/3/1.5/1.5/3/1.5/3/1, power-net widths), every route with KICAD_ROUTE_TRACE=1:

| seed | start | `--quick 2` blocking | joins | vias | copper_mm | segments |
|---|---|---|---|---|---|---|
| 3 | scattered | **65** | 74 | 390 | 5265 | 4835 |
| 1 | scattered | 68 | 74 | 356 | 5293 | 4847 |
| 2 | scattered | 71 | 80 | 358 | 4782 | 4718 |
| 11 | clustered | 73 | 83 | 362 | 5155 | 4859 |
| 7 | clustered | 88 | 104 | 275 | 4098 | 4024 |
| 8 | clustered | 89 | 101 | 287 | 4508 | 4230 |

- `--confirm 2` (full routes, ~50 min each): seed 3 blocking 1 / vias 782 (quick_score; board_score 7), seed 1 blocking 6
  (board_score 7, joins 7). **Kept: seed 3.**
- route_review on `s3_fast` listed 8 two-pad parts turned against their wiring (R78, C42, L2, R136, C179, R88, C16, R66).
  Turned all 8 (place_pose, legal; buildable; 0 floorplan errors) -> `cand_turn.kicad_pcb`, full-routed with the same chain:
  board_score blocking 8 (joins 4, vias 771) vs 7 -> **rejected**, kept seed 3 as placed.
- `place_pose replicate --intent` (I/Q copies) on the turned candidate: REFUSED (C43 would leave can J12's zone).
- Floorplan warnings on the kept placement: link `rf_pll_ref:0` J1 -> C3 29.9 mm (J1 is fixed at the bottom edge ~20 mm
  below can J7; my 3 mm default cannot be met there), `rf_pll_ref:1` C3 -> U1 3.61 mm; proximity L10/U21 pin 7 3.33 mm,
  L11/U22 pin 7 3.65 mm, L9/U22 2.25 mm, R15/U1 2.99 mm (all over my 2.0 mm defaults); replicate U15 vs U14 up to 16.9 mm,
  U11 vs U10 up to 33.3 mm (rotated differently: the I/Q copies are NOT matched). All 7 power chains and the 3 digital->J5 links are met.

## Tool gaps (and tools that said "fine" about something that was not)

1. **BOX1 refused at its declared pose in every seed** (`refused` in judge.json; place_simple exit 4): place_simple's
   `_fixed_pose_check` tests the enclosure footprint (a container / pin_frame, 124 x 124 mm) by its FRAME rect
   against the can keep-outs and the `fence:` keep-outs, while the grade (`keepout_findings`) measures containers on
   their pad copper. The `can:*` keep-outs were fixed by adding BOX1 to `allow`; the compiled fence keep-outs carry
   `allow: ()` and no intent key can admit a container. BOX1 stays at its declared pose regardless (it is fixed),
   so the refusal is noise, but it makes every run exit 4.
2. **board_score's counts do not match its own lists** on the full route of seed 3: `unrouted.count` 4 with an
   empty `unrouted.nets`, and `broken.count` 3 with two nets listed (GND at U38, Net-(C9-Pad1) at U1).
   quick_score (judge_seeds) reported the same board at blocking 1, because it leaves the poured nets out.
3. **`-5V`, `-15V`, `-24V` cannot be passed as argparse values** (a leading '-' reads as an option):
   `route.py --power-nets` took globs `?5V` `?15V` `?24V` instead; `route_planes.py --nets -5V` could not be written.
   This is a real-user trap on any board with negative rails.
4. `proximity` rows without `pads` (C18/R15/C19 at U1) are priced over every shared-net leg but graded on the
   closest pair -- place_simple warns about it, correctly; my rows should have named pads.
5. The brief's keep_away lists `/TOP/PLL/PLL_ENout` on BOTH sides of the rule (aggregator and victim).
6. `helpers/cans.py` in the run folder (an older trial's helper) says "a can is solid today"; KRT now compiles
   `cans[]` itself, so it was not used.
7. check_floorplan reports `cans[]` as "CARRIED, NOT physically checked" (the verifier measured can containment by hand); the compiled `can:*` blocks do grade zones.
8. The J5 QSH connector is 0.5 mm pitch on B: the router warns "via 0.60mm is large for 0.50mm pitch ... No via
   fits" -- the judging chain used the board's Default via (0.6/0.4); most diff-pair failures in the judging route are there.

## Deviations from the skill

- **No datasheet templates** (3.5). U21/U22 (Mini-Circuits PMA2-43LN+) are rf-front-end candidates recorded with
  `skip`: their support parts are a bias tee and DC blocks, held instead by `proximity[]` rows at the pins; a
  datasheet fit for them, and a check of every other RF MMIC (U3/U17/U25 splitters, U23, U24, U26/U27 mixers) against
  a datasheet layout, was not done within the 4 h 15 cap on a 458-part board. No datasheet was downloaded.
- **EMC / layout-note rows**: the schematic has no `### Layout notes`; `emc_roles` read U1, U21, U22 as "switching
  converter?" from their inductors -- none is one (ferrites / RF chokes); no keep_away rows were added beyond the brief's.
- **No `route_planes` step in the judging chain**: the board already carries the designer's pours (GND on 6 layers,
  -5V In2, 5V_2 In3, 3V3_1 In5); `--skip-existing-zones` would keep them all (a no-op), and `-5V` cannot be passed (gap 3).
- One placement pass only (12 seeds); the first launch was stopped after one minute to add BOX1 to the can keep-outs' `allow`.
- `judge_seeds --confirm 2` as the user asked (the skill's default would be `close`, which named only seed 3).
- The diff-pair step used route_diff's defaults (the board's Default class: 0.2 width / 0.25 gap), no `--impedance`
  (no stackup review was run for the judging chain).

## Stop rule and remaining blockers

Stop rule: the time cap (stop-new at 3 h 30) -- condition 2, budget spent; one placement pass and one placement
repair (the route_review turns, rejected) were measured. Remaining blockers on the full route of the kept placement (`s3_full.kicad_pcb`):
- **Net-(C9-Pad1)** (U1 pin 14 to L4/C9, PLL can J7): `check_reachability --pad U1.14`: PASSABLE at 0.25 mm track on the
  placement (bottleneck 0.40 mm, margin +150 um, throat between U1.15 and U1.13); CAGED only with the routed copper in place
  -> a routing finding (rip-up / reroute), not a placement one.
- **GND** stranded pad on U38 (227.47, 113.60, F.Cu): PASSABLE on the placement (margin +150 um, throat U38.4/U38.2), CAGED
  by routed copper -> routing finding.
- board_score counts unrouted 4 with an empty net list (tool gap 2); nothing further is named.
Recorded as a `--kind classification --shape parameter` ledger row.

## Floors

The judging routes ran route.py's defaults (`--escalation fab --fab-tier auto`). Seed 3's full route printed
`Design rules [...]: 398 feature(s) on 115 net(s) delivered below the requested size (smallest clearance 0.15 mm,
smallest track width 0.0889 mm, smallest via diameter 0.25 mm); 5936 fab-tier escalation(s) to advanced` -- below the
board's authored floors (clearance 0.2, track 0.15 min / 0.25 Default, via 0.55 min). The routes are placement
evidence only; this run ships no copper.

## Silkscreen

`beautify_labels` on seed 3; KiCad DRC silk classes before -> after: silk_overlap 199 -> 199, silk_over_copper
199 -> 36, silk_edge_clearance 23 -> 22 (421 -> 257). The labelled board was kept as `final.kicad_pcb`.

## Timeline (2026-10-30, local) and where the time went

- 15:35 first command; 15:35-15:41 read board/brief/context/schematic, groups.json, intent additions, check_groups, plan check
- 15:40 placement launched; stopped at ~1 min (BOX1 refused by the can keep-outs), intent fixed, relaunched 15:42
- ~16:12 12 seeds placed and graded (about 30 min: 12 parallel anneals of 221500 moves, 5-17 min each, 2 runs on several)
- 16:13-16:24 judging routes (`--quick 2`, 6 at once, 213-613 s each)
- 16:24-17:46 `--confirm 2` full routes of seeds 3 and 1 (2966 s and 3106 s)
- 17:47-18:34 route_review turns + full route of the candidate (rejected); label tidy, ledger, report drafting in parallel
- 18:34 final board, grade.py, measure.py, verifier
measure.py: wall 3:00:00 at measurement, of which 10101 s waiting on jobs (placement and routes), 530 s model, 169 s other tools.

## Verifier

One verifier (fresh subagent, `references/verifier.md` filled for `place`), 1 call: `verdict_1.txt`
**VERDICT=PASS** for the placement -- sha matched; buildable (blocking 0, no oob pad copper, no mating keep-out);
check_floorplan 0 errors / 19 warnings; render `a_off_outline` empty (pad, graphic, keep-out copper); all 15 mechanical
poses exact; all 282 can members' pad copper inside their can's zone on the listed face (measured by the verifier).
Routed-evidence condition: **NOT MET** (board_score blocking 7 on `s3_full`). It names as UNEXAMINED: member bodies vs
the can wall (pads only), heights under the lids (174 declared, not cross-checked), BOX1/FIX courtyards (none drawn),
the skipped floorplan rules, and the routed board's diff_pairs/impedance/length/net_widths.
It also noted the brief and the intent disagree on 12 can keep-outs' `allow` (my BOX1 addition lives in the intent only).

Ledger closed with `record --final --stop-condition 2` (budget spent). The verifier's file is a single place-mode
verdict, not per-lens files, so it is not passed as `--lens-file` (converge refuses a non-lens VERDICT line).

Datasheets: none downloaded (`datasheets/` is empty).


