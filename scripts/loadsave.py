import sys, pcbnew
src, dst = sys.argv[1:3]
b = pcbnew.LoadBoard(src)
pcbnew.SaveBoard(dst, b)
ds = b.GetDesignSettings()
nc = ds.m_NetSettings.GetNetclasses()
for k, v in nc.items():
    print(k, v.GetClearance(), v.GetTrackWidth(), v.GetViaDiameter(), v.GetViaDrill())
d = ds.m_NetSettings.GetDefaultNetclass()
print('default', d.GetClearance(), d.GetTrackWidth(), d.GetViaDiameter(), d.GetViaDrill())
print('copper layers', b.GetCopperLayerCount())
for i in range(pcbnew.PCB_LAYER_ID_COUNT):
    if b.IsLayerEnabled(i): print(i, b.GetLayerName(i), '| std:', b.GetStandardLayerName(i))
