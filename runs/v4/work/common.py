import sys, re, json, math
sys.path.insert(0,'/tmp/pcb-trials/timiq/v2/krt/py_placer'); import _path
from kicad_parser import parse_kicad_pcb
from placement import legality
HUMAN='/tmp/pcb-trials/timiq/_truth/human_stripped.kicad_pcb'
# box squares (Infinionist 10-26, from BOX1 F.SilkS)
OUT=(122.21,92.95,246.21,216.95); MID=(126.96,97.7,241.46,212.2); INN=(131.96,102.7,236.46,207.2)
def inter(a,b): return min(a[2],b[2])-max(a[0],b[0])>1e-6 and min(a[3],b[3])-max(a[1],b[1])>1e-6
def inside(a,b,t=1e-6): return a[0]>=b[0]-t and a[1]>=b[1]-t and a[2]<=b[2]+t and a[3]<=b[3]+t
def load(path):
    p=parse_kicad_pcb(path); G={g.ref:g for g in legality.graded_parts_from_file(p,path)}
    return p,G
