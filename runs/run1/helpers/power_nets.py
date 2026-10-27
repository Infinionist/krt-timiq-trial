# analyze-power-nets followed by hand (skill Steps 1-6); currents are datasheet typical/max supply figures.
import sys
sys.path.insert(0, "py_tools")
from analyze_power_paths import (analyze_pcb, get_components_needing_analysis, classify_component,
    trace_power_paths, get_power_net_recommendations, format_analysis_report, ComponentRole as R)
comps, pcb = analyze_pcb(sys.argv[1])
unk = get_components_needing_analysis(comps)
print("UNKNOWN:", sorted(getattr(u, "ref", getattr(u, "reference", str(u))) for u in unk))
C = {
 'J6': (R.POWER_SOURCE, 1500, 'Molex 39-30-1061 6-pin Mini-Fit power entry (3 rails + GND)'),
 'U39': (R.POWER_SOURCE, 1000, 'TPS7A4700 1 A LDO'), 'U40': (R.POWER_SOURCE, 1000, 'TPS7A4700 1 A LDO'),
 'U41': (R.POWER_SOURCE, 1000, 'TPS7A4700'), 'U42': (R.POWER_SOURCE, 1000, 'TPS7A4700'),
 'U43': (R.POWER_SOURCE, 1000, 'TPS7A4700'), 'U44': (R.POWER_SOURCE, 1000, 'TPS7A3301 -1 A LDO'),
 'U45': (R.POWER_SOURCE, 1000, 'TPS7A3301 -1 A LDO'),
 'U1': (R.CURRENT_SINK, 300, 'LMX2541 PLL+VCO ~250-300 mA'), 'U2': (R.CURRENT_SINK, 60, 'CVHD-950 VCXO'),
 'U16': (R.CURRENT_SINK, 180, 'HMC1097 IQ mod ~170 mA @5V'), 'U18': (R.CURRENT_SINK, 100, 'HMC705 ~95 mA'),
 'U19': (R.CURRENT_SINK, 100, 'HMC705'), 'U20': (R.CURRENT_SINK, 100, 'HMC705'),
 'U21': (R.CURRENT_SINK, 60, 'PMA2-43LN+ 50 mA'), 'U22': (R.CURRENT_SINK, 60, 'PMA2-43LN+ 50 mA'),
 'U4': (R.CURRENT_SINK, 20, 'LTC2758 DAC'), 'U29': (R.CURRENT_SINK, 30, 'ADS8694'),
 'U31': (R.CURRENT_SINK, 70, 'SN75LVDT388A'), 'U32': (R.CURRENT_SINK, 70, 'SN75LVDT388A'),
 'U34': (R.CURRENT_SINK, 70, 'SN75LVDT388A'), 'U38': (R.CURRENT_SINK, 70, 'SN75LVDS389'),
}
for r, (role, ma, n) in C.items():
    if r in comps: classify_component(comps, r, role, current_rating_ma=ma, notes=n)
paths = trace_power_paths(pcb, comps)
rec = get_power_net_recommendations(pcb, comps, paths)
print(format_analysis_report(pcb, comps, paths, rec)[-3000:])
print("REC", rec)
