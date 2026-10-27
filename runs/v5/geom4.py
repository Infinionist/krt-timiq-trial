#!/usr/bin/env python3
"""geom4.py : plan v4 geometry helpers (system python3, pcbnew). courtyard_dims(board) -> {ref: (w, h, face)} of each footprint's courtyard bounding box AS ON THE BOARD
(its current rotation), from pcbnew's own courtyard polygon (F.CrtYd / B.CrtYd); a footprint with none gets its pad bounding box."""
import os
import sys


def courtyard_dims(path):
    import pcbnew
    fd = os.dup(2)
    os.dup2(os.open(os.devnull, os.O_WRONLY), 2)
    try:
        b = pcbnew.LoadBoard(path)
    finally:
        os.dup2(fd, 2)
    mm = pcbnew.ToMM
    out = {}
    for f in b.GetFootprints():
        face = 'B' if f.IsFlipped() else 'F'
        layer = pcbnew.B_CrtYd if face == 'B' else pcbnew.F_CrtYd
        bb = None
        try:
            poly = f.GetCourtyard(layer)
            if poly.OutlineCount() > 0:
                bb = poly.BBox()
        except Exception:
            bb = None
        if bb is None or bb.GetWidth() <= 0:
            pads = list(f.Pads())
            if not pads:
                continue
            x0 = min(p.GetBoundingBox().GetX() for p in pads)
            y0 = min(p.GetBoundingBox().GetY() for p in pads)
            x1 = max(p.GetBoundingBox().GetRight() for p in pads)
            y1 = max(p.GetBoundingBox().GetBottom() for p in pads)
            out[f.GetReference()] = (mm(x1 - x0), mm(y1 - y0), face, (mm(x0), mm(y0), mm(x1), mm(y1)))
        else:
            out[f.GetReference()] = (mm(bb.GetWidth()), mm(bb.GetHeight()), face, (mm(bb.GetX()), mm(bb.GetY()), mm(bb.GetRight()), mm(bb.GetBottom())))
    return out


if __name__ == '__main__':
    d = courtyard_dims(sys.argv[1])
    for r in sys.argv[2:]:
        print(r, d.get(r))
