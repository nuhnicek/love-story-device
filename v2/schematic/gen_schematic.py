"""
Schematic for keychain v2: Seeed XIAO ESP32-C3 + SIM800L red mini + 802530 LiPo,
wired point-to-point (no custom PCB). Writes keychain-v2.kicad_sch next to this script.

  python3 v2/schematic/gen_schematic.py
  (then: kicad-cli sch erc / sch export pdf, see v2/README.md)

Reuses the tiny schematic writer from hardware/scripts (schlib.py, sexpr.py).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "hardware", "scripts"))

import schlib  # noqa: E402
import sexpr  # noqa: E402
from schlib import font, prop  # noqa: E402
from sexpr import Q  # noqa: E402

PROJECT = "keychain-v2"
SCH = os.path.join(HERE, PROJECT + ".kicad_sch")


def pin(t, x, y, ang, name, num):
    return ["pin", t, "line", ["at", x, y, ang], ["length", 2.54],
            ["name", Q(name), font()], ["number", Q(num), font()]]


def xiao_symbol():
    """XIAO ESP32-C3, top-view pin numbers 1-14 + BAT+/BAT- pads on the underside."""
    left = [("1", "D0/IO2"), ("2", "D1/IO3"), ("3", "D2/IO4"), ("4", "D3/IO5"),
            ("5", "D4/IO6"), ("6", "D5/IO7"), ("7", "D6/TX")]
    right = [("8", "D7/RX"), ("9", "D8/IO8"), ("10", "D9/IO9"), ("11", "D10/IO10")]
    body = ["symbol", Q("XIAO_ESP32C3_0_1"),
            ["rectangle", ["start", -10.16, 16.51], ["end", 10.16, -16.51],
             ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]]
    pins = ["symbol", Q("XIAO_ESP32C3_1_1")]
    for i, (n, nm) in enumerate(left):
        pins.append(pin("bidirectional", -12.7, 7.62 - i * 2.54, 0, nm, n))
    for i, (n, nm) in enumerate(right):
        pins.append(pin("bidirectional", 12.7, 7.62 - i * 2.54, 180, nm, n))
    pins.append(pin("power_out", -5.08, 19.05, 270, "5V", "14"))
    pins.append(pin("power_out", 0, 19.05, 270, "3V3", "12"))
    pins.append(pin("passive", 5.08, 19.05, 270, "BAT+", "15"))
    pins.append(pin("power_in", -2.54, -19.05, 90, "GND", "13"))
    pins.append(pin("passive", 2.54, -19.05, 90, "BAT-", "16"))
    return ["symbol", Q("XIAO_ESP32C3"), ["pin_names", ["offset", 1.016]],
            ["exclude_from_sim", "no"], ["in_bom", "yes"], ["on_board", "yes"],
            prop("Reference", "U", 6.35, 20.32), prop("Value", "XIAO_ESP32C3", 6.35, -20.32),
            prop("Footprint", "", 0, 0, True),
            prop("Datasheet", "https://wiki.seeedstudio.com/XIAO_ESP32C3_Getting_Started/", 0, 0, True),
            prop("Description", "Seeed Studio XIAO ESP32-C3, 21 x 17.8 mm, USB-C, LiPo charger "
                 "(380 mA); BAT+/BAT- are pads on the underside", 0, 0, True),
            body, pins]


v1 = sexpr.load_library(os.path.join(ROOT, "hardware", "keychain.kicad_sym"))
CUSTOM = {"XIAO_ESP32C3": xiao_symbol(), "SIM800L_Red_Mini": v1["SIM800L_Red_Mini"],
          "VBAT": v1["VBAT"]}
for s in CUSTOM.values():
    for p in sexpr.find(s, "property"):
        if p[1] == "Footprint":
            p[2] = Q("")
with open(os.path.join(HERE, PROJECT + ".kicad_sym"), "w") as f:
    f.write(sexpr.dump(["kicad_symbol_lib", ["version", 20241209],
                        ["generator", Q("gen_schematic.py")], ["generator_version", Q("10.0")]]
                       + list(CUSTOM.values())) + "\n")

S = schlib.Sheet(PROJECT, SCH, power={"GND": "power:GND", "VBAT": "keychain:VBAT"},
                 custom=CUSTOM, seed="3f1d9b72-5c0e-4a8b-9d26-7e41c3a5b8f0")
place, text, box = S.place, S.text, S.box


def res(ref, val, x, y, n1, n2):
    place("Device:R", ref, val, x, y, 0, "", {"1": n1, "2": n2})


# ============================================================ A: battery + buffer
box(15.24, 22.86, 96.52, 101.6, "A. LiPo 802530 + SIM800L supply buffer")
place("Device:Battery_Cell", "BT1", "LiPo 802530 + PCM", 30.48, 55.88, 0, "",
      {"1": "VBAT", "2": "GND"}, field_at={"Value": (3.81, 2.54)})
place("Device:C_Polarized", "C1", "470uF 6.3V polymer", 60.96, 55.88, 0, "",
      {"1": "VBAT", "2": "GND"}, field_at={"Value": (2.54, 1.27)})
place("power:PWR_FLAG", "#FLG01", "PWR_FLAG", 86.36, 40.64, 180, "", {"1": "VBAT"})
place("power:PWR_FLAG", "#FLG02", "PWR_FLAG", 86.36, 71.12, 0, "", {"1": "GND"})
text("BT1: 3.7 V pouch cell WITH protection board,", 20.32, 76.2)
text("  8 x 25 x 30 mm, ~500 mAh (PCM inside the 30 mm)", 20.32, 78.74)
text("C1: polymer tantalum 7343 (e.g. KEMET T520D477M006),", 20.32, 83.82)
text("  wired right at the SIM800L VCC/GND pins: 2 A bursts", 20.32, 86.36)
text("Battery -> SIM800L: short, thick wires (26 AWG)", 20.32, 91.44)
text("SIM800L VCC max 4.4 V: never connect it to 5V", 20.32, 93.98)

# ============================================================ B: XIAO
box(101.6, 22.86, 190.5, 101.6, "B. XIAO ESP32-C3 (MCU + USB-C + 380 mA charger)")
place("keychain:XIAO_ESP32C3", "U1", "XIAO ESP32-C3", 157.48, 55.88, 0, "",
      {"2": "BTN", "3": "VBAT_SENSE", "4": "SIM_RI", "5": "DRV", "6": "RST_DRV",
       "7": "MCU_TX", "8": "MCU_RX", "15": "VBAT", "16": "GND", "13": "GND"},
      nc=("1", "9", "10", "11", "12", "14"),
      field_at={"Reference": (20.32, 17.78), "Value": (20.32, 20.32)})
place("Switch:SW_Push", "SW1", "Tact 3x6x4.3", 111.76, 50.8, 0, "", {"1": "BTN", "2": "GND"})
res("R6", "220k", 134.62, 76.2, "VBAT", "VBAT_SENSE")
res("R7", "220k", 114.3, 76.2, "VBAT_SENSE", "GND")
place("Device:C", "C2", "100nF", 124.46, 76.2, 0, "", {"1": "VBAT_SENSE", "2": "GND"})
text("Deep-sleep wake: D1 (button),", 104.14, 30.48)
text("  D3 (modem RI), both active low", 104.14, 33.02)
text("D0/D8/D9: boot strapping, left free", 104.14, 35.56)
text("R6/R7: VBAT/2 into A2 (~9.5 uA)", 104.14, 38.1)

# ============================================================ C: SIM800L
box(195.58, 22.86, 284.48, 101.6, "C. SIM800L red mini (2.8 V logic)")
place("keychain:SIM800L_Red_Mini", "M1", "SIM800L (M374C)", 261.62, 53.34, 0, "",
      {"2": "VBAT", "6": "GND", "4": "SIM_RXD", "5": "MCU_RX", "3": "SIM_RST", "12": "SIM_RI"},
      nc=("1", "11", "7", "8", "9", "10"), field_at={"Value": (8.89, 16.51)})
res("R1", "4.7k", 208.28, 71.12, "MCU_TX", "SIM_RXD")
res("R2", "15k", 220.98, 71.12, "SIM_RXD", "GND")
res("R3", "1k", 236.22, 71.12, "RST_DRV", "SIM_RST")
text("R1/R2: 3.3 V -> 2.5 V into SIM800L RXD", 198.12, 91.44)
text("TXD and RING (2.8 V) go straight to D7 / D3", 198.12, 93.98)
text("R3: D5 only ever pulls RST low", 198.12, 96.52)

# ============================================================ D: motor + heart
box(15.24, 106.68, 177.8, 162.56, "D. Vibration motor + heart LEDs (one PWM driver, D4)")
res("R4", "1k", 30.48, 129.54, "DRV", "BASE")
res("R5", "100k", 45.72, 129.54, "BASE", "GND")
place("Transistor_BJT:Q_NPN_CBE", "Q1", "BC337-40", 66.04, 129.54, 0, "",
      {"2": "BASE", "1": "MOT_N", "3": "GND"})
place("Device:D", "D1", "1N4148", 96.52, 124.46, 0, "", {"1": "VBAT", "2": "MOT_N"})
place("Motor:Motor_DC", "MOT1", "0820 coin motor", 121.92, 134.62, 0, "",
      {"1": "VBAT", "2": "MOT_N"})
res("R8", "470", 147.32, 129.54, "VBAT", "HEART_A")
place("Device:LED", "D2", "3 mm pink LED", 160.02, 142.24, 0, "",
      {"2": "HEART_A", "1": "MOT_N"})
text("R5 keeps Q1 off while the XIAO sleeps (its pins float). D1: flyback.", 20.32, 147.32)
text("D2 + R8: one of the 10 LED + resistor pairs, all in parallel on the heart perfboard", 20.32, 149.86)
text("  (enclosure/heart_perfboard.py). Motor and heart share Q1.", 20.32, 152.4)
text("Q1: motor ~80 mA + 10 LEDs ~40 mA", 20.32, 154.94)

# ============================================================ E: notes
box(182.88, 106.68, 284.48, 162.56, "E. Build notes")
for i, s in enumerate([
        "No custom PCB: modules + through-hole parts on wires.",
        "R1-R8, C2, Q1, D1 sit inline on the wires (heat-shrink)",
        "or on free perfboard holes; C1 at the SIM800L pins.",
        "",
        "Stack: battery | XIAO + switch + small parts | SIM800L",
        "| heart perfboard | lid (see v2/case)",
        "",
        "Unused: D0, D8-D10, 3V3, 5V. Battery only on BAT+/BAT-.",
        "Firmware must hold D6 (TX) high in deep sleep",
        "(gpio_hold), or the modem sees a break and wakes.",
        "Flash over USB-C before closing the case.",
]):
    text(s, 185.42, 116.84 + i * 2.54)

S.write("GSM touch keychain v2 - XIAO ESP32-C3 module version",
        ["XIAO ESP32-C3 + SIM800L red mini + 802530 LiPo, point-to-point wiring",
         "Generated by v2/schematic/gen_schematic.py - edit the script, not this file"],
        os.devnull)
with open(os.path.join(HERE, "sym-lib-table"), "w") as f:
    f.write('(sym_lib_table\n  (version 7)\n  (lib (name "keychain")(type "KiCad")'
            '(uri "${KIPRJMOD}/%s.kicad_sym")(options "")(descr "Project parts"))\n)\n' % PROJECT)
pro = os.path.join(HERE, PROJECT + ".kicad_pro")
if not os.path.exists(pro):
    with open(pro, "w") as f:
        json.dump({"meta": {"filename": PROJECT + ".kicad_pro", "version": 3}}, f, indent=2)
print("schematic:", SCH)
