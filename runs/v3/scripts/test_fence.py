#!/usr/bin/env python3
"""Tests for fence.py. Each must-fail case is checked against a passing twin, so the failing result is the mutation's doing.
Run: /tmp/pcb-trials/timiq/krt/.venv/bin/python -X utf8 test_fence.py   (exit nonzero on failure)"""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fence
fence._shapely()
from shapely.geometry import Polygon, box


def P(ref, x, y, w=2.0, h=1.0, side='F', nets=(), tht=False):
    return fence.Part(ref, side, (x - w / 2, y - h / 2, x + w / 2, y + h / 2),
                      (x - w / 2, y - h / 2, x + w / 2, y + h / 2) if tht else None, tht, set(nets), [(n, x, y) for n in nets])


def board(parts, bounds=(0, 0, 100, 100), holes=()):
    return fence.Board({p.ref: p for p in parts}, bounds, set(), list(holes))


def block():
    """A 3 x 3 grid of members (2 x 1 mm, 5 mm pitch) on nets N00..N22, all on the net SIG."""
    ms = [P(f'M{i}{j}', 20 + 5 * i, 20 + 5 * j, nets=[f'N{i}{j}', 'SIG']) for i in range(3) for j in range(3)]
    return ms, [m.ref for m in ms]


class FenceTests(unittest.TestCase):
    def setUp(self):
        self.ms, self.refs = block()

    def run_(self, extra=(), bounds=(0, 0, 100, 100), holes=(), **kw):
        b = board(list(self.ms) + list(extra), bounds=bounds, holes=holes)
        return fence.check_fences(b, {'X': self.refs}, **kw)['fences']['X'], b

    def test_pass(self):
        f, _ = self.run_([P('FAR', 80, 80, nets=['SIG', 'OUT'])])
        self.assertTrue(f['pass'], f)
        self.assertEqual(f['members_inside']['inside'], 9)
        self.assertEqual(f['nets_crossing']['signal'], 1)          # SIG only

    def test_foreign_inside_fails(self):
        f, _ = self.run_([P('FAR', 80, 80)])
        self.assertTrue(f['pass'])
        f, _ = self.run_([P('FAR', 80, 80), P('INSIDE', 25, 25, w=1, h=0.5)])   # in the gap of the grid
        self.assertFalse(f['pass'])
        self.assertEqual(f['no_foreign_inside']['foreign'], ['INSIDE'])

    def test_ring_violation_fails(self):
        # member M22 right edge x=31; wall inner edge 31.5, outer 32.5; clearance to 33.0.
        f, _ = self.run_([P('RING', 33.0, 30, w=1.2, h=0.5)])      # x 32.4..33.6: in the wall / clear band
        self.assertFalse(f['pass'])
        self.assertEqual(f['ring_clear']['in_ring'], ['RING'])
        self.assertEqual(f['no_foreign_inside']['foreign'], [])
        g, _ = self.run_([P('RING', 33.7, 30, w=1.2, h=0.5)])      # x 33.1..34.3: clear
        self.assertTrue(g['pass'], g)

    def test_b_side_smd_is_not_foreign(self):
        f, _ = self.run_([P('BSIDE', 25, 25, side='B')])
        self.assertTrue(f['pass'])
        self.assertEqual(f['b_under'], ['BSIDE'])

    def test_tht_on_back_is_foreign(self):
        f, _ = self.run_([P('THT', 25, 25, side='B', tht=True)])
        self.assertFalse(f['pass'])

    def test_member_outside_hand_drawn_fence_fails(self):
        b = board(self.ms)
        small = Polygon([(18, 18), (24, 18), (24, 24), (18, 24)])
        f = fence.check_fences(b, {'X': self.refs}, centres={'X': small})['fences']['X']
        self.assertFalse(f['members_inside']['ok'])
        self.assertFalse(f['pass'])
        big = Polygon([(17, 17), (34, 17), (34, 34), (17, 34)])
        g = fence.check_fences(b, {'X': self.refs}, centres={'X': big})['fences']['X']
        self.assertTrue(g['members_inside']['ok'], g)
        self.assertTrue(g['pass'], g)

    def test_fabricable(self):
        ok, _ = fence.fabricable(Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]), 3.0)
        self.assertTrue(ok)
        ok, why = fence.fabricable(Polygon([(0, 0), (10, 0), (10, 5), (11, 5), (11, 10), (0, 10)]), 3.0)   # 1 mm jog
        self.assertFalse(ok)
        self.assertTrue(any('shorter' in w for w in why))
        ok, why = fence.fabricable(Polygon([(0, 0), (10, 0), (5, 10)]), 3.0)
        self.assertFalse(ok)
        self.assertTrue(any('diagonal' in w for w in why))
        ok, why = fence.fabricable(Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], [[(3, 3), (6, 3), (6, 6), (3, 6)]]), 3.0)
        self.assertFalse(ok)
        self.assertTrue(any('hole' in w for w in why))

    def test_hand_drawn_short_segment_fails_the_fence(self):
        b = board(self.ms)
        good = Polygon([(10, 10), (41, 10), (41, 40), (10, 40)])
        jog = Polygon([(10, 10), (41, 10), (41, 30), (42, 30), (42, 40), (10, 40)])
        self.assertTrue(fence.check_fences(b, {'X': self.refs}, centres={'X': good})['fences']['X']['pass'])
        f = fence.check_fences(b, {'X': self.refs}, centres={'X': jog})['fences']['X']
        self.assertFalse(f['fabricable']['ok'])
        self.assertFalse(f['pass'])

    def _l_block(self):
        return [P(f'L{i}', 20, 20 + 6 * i) for i in range(6)] + [P(f'B{i}', 20 + 6 * i, 50) for i in range(1, 6)]

    def test_carved_outline_is_fabricable_and_smaller_than_bbox(self):
        ms = self._l_block()
        b = board(ms)
        f = fence.check_fences(b, {'X': [m.ref for m in ms]})['fences']['X']
        self.assertTrue(f['fabricable']['ok'], f['fabricable'])
        self.assertTrue(f['pass'], f)
        self.assertLess(f['area_outer'], f['bbox_area_outer'] - 50)
        flat = fence.check_fences(b, {'X': [m.ref for m in ms]}, carve=False)['fences']['X']
        self.assertAlmostEqual(flat['area_outer'], flat['bbox_area_outer'], 2)

    def test_foreign_in_the_notch_is_fine_with_carving_and_a_fail_without(self):
        ms = self._l_block()
        b = board(ms + [P('NOTCH', 40, 25)])
        names = [m.ref for m in ms]
        self.assertTrue(fence.check_fences(b, {'X': names})['fences']['X']['pass'])
        f = fence.check_fences(b, {'X': names}, carve=False)['fences']['X']
        self.assertFalse(f['pass'])
        self.assertEqual(f['no_foreign_inside']['foreign'], ['NOTCH'])

    def test_two_fences_too_close_fail(self):
        a = [P('A1', 10, 10), P('A2', 14, 10)]
        far = [P('C1', 40, 10), P('C2', 44, 10)]
        near = [P('C1', 20.2, 10), P('C2', 24.2, 10)]     # member gap 5.2 mm: walls clear each other (2 x 1.5) but not the clearance
        tight = [P('C1', 18.6, 10), P('C2', 22.6, 10)]    # member gap 3.6 mm: walls would touch
        for c, want in ((far, True), (near, True), (tight, False)):
            r = fence.check_fences(board(a + c), {'A': ['A1', 'A2'], 'C': ['C1', 'C2']}, min_seg=3.0)
            self.assertEqual(r['pass'], want, (c, r['fences']))
        r = fence.check_fences(board(a + tight), {'A': ['A1', 'A2'], 'C': ['C1', 'C2']}, min_seg=3.0)
        self.assertFalse(r['fences']['A']['fence_clearance']['ok'])

    def test_board_edge_and_hole(self):
        f, _ = self.run_()
        self.assertTrue(f['on_board']['ok'])
        f, _ = self.run_(bounds=(19, 0, 100, 100))
        self.assertFalse(f['on_board']['ok'])
        f, _ = self.run_(holes=[('hole', 16.0, 20.0, 3.0)])
        self.assertFalse(f['on_board']['ok'])
        f, _ = self.run_(holes=[('hole', 60.0, 60.0, 2.0)])
        self.assertTrue(f['on_board']['ok'])

    def test_nets_crossing_are_classified(self):
        ms, refs = block()
        ms[0].nets |= {'GND', '+5V', 'CLK'}
        out = P('OUT', 80, 80, nets=['GND', '+5V', 'CLK', 'SIG'])
        r = fence.check_fences(board(ms + [out]), {'X': refs})['fences']['X']['nets_crossing']
        self.assertEqual((r['signal'], r['power'], r['ground']), (2, 1, 1), r)

    def test_wall_crossings_count_mst_edges_between_member_and_other_pads(self):
        self.assertEqual(fence.mst_crossings([(0, 0), (1, 0)], [(10, 0)])[0], 1)
        c, ln = fence.mst_crossings([(0, 0), (1, 0)], [(10, 0)])
        self.assertAlmostEqual(ln, 9.0)
        self.assertEqual(fence.mst_crossings([(0, 0)], []), (0, 0.0))
        self.assertEqual(fence.mst_crossings([(0, 0), (5, 0)], [(2, 1), (3, 1)])[0], 2)   # in-out-out-in: the tree crosses twice
        ms, refs = block()
        far = P('OUT', 80, 20, nets=['SIG'])
        near = P('OUT', 40, 20, nets=['SIG'])
        a = fence.check_fences(board(ms + [far]), {'X': refs})['fences']['X']['wall_crossings']['signal']
        b = fence.check_fences(board(ms + [near]), {'X': refs})['fences']['X']['wall_crossings']['signal']
        self.assertEqual(a['edges'], 1)
        self.assertGreater(a['length_mm'], b['length_mm'] + 30)       # farther away = longer wire over the wall

    def test_container_and_can_standin_are_not_foreign(self):
        can = P('J9', 25, 25, w=30, h=30)
        r = fence.check_fences(board(self.ms + [can]), {'J9': self.refs})['fences']['J9']
        self.assertTrue(r['pass'], r)
        r = fence.check_fences(board(self.ms + [can]), {'X': self.refs})['fences']['X']      # same part, not a stand-in: foreign
        self.assertFalse(r['pass'])

    def test_exit_codes(self):
        # the CLI on real files: a tiny board gives 0, the same board with a foreign part inside gives 4, a missing file 2
        def pcb(parts):
            fps = []
            for n, (ref, x, y) in enumerate(parts):
                fps.append(f'\t(footprint "T:R" (layer "F.Cu") (uuid "{n:08d}-0000-4000-8000-000000000000") (at {x} {y})\n'
                           f'\t\t(property "Reference" "{ref}" (at 0 0) (layer "F.SilkS") (uuid "{n:08d}-0000-4000-8000-000000000001"))\n'
                           f'\t\t(pad "1" smd rect (at -0.6 0) (size 0.8 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (net 1 "SIG"))\n'
                           f'\t\t(pad "2" smd rect (at 0.6 0) (size 0.8 0.8) (layers "F.Cu" "F.Paste" "F.Mask") (net 2 "x{ref}"))\n\t)')
            edge = ''.join(f'\t(gr_line (start {a} {b}) (end {c} {d}) (stroke (width 0.1) (type default)) (layer "Edge.Cuts") (uuid "00000000-0000-4000-8000-0000000001{i:02d}"))\n'
                           for i, (a, b, c, d) in enumerate([(0, 0, 100, 0), (100, 0, 100, 100), (100, 100, 0, 100), (0, 100, 0, 0)]))
            return ('(kicad_pcb (version 20260206) (generator "pcbnew") (generator_version "10.0")\n\t(general (thickness 1.6))\n\t(paper "A4")\n'
                    '\t(layers (0 "F.Cu" signal) (2 "B.Cu" signal) (5 "F.SilkS" user "F.Silkscreen") (1 "F.Mask" user) (13 "F.Paste" user) (25 "Edge.Cuts" user))\n'
                    '\t(setup (pad_to_mask_clearance 0))\n\t(net 0 "")\n\t(net 1 "SIG")\n\t(net 2 "x")\n' + edge + '\n'.join(fps) + '\n)\n')
        mem = [('M1', 20, 20), ('M2', 26, 20), ('M3', 20, 26), ('M4', 26, 26)]
        with tempfile.TemporaryDirectory() as d:
            blocks = os.path.join(d, 'b.json')
            json.dump({'X': {'members': [m[0] for m in mem]}}, open(blocks, 'w'))
            good = os.path.join(d, 'good.kicad_pcb')
            open(good, 'w').write(pcb(mem + [('FAR', 70, 70)]))
            bad = os.path.join(d, 'bad.kicad_pcb')
            open(bad, 'w').write(pcb(mem + [('FAR', 70, 70), ('IN', 23, 23)]))
            self.assertEqual(fence.main([good, '--blocks', blocks, '--quiet']), 0)
            self.assertEqual(fence.main([bad, '--blocks', blocks, '--quiet']), 4)
            self.assertEqual(fence.main([os.path.join(d, 'none.kicad_pcb'), '--blocks', blocks, '--quiet']), 2)


if __name__ == '__main__':
    unittest.main()
