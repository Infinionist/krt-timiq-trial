#!/usr/bin/env python3
"""Build prompt.md the way krt/kicad_routing_plugin/placement_run.py builds the headless placement prompt
(`/<skill> <mode> <board> — <instructions>`, instructions from build_placement_instructions), plus the trial's capture rules.
Differences from the GUI, all deliberate: the board is RUN2/TimIQ_RF.kicad_pcb (not input.kicad_pcb) and the given
intent.json is passed as the skill's third argument (edgehero's flow); the datasheet sentence says the folder is
emptied by the orchestrator, not by a runner."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'krt', 'kicad_routing_plugin'))
import placement_run as pr  # flat import, wx-free
RUN = os.path.join(HERE, 'run2')
board = os.path.join(RUN, 'TimIQ_RF.kicad_pcb')
intent = os.path.join(RUN, 'intent.json')
extra = open(os.path.join(HERE, 'capture_rules2.md'), encoding='utf-8').read().strip()
instr = pr.build_placement_instructions(RUN, 'place_route', extra=extra)
instr = instr.replace('input.kicad_pcb', 'TimIQ_RF.kicad_pcb')
instr = instr.replace('which is deleted when this run ends', 'which the orchestrator deletes after the run')
args = f"{pr.PLACEMENT_SKILL_MODES['place_route']} {board} {intent}"
prompt = f"/{pr.PLACEMENT_SKILLS['place_route']} {args} — {instr}"
out = os.path.join(HERE, 'prompt2.md')
open(out, 'w', encoding='utf-8').write(prompt + '\n')
print(out, len(prompt), 'chars')
print('allowed tools:', pr.PLACEMENT_ALLOWED_TOOLS)
