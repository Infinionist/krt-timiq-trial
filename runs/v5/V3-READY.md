# TimIQ plan v3 inputs: ready (builder, 10-26). No seeds were run; run_seeds.sh was not started.

## Gate
`python3 /tmp/pcb-trials/timiq/v5/gate.py` -> GATE PASS (plan-only 0 errors, check_groups 0 errors, 45/45 ICs covered, 6 cans: can<J> + can<J>_anchor + power block,
0 footprints without a courtyard). New this round: check 6 (`inputs_problems`): BOX1 in every keep-out allow list, every pin row (a row with `pads`) at 3.0 mm,
and `intent_reattached.json` allows BOX1 + the six cans in each can keep-out and holds one overlap_waiver per can x (member + optional) (290).

## Tests (`python3 /tmp/pcb-trials/timiq/v5/tests/test_scripts.py`, ~2.5 min, run twice: 97 ok, 0 FAIL, "ALL HOLD"; 49 of them are MUST FAIL cases; includes tests/test_netrows.py)
Each MUST FAIL runs the check on bad input and asserts it fails; "fail-first" ones run the OLD inputs/scripts in probe3/old/ and assert the old behaviour is the failure.
- gate, block shapes: can<J>/can<J>_anchor/power present; J9 member dropped; anchor block removed; power block removed; anchor zone outside the interior; hard anchor zone;
  face pinned on a can block; anchor IC also in the member block; optional part dropped from cans.json -> all FAIL as asked. PASS
- courtyards: old board (probe3/old/fixed.kicad_pcb) fails the gate; the real board with C130's courtyard removed fails naming C130; real board 0 missing; BOX1 the only one without. PASS
- pin rows: real intent 244 pin rows all 3.0 mm + 83 part rows 5.0; one row doctored to 2.0 fails (pure + CLI); the old intent (246 rows at 2.0) fails. netrows tests PASS (3.0). PASS
- BOX1: removed from wall-band-left, from can-J8 (CLI), from can-J9 of the reattached intent, a can missing from the reattached list; old intent (no BOX1 in can keep-outs) fails. PASS
- waivers: J7/C2 removed fails (pure + CLI); J10 optional parts without waiver fails; check_assembly on the human board reads them (waived pairs none 210, J7 missing 488, all 544). PASS
- designer_check: optional part is not an intruder (old script fails the same file); a real intruder (C48 unlisted) still fails; a declared member not on the board fails;
  a member on the "other" face still counts (old script fails it); LED resistors out of far (28 vs old 36; --max-far 27 fails, old script fails 28); anchor miss is INFO, run
  still exits 0; old script prints no INFO line; filter-reg numbers; keep_away reading equals KRT check_floorplan min_gap_mm (2.0658 / 28.613) within 0.01; the pile reads INSIDE. PASS
- carried over (reattach, cans_io, holes, human board 8/8 with C20/R16 waived, 40 mm hole radii, --max-far 0, unplaced pile): PASS

## designer_check.py changes
Members: any face, `members` list (falls back to refs F+B), optional parts ignored; far: LED series resistors (resistor on a net with an `LED:*` pad) left out, HUMAN_FAR 36 -> 28;
INFO lines (never a failure; JSON entries have `"pass": null, "info": true`): `anchors` (anchor IC outside its anchor zone + 1 mm), `filter-reg` (L12-L14, C143-C150 to the nearest
regulator they serve), `keep_away` (per rule: min aggressor-victim pad-edge gap, closest pair, inside/outside the gap, min per victim group). Run with /usr/bin/python3.

## Human-board reference numbers (`python3 human_reference.py` -> human_reference.json)
- far passives (> 10 mm pad edge from their IC pin): 28 of 372 (36 before the LED resistors R1, R154, R155, R160-R164 are left out). Worst: C149 37.0, C150 34.8, C144 33.9, C145 32.2, C96 30.3, C97 25.7.
- proximity rows of the v3 intent on the human layout: pin rows (244): 68 within 2.0 mm, 104 within 3.0, 154 within 5.0; median 3.54 mm. Part rows (83): 49 within 5.0, 72 within 10.
- filter -> regulator (nearest regulator served): L12 0.0 (U40), L13 20.0 (U43), L14 20.4 (U45), C143 0.0, C144 33.9, C145 32.2, C146 1.8, C147 1.8, C148 4.5, C149 36.8, C150 34.8. Max 36.8.
  The human keeps the 24V/-24V filter parts at J6 and the regulators ~20-37 mm away: the v3 ordered chain asks for more than the human did.
- anchors: with the v3 anchor zones the human has 5 of 7 anchor ICs inside; U11 (J9) 2.1 mm and U4 (J12) 5.5 mm outside.
- keep_away (3.0 mm, pad edge, plan view): rule 0 digital -> sensitive min 2.07 mm (U1 pad 20 PLL_LOCKED to C3 pad 1 PLL_IN), INSIDE; by victim group: LO/PLL 2.07, ADC inputs 2.52 (C110/U29), RF to SMAs 3.65, DAC I/Q 14.0.
  Rule 1 power rails -> sensitive min 28.61 mm (C169 -24V to U4 DAC_I). KRT lists 3 human part pairs inside 3.0: C3/U1 2.07, C110/U29 2.52, C16/U1 2.52.

## Is 3.0 mm keep_away sane? (value not changed)
Yes as a soft WARN. The power rule is nowhere near it (28.6 mm on the human). The digital rule: the human holds >= 3.65 mm to the RF notch nets and 14 mm to the DAC nets; it dips below 3.0 only at
the pins of two chips (U1, U29: an RF/ADC input cap next to a digital pin of the same IC, 2.07-2.52 mm). So 3.0 asks for a little more than the human did at U1/U29 and the same elsewhere. Those
3 pairs may stay inside the band when the 3.0 mm pin rows pin the input cap to its own pin; 2.0 mm would pass the human exactly (min 2.07). It is WARN in KRT, so it blocks nothing.

## Renders
/tmp/pcb-trials/timiq/v5/floorplan.png (top view) and /tmp/pcb-trials/timiq/v5/floorplan_bottom.png: can interiors (solid), can footprint boxes (dotted), anchor zones (dashed, soft), power zone (amber),
fixed parts and holes, keep_away aggressor (magenta) and victim (teal) outlines / A,V chips / side panel per can, legend. Both viewed and legible. Source: render_floorplan.py (`/usr/bin/python3`).

## run_seeds.sh
Copies v5/intent_reattached.json (heredoc gone); check_assembly gets `--intent $S/intent_reattached.json`; JOBS cap 12 kept. Fixed a bug: designer_check.py was started with KRT's venv python (no pcbnew, it
would have exited at import): now /usr/bin/python3. `bash -n` OK. v5/seeds/ (run 1) still exists: the script refuses to start until it is moved aside.

## Open questions
1. The 290 waivers do not change check_assembly's blocking set (same 23 pad-intersection pairs on c2 with and without; only advisory courtyard/fab pairs go 234 -> 572 waived). Keep for a quiet report, or drop?
2. Pin rows at 3.0 mm: only 104 of 244 hold on the human layout (median 3.54). The placer may leave many as warnings; expected, not a defect. OK?
3. keep_away stays 3.0 (WARN) or 2.0 (human-exact)? See above.
4. I added gate check 6 (inputs_problems) so the pin-row / BOX1 / waiver tests have a script that decides; not in the spec, small, tell me if you want it out.
