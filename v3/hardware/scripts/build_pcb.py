"""
keychain v3 PCB: nRF9151 SiP + TP4054 charger + nano-SIM + U.FL, 4-layer 1.0 mm.
Run with KiCad's bundled Python:
  $KPY v3/hardware/scripts/build_pcb.py

Assembly concept (hand assembly, no SMT service):
  TOP    every SMD part (stencil + solder paste + hot plate / hot air): SiP, USB-C,
         U.FL, charger, LDO, MOSFET, ESD, 0603 passives (RF trio 0402)
  BOTTOM the hinged nano-SIM holder (pads on its outer edge -> soldering iron after
         the top is done) and wire pads: battery, motor, heart, SWD, UART
Stack-up: JLC04101H-7628 (1.0 mm). L1 signals + RF, L2 solid GND, L3 signals + GND pour, L4 signals.
"""
import os
import sys

import pcbnew as pn

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(HW))
sys.path.insert(0, os.path.join(ROOT, "hardware", "scripts"))
import pcblib  # noqa: E402
from pcblib import mm, V  # noqa: E402

NAME = "keychain-v3"
OUT = os.path.join(HW, NAME + ".kicad_pcb")
FPLIB = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"

BX, BY, BW, BH, CORNER = 95.5, 84.0, 30.0, 50.0, 1.5   # 30 x 50 mm; heart area y 84-102, electronics below
UX, UY = 112.0, 108.5          # nRF9151 centre

board = pn.NewBoard(OUT)
board.SetCopperLayerCount(4)
board.SetLayerType(pn.In1_Cu, pn.LT_POWER)
board.SetLayerType(pn.In2_Cu, pn.LT_SIGNAL)     # routable, GND-poured after routing
net = pcblib.Nets(board)

NETCLASSES = [("Default", 0.15, 0.13, 0.6, 0.3, 2147483647),
              ("Power", 0.4, 0.15, 0.6, 0.3, 0),
              ("Motor", 0.3, 0.15, 0.6, 0.3, 1),
              ("NrfSupply", 0.3, 0.15, 0.6, 0.3, 1),       # fits the SiP's 0.5 mm pitch
              ("USBData", 0.2, 0.15, 0.6, 0.3, 1),         # full-speed USB, short pair
              ("RF", 0.35, 0.2, 0.6, 0.3, 2)]
# schematic local labels come through as "/NAME", global power nets without the slash
PATTERNS = [("VBAT", "Power"), ("GND", "Power"), ("VBUS", "Power"), ("*VDD_NRF", "NrfSupply"),
            ("*MOT_N", "Motor"), ("*LTE_ANT*", "RF"), ("*USB_D?", "USBData"), ("*VLED", "Power")]
pcblib.apply_rules(board, NETCLASSES, PATTERNS, thickness=1.0)
ds = board.GetDesignSettings()
ds.m_HoleClearance = mm(0.05)       # real 0.2 mm rule in the .kicad_dru (SW1 bosses)
ds.m_MinClearance = mm(0.1)
ds.m_TrackMinWidth = mm(0.09)

# ---------------------------------------------------------------- outline
def edge(shape, **kw):
    s = pn.PCB_SHAPE(board)
    s.SetShape(shape)
    for k, v in kw.items():
        getattr(s, k)(*v) if isinstance(v, tuple) else getattr(s, k)(v)
    s.SetLayer(pn.Edge_Cuts); s.SetWidth(mm(0.1))
    board.Add(s)


r = CORNER
x1, y1, x2, y2 = BX, BY, BX + BW, BY + BH
for a, b in (((x1 + r, y1), (x2 - r, y1)), ((x2, y1 + r), (x2, y2 - r)),
             ((x2 - r, y2), (x1 + r, y2)), ((x1, y2 - r), (x1, y1 + r))):
    s = pn.PCB_SHAPE(board); s.SetShape(pn.SHAPE_T_SEGMENT)
    s.SetStart(V(*a)); s.SetEnd(V(*b)); s.SetLayer(pn.Edge_Cuts); s.SetWidth(mm(0.1))
    board.Add(s)
for c, st in (((x2 - r, y1 + r), (x2 - r, y1)), ((x2 - r, y2 - r), (x2, y2 - r)),
              ((x1 + r, y2 - r), (x1 + r, y2)), ((x1 + r, y1 + r), (x1, y1 + r))):
    s = pn.PCB_SHAPE(board); s.SetShape(pn.SHAPE_T_ARC)
    s.SetCenter(V(*c)); s.SetStart(V(*st))
    s.SetArcAngleAndEnd(pn.EDA_ANGLE(90, pn.DEGREES_T), True)
    s.SetLayer(pn.Edge_Cuts); s.SetWidth(mm(0.1))
    board.Add(s)


# ---------------------------------------------------------------- parts
def place(fpid, ref, val, x, y, rot=0, bottom=False, pads=None):
    lib, name = fpid.split(":")
    fp = pn.FootprintLoad(os.path.join(HW, "keychain.pretty") if lib == "keychain" else FPLIB + lib + ".pretty", name)
    if fp is None:
        sys.exit("footprint not found: " + fpid)
    fp.SetFPID(pn.LIB_ID(lib, name))
    fp.SetReference(ref); fp.SetValue(val)
    fp.SetPosition(V(x, y))
    board.Add(fp)
    if bottom:
        fp.Flip(V(x, y), pn.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    for p in fp.Pads():
        n = (pads or {}).get(p.GetNumber())
        if n:
            p.SetNet(net(n))
    return fp


R06, C06 = "Resistor_SMD:R_0603_1608Metric", "Capacitor_SMD:C_0603_1608Metric"
R04, C04 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric"


def R(ref, val, x, y, a, b, rot=0, fp=R06):
    return place(fp, ref, val, x, y, rot, pads={"1": a, "2": b})


def C(ref, val, x, y, a, b, rot=0, fp=C06):
    return place(fp, ref, val, x, y, rot, pads={"1": a, "2": b})


# --- nRF9151
U1_NETS = {"14": "VDD_NRF", "10": "ENABLE", "24": "DEC0", "65": "+3V0", "3": "SWDCLK",
           "4": "SWDIO", "9": "nRESET", "16": "SIM_RST", "17": "SIM_IO", "18": "SIM_CLK",
           "19": "SIM_1V8", "35": "LTE_ANT0", "62": "DRV", "49": "BTN", "50": "USB_DET", "63": "LED_DATA3V", "80": "LED_EN",
           "11": "UART_TX", "12": "UART_RX"}
for g in ["1", "7", "13", "15", "20", "25", "30", "34", "36", "38", "39", "40", "41", "43", "46",
          "51", "55", "60", "66", "71", "76"] + [str(n) for n in range(105, 114)]:
    U1_NETS[g] = "GND"
place("Package_LGA:Nordic_nRF9151-LAxx_LGA-80-33EP_12.1x11.1mm_P0.5mm", "U1", "nRF9151-LACA",
      UX, UY, 0, pads=U1_NETS)

# --- left column: reset, enable, VDD decoupling, SIM ESD
R("R5", "1k", 100.9, 104.4, "nRESET_PAD", "nRESET")
C("C12", "100nF", 100.9, 106.0, "nRESET", "GND", rot=180)     # signal pad towards U1
R("R4", "10k", 100.9, 107.6, "VDD_NRF", "ENABLE")
C("C5", "10uF", 100.9, 109.2, "VDD_NRF", "GND", rot=180)      # VDD pads towards U1 pin 14
C("C6", "1uF", 100.9, 110.8, "VDD_NRF", "GND", rot=180)
place("Package_SON:USON-10_2.5x1.0mm_P0.5mm", "U4", "TPD4E05U06DQA", 110.65, 118.2, 0,   # at the SIM contacts
      pads={"1": "SIM_RST", "2": "SIM_CLK", "4": "SIM_IO", "5": "SIM_1V8", "3": "GND", "8": "GND"})
place(C06, "C13", "100nF", 107.2, 117.4, 180, bottom=True, pads={"1": "SIM_1V8", "2": "GND"})

# --- top band: VDD_GPIO decoupling, gate resistor
C("C10", "100nF", 114.0, 101.5, "+3V0", "GND", rot=180)      # +3V0 pad right above pin 65
C("C11", "4.7uF", 124.1, 104.5, "+3V0", "GND", rot=90)     # beside the +3V0 lane (the heart tip sits above the SiP now)
R("R7", "100R", 117.2, 101.5, "DRV", "GATE")

# --- right column: motor driver, LDO, button
R("R8", "100k", 120.25, 101.5, "GATE", "GND")
place("Package_TO_SOT_SMD:SOT-23", "Q1", "AO3400A", 120.6, 104.6, 90,
      pads={"1": "GATE", "2": "GND", "3": "MOT_N"})
place("Diode_SMD:D_SOD-123", "D1", "1N4148W", 120.6, 109.4, 90, pads={"1": "VBAT", "2": "MOT_N"})
place("Package_TO_SOT_SMD:SOT-23-3", "U3", "XC6206P302MR", 120.6, 114.2, 90,
      pads={"1": "GND", "2": "+3V0", "3": "VBAT"})
C("C8", "1uF", 120.6, 117.4, "+3V0", "GND")
C("C7", "1uF", 120.6, 119.0, "VBAT", "GND")
place("Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010", "SW1", "Side tact",
      BX + BW - 1.8, 129.0, 90, pads={"1": "BTN", "2": "GND"})   # actuator 0.24 mm proud of the edge

# --- RF: ANT -> R6 0R (C14/C15 DNP shunts) -> U.FL
ANT_X = UX + 2.25               # U1 pad 35, straight down to the U.FL
R("R6", "0R", ANT_X, 115.4, "LTE_ANT0", "LTE_ANT", rot=270, fp=R04)
C("C14", "DNP", ANT_X - 1.45, 114.89, "LTE_ANT0", "GND", rot=180, fp=C04)
C("C15", "DNP", ANT_X + 1.45, 115.91, "LTE_ANT", "GND", rot=0, fp=C04)
for ref in ("C14", "C15"):                 # antenna tuning, not fitted by default
    fp = board.FindFootprintByReference(ref)
    fp.SetDNP(True)
    fp.SetFPID(pn.LIB_ID("keychain", "C_0402_NoPaste"))   # own copy without stencil apertures
    for p in fp.Pads():                    # -> no stray solder blobs on the empty pads
        ls = p.GetLayerSet(); ls.RemoveLayer(pn.F_Paste); p.SetLayerSet(ls)
place("Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", "J2", "U.FL", ANT_X, 119.1, 270,
      pads={"1": "LTE_ANT", "2": "GND"})

# --- DEC0
C("C9", "4.7uF", UX - 3.25, 116.0, "DEC0", "GND", rot=270)  # right below pin 24

# --- power band: ferrite, VBAT caps, charger, CC resistors
place("Inductor_SMD:L_0805_2012Metric", "FB1", "22R@100MHz 6A", 100.4, 115.65, 0,
      pads={"1": "VBAT", "2": "VDD_NRF"})
C("C3", "10uF", 100.1, 117.5, "VBAT", "GND")
C("C4", "1uF", 100.1, 119.1, "VBAT", "GND")
place("Package_TO_SOT_SMD:SOT-23-5", "U2", "TP4054", 103.6, 123.3, 0,    # next to the USB-C VBUS pins
      pads={"2": "GND", "3": "VBAT", "4": "VBUS", "5": "PROG"})
C("C1", "4.7uF", 107.4, 123.4, "VBUS", "GND", rot=90)  # charger input, at U2
C("C2", "4.7uF", 100.0, 123.3, "VBAT", "GND", rot=90)  # charger output, at U2
R("R3", "4.7k", 100.0, 125.55, "PROG", "GND", fp=R04)
place("Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", "J1", "USB-C 16P",
      106.6, BY + BH - 3.1, 0,       # footprint's "PCB Edge" line is 3.1 mm in front of its origin
      pads={"A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS", "A1": "GND", "A12": "GND",
            "B1": "GND", "B12": "GND", "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP",
            "A7": "USB_DM", "B7": "USB_DM", "SH": "GND"})

# --- USB-serial (CP2102N) + auto-reset: bottom right, between the U.FL and the button.
# Rotated so D+/D- face down (to the USB-C), UART/DTR/RTS face left, VBUS/RST face right.
place("Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", "U5", "CP2102N-A02-GQFN24", 115.2, 123.8, 90,
      pads={"3": "USB_DP", "4": "USB_DM", "5": "V3U", "6": "V3U", "7": "VBUS", "8": "USB_VSNS",
            "9": "CP_RST", "2": "GND", "25": "GND", "19": "CP_RTS", "20": "CP_RXD", "21": "CP_TXD",
            "23": "CP_DTR"})
place("Package_TO_SOT_SMD:SOT-23", "Q2", "DTC114E", 110.4, 123.3, 180,     # pins 1/2 face U5: E-RTS top, B-DTR bottom
      pads={"1": "CP_DTR", "2": "CP_RTS", "3": "nRESET"})
# right of U5, in pin order: RST pull-up, VBUS-sense divider, VREGIN cap; USB_DET divider
R("R11", "10k", 119.4, 122.9, "V3U", "CP_RST", fp=R04)
R("R10", "47.5k", 119.4, 124.0, "USB_VSNS", "GND", fp=R04)
R("R9", "22.1k", 119.4, 125.1, "VBUS", "USB_VSNS", fp=R04)
C("C16", "1uF", 119.4, 121.8, "VBUS", "GND", rot=180, fp=C04)   # GND pad towards U5 (open pour)
R("R15", "100k", 121.6, 122.9, "VBUS", "USB_DET", fp=R04)
R("R16", "100k", 121.6, 124.0, "USB_DET", "GND", fp=R04)
# below U5: its 3.3 V regulator caps (VDD/VIO pins are at its bottom right)
C("C17", "1uF", 117.0, 127.2, "V3U", "GND", fp=C04)
C("C18", "100nF", 117.0, 128.3, "V3U", "GND", fp=C04)
# UART series resistors (anywhere on the line): above the charger
R("R12", "4.7k", 105.4, 121.0, "UART_TX", "CP_RXD", fp=R04)
R("R13", "4.7k", 107.4, 121.0, "CP_TXD", "UART_RX", fp=R04)
# USB-C CC pull-downs right above the CC pins
R("R1", "5.1k", 104.6, 125.55, "CC1", "GND", rot=180, fp=R04)
R("R2", "5.1k", 107.7, 125.55, "CC2", "GND", rot=180, fp=R04)

# --- RGB heart: 20 x Wurth WL-ICLED 2020 on a heart curve, each turned along the curve,
# equal spacing (chord) so neighbours never get closer than ~3.3 mm; drivers sit inside
import json  # noqa: E402
import math  # noqa: E402

HEART_N, HEART_CX, HEART_TOP, HEART_W, HEART_H = 18, 110.5, 86.0, 26.0, 14.0
HEART_P, HEART_PHASE = 2.0, 0.5      # lobe shape exponent, where LED 1 sits (found by search:
#                                       the arrangement with the most room between LEDs)


def heart_curve(n=6000):
    """Heart curve scaled into HEART_W x HEART_H (x = 16 sin^p t, classic y)."""
    f = lambda t: (16 * abs(math.sin(t)) ** HEART_P * math.copysign(1, math.sin(t)),
                   -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)))
    raw = [f(2 * math.pi * i / n) for i in range(n + 1)]
    xs, ys = [q[0] for q in raw], [q[1] for q in raw]
    xw, y0, y1 = max(xs) - min(xs), min(ys), max(ys)
    return [(HEART_CX + x * HEART_W / xw, HEART_TOP + (y - y0) * HEART_H / (y1 - y0)) for x, y in raw]


def heart_points(n=HEART_N):
    """n points at equal arc length; LEDs stay upright (0/90 deg: neighbours never touch corners)."""
    pts = heart_curve()
    per = [0.0]
    for a_, b_ in zip(pts, pts[1:]):
        per.append(per[-1] + math.dist(a_, b_))
    out, k = [], 0
    for j in range(n):
        while per[k] < (j + HEART_PHASE) / n * per[-1]:
            k += 1
        a_, b_ = pts[max(k - 15, 0)], pts[min(k + 15, len(pts) - 1)]
        ang = math.degrees(math.atan2(b_[1] - a_[1], b_[0] - a_[0]))
        # +180: the footprint's data runs DIN (pad 3) -> DOUT (pad 1) towards -x, so DOUT faces the next LED
        out.append((pts[k][0], pts[k][1], (180 - round(ang / 90) * 90) % 360))   # KiCad angles turn the other way
    return out, per[-1] / n


HEART, HEART_PITCH = heart_points()
HC = (HEART_CX, HEART_TOP + 0.42 * HEART_H)          # roughly the middle of the heart
for i, (x, y, ang) in enumerate(HEART):
    nxt = "LED_D%d" % (i + 1) if i < HEART_N - 1 else None
    pads = {"4": "VLED", "2": "GND", "3": "LED_D%d" % i}
    if nxt:
        pads["1"] = nxt
    place("keychain:LED_WL-ICLED_2020", "D%d" % (3 + i), "WL-ICLED 2020", x, y, ang, pads=pads)

# heart outline for route.py: VLED plane on layer 3 + no autorouting on layer 3 inside it
def _hull(P):
    P = sorted(set(P))
    def half(seq):
        h = []
        for q in seq:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (q[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (q[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(q)
        return h
    lo, up = half(P), half(P[::-1])
    return lo[:-1] + up[:-1]


_e = (BX + 0.3, BY + 0.3, BX + BW - 0.3, BY + BH - 0.3)
_outline = [(round(min(max(x_, _e[0]), _e[2]), 3), round(min(max(y_, _e[1]), _e[3]), 3)) for x_, y_ in
            _hull([(x_ + 2.4 * math.cos(k * math.pi / 12), y_ + 2.4 * math.sin(k * math.pi / 12))
                   for x_, y_, _ in HEART for k in range(24)])]
json.dump({"outline": _outline}, open(os.path.join(HW, "heart_outline.json"), "w"))

# drivers inside the heart: load switch (left), level shifter (right), next to their pins
U6X, U6Y, U7X, U7Y = 105.0, 92.3, 116.0, 92.3
place("Package_TO_SOT_SMD:SOT-23-6", "U6", "TPS22917DBV", U6X, U6Y, 0,
      pads={"1": "VBAT", "2": "GND", "3": "LED_EN", "6": "VLED"})
C("C19", "1uF", U6X - 3.1, U6Y - 0.95, "VBAT", "GND", fp=C04, rot=180)   # VBAT pad towards pin 1
R("R17", "100k", U6X + 1.5, U6Y + 2.7, "LED_EN", "GND", fp=R04)
C("C20", "10uF", U6X + 3.9, U6Y - 0.95, "VLED", "GND")                  # right at U6's output pin
place("Package_TO_SOT_SMD:SOT-23-5", "U7", "SN74LV1T34DBV", U7X, U7Y, 0,
      pads={"2": "LED_DATA3V", "3": "GND", "4": "LED_DIN", "5": "VLED"})
C("C21", "100nF", U7X + 3.3, U7Y - 0.95, "VLED", "GND", fp=C04)
R("R18", "330R", U7X - 0.8, U7Y + 2.8, "LED_DIN", "LED_D0", fp=R04, rot=180)

# each LED's 100 nF: first free spot (courtyard check) inside, beside, then outside the LED
def crtyd(fp):
    """Courtyard bounding box from the footprint's courtyard graphics (works for rotated parts)."""
    L = pn.B_CrtYd if fp.IsFlipped() else pn.F_CrtYd
    bb = None
    for it in fp.GraphicalItems():
        if it.GetLayer() == L:
            b_ = it.GetBoundingBox()
            if bb is None:
                bb = b_
            else:
                bb.Merge(b_)
    return bb if bb is not None else fp.GetBoundingBox(False)


def crt_poly(fp):
    L = pn.B_CrtYd if fp.IsFlipped() else pn.F_CrtYd
    fp.BuildCourtyardCaches()
    return fp.GetCourtyard(L)


def in_outline(x_, y_, margin=1.3):
    """(mm) inside the heart's VLED plane outline, margin mm away from its edge"""
    ins = False
    P = _outline
    for (x1, y1), (x2, y2) in zip(P, P[1:] + P[:1]):
        if (y1 > y_) != (y2 > y_) and x_ < x1 + (y_ - y1) * (x2 - x1) / (y2 - y1):
            ins = not ins
    if not ins:
        return False
    for (x1, y1), (x2, y2) in zip(P, P[1:] + P[:1]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0, min(1, ((x_ - x1) * dx + (y_ - y1) * dy) / (dx * dx + dy * dy or 1)))
        if math.dist((x_, y_), (x1 + t * dx, y1 + t * dy)) < margin:
            return False
    return True


def collides(fp):
    """True if fp's courtyard polygon touches another courtyard on its side, or is near the edge."""
    if fp.GetReference() in LEDCAPS and not in_outline(pn.ToMM(fp.GetPosition().x), pn.ToMM(fp.GetPosition().y)):
        return True
    pa, bb = crt_poly(fp), crtyd(fp)
    for o in board.GetFootprints():
        if o.GetReference() == fp.GetReference() or o.IsFlipped() != fp.IsFlipped():
            continue
        if not bb.Intersects(crtyd(o)):
            continue
        pb = crt_poly(o)
        if pa.Collide(pb.Outline(0)) if pb.OutlineCount() else True:
            return True
    e = board.GetBoardEdgesBoundingBox()
    return not (bb.GetLeft() > e.GetLeft() + mm(0.3) and bb.GetRight() < e.GetRight() - mm(0.3)
                and bb.GetTop() > e.GetTop() + mm(0.3) and bb.GetBottom() < e.GetBottom() - mm(0.3))


NOCAP = []
LEDCAPS = {"C%d" % (22 + i) for i in range(HEART_N)}
for i, (x, y, _a) in enumerate(HEART):
    d = math.dist((x, y), HC)
    ux, uy = (HC[0] - x) / d, (HC[1] - y) / d          # towards the inside
    vx, vy = -uy, ux                                  # along the curve
    r2 = math.sqrt(0.5)
    dirs = [(ux, uy), ((ux + vx) * r2, (uy + vy) * r2), ((ux - vx) * r2, (uy - vy) * r2),
            (vx, vy), (-vx, -vy), (-ux, -uy)]
    cands = [(dx, dy, k) for k in (2.0, 2.3, 2.6, 2.9, 3.2, 3.5, 3.8, 4.2, 4.6, 5.0) for dx, dy in dirs]
    fp = C("C%d" % (22 + i), "100nF", x, y, "VLED", "GND", fp=C04)
    for dx, dy, k in cands:          # move one footprint around (removing + re-adding breaks SWIG)
        fp.SetOrientationDegrees(90 if abs(dx) > abs(dy) else 0)
        fp.SetPosition(V(x + dx * k, y + dy * k))
        if not collides(fp):
            break
    else:                            # crowded spot: nearest free place inside the heart (VLED plane)
        grid = [(HEART_CX + gx * 0.5, HEART_TOP + gy * 0.5) for gx in range(-24, 25) for gy in range(2, 26)]
        grid.sort(key=lambda q: math.dist(q, (x, y)))
        for gx, gy in grid:
            fp.SetOrientationDegrees(0)
            fp.SetPosition(V(gx, gy))
            if not collides(fp):
                break
        else:
            NOCAP.append("D%d" % (3 + i))
# --- bottom: nano-SIM holder + wire pads
place("Connector_Card:nanoSIM_GCT_SIM8060-6-0-14-00", "J3", "nano-SIM hinged", UX, 108.4, 0,
      bottom=True, pads={"1": "SIM_1V8", "2": "SIM_RST", "3": "SIM_CLK", "5": "GND",
                         "7": "SIM_IO", "SH": "GND"})


def wirepad(ref, val, x, y, size, n):
    return pcblib.wirepad(board, net, ref, val, x, y, size, n)


# same top-to-bottom order as the SiP pins they come from (no crossings)
DBG = [("TP8", "CK", "SWDCLK"), ("TP7", "IO", "SWDIO"), ("TP9", "RST", "nRESET_PAD"),
       ("TP10", "VT", "+3V0"), ("TP11", "GND", "GND")]          # UART log now via USB-C
for i, (ref, val, n) in enumerate(DBG):
    wirepad(ref, val, 99.2, 101.8 + i * 1.8, 0.9, n)
wirepad("TP1", "BAT+", 114.0, 128.6, 1.5, "VBAT")
wirepad("TP2", "BAT-", 116.8, 128.6, 1.5, "GND")
wirepad("TP3", "MOT+", 119.0, 117.4, 1.0, "VBAT")
wirepad("TP4", "MOT-", 121.6, 117.4, 1.0, "MOT_N")

# test pads (bottom, 0.9 mm) for checking a freshly soldered board: see v3/TESTING.md
# (ref, label, net, x, y, label dx, label dy)
TESTPADS = [("TP12", "VLED", "VLED", 96.6, 101.0, 0.75, -1.2), ("TP13", "GND", "GND", 96.6, 104.3, 0.15, 1.2),
            ("TP14", "GATE", "GATE", 124.4, 101.0, -0.75, 1.2), ("TP15", "LED", "LED_DIN", 124.4, 107.3, -0.15, 1.2),
            ("TP16", "BTN", "BTN", 121.7, 110.0, 0, 1.25),
            ("TP17", "VDD", "VDD_NRF", 99.3, 112.8, 0.2, 1.2), ("TP18", "SIM", "SIM_1V8", 99.3, 115.4, 0.2, 1.2),
            ("TP19", "PRG", "PROG", 99.4, 131.8, 0.2, -1.25),
            ("TP20", "5V", "VBUS", 104.6, 132.7, 0, -1.25), ("TP21", "V3U", "V3U", 119.0, 132.5, 0, -1.25),
            ("TP22", "DET", "USB_DET", 121.9, 124.9, -2.0, 0), ("TP23", "GND", "GND", 113.2, 132.9, 0, -1.25)]
for ref, lab, n, x, y, dx, dy in TESTPADS:
    wirepad(ref, lab, x, y, 0.9, n)

print("LEDs without a cap spot:", NOCAP)
if "--place-only" in sys.argv:
    pn.SaveBoard(OUT, board)
    sys.exit(0)

# ---------------------------------------------------------------- silkscreen
pcblib.refs_to_fab(board)


def silk(text, x, y, size=0.8, layer=pn.B_SilkS, justify=None, angle=0):
    return pcblib.silk(board, text, x, y, size, layer, angle=angle, justify=justify)


for i, (ref, val, n) in enumerate(DBG):
    silk(val, 99.95, 101.8 + i * 1.8, 0.8, justify="right")
silk("BAT", 115.4, 130.6, 0.8)
silk("+", 114.0, 127.1, 0.9)
silk("-", 116.8, 127.1, 0.9)
silk("MOT", 120.3, 116.1, 0.8)
silk("+", 117.8, 117.4, 0.8)
silk("SIM", UX, 117.0, 0.8)
silk("TOUCH v3", HEART_CX, HC[1] + 1.0, 0.8)
for ref, lab, n, x, y, dx, dy in TESTPADS:
    silk(lab, x + dx, y + dy, 0.8)
silk("ANT", ANT_X + 3.5, 119.6, 0.8, pn.F_SilkS)

# ---------------------------------------------------------------- schematic sync + project
pcblib.sync_from_schematic(board, net, os.path.join(HW, NAME + ".kicad_sch"),
                           allow_dropped=())
# ---------------------------------------------------------------- RF tracks (fixed)
def pad_pos(ref, num):
    fp = board.FindFootprintByReference(ref)
    for p in fp.Pads():
        if p.GetNumber() == num:
            return p.GetPosition()
    sys.exit("pad %s.%s" % (ref, num))


def track(a, b, n, w=0.35, layer=pn.F_Cu):
    t = pn.PCB_TRACK(board)
    t.SetStart(a); t.SetEnd(b); t.SetWidth(mm(w)); t.SetLayer(layer)
    t.SetNet(n); t.SetLocked(True)
    board.Add(t)


def path(pts, n, w=0.35):
    for a, b in zip(pts, pts[1:]):
        track(a, b, n, w)


ant, r6a, r6b = pad_pos("U1", "35"), pad_pos("R6", "1"), pad_pos("R6", "2")
c14, c15, ufl = pad_pos("C14", "1"), pad_pos("C15", "1"), pad_pos("J2", "1")
A0 = board.FindFootprintByReference("R6").FindPadByNumber("1").GetNet()
A1 = board.FindFootprintByReference("R6").FindPadByNumber("2").GetNet()
neck = pn.VECTOR2I(ant.x, ant.y + mm(0.4))
track(ant, neck, A0, w=0.25)
path([neck, r6a], A0)
path([pn.VECTOR2I(r6a.x, c14.y), c14], A0)
path([r6b, ufl], A1)
path([pn.VECTOR2I(r6b.x, c15.y), c15], A1)

# DRV: 2 mm from U1 pad 62 up to R7 (fixed, so the GND fan-out leaves it room)
drv, r7 = pad_pos("U1", "62"), pad_pos("R7", "1")
DRVN = board.FindFootprintByReference("R7").FindPadByNumber("1").GetNet()
path([drv, pn.VECTOR2I(drv.x, r7.y + mm(0.6)), pn.VECTOR2I(r7.x, r7.y + mm(0.2)), r7], DRVN, w=0.15)


def net_of(ref, num):
    return board.FindFootprintByReference(ref).FindPadByNumber(num).GetNet()


# short fixed supply connections at the SiP (decoupling right at the pins)
vdd, c5, c6 = pad_pos("U1", "14"), pad_pos("C5", "1"), pad_pos("C6", "1")
path([vdd, pn.VECTOR2I(c6.x, vdd.y)], net_of("U1", "14"), w=0.3)
path([c5, c6], net_of("U1", "14"), w=0.3)
g65, c10 = pad_pos("U1", "65"), pad_pos("C10", "1")
path([g65, pn.VECTOR2I(g65.x, c10.y + mm(0.7)), pn.VECTOR2I(c10.x, c10.y + mm(0.3)), c10], net_of("U1", "65"), w=0.2)
c11 = pad_pos("C11", "1")            # 4.7 uF: short stub onto the +3V0 lane along the right side
path([c11, pn.VECTOR2I(mm(122.45), c11.y)], net_of("U1", "65"), w=0.2)
def via(x, y, n):
    v = pn.PCB_VIA(board)
    v.SetPosition(V(x, y)); v.SetWidth(mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(n); v.SetLocked(True)
    board.Add(v)


def bpath(pts, n, w=0.15):
    for a_, b_ in zip(pts, pts[1:]):
        track(V(*a_), V(*b_), n, w, layer=pn.B_Cu)


# U4 (ESD, top) -> SIM contacts (bottom): pin -> via -> bottom run -> contact.
# Runs are stacked so they never cross: RST nearest the contacts, then CLK, IO, VCC.
u4 = {n: pad_pos("U4", n) for n in ("1", "2", "4", "5")}
j3 = {n: pad_pos("J3", n) for n in ("1", "2", "3", "7")}
X = lambda p: pn.ToMM(p.x)
Y = lambda p: pn.ToMM(p.y)
RSTN, CLKN, ION, VCCN = (net_of("U4", n) for n in ("1", "2", "4", "5"))
xp = X(u4["1"])                                   # pad column centre
# RST: straight up to a via, bottom run to contact 2
via(xp, Y(u4["1"]) - 0.75, RSTN)
path([u4["1"], V(xp, Y(u4["1"]) - 0.75)], RSTN, w=0.15)
bpath([(xp, Y(u4["1"]) - 0.75), (X(j3["2"]), Y(u4["1"]) - 0.75), (X(j3["2"]), Y(j3["2"]))], RSTN)
# CLK / IO: via left of the pad, bottom run below RST to contacts 3 / 7
for pin, cont, n, dy in (("2", "3", CLKN, 0.25), ("4", "7", ION, 0.3)):
    vx, vy = xp - 0.815, Y(u4[pin]) + dy
    via(vx, vy, n)
    path([u4[pin], V(vx, vy)], n, w=0.15)
    bpath([(vx, vy), (X(j3[cont]), vy), (X(j3[cont]), Y(j3[cont]))], n)
# VCC (SIM_1V8): via below pin 5, bottom run left and up to contact 1, C13 on the way
vy = Y(u4["5"]) + 0.75
via(xp, vy, VCCN)
path([u4["5"], V(xp, vy)], VCCN, w=0.15)
c13 = pad_pos("C13", "1")
bpath([(xp, vy), (108.9, vy), (108.9, Y(j3["1"]))], VCCN)
bpath([(108.9, Y(c13)), (X(c13), Y(c13))], VCCN)

# SIM_1V8 from the SiP: pin 19 -> via (left of the SiP corner) -> bottom run into the VCC line
p19 = pad_pos("U1", "19")
via(104.9, 113.35, VCCN)
path([p19, V(105.5, Y(p19)), V(104.9, 113.35)], VCCN, w=0.15)
bpath([(104.9, 113.35), (104.9, 116.2), (108.9, 116.2)], VCCN)

# +3V0 from the LDO (right column) to the VDD_GPIO caps: along the right and top edge
u3o = pad_pos("U3", "2")
G = net_of("U1", "65")
path([u3o, V(122.45, Y(u3o)), V(122.45, 101.6), V(121.6, 100.55), V(X(c10), 100.55), c10], G, w=0.2)  # cut the rounded corner

# ENABLE pull-up: R4's VDD pad (outer side) joins the C5/C6 VDD line through the gap
# between the C5 and C6 ground pads
r4v = pad_pos("R4", "1")
path([r4v, V(99.4, Y(r4v)), V(99.4, 110.0), V(X(pad_pos("C5", "1")), 110.0)], net_of("U1", "14"), w=0.2)

# BTN: SiP pin 49 (P0.30) -> via clear of the SIM holder's shield pad -> bottom layer
# down the right side -> via in SW1's pad
b49, sw = pad_pos("U1", "49"), pad_pos("SW1", "1")
BTNN = net_of("U1", "49")
for p in board.FindFootprintByReference("SW1").Pads():
    if p.GetNumber() == "1" and pn.ToMM(p.GetPosition().y) < pn.ToMM(sw.y) + 0.01:
        sw = p.GetPosition()
path([b49, V(118.45, Y(b49))], BTNN, w=0.15)
via(118.45, Y(b49), BTNN)
bpath([(118.45, Y(b49)), (119.2, Y(b49) + 0.75), (119.2, 116.0), (118.0, 116.0), (118.0, Y(sw)), (X(sw), Y(sw))], BTNN)
via(X(sw), Y(sw), BTNN)

# USB D+/D-: CP2102N -> via -> inner layer 3 -> tie vias under the USB-C body -> both
# contact rows (A6/B6 = D+, A7/B7 = D-), so the pair never crosses anything on top
def ipath(pts, n, w=0.2):
    for a_, b_ in zip(pts, pts[1:]):
        track(V(*a_), V(*b_), n, w, layer=pn.In2_Cu)


DP, DM = net_of("U5", "3"), net_of("U5", "4")
udp, udm = pad_pos("U5", "3"), pad_pos("U5", "4")
path([udp, V(X(udp), Y(udp) + 0.55), V(114.7, 126.9)], DP, w=0.2)
via(114.7, 126.9, DP)
path([udm, V(X(udm), 127.0), V(115.3, 127.75)], DM, w=0.2)
via(115.3, 127.75, DM)
ipath([(114.7, 126.9), (112.3, 129.3), (106.1, 129.3)], DP)
ipath([(115.3, 127.75), (113.05, 130.0), (105.3, 130.0)], DM)
for x_, y_, n_ in ((106.1, 129.3, DP), (107.6, 129.3, DP), (105.3, 130.0, DM), (106.85, 130.0, DM)):
    via(x_, y_, n_)
a6, b6, a7, b7 = (pad_pos("J1", k) for k in ("A6", "B6", "A7", "B7"))
path([a6, V(106.1, 129.3)], DP, w=0.2)
path([b6, V(107.6, 129.3)], DP, w=0.2)
path([b7, V(X(b7), 128.4), V(105.3, 128.95), V(105.3, 130.0)], DM, w=0.2)
path([a7, V(106.85, 130.0)], DM, w=0.2)


# VLED: load switch output straight to its 10 uF
u6o, c20 = pad_pos("U6", "6"), pad_pos("C20", "1")
path([u6o, c20], net_of("U6", "6"), w=0.3)

# SIM_CLK: SiP pin 18 -> via left of the SiP (above the SIM-VCC via) -> inner layer 3
# -> the CLK via next to U4
p18 = pad_pos("U1", "18")
CLKN = net_of("U1", "18")
path([p18, V(104.85, Y(p18)), V(104.6, Y(p18) + 0.25)], CLKN, w=0.15)
via(104.6, Y(p18) + 0.25, CLKN)
ipath([(104.6, Y(p18) + 0.25), (105.9, Y(p18) + 0.25), (109.45, Y(p18) + 3.8), (109.45, 117.95)], CLKN, w=0.15)

# SIM_IO: SiP pin 17 -> via further left -> inner layer 3, parallel to CLK -> IO via at U4
p17 = pad_pos("U1", "17")
ION_ = net_of("U1", "17")
path([p17, V(103.6, Y(p17))], ION_, w=0.15)
via(103.6, Y(p17), ION_)
ipath([(103.6, Y(p17)), (103.6, 114.0), (108.6, 119.0), (109.45, 119.0)], ION_, w=0.15)

# SIM_RST: SiP pin 16 -> via just left of the SiP (between the VDD and SIM_IO tracks)
# -> inner layer 3, innermost of the three SIM runs -> the RST via at U4
p16 = pad_pos("U1", "16")
RSTN_ = net_of("U1", "16")
path([p16, V(105.3, Y(p16)), V(104.3, 111.0)], RSTN_, w=0.15)
via(104.3, 111.0, RSTN_)                 # clear of the SIM holder's shield pad underneath
xr = X(pad_pos("U4", "1"))
ipath([(104.3, 111.0), (105.4, 111.0), (xr, 111.0 + xr - 105.4), (xr, Y(pad_pos("U4", "1")) - 0.75)], RSTN_, w=0.15)

# nRESET from the auto-reset transistor: via next to Q2, bottom layer up the free left
# side, via next to SiP pin 9 (the short top-side links are left to the router)
q2c, p9 = pad_pos("Q2", "3"), pad_pos("U1", "9")
NRN = net_of("U1", "9")
path([q2c, V(108.5, Y(q2c))], NRN, w=0.15)
via(108.5, Y(q2c), NRN)
bpath([(108.5, Y(q2c)), (103.8, Y(q2c)), (102.3, Y(q2c) - 1.5), (102.3, 108.1), (103.2, 107.2), (104.6, 107.2)], NRN)
via(104.6, 107.2, NRN)
path([V(104.6, 107.2), V(105.2, Y(p9)), p9], NRN, w=0.15)

# VBAT to the LED load switch: down the free lane along the left board edge to FB1
u6i, fb1 = pad_pos("U6", "1"), pad_pos("FB1", "1")
path([V(98.75, 100.4), V(98.75, Y(fb1) - 0.6), fb1], net_of("U6", "1"), w=0.3)
# LED data from the level shifter output (pin 4) down to R18 below U7
_u74, _r18 = pad_pos("U7", "4"), pad_pos("R18", "1")
path([_u74, V(X(_u74) - 0.75, Y(_u74) + 1.05), _r18], net_of("U7", "4"), w=0.15)

def via_spot(pad_ref, pad_num, toward=None, r_list=(0.9, 1.1, 1.3)):
    """First collision-free via position around a pad (all copper, holes, edge)."""
    pc = pad_pos(pad_ref, pad_num)
    own = board.FindFootprintByReference(pad_ref).FindPadByNumber(pad_num).GetNetCode()
    e = board.GetBoardEdgesBoundingBox()
    pref = math.atan2(toward[1] - pc.y, toward[0] - pc.x) if toward else 0.0
    angs = sorted((2 * math.pi * k / 24 for k in range(24)),
                  key=lambda a: abs((a - pref + math.pi) % (2 * math.pi) - math.pi))
    for r in r_list:
        for a_ in angs:
            x_, y_ = pc.x + mm(r) * math.cos(a_), pc.y + mm(r) * math.sin(a_)
            if not (e.GetLeft() + mm(0.6) < x_ < e.GetRight() - mm(0.6) and e.GetTop() + mm(0.6) < y_ < e.GetBottom() - mm(0.6)):
                continue
            c_ = pn.SHAPE_CIRCLE(pn.VECTOR2I(int(x_), int(y_)), mm(0.3))
            ok = True
            for f_ in board.GetFootprints():
                for q in f_.Pads():
                    if q.GetNetCode() == own and own:
                        continue
                    for L in (pn.F_Cu, pn.B_Cu):
                        if q.IsOnLayer(L) and q.GetEffectiveShape(L).Collide(c_, mm(0.15)):
                            ok = False
                    if q.GetDrillSize().x and math.hypot(q.GetPosition().x - x_, q.GetPosition().y - y_) < q.GetDrillSize().x / 2 + mm(0.55):
                        ok = False
            for t_ in board.GetTracks():
                if t_.GetNetCode() != own and t_.GetEffectiveShape(t_.GetLayer() if t_.GetClass() != "PCB_VIA" else pn.F_Cu).Collide(c_, mm(0.15)):
                    ok = False
            if ok:
                return x_, y_
    sys.exit("no via spot next to %s.%s" % (pad_ref, pad_num))


# LED data: SiP pin 63 runs up between the fixed DRV (62) and VDD_GPIO (65) tracks,
# drops to inner layer 3 and comes up next to U7's input
p63, u7a = pad_pos("U1", "63"), pad_pos("U7", "2")
LDN = net_of("U1", "63")
path([p63, V(X(p63), 102.75), V(115.55, 102.3)], LDN, w=0.15)
via(115.55, 102.3, LDN)
_v = via_spot("U7", "2", toward=(mm(115.55), mm(102.3)))
ipath([(115.55, 102.3), (pn.ToMM(int(_v[0])), pn.ToMM(int(_v[1])))], LDN, w=0.15)
via(pn.ToMM(int(_v[0])), pn.ToMM(int(_v[1])), LDN)
path([pn.VECTOR2I(int(_v[0]), int(_v[1])), u7a], LDN, w=0.15)

# ENABLE: pin 10 straight left to R4's ENABLE pad (between the nRESET and VDD tracks)
p10, r4e = pad_pos("U1", "10"), pad_pos("R4", "2")
path([p10, V(102.4, Y(p10)), r4e], net_of("U1", "10"), w=0.15)
# charger output: C2 (VBAT pad) joins the battery line along the left edge lane to FB1
c2v = pad_pos("C2", "1")
path([fb1, V(98.75, Y(fb1) + 0.6), V(98.75, Y(c2v)), c2v], net_of("C2", "1"), w=0.3)
# battery pad (bottom) <- left-edge battery lane: via at the lane's end, bottom run along y 125
VB = net_of("C2", "1")
bat = pad_pos("TP1", "1")
path([V(98.75, Y(c2v)), V(98.75, 125.0)], VB, w=0.3)
via(98.75, 125.0, VB)
bpath([(98.75, 125.0), (X(bat), 125.0), (X(bat), Y(bat))], VB, w=0.4)
# USB_DET: SiP pin 50 -> via (between the SIM holder's shield pads underneath)
# -> inner layer 3 down the right edge -> via next to the R15/R16 divider
p50, r15d = pad_pos("U1", "50"), pad_pos("R15", "2")
UDN = net_of("U1", "50")
path([p50, V(118.0, Y(p50)), V(118.45, Y(p50) - 0.5)], UDN, w=0.15)
via(118.45, Y(p50) - 0.5, UDN)
ipath([(118.45, Y(p50) - 0.5), (122.2, Y(p50) + 3.25), (122.2, 121.9)], UDN, w=0.15)
via(122.2, 121.9, UDN)
path([V(122.2, 121.9), r15d], UDN, w=0.15)
# battery line (left/bottom) -> regulator & motor side (right) on inner layer 3
via(112.0, 125.0, VB)                    # on the bottom battery run
via(118.9, 119.9, VB)                    # next to C7 (LDO input)
ipath([(112.0, 125.0), (118.9, 119.9)], VB, w=0.3)
path([V(118.9, 119.9), pad_pos("C7", "1")], VB, w=0.3)

# auto-reset handshake: Q2 E/B straight across to U5 RTS/DTR
path([pad_pos("Q2", "2"), pad_pos("U5", "19")], net_of("Q2", "2"), w=0.15)
path([pad_pos("Q2", "1"), pad_pos("U5", "23")], net_of("Q2", "1"), w=0.15)
# UART between the series resistors and the CP2102N, past Q2 on inner layer 3 (the autorouter
# found this once and missed it later, so it is fixed now): RXD dives next to R12 and comes up
# between Q2's pins, TXD dives next to R13 and comes up right at the CP2102N pin
_RX, _TX = net_of("U5", "20"), net_of("U5", "21")
path([V(105.91, 121.0), V(105.91, 122.19)], _RX, w=0.15)
via(105.91, 122.19, _RX)
ipath([(105.91, 122.19), (106.03, 122.32), (110.04, 122.32), (110.16, 122.2)], _RX, w=0.15)
via(110.16, 122.2, _RX)
path([V(110.16, 122.2), V(110.38, 122.42), V(110.38, 122.84)], _RX, w=0.15)
path([V(110.38, 122.84), V(110.53, 122.99)], _RX, w=0.112)
path([V(110.53, 122.99), V(113.21, 122.99), pad_pos("U5", "20")], _RX, w=0.15)
path([pad_pos("R13", "1"), V(106.89, 121.42)], _TX, w=0.112)
path([V(106.89, 121.42), V(106.53, 121.77)], _TX, w=0.112)
via(106.53, 121.77, _TX)
ipath([(106.53, 121.77), (106.44, 121.68), (105.65, 121.68), (105.35, 121.98), (105.35, 122.38),
       (105.71, 122.74), (111.6, 122.74), (112.41, 123.55)], _TX, w=0.15)
via(112.41, 123.55, _TX)
path([V(112.41, 123.55), pad_pos("U5", "21")], _TX, w=0.15)
# VBUS to the USB-detect divider: from C16 over the top of the resistor column
# (keeps the pour between the columns open for the GND pads)
c16v, r15v = pad_pos("C16", "1"), pad_pos("R15", "1")
VBN = net_of("R15", "1")
path([c16v, V(X(c16v), Y(c16v) - 0.65), V(X(r15v), Y(c16v) - 0.65), r15v], VBN, w=0.2)
# ...and C16's VBUS joins R9 / U5 VREGIN through the bottom side
r9v = pad_pos("R9", "1")
w1 = via_spot("C16", "1", toward=(r9v.x, r9v.y))
w2 = via_spot("R9", "1", toward=(c16v.x, c16v.y))
for ww, pp in ((w1, c16v), (w2, r9v)):
    via(pn.ToMM(int(ww[0])), pn.ToMM(int(ww[1])), VBN)
    track(pp, pn.VECTOR2I(int(ww[0]), int(ww[1])), VBN, 0.2)
bpath([(pn.ToMM(int(w1[0])), pn.ToMM(int(w1[1]))), (pn.ToMM(int(w2[0])), pn.ToMM(int(w2[1])))], VBN, w=0.2)

# CP2102N exposed pad -> its GND pin 2 (which gets a via), so the pad is never an island
u5g = pad_pos("U5", "2")
path([V(X(u5g), Y(u5g) - 0.85), u5g], net_of("U5", "2"), w=0.25)   # straight down out of the pad

d0, c9 = pad_pos("U1", "24"), pad_pos("C9", "1")
path([d0, c9], net_of("U1", "24"), w=0.25)

# test pads: each gets a fixed link = short top stub from a nearby pad of its net -> via
# -> straight bottom track to the test pad, collision-checked against all copper, so the
# autorouter never has to fit them in
def seg_clear(a, b, layer, code, w=0.2, clr=0.2):
    sh = pn.SHAPE_SEGMENT(a, b, mm(w))
    for f_ in board.GetFootprints():              # footprint keep-outs (no tracks on this layer)
        for z in f_.Zones():
            if z.GetIsRuleArea() and z.GetDoNotAllowTracks() and z.IsOnLayer(layer) \
                    and z.Outline().Collide(sh, mm(0.1)):
                return False
    for f_ in board.GetFootprints():
        for q in f_.Pads():
            if q.GetNetCode() == code and code:
                continue
            if q.IsOnLayer(layer) and q.GetEffectiveShape(layer).Collide(sh, mm(clr)):
                return False
            if q.GetDrillSize().x and q.GetEffectiveHoleShape().Collide(sh, mm(clr + 0.1)):
                return False
    for t_ in board.GetTracks():
        if t_.GetNetCode() == code:
            continue
        if (t_.GetClass() == "PCB_VIA" or t_.GetLayer() == layer) and \
                t_.GetEffectiveShape(layer if t_.GetClass() == "PCB_VIA" else t_.GetLayer()).Collide(sh, mm(clr)):
            return False
    return True


NOVIA = [z for f_ in board.GetFootprints() for z in f_.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]


def via_free(x_, y_, code):
    c_ = pn.SHAPE_CIRCLE(pn.VECTOR2I(int(x_), int(y_)), mm(0.3))
    for z in NOVIA:
        if z.Outline().Collide(pn.VECTOR2I(int(x_), int(y_)), mm(0.45)):
            return False
    e = board.GetBoardEdgesBoundingBox()
    if not (e.GetLeft() + mm(0.6) < x_ < e.GetRight() - mm(0.6) and e.GetTop() + mm(0.6) < y_ < e.GetBottom() - mm(0.6)):
        return False
    for f_ in board.GetFootprints():
        for q in f_.Pads():
            if q.GetNetCode() == code and code:
                continue
            for L in (pn.F_Cu, pn.B_Cu):
                if q.IsOnLayer(L) and q.GetEffectiveShape(L).Collide(c_, mm(0.2)):
                    return False
            if q.GetDrillSize().x and math.hypot(q.GetPosition().x - x_, q.GetPosition().y - y_) < q.GetDrillSize().x / 2 + mm(0.6):
                return False
    for t_ in board.GetTracks():
        if t_.GetNetCode() == code:
            continue
        L = pn.F_Cu if t_.GetClass() == "PCB_VIA" else t_.GetLayer()
        if t_.GetEffectiveShape(L).Collide(c_, mm(0.2)):
            return False
    return True


def connect_testpad(tp):
    tpad = board.FindFootprintByReference(tp).FindPadByNumber("1")
    code, tpos = tpad.GetNetCode(), tpad.GetPosition()
    srcs = [q for f_ in board.GetFootprints() if not f_.IsFlipped() for q in f_.Pads()
            if q.GetNetCode() == code and q.IsOnLayer(pn.F_Cu)]
    srcs.sort(key=lambda q: math.hypot(q.GetPosition().x - tpos.x, q.GetPosition().y - tpos.y))
    # direct: a bottom track of the same net is already close by
    for t_ in list(board.GetTracks()):
        if t_.GetClass() == "PCB_VIA" or t_.GetLayer() != pn.B_Cu or t_.GetNetCode() != code:
            continue
        a_, b_ = t_.GetStart(), t_.GetEnd()
        dx_, dy_ = b_.x - a_.x, b_.y - a_.y
        L2 = dx_ * dx_ + dy_ * dy_ or 1
        k_ = max(0.0, min(1.0, ((tpos.x - a_.x) * dx_ + (tpos.y - a_.y) * dy_) / L2))
        pp = pn.VECTOR2I(int(a_.x + k_ * dx_), int(a_.y + k_ * dy_))
        if math.hypot(pp.x - tpos.x, pp.y - tpos.y) < mm(4) and seg_clear(tpos, pp, pn.B_Cu, code):
            track(tpos, pp, tpad.GetNet(), 0.2, layer=pn.B_Cu)
            return True
    for v_ in list(board.GetTracks()):            # ...or a via of the same net
        if v_.GetClass() == "PCB_VIA" and v_.GetNetCode() == code:
            vp_ = v_.GetPosition()
            if math.hypot(vp_.x - tpos.x, vp_.y - tpos.y) < mm(6) and seg_clear(tpos, vp_, pn.B_Cu, code):
                track(tpos, vp_, tpad.GetNet(), 0.2, layer=pn.B_Cu)
                return True
    for q in srcs[:8]:
        pc = q.GetPosition()
        pref = math.atan2(tpos.y - pc.y, tpos.x - pc.x)
        angs = sorted((2 * math.pi * k / 24 for k in range(24)),
                      key=lambda a: abs((a - pref + math.pi) % (2 * math.pi) - math.pi))
        for r_ in (0.9, 1.1, 1.3, 1.6, 2.0):
            for a_ in angs:
                vx_, vy_ = pc.x + mm(r_) * math.cos(a_), pc.y + mm(r_) * math.sin(a_)
                vp = pn.VECTOR2I(int(vx_), int(vy_))
                if via_free(vx_, vy_, code) and seg_clear(pc, vp, pn.F_Cu, code) \
                        and seg_clear(vp, tpos, pn.B_Cu, code):
                    n_ = tpad.GetNet()
                    track(pc, vp, n_, 0.2)
                    via(pn.ToMM(vp.x), pn.ToMM(vp.y), n_)
                    track(vp, tpos, n_, 0.2, layer=pn.B_Cu)
                    return True
    # second try: top stub -> via -> inner layer 3 -> via next to the test pad -> bottom stub
    def spots(pc, toward, rs=(0.9, 1.1, 1.3, 1.6, 2.0)):
        pref = math.atan2(toward.y - pc.y, toward.x - pc.x)
        angs = sorted((2 * math.pi * k / 24 for k in range(24)),
                      key=lambda a: abs((a - pref + math.pi) % (2 * math.pi) - math.pi))
        for r_ in rs:
            for a_ in angs:
                yield pn.VECTOR2I(int(pc.x + mm(r_) * math.cos(a_)), int(pc.y + mm(r_) * math.sin(a_)))
    ends = [v2 for v2 in spots(tpos, tpos, (1.0, 1.3, 1.6, 2.0))
            if via_free(v2.x, v2.y, code) and seg_clear(v2, tpos, pn.B_Cu, code)]
    for q in srcs[:8]:
        pc = q.GetPosition()
        for v1 in spots(pc, tpos):
            if not (via_free(v1.x, v1.y, code) and seg_clear(pc, v1, pn.F_Cu, code)):
                continue
            for v2 in ends:
                if math.hypot(v1.x - v2.x, v1.y - v2.y) > mm(0.9) and seg_clear(v1, v2, pn.In2_Cu, code):
                    n_ = tpad.GetNet()
                    track(pc, v1, n_, 0.2)
                    via(pn.ToMM(v1.x), pn.ToMM(v1.y), n_)
                    track(v1, v2, n_, 0.2, layer=pn.In2_Cu)
                    via(pn.ToMM(v2.x), pn.ToMM(v2.y), n_)
                    track(v2, tpos, n_, 0.2, layer=pn.B_Cu)
                    return True
    return False


# into the heart on layer 3: VBAT from the left-edge lane to U6, LED_EN to U6 from a via
# outside the heart that the autorouter connects to the SiP
def hop(ref, num, outside, w=0.2, out_track_from=None):
    pin = pad_pos(ref, num)
    n_ = net_of(ref, num)
    vi = via_spot(ref, num, toward=(mm(outside[0]), mm(outside[1])))
    via(pn.ToMM(int(vi[0])), pn.ToMM(int(vi[1])), n_)
    track(pin, pn.VECTOR2I(int(vi[0]), int(vi[1])), n_, w)
    via(outside[0], outside[1], n_)
    ipath([(pn.ToMM(int(vi[0])), pn.ToMM(int(vi[1]))), outside], n_, w=w)
    if out_track_from:
        path([V(*out_track_from), V(*outside)], n_, w=w)


def spots(pc, toward, rs=(0.9, 1.1, 1.3, 1.6, 2.0)):
    pref = math.atan2(toward.y - pc.y, toward.x - pc.x)
    angs = sorted((2 * math.pi * k / 24 for k in range(24)),
                  key=lambda a: abs((a - pref + math.pi) % (2 * math.pi) - math.pi))
    for r_ in rs:
        for a_ in angs:
            yield pn.VECTOR2I(int(pc.x + mm(r_) * math.cos(a_)), int(pc.y + mm(r_) * math.sin(a_)))


LINKFAIL = []


def link(ref_a, num_a, ref_b, num_b, layers=(pn.B_Cu, pn.In2_Cu), w=0.15):
    """pad -> via -> straight run on the first layer that is free -> via -> pad, all collision-checked."""
    pa, pb = pad_pos(ref_a, num_a), pad_pos(ref_b, num_b)
    code, n_ = net_of(ref_a, num_a).GetNetCode(), net_of(ref_a, num_a)
    if seg_clear(pa, pb, pn.F_Cu, code, w=w):          # neighbours facing each other: straight on top
        track(pa, pb, n_, w)
        return True
    for mid in (pn.VECTOR2I(pa.x, pb.y), pn.VECTOR2I(pb.x, pa.y)):     # or one bend on top
        if seg_clear(pa, mid, pn.F_Cu, code, w=w) and seg_clear(mid, pb, pn.F_Cu, code, w=w):
            track(pa, mid, n_, w); track(mid, pb, n_, w)
            return True
    va = [v for v in spots(pa, pb) if via_free(v.x, v.y, code) and seg_clear(pa, v, pn.F_Cu, code)]
    vb = [v for v in spots(pb, pa) if via_free(v.x, v.y, code) and seg_clear(pb, v, pn.F_Cu, code)]
    va, vb = va[:10], vb[:10]
    for L in layers:
        for v1 in va:
            for v2 in vb:
                if math.hypot(v1.x - v2.x, v1.y - v2.y) > mm(0.95) and seg_clear(v1, v2, L, code, w=w):
                    track(pa, v1, n_, w); track(pb, v2, n_, w)
                    via(pn.ToMM(v1.x), pn.ToMM(v1.y), n_); via(pn.ToMM(v2.x), pn.ToMM(v2.y), n_)
                    track(v1, v2, n_, w, layer=L)
                    return True
    LINKFAIL.append("%s.%s->%s.%s (via spots %d/%d)" % (ref_a, num_a, ref_b, num_b, len(va), len(vb)))
    return False


hop("U6", "1", (98.75, 100.4), w=0.3)
# LED_EN: U6 pin 3 -> layer 3 -> via just above SiP pin 80 (outside the no-via zone under the SiP)
_p80 = pad_pos("U1", "80")
_code = net_of("U1", "80").GetNetCode()
for _v in spots(_p80, V(U6X, U6Y), rs=(1.0, 1.3, 1.6, 2.0)):
    if pn.ToMM(_v.y) < 103.3 and via_free(_v.x, _v.y, _code) and seg_clear(_p80, _v, pn.F_Cu, _code):
        hop("U6", "3", (pn.ToMM(_v.x), pn.ToMM(_v.y)))
        track(_p80, _v, net_of("U1", "80"), 0.15)
        break
else:
    sys.exit("no via spot for LED_EN at SiP pin 80")

# first LED's data (R18 -> D3), inside the heart: bottom side if free, else layer 3
link("R18", "2", "D3", "3")
# LED data chain: every DOUT -> next DIN through the bottom side under the heart
for k in range(1, HEART_N):
    link("D%d" % (2 + k), "1", "D%d" % (3 + k), "3")


print("links that found no free path:", LINKFAIL or "none")
failed = [tp[0] for tp in TESTPADS if tp[2] != "GND" and not connect_testpad(tp[0])]
if not connect_testpad("TP10"):
    failed.append("TP10")
print("test pads without a fixed link (left to the router):", failed or "none")

pcblib.link_symbols(board, os.path.join(HW, "sch_uuids.json"), NAME + ".kicad_sch")
pcblib.save_custom_footprints(board, os.path.join(HW, "keychain.pretty"))
board.BuildConnectivity()
pn.SaveBoard(OUT, board)
pcblib.write_project(OUT[:-len(".kicad_pcb")] + ".kicad_pro", NETCLASSES, PATTERNS,
                     extra_rules={"min_hole_clearance": 0.05, "min_clearance": 0.1,
                                  "min_track_width": 0.09})
print("saved", OUT, "footprints:", len(board.GetFootprints()))
