import pcbnew, sys, json
src, dst = sys.argv[1], sys.argv[2]; keep = set(sys.argv[3:])
b = pcbnew.LoadBoard(src)
for f in list(b.GetFootprints()):
    if f.GetReference() not in keep: b.Remove(f)
pcbnew.SaveBoard(dst, b)
