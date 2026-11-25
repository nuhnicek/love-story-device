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

BX, BY, BW, BH, CORNER = 98.0, 100.0, 25.0, 30.0, 1.5   # 2 mm extra on the left = routing channel
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
              ("RF", 0.35, 0.2, 0.6, 0.3, 2)]
# schematic local labels come through as "/NAME", global power nets without the slash
PATTERNS = [("VBAT", "Power"), ("GND", "Power"), ("VBUS", "Power"), ("*VDD_NRF", "NrfSupply"),
            ("*MOT_N", "Motor"), ("*LTE_ANT*", "RF")]
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
           "19": "SIM_1V8", "35": "LTE_ANT0", "62": "DRV", "45": "BTN", "44": "CHRG",
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
C("C11", "4.7uF", 110.9, 101.5, "+3V0", "GND", rot=180)
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
      BX + BW - 1.8, 125.0, 90, pads={"1": "BTN", "2": "GND"})   # actuator 0.24 mm proud of the edge

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
R("R1", "5.1k", 100.1, 120.7, "CC1", "GND")
R("R2", "5.1k", 105.2, 120.7, "CC2", "GND")
place("Package_TO_SOT_SMD:SOT-23-5", "U2", "TP4054", 115.3, 123.6, 0,
      pads={"1": "CHRG", "2": "GND", "3": "VBAT", "4": "VBUS", "5": "PROG"})
C("C1", "4.7uF", 115.3, 126.4, "VBUS", "GND")          # charger input, at U2
C("C2", "4.7uF", 118.2, 123.6, "VBAT", "GND", rot=90)  # charger output, at U2
R("R3", "4.7k", 116.0, 128.4, "PROG", "GND")
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


# same top-to-bottom order as the SiP pins they come from (no crossings)
DBG = [("TP8", "CK", "SWDCLK"), ("TP7", "IO", "SWDIO"), ("TP9", "RST", "nRESET_PAD"),
       ("TP12", "TX", "UART_TX"), ("TP13", "RX", "UART_RX"), ("TP10", "VT", "+3V0"),
       ("TP11", "GND", "GND")]
for i, (ref, val, n) in enumerate(DBG):
    wirepad(ref, val, 99.2, 101.8 + i * 1.8, 0.9, n)
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
    silk(val, 99.95, 101.8 + i * 1.8, 0.8, justify="right")
silk("BAT", 115.4, 126.6, 0.8)
silk("+", 114.0, 123.1, 0.9)
silk("-", 116.8, 123.1, 0.9)
silk("MOT", 120.3, 116.1, 0.8)
silk("HEART", 120.3, 121.5, 0.8)
silk("+", 117.8, 117.4, 0.8)
silk("+", 117.8, 120.2, 0.8)
silk("SIM", UX, 117.0, 0.8)
silk("TOUCH v3", 106.6, 129.0, 0.8)
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
c11 = pad_pos("C11", "1")            # 4.7 uF joins the 100 nF over the top of both caps
path([c11, pn.VECTOR2I(c11.x, mm(100.55)), pn.VECTOR2I(c10.x, mm(100.55)), c10], net_of("U1", "65"), w=0.2)
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
path([u3o, V(122.45, Y(u3o)), V(122.45, 101.6), V(121.6, 100.55), V(X(c10), 100.55)], G, w=0.2)  # cut the rounded corner

# UART TX: pin 11 -> lane between the R4 and C5 rows -> via into the TX wire pad
p11, tx = pad_pos("U1", "11"), pad_pos("TP12", "1")
TXN = net_of("U1", "11")
ylane = 108.4
path([p11, V(X(p11) - 0.75, Y(p11)), V(X(p11) - 1.1, ylane), V(X(tx), ylane), tx], TXN, w=0.15)
via(X(tx), Y(tx), TXN)

d0, c9 = pad_pos("U1", "24"), pad_pos("C9", "1")
path([d0, c9], net_of("U1", "24"), w=0.25)

pcblib.link_symbols(board, os.path.join(HW, "sch_uuids.json"), NAME + ".kicad_sch")
pcblib.save_custom_footprints(board, os.path.join(HW, "keychain.pretty"))
board.BuildConnectivity()
pn.SaveBoard(OUT, board)
pcblib.write_project(OUT[:-len(".kicad_pcb")] + ".kicad_pro", NETCLASSES, PATTERNS,
                     extra_rules={"min_hole_clearance": 0.05, "min_clearance": 0.1,
                                  "min_track_width": 0.09})
print("saved", OUT, "footprints:", len(board.GetFootprints()))
