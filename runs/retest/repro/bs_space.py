"""Repro: board_score drops/misfiles nets whose names contain a space.
Feeds score_connectivity a check_connected output (shape copied from TimIQ s3_full).
Exit 1 when the bug shows (names lost or pad misattributed), 0 when fixed."""
import sys, os
K = sys.argv[1]
sys.path.insert(0, os.path.join(K, 'py_tools'))
import board_score as bs
def out(sheet):
    n = f'/TOP/{sheet}/'
    return f"""  Unrouted nets (1):
    {n}DAC_MOSI-P (2 pads)

  Connectivity issues (2):

  Net-(C9-Pad1) (net 152):
    Disconnected components: 2
    Disconnected pads:
      (149.21, 182.06) on F.Cu [U1]

  {n}FD0_N1-P (net 346):
    Disconnected components: 2
    Disconnected pads:
      (224.64, 131.49) on F.Cu [U34]
"""
bs.poured_net_names = lambda b: set()
bad = 0
for sheet in ('digital_interface', 'digital interface'):
    o = out(sheet)
    bs.run_tool = lambda root, tool, *a, o=o: (1, o + "\nTotal: 3 nets with issues\n")
    bs._CONN_TOTAL = __import__('re').compile(r'Total: (\d+)')
    r = bs.score_connectivity(K, 'x.kicad_pcb')
    names = r.get('unrouted_net_names'); det = r.get('broken_detail', {})
    c9 = [p['ref'] for p in det.get('Net-(C9-Pad1)', {}).get('stranded_pads', [])]
    ok = len(names) == 1 and len(det) == 2 and c9 == ['U1']
    print(f"{sheet!r}: unrouted={r['unrouted']} names={names} broken nets={list(det)} C9 pads={c9} -> {'ok' if ok else 'BUG'}")
    bad += not ok
sys.exit(1 if bad else 0)
