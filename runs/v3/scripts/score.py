#!/usr/bin/env python3
"""score.py: one row of the variant-3 score table for a placed board, by script.

    score.py LABEL BOARD --blocks BLOCKS.json --intent INTENT.json --baseline PILE.kicad_pcb --groups GROUPS.json --json OUT.json

Runs, on the board as given: fence.py's checks (members inside, rings clear, nothing foreign inside, fabricable, nets crossing,
areas), KRT check_floorplan --intent (errors, hpwl), KRT check_assembly --baseline (buildable, blocking), and the placer's own
cost model on the board (wire mm, airwire crossings; `placement.simple.Model.total`). Exit 0 always unless a tool crashes.
"""
import argparse, json, os, re, subprocess, sys, tempfile

KRT = os.environ.get('KRT_ROOT', '/tmp/pcb-trials/timiq/krt')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PY = sys.executable


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    return r.returncode, r.stdout + r.stderr


def summary(out):
    m = re.search(r'^JSON_SUMMARY: (\{.*\})\s*$', out, re.M)
    return json.loads(m.group(1)) if m else {}


def model_cost(board, intent, groups):
    sys.path[:0] = [os.path.join(KRT, p) for p in ('py_placer', 'py_router', 'py_tools', 'tests')]
    import place_simple as ps
    from kicad_parser import parse_kicad_pcb
    from placement import floorplan as fp
    from placement.grouping import load_groups
    from placement.groups import parse_sources
    pcb = parse_kicad_pcb(board)
    args = ps.build_parser().parse_args([board, '/dev/null', '--groups', groups, '--intent', intent])
    it = fp.load_intent(intent)
    blocks, _ = fp.resolve_blocks(it, pcb, parse_sources('auto'))
    st, model, mov, _ = ps.build(pcb, board, load_groups(groups), json.load(open(intent)), args, it, blocks, set())
    t = model.total()
    return {'wire_mm': round(t['wire'], 1), 'crossings': t['crossings'], 'pad_hits': t.get('pad_hits')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('label'); ap.add_argument('board')
    ap.add_argument('--blocks', required=True); ap.add_argument('--intent', required=True)
    ap.add_argument('--baseline', required=True); ap.add_argument('--groups', required=True)
    ap.add_argument('--json', required=True)
    ap.add_argument('--fence-args', nargs='*', default=[])
    a = ap.parse_args()
    row = {'label': a.label, 'board': a.board}
    with tempfile.TemporaryDirectory() as td:
        fj = os.path.join(td, 'fence.json')
        rc, out = run([PY, '-X', 'utf8', os.path.join(HERE, 'fence.py'), a.board, '--blocks', a.blocks, '--intent', a.intent, '--json', fj, '--quiet'] + a.fence_args)
        row['fence_rc'] = rc
        rep = json.load(open(fj))
        row['fence'] = {'pass': rep['pass'], 'totals': rep['totals'],
                        'per_block': {n: {'members_inside': f['members_inside']['inside'], 'members': f['members_inside']['of'],
                                          'foreign_inside': len(f['no_foreign_inside']['foreign']), 'ring_violations': len(f['ring_clear']['in_ring']),
                                          'fabricable': f['fabricable']['ok'], 'fence_clearance': f['fence_clearance']['ok'], 'on_board': f['on_board']['ok'],
                                          'area_outer': f['area_outer'], 'area_inner': f['area_inner'], 'bbox_area_outer': f['bbox_area_outer'],
                                          'nets_signal': f['nets_crossing']['signal'], 'wall_cross_edges': f['wall_crossings']['signal']['edges'], 'wall_cross_mm': f['wall_crossings']['signal']['length_mm'], 'nets_power': f['nets_crossing']['power'],
                                          'nets_ground': f['nets_crossing']['ground'], 'pass': f['pass']}
                                      for n, f in rep['fences'].items()}}
        fo = os.path.join(td, 'fp.json')
        rc, out = run([PY, '-X', 'utf8', os.path.join(KRT, 'py_tools/check_floorplan.py'), a.board, '--intent', a.intent, '--json', fo])
        s = summary(out)
        row['floorplan'] = {'rc': rc, 'errors': s.get('errors'), 'violations': s.get('violations'), 'hpwl': s.get('hpwl'),
                            'overlap_area': s.get('overlap_area'), 'oob_count': s.get('oob_count'), 'by_rule': s.get('violations_by_rule')}
        ao = os.path.join(td, 'asm.json')
        rc, out = run([PY, '-X', 'utf8', os.path.join(KRT, 'py_tools/check_assembly.py'), a.board, '--intent', a.intent, '--baseline', a.baseline, '--json', ao])
        try:
            d = json.load(open(ao))
            row['assembly'] = {'rc': rc, 'buildable': d.get('buildable'), 'blocking': d.get('blocking'), 'advisory': d.get('advisory')}
        except (OSError, ValueError):
            row['assembly'] = {'rc': rc, 'error': out[-300:]}
    try:
        row['model'] = model_cost(a.board, a.intent, a.groups)
    except Exception as e:      # noqa: BLE001
        row['model'] = {'error': repr(e)}
    json.dump(row, open(a.json, 'w'), indent=1)
    print(json.dumps({k: v for k, v in row.items() if k != 'fence'}, default=str))
    print(json.dumps(row['fence']['totals']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
