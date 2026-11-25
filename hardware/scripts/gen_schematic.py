"""
Generate the schematic (KiCad 10 .kicad_sch) for the GSM touch-keychain carrier,
plus the project symbol library (keychain.kicad_sym) and sch_uuids.json, which
build_pcb.py uses to link every footprint to its symbol (schematic parity).

  python3 hardware/scripts/gen_schematic.py

Style: functional blocks; every pin gets a short stub with a power symbol or a
net label, so the drawing reads like the netlist in hardware/netlist.txt.
"""
import copy
import json
import math
import os
import uuid

import sexpr
from sexpr import Q, first, find

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
SYMDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/"
PROJECT = "keychain-carrier"
SCH = os.path.join(HW, PROJECT + ".kicad_sch")
NS = uuid.UUID("6b0d1c4e-3f7a-4c55-9a51-2e1f6a7c9b10")


def uid(*k):
    return Q(str(uuid.uuid5(NS, "/".join(map(str, k)))))


ROOT = uid("root")
STUB = 2.54
POWER = {"GND": "power:GND", "VBAT": "keychain:VBAT", "VBUS": "power:VBUS"}


def font(size=1.27, hide=False, justify=None, bold=False):
    f = ["font", ["size", size, size]]
    if bold:
        f.append(["bold", "yes"])
    e = ["effects", f]
    if justify:
        e.append(["justify"] + justify)
    if hide:
        e.append(["hide", "yes"])
    return e


# ------------------------------------------------------------ custom symbols
def prop(name, value, x=0.0, y=0.0, hide=False):
    return ["property", Q(name), Q(value), ["at", x, y, 0], font(hide=hide)]


def sim800l_symbol():
    left = [("4", "RXD", "input"), ("5", "TXD", "output"), ("12", "RING", "output"),
            ("11", "DTR", "input"), ("3", "RST", "input"), ("1", "NET", "output")]
    right = [("10", "MIC+", "passive"), ("9", "MIC-", "passive"),
             ("8", "SPK+", "passive"), ("7", "SPK-", "passive")]
    body = ["symbol", Q("SIM800L_Red_Mini_0_1"),
            ["rectangle", ["start", -7.62, 11.43], ["end", 7.62, -11.43],
             ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]]
    pinsu = ["symbol", Q("SIM800L_Red_Mini_1_1")]
    for i, (n, nm, t) in enumerate(left):
        pinsu.append(["pin", t, "line", ["at", -10.16, 8.89 - i * 2.54, 0], ["length", 2.54],
                      ["name", Q(nm), font()], ["number", Q(n), font()]])
    pinsu.append(["pin", "power_in", "line", ["at", 0, 13.97, 270], ["length", 2.54],
                  ["name", Q("VCC"), font()], ["number", Q("2"), font()]])
    pinsu.append(["pin", "power_in", "line", ["at", 0, -13.97, 90], ["length", 2.54],
                  ["name", Q("GND"), font()], ["number", Q("6"), font()]])
    for i, (n, nm, t) in enumerate(right):
        pinsu.append(["pin", t, "line", ["at", 10.16, 8.89 - i * 2.54, 180], ["length", 2.54],
                      ["name", Q(nm), font()], ["number", Q(n), font()]])
    return ["symbol", Q("SIM800L_Red_Mini"), ["pin_names", ["offset", 1.016]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            prop("Reference", "M", 3.81, 13.97), prop("Value", "SIM800L_Red_Mini", 3.81, -13.97),
            prop("Footprint", "keychain:SIM800L_Red_Mini_25.2x23", 0, 0, True),
            prop("Datasheet", "", 0, 0, True),
            prop("Description", "SIM800L red mini GSM breakout (25.2x23 mm, 12 pins)", 0, 0, True),
            body, pinsu]


def vbat_symbol(stock):
    s = copy.deepcopy(stock["+BATT"])
    s[1] = Q("VBAT")
    for p in find(s, "property"):
        if p[1] == "Value":
            p[2] = Q("VBAT")
        if p[1] == "Description":
            p[2] = Q("Power symbol creates a global label with name \"VBAT\"")
    for unit in find(s, "symbol"):
        unit[1] = Q(unit[1].replace("+BATT", "VBAT"))
        for p in find(unit, "pin"):
            first(p, "name")[1] = Q("VBAT")
    return s


libs = {}


def lib(name):
    if name not in libs:
        libs[name] = sexpr.load_library(SYMDIR + name + ".kicad_sym")
    return libs[name]


KEYCHAIN = {"SIM800L_Red_Mini": sim800l_symbol(), "VBAT": vbat_symbol(lib("power"))}
with open(os.path.join(HW, "keychain.kicad_sym"), "w") as f:
    f.write(sexpr.dump(["kicad_symbol_lib", ["version", 20241209],
                        ["generator", Q("gen_schematic.py")], ["generator_version", Q("10.0")]]
                       + list(KEYCHAIN.values())) + "\n")

lib_symbols = {}


def libsym(lib_id):
    if lib_id not in lib_symbols:
        ln, name = lib_id.split(":")
        if ln == "keychain":
            s = copy.deepcopy(KEYCHAIN[name])
            s[1] = Q(lib_id)
        else:
            s = sexpr.flatten(lib(ln), name, ln)
        lib_symbols[lib_id] = s
    return lib_symbols[lib_id]


# ------------------------------------------------------------ geometry
def xform(px, py, X, Y, rot):
    """symbol coords (y up) -> sheet coords (y down)."""
    x, y = px, -py
    a = math.radians(rot)
    c, s = round(math.cos(a)), round(math.sin(a))
    return X + x * c + y * s, Y - x * s + y * c


def snap(v):
    return round(v / 1.27) * 1.27


items = []
uuids = {}
pwr_count = [0]


def wire(a, b):
    items.append(["wire", ["pts", ["xy", a[0], a[1]], ["xy", b[0], b[1]]],
                  ["stroke", ["width", 0], ["type", "default"]], ["uuid", uid("w", a, b)]])


def label(name, at, direction):
    ang = {"right": 0, "up": 90, "left": 180, "down": 270}[direction]
    just = ["left", "bottom"] if direction in ("right", "up") else ["right", "bottom"]
    items.append(["label", Q(name), ["at", at[0], at[1], ang], font(justify=just),
                  ["uuid", uid("l", name, at)]])


def text(s, x, y, size=1.27, bold=False):
    items.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", x, y, 0],
                  font(size, justify=["left", "bottom"], bold=bold), ["uuid", uid("t", s[:40], x, y)]])


def box(x1, y1, x2, y2, title):
    items.append(["rectangle", ["start", x1, y1], ["end", x2, y2],
                  ["stroke", ["width", 0.2], ["type", "dash"]], ["fill", ["type", "none"]],
                  ["uuid", uid("r", title)]])
    text(title, x1 + 1.27, y1 + 3.81, 2.0, True)


def place(lib_id, ref, value, x, y, rot=0, footprint="", nets=None, nc=(), on_board=True,
          in_bom=True, extra=None, field_at=None):
    nets = nets or {}
    sym = libsym(lib_id)
    X, Y = snap(x), snap(y)
    u = uid("s", ref)
    if not ref.startswith("#"):
        uuids[ref] = str(u)
    inst = ["symbol", ["lib_id", Q(lib_id)], ["at", X, Y, rot], ["unit", 1],
            ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"],
            ["on_board", "yes" if on_board else "no"], ["dnp", "no"], ["uuid", u]]
    values = {"Reference": ref, "Value": value, "Footprint": footprint}
    values.update(extra or {})
    for p in find(sym, "property"):
        name = p[1]
        if name.startswith("ki_"):
            continue                      # library search metadata, not instance fields
        at = first(p, "at")
        px, py = xform(float(at[1]), float(at[2]), X, Y, rot)
        pang = (float(at[3]) if len(at) > 3 else 0.0) + rot
        if field_at and name in field_at:
            px, py = X + field_at[name][0], Y + field_at[name][1]
            pang = 0
        eff = copy.deepcopy(first(p, "effects")) or font()
        hidden = (first(p, "hide") is not None and first(p, "hide")[1] == "yes") or \
            first(eff, "hide") is not None or ref.startswith("#") and name == "Reference" or \
            name in ("Footprint", "Datasheet", "Description") or name not in values
        for h in find(eff, "hide"):
            eff.remove(h)
        if hidden:
            eff.append(["hide", "yes"])
        val = values.get(name, p[2])
        inst.append(["property", Q(name), Q(val), ["at", px, py, pang % 180], eff])   # keep text upright
    for name, val in (extra or {}).items():
        if not any(pp[1] == name for pp in find(sym, "property")):
            inst.append(["property", Q(name), Q(val), ["at", X, Y, 0], font(hide=True)])
    seen = {}
    for num, pname, px, py, ang, ptype in sexpr.pins(sym):
        inst.append(["pin", Q(num), ["uuid", uid("p", ref, num)]])
        ex, ey = xform(px, py, X, Y, rot)
        ex, ey = round(ex, 2), round(ey, 2)
        if (ex, ey) in seen:
            continue
        seen[(ex, ey)] = num
        # outward direction = opposite of the pin's body direction
        oa = math.radians(ang + 180)
        dx, dy = round(math.cos(oa)), -round(math.sin(oa))
        a = math.radians(rot)
        c, s = round(math.cos(a)), round(math.sin(a))
        dx, dy = dx * c + dy * s, -dx * s + dy * c
        direction = {(1, 0): "right", (-1, 0): "left", (0, -1): "up", (0, 1): "down"}[(dx, dy)]
        if num in nc:
            items.append(["no_connect", ["at", ex, ey], ["uuid", uid("nc", ref, num)]])
            continue
        n = nets.get(num)
        if not n:
            continue
        end = (round(ex + dx * STUB, 2), round(ey + dy * STUB, 2))
        wire((ex, ey), end)
        if n in POWER:
            pwr_count[0] += 1
            if n == "GND":
                prot = 180 if direction == "up" else 0
            else:
                prot = 180 if direction == "down" else 0
            place(POWER[n], "#PWR%02d" % pwr_count[0], n, end[0], end[1], prot)
        else:
            label(n, end, direction)
    inst.append(["instances", ["project", Q(PROJECT),
                               ["path", Q("/" + ROOT), ["reference", Q(ref)], ["unit", 1]]]])
    items.append(inst)


R = "Device:R"
C = "Device:C"
FP_R = "Resistor_SMD:R_0402_1005Metric"
FP_C = "Capacitor_SMD:C_0402_1005Metric"


def res(ref, val, x, y, n1, n2, rot=0, lcsc=""):
    place(R, ref, val, x, y, rot, FP_R, {"1": n1, "2": n2}, extra={"LCSC": lcsc} if lcsc else None)


def cap(ref, val, x, y, n1, n2, fp=FP_C, lib_id=C, lcsc=""):
    place(lib_id, ref, val, x, y, 0, fp, {"1": n1, "2": n2}, extra={"LCSC": lcsc} if lcsc else None)


def tp(ref, val, x, y, n, size, rot=0):
    place("Connector:TestPoint", ref, val, x, y, rot, "keychain:WirePad_%.1fmm" % size,
          {"1": n}, in_bom=False)


# ============================================================ BLOCK A: USB-C + charger
box(15.24, 22.86, 137.16, 96.52, "A. USB-C input + LiPo charger (MCP73831, ~213 mA)")
place("Connector:USB_C_Receptacle_PowerOnly_6P", "J1", "USB-C 6P", 33.02, 55.88, 0,
      "Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal",
      {"A9": "VBUS", "B9": "VBUS", "A5": "CC1", "B5": "CC2", "A12": "GND", "B12": "GND", "SH": "GND"})
res("R8", "5.1k", 63.5, 68.58, "CC1", "GND", lcsc="C25905")
res("R9", "5.1k", 71.12, 68.58, "CC2", "GND", lcsc="C25905")
cap("C3", "4.7uF", 78.74, 60.96, "VBUS", "GND")
place("Battery_Management:MCP73831-2-OT", "U2", "MCP73831T-2ACI/OT", 106.68, 58.42, 0,
      "Package_TO_SOT_SMD:SOT-23-5",
      {"1": "STAT", "2": "GND", "3": "VBAT", "4": "VBUS", "5": "PROG"}, nc=("1",),
      field_at={"Reference": (-10.16, -8.89), "Value": (-12.7, 10.16)})
res("R10", "4.7k", 91.44, 81.28, "PROG", "GND", lcsc="C25900")
cap("C4", "4.7uF", 132.08, 63.5, "VBAT", "GND")
text("I_chg = 1000 V / R10 = 213 mA (0.85 C for 250 mAh)", 20.32, 91.44)
text("CC 5.1k pull-downs: 5 V from any USB-C charger", 20.32, 93.98)

# ============================================================ BLOCK B: battery + bulk
box(15.24, 101.6, 137.16, 157.48, "B. LiPo cell + SIM800L supply buffer")
place("Device:Battery_Cell", "BAT1", "LiPo 250mAh", 27.94, 129.54, 0, "",
      {"1": "VBAT", "2": "GND"}, on_board=False, in_bom=False)
tp("BT1", "BAT+", 48.26, 124.46, "VBAT", 1.5, rot=180)
tp("BT2", "BAT-", 60.96, 129.54, "GND", 1.5)
cap("C2", "470uF tant", 81.28, 129.54, "VBAT", "GND",
    fp="Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D", lib_id="Device:C_Polarized")
cap("C5", "10uF", 99.06, 129.54, "VBAT", "GND", fp="Capacitor_SMD:C_0603_1608Metric", lcsc="C19702")
# VBAT is driven by U2 (power_out), so it needs no PWR_FLAG
place("power:PWR_FLAG", "#FLG02", "PWR_FLAG", 114.3, 132.08, 0, "", {"1": "GND"})
place("power:PWR_FLAG", "#FLG03", "PWR_FLAG", 127.0, 124.46, 180, "", {"1": "VBUS"})
text("BAT1 = pouch cell WITH protection PCM, wired to pads BT1/BT2", 20.32, 148.59)
text("C2: polymer tantalum (2 A GSM bursts); battery feeds SIM800L directly", 20.32, 151.13)
text("SIM800L VCC abs. max 4.4 V - never power VBAT from 5 V", 20.32, 153.67)

# ============================================================ BLOCK C: MCU
box(142.24, 22.86, 210.82, 96.52, "C. ATtiny85 (PB5 = RESET kept for ISP)")
place("MCU_Microchip_ATtiny:ATtiny85-20S", "U1", "ATtiny85-20SU", 170.18, 53.34, 0,
      "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
      {"8": "VBAT", "4": "GND", "5": "MCU_RX", "6": "MCU_TX", "7": "BTN", "2": "RING",
       "3": "DRV", "1": "RESET"}, field_at={"Value": (-8.89, 16.51)})
cap("C1", "100nF", 149.86, 53.34, "VBAT", "GND")
res("R6", "10k", 203.2, 53.34, "RESET", "VBAT", rot=180, lcsc="C25744")
place("Switch:SW_Push", "SW1", "Side tact", 190.5, 68.58, 0,
      "Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010",
      {"1": "BTN", "2": "GND"})
for i, (ref, val, n) in enumerate([("TP1", "RST", "RESET"), ("TP2", "MOSI", "MCU_RX"),
                                   ("TP3", "MISO", "MCU_TX"), ("TP4", "SCK", "BTN"),
                                   ("TP5", "VCC", "VBAT"), ("TP6", "GND", "GND")]):
    tp(ref, val, [147.32, 154.94, 162.56, 177.8, 185.42, 193.04][i], 83.82, n, 0.9)
text("ISP: flash BEFORE fitting SIM800L", 165.1, 95.25)

# ============================================================ BLOCK D: SIM800L
box(215.9, 22.86, 289.56, 96.52, "D. SIM800L module (on top side)")
place("keychain:SIM800L_Red_Mini", "M1", "SIM800L (M374C)", 264.16, 53.34, 0,
      "keychain:SIM800L_Red_Mini_25.2x23",
      {"2": "VBAT", "6": "GND", "4": "SIM_RXD", "5": "SIM_TXD", "12": "RING"},
      nc=("1", "3", "11", "7", "8", "9", "10"), field_at={"Value": (8.89, 16.51)})
res("R1", "1k", 228.6, 71.12, "SIM_TXD", "MCU_RX", lcsc="C11702")
res("R2", "47k", 241.3, 71.12, "MCU_TX", "SIM_RXD", lcsc="C25792")
res("R3", "100k", 254.0, 71.12, "SIM_RXD", "GND", lcsc="C25741")
text("R1: isolates SIM TXD from ISP MOSI", 218.44, 91.44)
text("R2/R3: 4.2 V -> 2.86 V (2.8 V logic)", 218.44, 93.98)
text("DTR unused: AT+CSCLK=2 (auto sleep)", 218.44, 33.02)

# ============================================================ BLOCK E: motor + LED
box(142.24, 101.6, 289.56, 157.48, "E. Vibration motor + LED driver (shared PB4 PWM)")
res("R4", "100R", 160.02, 129.54, "DRV", "GATE", lcsc="C25076")
res("R5", "100k", 172.72, 137.16, "GATE", "GND", lcsc="C25741")
place("Transistor_FET:2N7002", "Q1", "2N7002", 190.5, 132.08, 0, "Package_TO_SOT_SMD:SOT-23",
      {"1": "GATE", "2": "GND", "3": "MOT_N"}, extra={"LCSC": "C8545"})
place("Device:D", "D1", "1N4148WT", 218.44, 119.38, 0, "Diode_SMD:D_SOD-523",
      {"1": "VBAT", "2": "MOT_N"})
place("Device:LED", "D2", "LED red 0805", 218.44, 137.16, 0, "LED_SMD:LED_0805_2012Metric",
      {"1": "MOT_N", "2": "LED_A"}, field_at={"Value": (0, 5.08)})
res("R7", "220R", 238.76, 137.16, "LED_A", "VBAT", rot=180, lcsc="C25091")
place("Motor:Motor_DC", "MOT1", "0820 motor", 254.0, 127.0, 0, "",
      {"1": "VBAT", "2": "MOT_N"}, on_board=False, in_bom=False)
tp("MT1", "MOT+", 271.78, 119.38, "VBAT", 1.0, rot=180)
tp("MT2", "MOT-", 281.94, 134.62, "MOT_N", 1.0)
text("MOT1 is off-board, wired to pads MT1/MT2.  D1 = flyback.", 144.78, 151.13)
text("LED + R7 sit in parallel with the motor, so they blink with the vibration.", 144.78, 153.67)

# ------------------------------------------------------------ write
sch = ["kicad_sch", ["version", 20250114], ["generator", Q("eeschema")],
       ["generator_version", Q("10.0")], ["uuid", ROOT], ["paper", Q("A4")],
       ["title_block", ["title", Q("GSM touch keychain - carrier board")],
        ["date", Q("2026-11-25")], ["rev", Q("1")],
        ["comment", 1, Q("SIM800L red mini + ATtiny85 + MCP73831, 25.2 x 23 mm")],
        ["comment", 2, Q("Generated by hardware/scripts/gen_schematic.py - edit the script, not this file")]],
       ["lib_symbols"] + list(lib_symbols.values())]
sch += items
sch.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
sch.append(["embedded_fonts", "no"])
with open(SCH, "w") as f:
    f.write(sexpr.dump(sch) + "\n")
with open(os.path.join(HW, "sch_uuids.json"), "w") as f:
    json.dump({"root": str(ROOT), "symbols": uuids}, f, indent=1, sort_keys=True)

for name, uri in (("sym-lib-table", "keychain.kicad_sym"), ("fp-lib-table", "keychain.pretty")):
    kind = "sym_lib_table" if name.startswith("sym") else "fp_lib_table"
    with open(os.path.join(HW, name), "w") as f:
        f.write('(%s\n  (version 7)\n  (lib (name "keychain")(type "KiCad")(uri "${KIPRJMOD}/%s")'
                '(options "")(descr "Project parts"))\n)\n' % (kind, uri))
print("schematic:", SCH, "symbols:", len(uuids))
