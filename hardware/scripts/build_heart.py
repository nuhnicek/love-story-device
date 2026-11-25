"""
Heart LED board: heart-shaped 2-layer PCB, 14 pink 0603 LEDs on the FRONT (the
visible face behind the enclosure window) and four 4 x 0402 resistor arrays on
the FRONT as well (single-sided assembly); only the 2 wire pads are on the BACK.
Run with KiCad's bundled Python:

  $KPY hardware/scripts/build_heart.py
"""
import math
import os

import pcbnew as pn
import pcblib
from pcblib import V, mm

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(HW, "heart")
OUT = os.path.join(DIR, "heart-led.kicad_pcb")
FPLIB = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"

N = 14            # LEDs
WIDTH = 12.5      # LED-centre heart width, mm (~12.5 x 11 mm; 2.85 mm LED pitch)
EDGE = 1.9        # LED centre -> board edge (radial 0603: 1.52 mm half-length)
CX, CY = 100.0, 100.0
S = WIDTH / 32.0  # classic heart curve is 32 units wide


def heart(t):
    """x right, y DOWN (board coords)."""
    x = 16 * math.sin(t) ** 3
    y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
    return CX + S * x, CY - S * y


# dense polyline + cumulative arc length
M = 4000
ts = [2 * math.pi * i / M for i in range(M + 1)]
pts = [heart(t) for t in ts]
cum = [0.0]
for a, b in zip(pts, pts[1:]):
    cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
L = cum[-1]


def at_len(s):
    s %= L
    i = max(0, min(M - 1, next(k for k in range(M) if cum[k + 1] >= s)))
    return i


def normal(i):
    """outward unit normal at polyline index i (curve runs clockwise on screen)."""
    a, b = pts[(i - 3) % M], pts[(i + 3) % M]
    tx, ty = b[0] - a[0], b[1] - a[1]
    n = math.hypot(tx, ty) or 1.0
    return ty / n, -tx / n


board = pn.NewBoard(OUT)
board.SetCopperLayerCount(2)
NETCLASSES = [("Default", 0.15, 0.15, 0.6, 0.3, 2147483647), ("Power", 0.25, 0.15, 0.6, 0.3, 0)]
PATTERNS = [("/LED+", "Power"), ("/LED-", "Power")]
pcblib.apply_rules(board, NETCLASSES, PATTERNS, thickness=0.8)
net = pcblib.Nets(board)

# ---------------------------------------------------------------- outline
# Inflate the LED-centre heart by EDGE with KiCad's own polygon engine (round
# corners): robust at the top notch and gives a nicely rounded board.
hp = pn.SHAPE_POLY_SET()
hp.NewOutline()
for i in range(0, M, 10):
    hp.Append(mm(pts[i][0]), mm(pts[i][1]))
hp.Inflate(mm(EDGE), pn.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))
edge = pn.PCB_SHAPE(board)
edge.SetShape(pn.SHAPE_T_POLY)
edge.SetPolyShape(hp)
edge.SetLayer(pn.Edge_Cuts); edge.SetWidth(mm(0.1)); edge.SetFilled(False)
board.Add(edge)


def place(lib, name, ref, value, x, y, rot, bottom, pads):
    fp = pn.FootprintLoad(FPLIB + lib + ".pretty", name)
    fp.SetFPID(pn.LIB_ID(lib, name))
    fp.SetReference(ref); fp.SetValue(value); fp.SetPosition(V(x, y))
    board.Add(fp)
    if bottom:
        fp.Flip(V(x, y), pn.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    for p in fp.Pads():
        if p.GetNumber() in pads:
            p.SetNet(net(pads[p.GetNumber()]))
    return fp


# ---------------------------------------------------------------- LEDs + resistors
# Start at the top notch so index 0 and N/2 (bottom tip) sit on the centre line.
for k in range(N):
    i = at_len(k * L / N)
    x, y = pts[i]
    nx, ny = normal(i)
    ang = math.degrees(math.atan2(-ny, nx))           # pad axis along the normal
    a = "A%d" % (k + 1)
    # LED radial (pad axis along the normal): fits the tight lobes. Anode (pad 2)
    # faces INWARD toward the resistor arrays; cathode faces out and drops to the
    # back side, which is almost empty.
    place("LED_SMD", "LED_0603_1608Metric", "D%d" % (k + 1), "LED pink 0603",
          x, y, ang + 180, False, {"1": "LED-", "2": a})

# 4 x (4 x 0402) resistor arrays in the open middle of the heart, same (front)
# side as the LEDs -> single-sided assembly. Positions are found by a small
# search: grid candidates, both orientations, must not touch any LED courtyard,
# each other, or come within 0.4 mm of the board edge; closest to centre wins.
def courtyard(fp):
    c = pn.SHAPE_POLY_SET(fp.GetCourtyard(pn.F_Cu if not fp.IsFlipped() else pn.B_Cu))
    if c.OutlineCount() == 0:
        c = pn.SHAPE_POLY_SET(fp.GetCourtyard(pn.F_CrtYd))
    return c

blocked = [courtyard(fp) for fp in board.GetFootprints()]
inner = pn.SHAPE_POLY_SET(hp)
inner.Deflate(mm(EDGE + 0.4), pn.CORNER_STRATEGY_ROUND_ALL_CORNERS, mm(0.01))


def fits(fp):
    c = courtyard(fp)
    if not inner.Contains(fp.GetPosition()):
        return False
    bb = c.BBox()
    for corner in (bb.GetOrigin(), bb.GetEnd(),
                   pn.VECTOR2I(bb.GetLeft(), bb.GetBottom()), pn.VECTOR2I(bb.GetRight(), bb.GetTop())):
        if not inner.Contains(corner):
            return False
    for o in blocked:
        t = pn.SHAPE_POLY_SET(c)
        t.BooleanIntersection(o)
        if t.OutlineCount():
            return False
    return True


arrays = []
for k in range(4):
    pads = {}
    for i in range(4):
        led = 4 * k + i + 1
        if led <= N:
            pads[str(i + 1)] = "LED+"
            pads[str(8 - i)] = "A%d" % led
    arrays.append(place("Resistor_SMD", "R_Array_Convex_4x0402", "RN%d" % (k + 1), "330R x4",
                        CX, CY, 0, False, pads))

# every legal spot (vs LEDs + outline) on a 0.2 mm grid, both orientations
probe = arrays[0]
legal = []
for i in range(-25, 26):
    for j in range(-15, 30):
        for rot in (0, 90):
            x, y = CX + 0.2 * i, CY + 0.2 * j
            probe.SetPosition(V(x, y)); probe.SetOrientationDegrees(rot)
            if fits(probe):
                w, h = (2.09, 2.59) if rot == 0 else (2.59, 2.09)
                legal.append((x, y, rot, x - w / 2, y - h / 2, x + w / 2, y + h / 2))
legal.sort(key=lambda c: (c[0] - CX) ** 2 + (c[1] - CY - 1.0) ** 2)


def apart(a, b):
    return a[5] <= b[3] or b[5] <= a[3] or a[6] <= b[4] or b[6] <= a[4]


def search(chosen, start):
    if len(chosen) == 4:
        return chosen
    for n in range(start, len(legal)):
        c = legal[n]
        if all(apart(c, o) for o in chosen):
            r = search(chosen + [c], n + 1)
            if r:
                return r
    return None


sol = search([], 0)
if not sol:
    raise SystemExit("no room for 4 resistor arrays inside the heart (%d legal spots)" % len(legal))
# give each array the spot closest to its own LEDs (best of all 24 permutations)
import itertools
led_xy = {}
for fp in board.GetFootprints():
    if fp.GetReference().startswith("D"):
        led_xy[int(fp.GetReference()[1:])] = (pn.ToMM(fp.GetPosition().x), pn.ToMM(fp.GetPosition().y))
cent = []
for k in range(4):
    ls = [led_xy[l] for l in range(4 * k + 1, min(N, 4 * k + 4) + 1)]
    cent.append((sum(p[0] for p in ls) / len(ls), sum(p[1] for p in ls) / len(ls)))
best = min(itertools.permutations(sol),
           key=lambda perm: sum(math.hypot(c[0] - spot[0], c[1] - spot[1]) for c, spot in zip(cent, perm)))
for fp, (x, y, rot, *_r) in zip(arrays, best):
    fp.SetPosition(V(x, y)); fp.SetOrientationDegrees(rot)
    print("%s at (%+.1f, %+.1f) rot %d" % (fp.GetReference(), x - CX, y - CY, rot))

pcblib.wirepad(board, net, "HP1", "LED+", CX - 1.1, CY + 0.6, 1.0, "LED+")
pcblib.wirepad(board, net, "HP2", "LED-", CX + 1.1, CY + 0.6, 1.0, "LED-")

# ---------------------------------------------------------------- text
pcblib.refs_to_fab(board)
pcblib.silk(board, "+", CX - 1.1, CY + 1.85, 0.8)
pcblib.silk(board, "-", CX + 1.1, CY + 1.85, 0.8)

# ---------------------------------------------------------------- schematic sync + save
pcblib.sync_from_schematic(board, net, os.path.join(DIR, "heart-led.kicad_sch"))
pcblib.link_symbols(board, os.path.join(DIR, "sch_uuids.json"), "heart-led.kicad_sch")
board.BuildConnectivity()
pn.SaveBoard(OUT, board)
pcblib.write_project(OUT[:-len(".kicad_pcb")] + ".kicad_pro", NETCLASSES, PATTERNS)
bb = board.GetBoardEdgesBoundingBox()
print("saved %s  %.1f x %.1f mm" % (OUT, pn.ToMM(bb.GetWidth()), pn.ToMM(bb.GetHeight())))
