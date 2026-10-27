# TimIQ RF KRT trial (discussion 118, for edgehero) — plan, approved by Infinionist 2026-10-26

Decisions (Infinionist 10-26): cost OK (~one 5-hour window, cap 4h15, likely ends NOT DONE with blockers named); fix the obvious
mechanical parts (lead drafts list from human poses, Infinionist checks; maybe fix more later); no EMC rows given (AI unaided, we
judge EMC in review); Infinionist accepts the KRT workspace trust prompt himself. Goal: useful feedback, stay on track.

Phases (planner report summarised in the session; KRT HEAD at plan time db056e03):
A. Setup, CPU only: fresh KRT clone (krt/), edgehero staging scripts (staging/, from edgehero@3c980631), timiq-hw @2cd7bfd5
   in src/, kicad-cli 10.0.6 upgrade + .kicad_pro with both netclasses, sch upgrade attempt, stage_board.sh pile,
   _truth/human_stripped.kicad_pcb, pilot board_brief/board_context/check_floorplan, control route of human placement.
B. Run: KRT's headless placement_run prompt (/plan-pcb-placement full, Opus, stream-json, PLACEMENT_ALLOWED_TOOLS) plus
   edgehero's capture rules (STATE.md, CHOSEN.json, placed_from/, final_route/ + KICAD_ROUTE_TRACE=1, TOOL_GAPS.md),
   user cap 4h15, background script run.sh, stream.jsonl kept. Check usage at 30 min.
C. Capture: whole run dir, timeline from stream.jsonl, renders per ledger board; films via staging/films.sh + route_movie.
D. Measure AI board AND human board with the same scripts (KRT grade/check tools, pcb layout facts, our pcbnew RF/EMC/DFM scripts).
E. Reference facts: datasheet layout pages via gem, quotes checked by script; stackup from TimIQ-RF_PCB.pdf.
F. Review with Infinionist: every finding and question, grouped (placement, routing, RF/stackup, EMC/EMI, approvals, DFM/yield,
   thermal, mechanical), each with measurement, human value, reference, image; we make the calls together; nothing posted
   to KRT until he OKs the text (D-048).

Infinionist 10-26 (after setup): fixed list OK as proposed (FIX1-8, BOX1, J1-J4, J5, J6, D2-D8 fixed; D1 and shield frames J7-J12 free). Schematic: via the GUI (eeschema under Xvfb, agent running).
Infinionist 10-26: schematic via GUI accepted (KRT reads sheets/notes, nets from board; ~15 conversion splits harmless). Trust: headless -p, KRT .claude has only WebFetch allow, no hooks/MCP; Infinionist approved the start.
Infinionist 10-26 (shield design notes, for a future KRT shield proposal): (1) a designer, even an AI, knows before placement which
parts go under which can, so membership should be declarable ("these parts under that can"). (2) Often the circuit is placed
first and a custom sheet-metal shield is drawn around it afterward (tight boards, or shielding not yet known to be needed;
customs are cheap vs OTS can sizes): shield as an OUTPUT of placement, i.e. a reserved fence ring around a block. Run 2 cans
are free; the AI declares membership itself from the schematic (we don't hand it the human's map).
Infinionist 10-26 (more shield requirements): (3) two-part cans: a frame plus a lid, often two BOM lines but not always (one footprint
or a lid-only BOM line). The model must pair them as one shield. (4) Height: error if any part assigned under a can is
taller than the can's inner clearance (lid underside minus board, per KRT's heights/covers; 1443 gives part heights from the GLB).
Test bench plan: variants (1) KRT as-is (container, or remove/restore), (2) declared membership patch, (3) fence ring after
placement; each scored by script on TimIQ: human passes, part on a wall fails, shielded circuits inside, cost to the rest
(area, wire length, nets crossing walls), plus the height check. Placer runs CPU-only; the full AI run only for the winner.
Infinionist 10-26: FIX1-FIX8 holes get the same clearance rule (3.5 mm from hole edge, or the human's clearance at that hole if closer).
BOX1 = Hammond 1590Q die-cast box over the RF section: RF parts inside, wall band clear, box height limit (facts list pending).
Infinionist 10-26: stop the drawn-fence variant (v3); it was a note for a future fix effort. Custom fences should generally be a
plain rectangle. v3 results/scripts kept in /tmp/pcb-trials/timiq/v3 for that later effort. Focus: v4 (OTS cans, all constraints).
Infinionist 10-26 (after conference + facts list): fix J7-J10 under the lid window (design intent known before placement); DXF over
FCStd. Rules: declare every constraint knowable before placement/route; use KRT as intended, and every deviation has a reason
and is reported. No more variant runs until the rewritten plan (constraints table, KRT-intended loop, scripted designer
check) is reviewed by Infinionist. v4 (running) is the last variant; results kept as a data point.
