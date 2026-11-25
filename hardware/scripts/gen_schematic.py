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


POWER = {"GND": "power:GND", "VBAT": "keychain:VBAT", "VBUS": "power:VBUS"}


from schlib import font, prop  # noqa: E402


# ------------------------------------------------------------ custom symbols
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


import schlib

def lib(name):
    return schlib.stock(name)


def tp4054_symbol():
    """TP4054 linear Li-ion charger: pin-compatible with MCP73831 (SOT-23-5)."""
    s = sexpr.flatten(lib("Battery_Management"), "MCP73831-2-OT", "Battery_Management")
    s[1] = Q("TP4054")
    names = {"1": "~{CHRG}", "2": "GND", "3": "BAT", "4": "VCC", "5": "PROG"}
    for p in find(s, "property"):
        if p[1] == "Value":
            p[2] = Q("TP4054")
        elif p[1] == "Datasheet":
            p[2] = Q("https://www.lcsc.com/search?q=TP4054")
        elif p[1] == "Description":
            p[2] = Q("Standalone linear Li-ion charger 4.2 V, 500 mA max, I = 1000 V / R_PROG, SOT-23-5")
    for unit in find(s, "symbol"):
        unit[1] = Q(unit[1].replace("MCP73831-2-OT", "TP4054").replace("Battery_Management:", ""))
        for p in find(unit, "pin"):
            first(p, "name")[1] = Q(names[first(p, "number")[1]])
            if first(p, "number")[1] == "1":
                p[1] = "open_collector"
    return s


KEYCHAIN = {"SIM800L_Red_Mini": sim800l_symbol(), "VBAT": vbat_symbol(lib("power")),
            "TP4054": tp4054_symbol()}
with open(os.path.join(HW, "keychain.kicad_sym"), "w") as f:
    f.write(sexpr.dump(["kicad_symbol_lib", ["version", 20241209],
                        ["generator", Q("gen_schematic.py")], ["generator_version", Q("10.0")]]
                       + list(KEYCHAIN.values())) + "\n")

S = schlib.Sheet(PROJECT, SCH, power=POWER, custom=KEYCHAIN)
place, text, box = S.place, S.text, S.box


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
box(15.24, 22.86, 137.16, 96.52, "A. USB-C input + LiPo charger (TP4054, ~213 mA)")
place("Connector:USB_C_Receptacle_PowerOnly_6P", "J1", "USB-C 6P", 33.02, 55.88, 0,
      "Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal",
      {"A9": "VBUS", "B9": "VBUS", "A5": "CC1", "B5": "CC2", "A12": "GND", "B12": "GND", "SH": "GND"})
res("R8", "5.1k", 63.5, 68.58, "CC1", "GND", lcsc="C25905")
res("R9", "5.1k", 71.12, 68.58, "CC2", "GND", lcsc="C25905")
cap("C3", "4.7uF", 78.74, 60.96, "VBUS", "GND")
place("keychain:TP4054", "U2", "TP4054", 106.68, 58.42, 0,
      "Package_TO_SOT_SMD:SOT-23-5",
      {"1": "CHRG", "2": "GND", "3": "VBAT", "4": "VBUS", "5": "PROG"}, nc=("1",),
      field_at={"Reference": (-10.16, -8.89), "Value": (-12.7, 10.16)})
res("R10", "4.7k", 91.44, 81.28, "PROG", "GND", lcsc="C25900")
cap("C4", "4.7uF", 132.08, 63.5, "VBAT", "GND")
text("I_chg = 1000 V / R10 = 213 mA (0.85 C for 250 mAh); TP4054 = MCP73831 pinout", 20.32, 91.44)
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
      {"8": "VBAT", "4": "GND", "5": "MCU_RX", "6": "MCU_TX", "7": "BTN", "2": "RST_DRV",
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
      {"2": "VBAT", "6": "GND", "4": "SIM_RXD", "5": "SIM_TXD", "3": "SIM_RST"},
      nc=("1", "12", "11", "7", "8", "9", "10"), field_at={"Value": (8.89, 16.51)})
res("R7", "1k", 266.7, 81.28, "RST_DRV", "SIM_RST", lcsc="C11702")
res("R1", "1k", 228.6, 71.12, "SIM_TXD", "MCU_RX", lcsc="C11702")
res("R2", "47k", 241.3, 71.12, "MCU_TX", "SIM_RXD", lcsc="C25792")
res("R3", "100k", 254.0, 71.12, "SIM_RXD", "GND", lcsc="C25741")
text("R1: isolates SIM TXD from ISP MOSI", 218.44, 91.44)
text("R2/R3: 4.2 V -> 2.86 V (2.8 V logic)", 218.44, 93.98)
text("DTR/RING unused: AT+CSCLK=2 sleep, data buffered by AT+CIPRXGET", 218.44, 33.02)
text("PB3 -> R7 -> RST: open-drain hard reset of a hung modem (never drive high)", 218.44, 88.9)

# ============================================================ BLOCK E: motor + LED
box(142.24, 101.6, 289.56, 157.48, "E. Vibration motor + heart LED driver (shared PB4 PWM)")
res("R4", "100R", 160.02, 129.54, "DRV", "GATE", lcsc="C25076")
res("R5", "100k", 172.72, 137.16, "GATE", "GND", lcsc="C25741")
place("Transistor_FET:AO3400A", "Q1", "AO3400A", 190.5, 132.08, 0, "Package_TO_SOT_SMD:SOT-23",
      {"1": "GATE", "2": "GND", "3": "MOT_N"})   # ~50 mOhm: motor + 14 LEDs, no dimming
place("Device:D", "D1", "1N4148WT", 218.44, 119.38, 0, "Diode_SMD:D_SOD-523",
      {"1": "VBAT", "2": "MOT_N"})
tp("HT1", "HEART+", 223.52, 132.08, "VBAT", 1.0, rot=180)
tp("HT2", "HEART-", 233.68, 142.24, "MOT_N", 1.0)
text("HT1/HT2 -> heart perfboard (+ / -)", 215.9, 149.86)
place("Motor:Motor_DC", "MOT1", "0820 motor", 254.0, 127.0, 0, "",
      {"1": "VBAT", "2": "MOT_N"}, on_board=False, in_bom=False)
tp("MT1", "MOT+", 271.78, 119.38, "VBAT", 1.0, rot=180)
tp("MT2", "MOT-", 281.94, 134.62, "MOT_N", 1.0)
text("MOT1 is off-board, wired to pads MT1/MT2.  D1 = flyback.", 144.78, 151.13)
text("Heart perfboard: 10 x 3 mm LEDs, one resistor each (enclosure/heart_perfboard.py), parallel to the motor.", 144.78, 153.67)

# ------------------------------------------------------------ write
S.write("GSM touch keychain - carrier board",
        ["SIM800L red mini + ATtiny85 + MCP73831, 25.2 x 23 mm",
         "Generated by hardware/scripts/gen_schematic.py - edit the script, not this file"],
        os.path.join(HW, "sch_uuids.json"))
schlib.write_lib_tables(HW, "keychain.kicad_sym", "keychain.pretty")
print("schematic:", SCH, "symbols:", len(S.uuids))
