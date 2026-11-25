"""
Generate the GSM touch-keychain carrier PCB (KiCad 10, pcbnew API).

Run with KiCad's bundled Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 \
      hardware/scripts/build_pcb.py

Concept: a 2-layer, 0.8 mm board with the SAME outline as the red SIM800L
mini module (25.2 x 23 mm). The module sits on TOP and is soldered through its
own 12 header holes with short pins. All electronics are on the BOTTOM side,
facing the LiPo pouch cell. The separate TP4056 board is replaced by an
on-board USB-C (power-only) + MCP73831 charger.

Board coordinates are top view in mm. Module pin 1 (NET) is at (X0, Y0).
"""
import os
import sys
import pcbnew as pn

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
OUT = os.path.join(HW, "keychain-carrier.kicad_pcb")
FPLIB = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/"

# ---------------------------------------------------------------- parameters
# SIM800L red mini geometry. Taken from a community footprint
# (github.com/shridattdudhat/SIM800L-Core-Module-KiCad-Footprint).
# MEASURE YOUR MODULE WITH CALIPERS BEFORE ORDERING.
BX, BY = 100.0, 100.0          # board top-left
BW, BH = 25.2, 23.0            # board size == module size
X0, Y0 = BX + 1.8, BY + 5.0    # module pin 1 (NET)
ROW_DX = 21.87                 # left row -> right row
PITCH = 2.54
RIGHT_ROW_DY = PITCH           # right row starts one pitch lower
MOD_DRILL, MOD_PAD = 0.9, 1.7
CORNER_R = 1.0

def mm(v):
    return pn.FromMM(v)

def V(x, y):
    return pn.VECTOR2I(mm(x), mm(y))

board = pn.NewBoard(OUT)
board.SetCopperLayerCount(2)
ds = board.GetDesignSettings()
ds.SetBoardThickness(mm(0.8))

# JLCPCB-friendly 2-layer rules
ds.m_TrackMinWidth = mm(0.127)
ds.m_MinClearance = mm(0.127)
ds.m_ViasMinSize = mm(0.5)
ds.m_MinThroughDrill = mm(0.3)
ds.m_HoleToHoleMin = mm(0.25)
ds.m_CopperEdgeClearance = mm(0.25)
ds.m_HoleClearance = mm(0.05)   # real 0.25 mm rule lives in keychain-carrier.kicad_dru

ns = ds.m_NetSettings
default_nc = ns.GetDefaultNetclass()
default_nc.SetTrackWidth(mm(0.2))
default_nc.SetClearance(mm(0.15))
default_nc.SetViaDiameter(mm(0.6))
default_nc.SetViaDrill(mm(0.3))
power_nc = pn.NETCLASS("Power")
power_nc.SetTrackWidth(mm(0.6))
power_nc.SetClearance(mm(0.2))
power_nc.SetViaDiameter(mm(0.7))
power_nc.SetViaDrill(mm(0.35))
ns.SetNetclass("Power", power_nc)
POWER_NETS = ["VBAT", "GND", "VBUS"]
for n in POWER_NETS:
    ns.SetNetclassPatternAssignment(n, "Power")
motor_nc = pn.NETCLASS("Motor")
motor_nc.SetTrackWidth(mm(0.3))
motor_nc.SetClearance(mm(0.15))
motor_nc.SetViaDiameter(mm(0.6))
motor_nc.SetViaDrill(mm(0.3))
ns.SetNetclass("Motor", motor_nc)
ns.SetNetclassPatternAssignment("/MOT_N", "Motor")

# ---------------------------------------------------------------- nets
NETS = {}

def net(name):
    if name not in NETS:
        ni = pn.NETINFO_ITEM(board, name)
        board.Add(ni)
        NETS[name] = ni
    return NETS[name]

# ---------------------------------------------------------------- outline
def edge_line(a, b):
    s = pn.PCB_SHAPE(board)
    s.SetShape(pn.SHAPE_T_SEGMENT)
    s.SetStart(V(*a)); s.SetEnd(V(*b))
    s.SetLayer(pn.Edge_Cuts); s.SetWidth(mm(0.1))
    board.Add(s)

def edge_arc(center, start, angle):
    s = pn.PCB_SHAPE(board)
    s.SetShape(pn.SHAPE_T_ARC)
    s.SetCenter(V(*center)); s.SetStart(V(*start))
    s.SetArcAngleAndEnd(pn.EDA_ANGLE(angle, pn.DEGREES_T), True)
    s.SetLayer(pn.Edge_Cuts); s.SetWidth(mm(0.1))
    board.Add(s)

r = CORNER_R
x1, y1, x2, y2 = BX, BY, BX + BW, BY + BH
edge_line((x1 + r, y1), (x2 - r, y1))
edge_line((x2, y1 + r), (x2, y2 - r))
edge_line((x2 - r, y2), (x1 + r, y2))
edge_line((x1, y2 - r), (x1, y1 + r))
edge_arc((x2 - r, y1 + r), (x2 - r, y1), 90)
edge_arc((x2 - r, y2 - r), (x2, y2 - r), 90)
edge_arc((x1 + r, y2 - r), (x1 + r, y2), 90)
edge_arc((x1 + r, y1 + r), (x1, y1 + r), 90)

# ---------------------------------------------------------------- footprints
def place(lib, name, ref, value, x, y, rot=0, bottom=True, pads=None, lcsc=""):
    fp = pn.FootprintLoad(FPLIB + lib + ".pretty", name)
    if fp is None:
        sys.exit("footprint not found: %s:%s" % (lib, name))
    fp.SetFPID(pn.LIB_ID(lib, name))
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetPosition(V(x, y))
    board.Add(fp)
    if bottom:
        fp.Flip(V(x, y), pn.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    if lcsc:
        fp.SetField("LCSC", lcsc)
        fp.GetField("LCSC").SetVisible(False)
    for p in fp.Pads():
        n = (pads or {}).get(p.GetNumber())
        if n:
            p.SetNet(net(n))
    return fp

def sim800l_module():
    """Custom footprint for the red SIM800L mini, placed on TOP."""
    fp = pn.FOOTPRINT(board)
    fp.SetFPID(pn.LIB_ID("keychain", "SIM800L_Red_Mini_25.2x23"))
    fp.SetReference("M1")
    fp.SetValue("SIM800L (M374C)")
    fp.SetAttributes(pn.FP_EXCLUDE_FROM_POS_FILES)  # hand-soldered module
    board.Add(fp)
    left = ["NET", "VCC", "RST", "RXD", "TXD", "GND"]          # pins 1..6
    right = ["RING", "DTR", "MIC+", "MIC-", "SPK+", "SPK-"]     # pins 12..7
    nets = {"VCC": "VBAT", "GND": "GND", "RXD": "SIM_RXD",
            "TXD": "SIM_TXD", "RING": "RING"}
    pins = []
    for i, nm in enumerate(left):
        pins.append((str(i + 1), nm, X0, Y0 + i * PITCH))
    for i, nm in enumerate(right):
        pins.append((str(12 - i), nm, X0 + ROW_DX, Y0 + RIGHT_ROW_DY + i * PITCH))
    for num, nm, x, y in pins:
        p = pn.PAD(fp)
        p.SetNumber(num)
        p.SetPinFunction(nm)
        p.SetAttribute(pn.PAD_ATTRIB_PTH)
        p.SetShape(pn.PAD_SHAPE_RECTANGLE if num == "1" else pn.PAD_SHAPE_CIRCLE)
        p.SetSize(V(MOD_PAD, MOD_PAD))
        p.SetDrillSize(V(MOD_DRILL, MOD_DRILL))
        p.SetLayerSet(pn.PAD.PTHMask())
        p.SetPosition(V(x, y))
        fp.Add(p)
        if nm in nets:
            p.SetNet(net(nets[nm]))
    # module outline on top fab/silk
    for layer, w in ((pn.F_Fab, 0.1), (pn.F_SilkS, 0.12)):
        s = pn.PCB_SHAPE(fp)
        s.SetShape(pn.SHAPE_T_RECT)
        s.SetStart(V(BX + 0.3, BY + 0.3)); s.SetEnd(V(BX + BW - 0.3, BY + BH - 0.3))
        s.SetLayer(layer); s.SetWidth(mm(w))
        fp.Add(s)
    return fp

sim800l_module()

R0402 = ("Resistor_SMD", "R_0402_1005Metric")
C0402 = ("Capacitor_SMD", "C_0402_1005Metric")
C0603 = ("Capacitor_SMD", "C_0603_1608Metric")

def R(ref, val, x, y, a, b, rot=0, lcsc=""):
    return place(*R0402, ref, val, x, y, rot, pads={"1": a, "2": b}, lcsc=lcsc)

def C(ref, val, x, y, a, b, rot=0, fp=C0402, lcsc=""):
    return place(*fp, ref, val, x, y, rot, pads={"1": a, "2": b}, lcsc=lcsc)

# --- MCU: ATtiny85-20SU (SOIC-8)
# 1 PB5/RESET  2 PB3  3 PB4  4 GND  5 PB0  6 PB1  7 PB2  8 VCC
place("Package_SO", "SOIC-8_3.9x4.9mm_P1.27mm", "U1", "ATtiny85-20SU",
      113.2, 107.5, 0,
      pads={"1": "RESET", "2": "RING", "3": "DRV", "4": "GND",
            "5": "MCU_RX", "6": "MCU_TX", "7": "BTN", "8": "VBAT"},
      lcsc="")
C("C1", "100nF", 117.6, 109.0, "VBAT", "GND", rot=90)

# --- SIM800L supply buffer (Case D tantalum + ceramic)
place("Capacitor_Tantalum_SMD", "CP_EIA-7343-31_Kemet-D", "C2",
      "470uF 6.3V tant", 105.4, 110.7, 270,
      pads={"1": "VBAT", "2": "GND"})
C("C5", "10uF", 108.7, 106.3, "VBAT", "GND", rot=90, fp=C0603, lcsc="C19702")

# --- UART: SIM TXD (2.8 V) -> 1k -> PB0 ; PB1 -> 47k/100k divider -> SIM RXD
R("R1", "1k", 108.7, 109.2, "SIM_TXD", "MCU_RX", rot=90, lcsc="C11702")
R("R2", "47k", 108.7, 111.2, "MCU_TX", "SIM_RXD", rot=90, lcsc="C25792")
R("R3", "100k", 108.7, 113.2, "SIM_RXD", "GND", rot=90, lcsc="C25741")

# --- reset pull-up (keeps PB5 as RESET for ISP)
R("R6", "10k", 111.0, 103.9, "RESET", "VBAT", rot=0, lcsc="C25744")

# --- motor + heart driver: PB4 -> 100R -> AO3400A gate, 100k pull-down
place("Package_TO_SOT_SMD", "SOT-23", "Q1", "AO3400A", 120.2, 107.2, 0,
      pads={"1": "GATE", "2": "GND", "3": "MOT_N"})
R("R4", "100R", 120.3, 104.6, "DRV", "GATE", rot=0, lcsc="C25076")
R("R5", "100k", 120.2, 109.8, "GATE", "GND", rot=0, lcsc="C25741")
place("Diode_SMD", "D_SOD-523", "D1", "1N4148WT", 120.2, 111.4, 0,
      pads={"1": "VBAT", "2": "MOT_N"})   # K=VBAT, A=MOT_N

# --- the LED heart is a separate board (hardware/heart), wired to HT1/HT2 below

# --- side-push button on the top edge, actuator points out of the board
place("Button_Switch_SMD", "SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010",
      "SW1", "Side tact", 116.6, BY + 1.8, 0,
      pads={"1": "BTN", "2": "GND"})   # MP = mechanical, no net

# --- USB-C (power only) + MCP73831 charger
place("Connector_USB", "USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal",
      "J1", "USB-C 6P", 112.6, BY + BH - 3.4, 180,
      pads={"A9": "VBUS", "B9": "VBUS", "A12": "GND", "B12": "GND",
            "A5": "CC1", "B5": "CC2", "SH": "GND"})
R("R8", "5.1k", 111.0, 114.6, "CC1", "GND", rot=0, lcsc="C25905")
R("R9", "5.1k", 114.2, 114.6, "CC2", "GND", rot=0, lcsc="C25905")
place("Package_TO_SOT_SMD", "SOT-23-5", "U2", "MCP73831T-2ACI/OT",
      120.3, 114.6, 90,
      pads={"1": "STAT", "2": "GND", "3": "VBAT", "4": "VBUS", "5": "PROG"},
      lcsc="")
R("R10", "4.7k", 120.2, 118.4, "PROG", "GND", rot=90, lcsc="C25900")  # ~213 mA
C("C3", "4.7uF", 118.6, 118.4, "VBUS", "GND", rot=90)
C("C4", "4.7uF", 121.6, 118.4, "VBAT", "GND", rot=90)

# --- wire pads: battery, motor, heart board, ISP (compact SMD pads, bottom)
import pcblib
def wirepad(ref, val, x, y, size, n):
    return pcblib.wirepad(board, net, ref, val, x, y, size, n)

wirepad("BT1", "BAT+", 111.2, 112.2, 1.5, "VBAT")
wirepad("BT2", "BAT-", 113.2, 112.2, 1.5, "GND")
wirepad("MT1", "MOT+", 121.3, 102.6, 1.0, "VBAT")
wirepad("MT2", "MOT-", 121.3, 101.1, 1.0, "MOT_N")
wirepad("HT1", "HEART+", 105.6, 101.2, 1.0, "VBAT")
wirepad("HT2", "HEART-", 107.4, 101.2, 1.0, "MOT_N")
# ISP pads in two staggered columns so every pad gets a readable label
ISP = [("TP1", "RST", "RESET", 103.7, 117.0), ("TP2", "MOSI", "MCU_RX", 106.6, 118.0),
       ("TP3", "MISO", "MCU_TX", 103.7, 119.0), ("TP4", "SCK", "BTN", 106.6, 120.0),
       ("TP5", "VCC", "VBAT", 103.7, 121.0), ("TP6", "GND", "GND", 106.6, 122.0)]
for ref, val, n, x, y in ISP:
    wirepad(ref, val, x, y, 0.9, n)

# GND pours are added by autoroute.py AFTER routing, so the router wires GND
# explicitly instead of assuming a plane.

# ---------------------------------------------------------------- text
# References go to the Fab layer (assembly PDF); the silkscreen gets short
# functional labels so you can see what every pad / hole is.
pcblib.refs_to_fab(board, top_refs=("M1",))

def silk(text, x, y, size=0.8, layer=pn.B_SilkS, justify=None):
    return pcblib.silk(board, text, x, y, size, layer, justify=justify)

# bottom side (mirrored text, reads correctly when the board is flipped)
silk("BAT", 112.2, 110.75, 0.8)
silk("+", 111.2, 113.65, 0.9)
silk("-", 113.2, 113.65, 0.9)
silk("MOT", 123.7, 101.85, 0.8)
silk("HEART", 106.5, 103.55, 0.8)
silk("+", 105.6, 102.45, 0.8)
silk("-", 107.4, 102.45, 0.8)
silk("ISP", 105.2, 116.0, 0.8)
for ref, val, n, x, y in ISP:
    # bottom text is mirrored: "right" justify on B.SilkS grows to the right on screen
    if x < 105:
        silk(val, x + 0.65, y, 0.8, justify="right")
    else:
        silk(val, x - 0.65, y, 0.8, justify="left")

# top side: SIM800L pin names next to the module holes, plus title
silk("TOUCH-GSM v1", BX + BW / 2, BY + 12.5, 0.8, pn.F_SilkS)
silk("SIM800L SIDE", BX + BW / 2, BY + 14.0, 0.8, pn.F_SilkS)
for i, nm in enumerate(["NET", "VCC", "RST", "RXD", "TXD", "GND"]):
    silk(nm, X0 + 1.2, Y0 + i * PITCH, 0.8, pn.F_SilkS, justify="left")
for i, nm in enumerate(["RING", "DTR", "MIC+", "MIC-", "SPK+", "SPK-"]):
    silk(nm, X0 + ROW_DX - 1.2, Y0 + RIGHT_ROW_DY + i * PITCH, 0.8, pn.F_SilkS, justify="right")

# ---------------------------------------------------------------- schematic sync + link
# The schematic is the source of truth: pad nets and fields come from its
# netlist (cross-checked against this script), footprints link to symbols.
net.items = NETS
pcblib.sync_from_schematic(board, net, os.path.join(HW, "keychain-carrier.kicad_sch"),
                           allow_dropped=("STAT",))
pcblib.link_symbols(board, os.path.join(HW, "sch_uuids.json"), "keychain-carrier.kicad_sch")
pcblib.save_custom_footprints(board, os.path.join(HW, "keychain.pretty"))
board.BuildConnectivity()
pn.SaveBoard(OUT, board)

# ---------------------------------------------------------------- project file
pcblib.write_project(
    OUT[:-len(".kicad_pcb")] + ".kicad_pro",
    [("Default", 0.2, 0.15, 0.6, 0.3, 2147483647),
     ("Power", 0.6, 0.2, 0.7, 0.35, 0),
     ("Motor", 0.3, 0.15, 0.6, 0.3, 1)],
    [("VBAT", "Power"), ("GND", "Power"), ("VBUS", "Power"), ("/MOT_N", "Motor")],
    extra_rules={"min_hole_clearance": 0.05})   # real 0.25 mm rule is in the .kicad_dru
print("saved", OUT, "footprints:", len(board.GetFootprints()))
