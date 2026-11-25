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

BX, BY, BW, BH, CORNER = 100.0, 100.0, 23.0, 30.0, 1.5
UX, UY = 112.0, 108.5          # nRF9151 centre

board = pn.NewBoard(OUT)
board.SetCopperLayerCount(4)
board.SetLayerType(pn.In1_Cu, pn.LT_POWER)
board.SetLayerType(pn.In2_Cu, pn.LT_SIGNAL)     # routable, GND-poured after routing
net = pcblib.Nets(board)

NETCLASSES = [("Default", 0.15, 0.13, 0.6, 0.3, 2147483647),
              ("Power", 0.4, 0.15, 0.6, 0.3, 0),
              ("Motor", 0.3, 0.15, 0.6, 0.3, 1),
              ("RF", 0.35, 0.25, 0.6, 0.3, 2)]
PATTERNS = [("VBAT", "Power"), ("GND", "Power"), ("VBUS", "Power"), ("VDD_NRF", "Power"),
            ("MOT_N", "Motor"), ("LTE_ANT*", "RF")]
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
    fp = pn.FootprintLoad(FPLIB + lib + ".pretty", name)
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
           "19": "SIM_1V8", "35": "LTE_ANT0", "62": "DRV", "67": "BTN", "68": "CHRG",
           "70": "UART_TX", "72": "UART_RX"}
for g in ["1", "7", "13", "15", "20", "25", "30", "34", "36", "38", "39", "40", "41", "43", "46",
          "51", "55", "60", "66", "71", "76"] + [str(n) for n in range(105, 114)]:
    U1_NETS[g] = "GND"
place("Package_LGA:Nordic_nRF9151-LAxx_LGA-80-33EP_12.1x11.1mm_P0.5mm", "U1", "nRF9151-LACA",
      UX, UY, 0, pads=U1_NETS)

# --- left column: reset, enable, VDD decoupling, SIM ESD
R("R5", "1k", 102.7, 104.4, "nRESET_PAD", "nRESET")
C("C12", "100nF", 102.7, 106.0, "nRESET", "GND")
R("R4", "10k", 102.7, 107.6, "VDD_NRF", "ENABLE")
C("C5", "10uF", 102.7, 109.2, "VDD_NRF", "GND")
C("C6", "1uF", 102.7, 110.8, "VDD_NRF", "GND")
place("Package_SON:USON-10_2.5x1.0mm_P0.5mm", "U4", "TPD4E05U06DQA", 102.9, 113.3, 180,
      pads={"5": "SIM_RST", "4": "SIM_IO", "2": "SIM_CLK", "1": "SIM_1V8", "3": "GND", "8": "GND"})
C("C13", "100nF", 101.1, 113.3, "SIM_1V8", "GND", rot=90)

# --- top band: VDD_GPIO decoupling, gate resistor
C("C10", "100nF", 110.9, 101.5, "+3V0", "GND")
C("C11", "4.7uF", 114.0, 101.5, "+3V0", "GND")
R("R7", "100R", 117.4, 101.5, "DRV", "GATE")

# --- right column: motor driver, LDO, button
R("R8", "100k", 120.8, 101.5, "GATE", "GND")
place("Package_TO_SOT_SMD:SOT-23", "Q1", "AO3400A", 120.6, 104.6, 90,
      pads={"1": "GATE", "2": "GND", "3": "MOT_N"})
place("Diode_SMD:D_SOD-123", "D1", "1N4148W", 120.6, 109.4, 90, pads={"1": "VBAT", "2": "MOT_N"})
place("Package_TO_SOT_SMD:SOT-23-3", "U3", "XC6206P302MR", 120.6, 114.2, 90,
      pads={"1": "GND", "2": "+3V0", "3": "VBAT"})
C("C8", "1uF", 120.6, 117.4, "+3V0", "GND")
C("C7", "1uF", 120.6, 119.0, "VBAT", "GND")
place("Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010", "SW1", "Side tact",
      BX + BW - 2.1, 125.0, 270, pads={"1": "BTN", "2": "GND"})

# --- RF: ANT -> R6 0R (C14/C15 DNP shunts) -> U.FL
ANT_X = UX + 2.25               # U1 pad 35, straight down to the U.FL
R("R6", "0R", ANT_X, 115.4, "LTE_ANT0", "LTE_ANT", rot=270, fp=R04)
C("C14", "DNP", ANT_X - 1.45, 114.89, "LTE_ANT0", "GND", rot=180, fp=C04)
C("C15", "DNP", ANT_X + 1.45, 115.91, "LTE_ANT", "GND", rot=0, fp=C04)
for ref in ("C14", "C15"):                 # antenna tuning, not fitted by default
    board.FindFootprintByReference(ref).SetDNP(True)
place("Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", "J2", "U.FL", ANT_X, 119.1, 270,
      pads={"1": "LTE_ANT", "2": "GND"})

# --- DEC0
C("C9", "4.7uF", 107.25, 116.0, "DEC0", "GND", rot=90)

# --- power band: ferrite, VBAT caps, charger, CC resistors
place("Inductor_SMD:L_0805_2012Metric", "FB1", "22R@100MHz 6A", 102.1, 115.65, 0,
      pads={"1": "VBAT", "2": "VDD_NRF"})
C("C3", "10uF", 101.9, 117.5, "VBAT", "GND")
C("C4", "1uF", 101.9, 119.1, "VBAT", "GND")
R("R1", "5.1k", 101.9, 120.7, "CC1", "GND")
R("R2", "5.1k", 105.2, 120.7, "CC2", "GND")
R("R3", "4.7k", 105.2, 118.2, "PROG", "GND", rot=90)
place("Package_TO_SOT_SMD:SOT-23-5", "U2", "TP4054", 108.6, 119.7, 90,
      pads={"1": "CHRG", "2": "GND", "3": "VBAT", "4": "VBUS", "5": "PROG"})
C("C2", "4.7uF", 117.6, 117.6, "VBAT", "GND", rot=90)
C("C1", "4.7uF", 117.6, 120.8, "VBUS", "GND", rot=90)
place("Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal", "J1", "USB-C 6P",
      106.6, BY + BH - 3.4, 0,
      pads={"A9": "VBUS", "B9": "VBUS", "A12": "GND", "B12": "GND", "A5": "CC1", "B5": "CC2",
            "SH": "GND"})

# --- bottom: nano-SIM holder + wire pads
place("Connector_Card:nanoSIM_GCT_SIM8060-6-0-14-00", "J3", "nano-SIM hinged", UX, 108.4, 0,
      bottom=True, pads={"1": "SIM_1V8", "2": "SIM_RST", "3": "SIM_CLK", "5": "GND",
                         "7": "SIM_IO", "SH": "GND"})


def wirepad(ref, val, x, y, size, n):
    return pcblib.wirepad(board, net, ref, val, x, y, size, n)


DBG = [("TP7", "IO", "SWDIO"), ("TP8", "CK", "SWDCLK"), ("TP9", "RST", "nRESET_PAD"),
       ("TP10", "VT", "+3V0"), ("TP11", "GND", "GND"), ("TP12", "TX", "UART_TX"),
       ("TP13", "RX", "UART_RX")]
for i, (ref, val, n) in enumerate(DBG):
    wirepad(ref, val, 101.0, 101.8 + i * 1.8, 0.9, n)
wirepad("TP1", "BAT+", 114.0, 124.6, 1.5, "VBAT")
wirepad("TP2", "BAT-", 116.8, 124.6, 1.5, "GND")
wirepad("TP3", "MOT+", 119.0, 117.4, 1.0, "VBAT")
wirepad("TP4", "MOT-", 121.6, 117.4, 1.0, "MOT_N")
wirepad("TP5", "HEART+", 119.0, 120.2, 1.0, "VBAT")
wirepad("TP6", "HEART-", 121.6, 120.2, 1.0, "MOT_N")

if "--place-only" in sys.argv:
    pn.SaveBoard(OUT, board)
    sys.exit(0)

# ---------------------------------------------------------------- silkscreen
pcblib.refs_to_fab(board)


def silk(text, x, y, size=0.8, layer=pn.B_SilkS, justify=None, angle=0):
    return pcblib.silk(board, text, x, y, size, layer, angle=angle, justify=justify)


for i, (ref, val, n) in enumerate(DBG):
    silk(val, 101.75, 101.8 + i * 1.8, 0.8, justify="right")
silk("BAT", 115.4, 126.6, 0.8)
silk("+", 114.0, 123.1, 0.9)
silk("-", 116.8, 123.1, 0.9)
silk("MOT", 120.3, 116.1, 0.8)
silk("HEART", 120.3, 121.5, 0.8)
silk("+", 117.8, 117.4, 0.8)
silk("+", 117.8, 120.2, 0.8)
silk("SIM", UX, 117.0, 0.8)
silk("TOUCH v3", 116.0, 128.6, 0.8, pn.F_SilkS)
silk("ANT", ANT_X, 121.9, 0.8, pn.F_SilkS)

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
path([ant, r6a], A0)
path([pn.VECTOR2I(r6a.x, c14.y), c14], A0)
path([r6b, ufl], A1)
path([pn.VECTOR2I(r6b.x, c15.y), c15], A1)

# DRV: 2 mm from U1 pad 62 up to R7 (fixed, so the GND fan-out leaves it room)
drv, r7 = pad_pos("U1", "62"), pad_pos("R7", "1")
DRVN = board.FindFootprintByReference("R7").FindPadByNumber("1").GetNet()
path([drv, pn.VECTOR2I(drv.x, r7.y + mm(0.6)), pn.VECTOR2I(r7.x, r7.y + mm(0.2)), r7], DRVN, w=0.15)

pcblib.link_symbols(board, os.path.join(HW, "sch_uuids.json"), NAME + ".kicad_sch")
pcblib.save_custom_footprints(board, os.path.join(HW, "keychain.pretty"))
board.BuildConnectivity()
pn.SaveBoard(OUT, board)
pcblib.write_project(OUT[:-len(".kicad_pcb")] + ".kicad_pro", NETCLASSES, PATTERNS,
                     extra_rules={"min_hole_clearance": 0.05, "min_clearance": 0.1,
                                  "min_track_width": 0.09})
print("saved", OUT, "footprints:", len(board.GetFootprints()))
