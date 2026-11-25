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

# --- motor driver: PB4 -> 100R -> 2N7002 gate, 100k pull-down
place("Package_TO_SOT_SMD", "SOT-23", "Q1", "2N7002", 120.2, 107.2, 0,
      pads={"1": "GATE", "2": "GND", "3": "MOT_N"}, lcsc="C8545")
R("R4", "100R", 120.3, 104.6, "DRV", "GATE", rot=0, lcsc="C25076")
R("R5", "100k", 120.2, 109.8, "GATE", "GND", rot=0, lcsc="C25741")
place("Diode_SMD", "D_SOD-523", "D1", "1N4148WT", 120.2, 111.4, 0,
      pads={"1": "VBAT", "2": "MOT_N"})   # K=VBAT, A=MOT_N

# --- status LED in parallel with the motor (same PWM)
place("LED_SMD", "LED_0805_2012Metric", "D2", "LED red 0805", 106.0, 101.2, 180,
      pads={"1": "MOT_N", "2": "LED_A"})    # 1=K, 2=A
R("R7", "220R", 108.9, 101.2, "LED_A", "VBAT", rot=0, lcsc="C25091")

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

# --- wire pads: battery, motor, ISP (compact custom SMD pads on bottom)
def wirepad(ref, val, x, y, size, n):
    fp = pn.FOOTPRINT(board)
    fp.SetFPID(pn.LIB_ID("keychain", "WirePad_%.1fmm" % size))
    fp.SetReference(ref); fp.SetValue(val)
    fp.SetAttributes(pn.FP_SMD | pn.FP_EXCLUDE_FROM_BOM | pn.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetPosition(V(x, y))
    board.Add(fp)
    p = pn.PAD(fp)
    p.SetNumber("1"); p.SetAttribute(pn.PAD_ATTRIB_SMD)
    p.SetShape(pn.PAD_SHAPE_ROUNDRECT); p.SetRoundRectRadiusRatio(0.2)
    p.SetSize(V(size, size)); p.SetLayerSet(p.SMDMask())
    p.SetPosition(V(x, y)); fp.Add(p)
    p.SetNet(net(n))
    cy = pn.PCB_SHAPE(fp); cy.SetShape(pn.SHAPE_T_RECT)
    h = size / 2 + 0.15
    cy.SetStart(V(x - h, y - h)); cy.SetEnd(V(x + h, y + h))
    cy.SetLayer(pn.F_CrtYd); cy.SetWidth(mm(0.05)); fp.Add(cy)
    fp.Flip(V(x, y), pn.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetTextSize(V(0.5, 0.5)); fp.Reference().SetTextThickness(mm(0.08))
    fp.Reference().SetPosition(V(x, y))
    return fp

wirepad("BT1", "BAT+", 111.2, 112.2, 1.5, "VBAT")
wirepad("BT2", "BAT-", 113.2, 112.2, 1.5, "GND")
wirepad("MT1", "MOT+", 121.3, 102.6, 1.0, "VBAT")
wirepad("MT2", "MOT-", 121.3, 101.1, 1.0, "MOT_N")
isp = [("TP1", "RST", "RESET"), ("TP2", "MOSI", "MCU_RX"),
       ("TP3", "MISO", "MCU_TX"), ("TP4", "SCK", "BTN"),
       ("TP5", "VCC", "VBAT"), ("TP6", "GND", "GND")]
ISP_XY = [(104.0, 117.4), (105.4, 117.4), (104.0, 118.8), (105.4, 118.8),
          (104.0, 120.2), (105.4, 120.2)]
for (ref, val, n), (x, y) in zip(isp, ISP_XY):
    wirepad(ref, val, x, y, 0.9, n)

# GND pours are added by autoroute.py AFTER routing, so the router wires GND
# explicitly instead of assuming a plane.

# ---------------------------------------------------------------- text
# The board is too dense for readable silkscreen references: hide silk refs and
# values; references stay on the Fab layer (assembly drawing PDF).
for fp in board.GetFootprints():
    fp.Value().SetVisible(False)
    ref = fp.Reference()
    if fp.GetReference() == "M1":
        ref.SetLayer(pn.F_Fab)
    else:
        ref.SetLayer(pn.B_Fab)
        ref.SetMirrored(True)
    ref.SetTextSize(V(0.5, 0.5)); ref.SetTextThickness(mm(0.08))
    for item in fp.GraphicalItems():
        if isinstance(item, pn.PCB_TEXT) and item.GetText() == "${REFERENCE}":
            item.SetVisible(False)          # keep exactly one ref per part

def silk(text, x, y, size=0.8, layer=pn.B_SilkS):
    t = pn.PCB_TEXT(board)
    t.SetText(text); t.SetPosition(V(x, y)); t.SetLayer(layer)
    t.SetTextSize(V(size, size)); t.SetTextThickness(mm(size * 0.15))
    t.SetMirrored(layer == pn.B_SilkS)
    board.Add(t)

silk("TOUCH-GSM v1", BX + BW / 2, BY + 11.0, 0.7, pn.F_SilkS)

# ---------------------------------------------------------------- schematic sync
# The schematic is the source of truth. Export its netlist, cross-check every
# pad against the net this script assigned (fail on any disagreement), then
# adopt the schematic net names (e.g. "/MCU_RX") and symbol fields.
import subprocess, tempfile
sys.path.insert(0, HERE)
import sexpr
nl_path = os.path.join(tempfile.mkdtemp(), "kc.net")
subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
                "-o", nl_path, os.path.join(HW, "keychain-carrier.kicad_sch")],
               check=True, capture_output=True)
nl = sexpr.parse(open(nl_path).read())
NETMAP = {}
for n in sexpr.find(sexpr.first(nl, "nets"), "net"):
    name = sexpr.first(n, "name")[1]
    for node in sexpr.find(n, "node"):
        NETMAP[(sexpr.first(node, "ref")[1], sexpr.first(node, "pin")[1])] = name
COMPS = {sexpr.first(c, "ref")[1]: c for c in sexpr.find(sexpr.first(nl, "components"), "comp")}

def norm(n):
    if not n or n.startswith("unconnected-"):
        return ""
    return n.lstrip("/")

errors = []
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if ref not in COMPS:
        errors.append("%s missing from schematic" % ref)
        continue
    for p in fp.Pads():
        if not p.GetNumber():
            continue                      # NPTH / mechanical
        sch = NETMAP.get((ref, p.GetNumber()), "")
        if norm(sch) != norm(p.GetNetname()) and not (p.GetNetname() == "STAT" and not norm(sch)):
            errors.append("%s.%s: pcb=%s sch=%s" % (ref, p.GetNumber(), p.GetNetname(), sch))
        p.SetNet(net(sch) if sch else pn.NETINFO_LIST.OrphanedItem())
    comp = COMPS[ref]
    fp.SetValue(sexpr.first(comp, "value")[1])
    sch_fields = {sexpr.first(f, "name")[1] for f in sexpr.find(sexpr.first(comp, "fields") or [], "field")}
    for fld in list(fp.GetFields()):
        if not fld.IsMandatory() and fld.GetName() not in sch_fields:
            fp.Remove(fld)                    # e.g. KiLib_Generator from the library
    for f in sexpr.find(sexpr.first(comp, "fields") or [], "field"):
        name = sexpr.first(f, "name")[1]
        val = f[2] if len(f) > 2 else ""
        if name == "Footprint" or name.startswith("ki_"):
            continue
        fp.SetField(name, val)
        fld = fp.GetField(name)
        if name not in ("Reference",):
            fld.SetVisible(False)
if errors:
    sys.exit("schematic/PCB mismatch:\n  " + "\n  ".join(errors))
for name in list(NETS):
    if name not in NETMAP.values():
        board.Remove(NETS.pop(name))      # drop the script's pre-sync net names

# ---------------------------------------------------------------- schematic link
# Link each footprint to its schematic symbol (UUIDs from gen_schematic.py) so
# KiCad's schematic-parity check and "Update PCB from Schematic" work.
import json
link = json.load(open(os.path.join(HW, "sch_uuids.json")))
for fp in board.GetFootprints():
    u = link["symbols"].get(fp.GetReference())
    if not u:
        sys.exit("footprint %s has no schematic symbol" % fp.GetReference())
    fp.SetPath(pn.KIID_PATH("/" + u))
    fp.SetSheetname("/")
    fp.SetSheetfile("keychain-carrier.kicad_sch")

# ---------------------------------------------------------------- project footprint lib
# Save the custom footprints (module + wire pads) to keychain.pretty.
PRETTY = os.path.join(HW, "keychain.pretty")
os.makedirs(PRETTY, exist_ok=True)
io = pn.PCB_IO_KICAD_SEXPR()
done = set()
for fp in board.GetFootprints():
    fid = fp.GetFPID()
    if fid.GetLibNickname() == "keychain" and str(fid.GetLibItemName()) not in done:
        lf = pn.FOOTPRINT(fp)               # copy, normalised to origin / top side
        if lf.IsFlipped():
            lf.Flip(lf.GetPosition(), pn.FLIP_DIRECTION_LEFT_RIGHT)
        lf.SetOrientationDegrees(0)
        lf.Move(pn.VECTOR2I(-lf.GetPosition().x, -lf.GetPosition().y))
        lf.SetPath(pn.KIID_PATH())
        lf.Reference().SetVisible(True)
        lf.Reference().SetLayer(pn.F_SilkS); lf.Reference().SetMirrored(False)
        io.FootprintSave(PRETTY, lf)
        done.add(str(fid.GetLibItemName()))

board.BuildConnectivity()
pn.SaveBoard(OUT, board)
print("saved", OUT, "footprints:", len(board.GetFootprints()))
