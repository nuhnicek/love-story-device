"""
Schematic for the no-custom-PCB version: Seeed XIAO nRF52840 + SIM800L red mini,
wired point-to-point (KiCad 10 .kicad_sch, written to hardware/xiao/).

  python3 hardware/scripts/gen_schematic_xiao.py

The XIAO replaces the carrier PCB: it has the MCU, USB-C and the LiPo charger
(BQ25101, 50/100 mA) on board. Everything else is through-hole parts on wires.
"""
import json
import os

import schlib
import sexpr
from schlib import font, prop
from sexpr import Q

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
OUT = os.path.join(HW, "xiao")
PROJECT = "keychain-xiao"
SCH = os.path.join(OUT, PROJECT + ".kicad_sch")
os.makedirs(OUT, exist_ok=True)


def pin(t, x, y, ang, name, num):
    return ["pin", t, "line", ["at", x, y, ang], ["length", 2.54],
            ["name", Q(name), font()], ["number", Q(num), font()]]


def xiao_symbol():
    """XIAO nRF52840, top view numbering 1-14 + the two battery pads on the underside."""
    left = [("1", "D0/A0"), ("2", "D1/A1"), ("3", "D2/A2"), ("4", "D3/A3"),
            ("5", "D4/SDA"), ("6", "D5/SCL"), ("7", "D6/TX")]
    right = [("8", "D7/RX"), ("9", "D8/SCK"), ("10", "D9/MISO"), ("11", "D10/MOSI")]
    body = ["symbol", Q("XIAO_nRF52840_0_1"),
            ["rectangle", ["start", -10.16, 16.51], ["end", 10.16, -16.51],
             ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]]
    pins = ["symbol", Q("XIAO_nRF52840_1_1")]
    for i, (n, nm) in enumerate(left):
        pins.append(pin("bidirectional", -12.7, 7.62 - i * 2.54, 0, nm, n))
    for i, (n, nm) in enumerate(right):
        pins.append(pin("bidirectional", 12.7, 7.62 - i * 2.54, 180, nm, n))
    pins.append(pin("power_out", -5.08, 19.05, 270, "5V", "14"))
    pins.append(pin("power_out", 0, 19.05, 270, "3V3", "12"))
    pins.append(pin("passive", 5.08, 19.05, 270, "BAT+", "15"))
    pins.append(pin("power_in", -2.54, -19.05, 90, "GND", "13"))
    pins.append(pin("passive", 2.54, -19.05, 90, "BAT-", "16"))
    return ["symbol", Q("XIAO_nRF52840"), ["pin_names", ["offset", 1.016]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            prop("Reference", "U", 6.35, 20.32), prop("Value", "XIAO_nRF52840", 6.35, -20.32),
            prop("Footprint", "", 0, 0, True),
            prop("Datasheet", "https://wiki.seeedstudio.com/XIAO_BLE/", 0, 0, True),
            prop("Description", "Seeed Studio XIAO nRF52840, 21 x 17.8 mm, USB-C, BQ25101 LiPo charger; "
                 "BAT+/BAT- are pads on the underside", 0, 0, True),
            body, pins]


old = sexpr.load_library(os.path.join(HW, "keychain.kicad_sym"))
KEYCHAIN = {"XIAO_nRF52840": xiao_symbol(), "SIM800L_Red_Mini": old["SIM800L_Red_Mini"],
            "VBAT": old["VBAT"]}
for s in KEYCHAIN.values():
    for p in sexpr.find(s, "property"):
        if p[1] == "Footprint":
            p[2] = Q("")
with open(os.path.join(OUT, PROJECT + ".kicad_sym"), "w") as f:
    f.write(sexpr.dump(["kicad_symbol_lib", ["version", 20241209],
                        ["generator", Q("gen_schematic_xiao.py")], ["generator_version", Q("10.0")]]
                       + list(KEYCHAIN.values())) + "\n")

S = schlib.Sheet(PROJECT, SCH, power={"GND": "power:GND", "VBAT": "keychain:VBAT"},
                 custom=KEYCHAIN, seed="0c7a51f2-9a8e-4d1b-b8e3-58d1a0e6c4a7")
place, text, box = S.place, S.text, S.box


def res(ref, val, x, y, n1, n2, rot=0):
    place("Device:R", ref, val, x, y, rot, "", {"1": n1, "2": n2})


# ============================================================ A: battery + buffer
box(15.24, 22.86, 96.52, 101.6, "A. LiPo cell + SIM800L supply buffer")
place("Device:Battery_Cell", "BT1", "LiPo 1S + PCM", 30.48, 55.88, 0, "",
      {"1": "VBAT", "2": "GND"}, field_at={"Value": (3.81, 2.54)})
place("Device:C_Polarized", "C1", "470uF 6.3V polymer", 60.96, 55.88, 0, "",
      {"1": "VBAT", "2": "GND"}, field_at={"Value": (2.54, 1.27)})
place("power:PWR_FLAG", "#FLG01", "PWR_FLAG", 86.36, 40.64, 180, "", {"1": "VBAT"})
place("power:PWR_FLAG", "#FLG02", "PWR_FLAG", 86.36, 71.12, 0, "", {"1": "GND"})
text("BT1: pouch cell WITH protection board (PCM);", 20.32, 76.2)
text("  case is made for a 502025 cell", 20.32, 78.74)
text("  (5 x 20 x 25 mm, ~250 mAh)", 20.32, 81.28)
text("C1: right at the SIM800L VCC/GND pins;", 20.32, 86.36)
text("  takes the 2 A GSM bursts (else the modem resets)", 20.32, 88.9)
text("Battery -> SIM800L: short, thick wires (26 AWG+)", 20.32, 93.98)
text("SIM800L VCC max 4.4 V: never connect it to 5V", 20.32, 96.52)

# ============================================================ B: XIAO
box(101.6, 22.86, 190.5, 101.6, "B. XIAO nRF52840 (MCU + USB-C + charger)")
place("keychain:XIAO_nRF52840", "U1", "XIAO nRF52840", 157.48, 55.88, 0, "",
      {"2": "BTN", "3": "DRV", "7": "MCU_TX", "8": "MCU_RX", "9": "RST_DRV",
       "15": "VBAT", "16": "GND", "13": "GND"},
      nc=("1", "4", "5", "6", "10", "11", "12", "14"),
      field_at={"Reference": (20.32, 17.78), "Value": (20.32, 20.32)})
place("Switch:SW_Push", "SW1", "Side tact", 119.38, 86.36, 0, "", {"1": "BTN", "2": "GND"})
text("USB-C on the XIAO charges the LiPo (BQ25101):", 104.14, 33.02)
text("P0.13 LOW = 100 mA, floating = 50 mA", 104.14, 35.56)
text("Battery voltage: internal divider, P0.31 (P0.14 LOW)", 104.14, 93.98)
text("Serial1 = D6/D7 hardware UART to the modem", 104.14, 96.52)

# ============================================================ C: SIM800L
box(195.58, 22.86, 284.48, 101.6, "C. SIM800L red mini (2.8 V logic)")
place("keychain:SIM800L_Red_Mini", "M1", "SIM800L (M374C)", 261.62, 53.34, 0, "",
      {"2": "VBAT", "6": "GND", "4": "SIM_RXD", "5": "MCU_RX", "3": "SIM_RST"},
      nc=("1", "12", "11", "7", "8", "9", "10"), field_at={"Value": (8.89, 16.51)})
res("R1", "4.7k", 208.28, 71.12, "MCU_TX", "SIM_RXD")
res("R2", "15k", 220.98, 71.12, "SIM_RXD", "GND")
res("R3", "1k", 236.22, 71.12, "RST_DRV", "SIM_RST")
text("R1/R2: 3.3 V -> 2.5 V into SIM800L RXD", 198.12, 93.98)
text("R3: D8 pulls RST low (never driven high)", 198.12, 96.52)
text("TXD (2.8 V) goes straight to D7", 198.12, 91.44)

# ============================================================ D: motor + heart
box(15.24, 106.68, 177.8, 162.56, "D. Vibration motor + heart LEDs (one PWM driver, D2)")
res("R4", "1k", 38.1, 129.54, "DRV", "BASE")
place("Transistor_BJT:Q_NPN_CBE", "Q1", "BC337-40", 63.5, 129.54, 0, "",
      {"2": "BASE", "1": "MOT_N", "3": "GND"})
place("Device:D", "D1", "1N4148", 96.52, 124.46, 0, "", {"1": "VBAT", "2": "MOT_N"})
place("Motor:Motor_DC", "MOT1", "0820 coin motor", 121.92, 134.62, 0, "",
      {"1": "VBAT", "2": "MOT_N"})
res("R5", "470", 147.32, 129.54, "VBAT", "HEART_A")
place("Device:LED", "D2", "3 mm pink LED", 160.02, 142.24, 0, "",
      {"2": "HEART_A", "1": "MOT_N"})
text("D1: flyback across the motor", 20.32, 147.32)
text("D2 + R5: one of the 10 LED + resistor pairs, all in parallel on the heart perfboard", 20.32, 149.86)
text("  (enclosure/heart_perfboard.py). Motor and heart share the BC337 like the PCB version.", 20.32, 152.4)
text("Q1 base current ~2.5 mA: motor ~80 mA + 10 LEDs ~40 mA", 20.32, 154.94)

# ============================================================ E: notes
box(182.88, 106.68, 284.48, 162.56, "E. Build notes")
for i, s in enumerate([
        "No custom PCB: XIAO, SIM800L and the heart perfboard",
        "are joined with thin insulated wire; the resistors,",
        "Q1 and D1 sit on the heart perfboard.",
        "",
        "Stack in the case: battery | XIAO (USB-C at the",
        "case's USB end) | SIM800L | heart perfboard",
        "",
        "Unused pins: D0, D3-D5, D9, D10, 3V3, 5V",
        "Never feed 5V/3V3 from the battery: BAT+ only.",
        "Flash over USB-C before closing the case.",
]):
    text(s, 185.42, 116.84 + i * 2.54)

S.write("GSM touch keychain - XIAO nRF52840 module version",
        ["XIAO nRF52840 + SIM800L red mini, point-to-point wiring, no custom PCB",
         "Generated by hardware/scripts/gen_schematic_xiao.py - edit the script, not this file"],
        os.devnull)
with open(os.path.join(OUT, "sym-lib-table"), "w") as f:
    f.write('(sym_lib_table\n  (version 7)\n  (lib (name "keychain")(type "KiCad")'
            '(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "Project parts"))\n)\n' % PROJECT)
pro = os.path.join(OUT, PROJECT + ".kicad_pro")
if not os.path.exists(pro):
    with open(pro, "w") as f:
        json.dump({"meta": {"filename": PROJECT + ".kicad_pro", "version": 3}}, f, indent=2)
print("schematic:", SCH)
