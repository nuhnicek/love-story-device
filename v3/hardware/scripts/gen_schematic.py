"""
Schematic for keychain v3: one custom board with the Nordic nRF9151 SiP
(MCU + LTE-M/NB-IoT modem), USB-C LiPo charger, nano-SIM, U.FL antenna,
motor/heart driver and a side button. Writes ../keychain-v3.kicad_sch.

  python3 v3/hardware/scripts/gen_schematic.py

nRF9151 support circuit follows Nordic's reference / the open-source Makerdiary
nRF9151 Connect Kit (CC BY-SA 4.0): ferrite + 10u/1u on VDD, 10k ENABLE pull-up,
4.7u DEC0, 100n + 4.7u VDD_GPIO, 1k + 100n on nRESET, UICC ESD on the SIM lines,
0R + 2x DNP pi network to the U.FL.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(HW))
sys.path.insert(0, os.path.join(ROOT, "hardware", "scripts"))

import schlib  # noqa: E402
import sexpr  # noqa: E402
from sexpr import Q  # noqa: E402

PROJECT = "keychain-v3"
SCH = os.path.join(HW, PROJECT + ".kicad_sch")

v1 = sexpr.load_library(os.path.join(ROOT, "hardware", "keychain.kicad_sym"))
CUSTOM = {"VBAT": v1["VBAT"], "TP4054": v1["TP4054"]}
with open(os.path.join(HW, PROJECT + ".kicad_sym"), "w") as f:
    f.write(sexpr.dump(["kicad_symbol_lib", ["version", 20241209],
                        ["generator", Q("gen_schematic.py")], ["generator_version", Q("10.0")]]
                       + list(CUSTOM.values())) + "\n")

POWER = {"GND": "power:GND", "VBAT": "keychain:VBAT", "VBUS": "power:VBUS", "+3V0": "power:+3V0"}
S = schlib.Sheet(PROJECT, SCH, power=POWER, custom=CUSTOM, seed="9b2e6c1a-4d7f-4e08-a3c5-1f6d8e2b7a90")
place, text, box = S.place, S.text, S.box

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_R04 = "Resistor_SMD:R_0402_1005Metric"
FP_C04 = "Capacitor_SMD:C_0402_1005Metric"


def res(ref, val, x, y, n1, n2, fp=FP_R, rot=0, **kw):
    place("Device:R", ref, val, x, y, rot, fp, {"1": n1, "2": n2}, **kw)


def cap(ref, val, x, y, n1, n2, fp=FP_C, rot=0, **kw):
    place("Device:C", ref, val, x, y, rot, fp, {"1": n1, "2": n2}, **kw)


def pad(ref, val, x, y, n, size=1.0, rot=0):
    place("Connector:TestPoint", ref, val, x, y, rot, "keychain:WirePad_%.1fmm" % size,
          {"1": n}, in_bom=False)


# ============================================================ A: USB-C + charger
box(15.24, 20.32, 142.24, 96.52, "A. USB-C + LiPo charger (TP4054)")
place("Connector:USB_C_Receptacle_PowerOnly_6P", "J1", "USB-C 6P", 33.02, 55.88, 0,
      "Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal",
      {"A9": "VBUS", "B9": "VBUS", "A5": "CC1", "B5": "CC2", "A12": "GND", "B12": "GND", "SH": "GND"})
res("R1", "5.1k", 63.5, 68.58, "CC1", "GND")
res("R2", "5.1k", 71.12, 68.58, "CC2", "GND")
cap("C1", "4.7uF", 81.28, 60.96, "VBUS", "GND")
place("keychain:TP4054", "U2", "TP4054", 109.22, 58.42, 0, "Package_TO_SOT_SMD:SOT-23-5",
      {"1": "CHRG", "2": "GND", "3": "VBAT", "4": "VBUS", "5": "PROG"},
      field_at={"Reference": (-10.16, -8.89), "Value": (-12.7, 10.16)})
res("R3", "4.7k", 93.98, 73.66, "PROG", "GND")
cap("C2", "4.7uF", 134.62, 63.5, "VBAT", "GND")
place("power:PWR_FLAG", "#FLG01", "PWR_FLAG", 127.0, 30.48, 180, "", {"1": "VBUS"})
text("I_chg = 1000 V / R3: 4.7k = 213 mA (200-500 mAh cells), 3.3k = 300 mA (>= 300 mAh)", 20.32, 88.9)
text("CHRG (open drain, low while charging) -> P0.09, so the firmware can show charging", 20.32, 91.44)

# ============================================================ B: battery, VDD, VDD_GPIO
box(15.24, 101.6, 142.24, 180.34, "B. Battery, nRF9151 supply, 3.0 V GPIO rail")
pad("TP1", "BAT+", 25.4, 124.46, "VBAT", 1.5, rot=180)
pad("TP2", "BAT-", 25.4, 144.78, "GND", 1.5)
place("power:PWR_FLAG", "#FLG02", "PWR_FLAG", 35.56, 144.78, 0, "", {"1": "GND"})
cap("C3", "10uF", 45.72, 134.62, "VBAT", "GND")
cap("C4", "1uF", 55.88, 134.62, "VBAT", "GND")
place("Device:FerriteBead", "FB1", "22R@100MHz 6A", 71.12, 121.92, 90,
      "Inductor_SMD:L_0805_2012Metric", {"1": "VBAT", "2": "VDD_NRF"},
      field_at={"Reference": (0, -3.81), "Value": (0, 3.81)})
cap("C5", "10uF", 86.36, 134.62, "VDD_NRF", "GND")
cap("C6", "1uF", 96.52, 134.62, "VDD_NRF", "GND")
place("power:PWR_FLAG", "#FLG03", "PWR_FLAG", 111.76, 116.84, 180, "", {"1": "VDD_NRF"})
place("Regulator_Linear:XC6206PxxxMR", "U3", "XC6206P302MR", 119.38, 157.48, 0,
      "Package_TO_SOT_SMD:SOT-23-3", {"3": "VBAT", "2": "+3V0", "1": "GND"},
      field_at={"Reference": (0, -7.62), "Value": (0, 7.62)})
cap("C7", "1uF", 104.14, 160.02, "VBAT", "GND")
cap("C8", "1uF", 134.62, 160.02, "+3V0", "GND")
text("Battery straight to nRF9151 VDD (3.0-5.5 V) through FB1; no regulator needed", 20.32, 170.18)
text("U3: 3.0 V for VDD_GPIO (Iq ~1 uA). It follows VDD up/down, as the nRF9151 requires", 20.32, 172.72)
text("Battery voltage: read by the modem (AT%XVBAT), no divider", 20.32, 175.26)

# ============================================================ C: nRF9151
box(147.32, 20.32, 266.7, 251.46, "C. nRF9151 SiP (Cortex-M33 + LTE-M/NB-IoT modem)")
U1_NETS = {"14": "VDD_NRF", "10": "ENABLE", "24": "DEC0", "65": "+3V0",
           "3": "SWDCLK", "4": "SWDIO", "9": "nRESET",
           "16": "SIM_RST", "17": "SIM_IO", "18": "SIM_CLK", "19": "SIM_1V8",
           "35": "LTE_ANT0",
           "62": "DRV", "67": "BTN", "68": "CHRG", "70": "UART_TX", "72": "UART_RX"}
U1_GND = ["1", "7", "13", "15", "20", "25", "30", "34", "36", "38", "39", "40", "41", "43",
          "46", "51", "55", "60", "66", "71", "76"] + [str(n) for n in range(105, 114)]
for g in U1_GND:
    U1_NETS[g] = "GND"
u1_sym = sexpr.flatten(schlib.stock("MCU_Nordic"), "nRF9151-LAxx", "MCU_Nordic")
U1_NC = sorted({p[0] for p in sexpr.pins(u1_sym)} - set(U1_NETS))
place("MCU_Nordic:nRF9151-LAxx", "U1", "nRF9151-LACA", 205.74, 132.08, 0,
      "Package_LGA:Nordic_nRF9151-LAxx_LGA-80-33EP_12.1x11.1mm_P0.5mm", U1_NETS, nc=U1_NC,
      field_at={"Reference": (30.48, -58.42), "Value": (30.48, -55.88)})
res("R4", "10k", 162.56, 50.8, "VDD_NRF", "ENABLE")
cap("C9", "4.7uF", 175.26, 50.8, "DEC0", "GND")
cap("C10", "100nF", 238.76, 50.8, "+3V0", "GND")
cap("C11", "4.7uF", 251.46, 50.8, "+3V0", "GND")
res("R5", "1k", 162.56, 220.98, "nRESET_PAD", "nRESET")
cap("C12", "100nF", 175.26, 220.98, "nRESET", "GND")
text("ENABLE pulled up: always on. nRESET: no external pull-up (internal 13k)", 149.86, 246.38)
text("P0.05 DRV (PWM), P0.08 BTN, P0.09 CHRG, P0.11/P0.12 UART (Zephyr default)", 149.86, 248.92)

# ============================================================ D: SIM
box(15.24, 185.42, 142.24, 251.46, "D. Nano-SIM (1.8 V class C) + UICC ESD")
place("Connector:SIM_Card_Shielded", "J3", "nano-SIM hinged", 109.22, 220.98, 0,
      "Connector_Card:nanoSIM_GCT_SIM8060-6-0-14-00",
      {"1": "SIM_1V8", "2": "SIM_RST", "3": "SIM_CLK", "5": "GND", "7": "SIM_IO", "SH": "GND"}, nc=("6",),
      field_at={"Reference": (-5.08, -12.7), "Value": (-5.08, 12.7)})
place("Power_Protection:TPD4E05U06DQA", "U4", "TPD4E05U06DQA", 53.34, 218.44, 0,
      "Package_SON:USON-10_2.5x1.0mm_P0.5mm",
      {"5": "SIM_RST", "4": "SIM_IO", "2": "SIM_CLK", "1": "SIM_1V8", "3": "GND", "8": "GND"},
      nc=("6", "7", "9", "10"))
cap("C13", "100nF", 81.28, 220.98, "SIM_1V8", "GND")
text("U4 + C13 right at the SIM holder. 1NCE SIMs: 1.8 V / 3 V multi-class", 20.32, 243.84)
text("J3 is on the BOTTOM side (hand-soldered after reflow)", 20.32, 246.38)

# ============================================================ E: antenna
box(271.78, 20.32, 403.86, 76.2, "E. LTE antenna: 50 ohm, U.FL")
place("Device:C", "C14", "DNP", 299.72, 50.8, 0, FP_C04, {"1": "LTE_ANT0", "2": "GND"}, dnp=True)
res("R6", "0R", 314.96, 40.64, "LTE_ANT0", "LTE_ANT", fp=FP_R04, rot=90)
place("Device:C", "C15", "DNP", 330.2, 50.8, 0, FP_C04, {"1": "LTE_ANT", "2": "GND"}, dnp=True)
place("Connector:Conn_Coaxial", "J2", "U.FL", 355.6, 40.64, 0,
      "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", {"1": "LTE_ANT", "2": "GND"})
text("Pi network for antenna tuning: R6 0R, C14/C15 not fitted", 274.32, 66.04)
text("Antenna: flexible LTE FPC with U.FL (700-2200 MHz, B3/B8/B20)", 274.32, 68.58)
text("RF trace: 0.35 mm on L1 over L2 GND (JLC04101H-7628), short", 274.32, 71.12)

# ============================================================ F: motor, heart, button
box(271.78, 81.28, 403.86, 157.48, "F. Vibration motor + heart LEDs, side button")
res("R7", "100R", 284.48, 111.76, "DRV", "GATE", rot=90)
res("R8", "100k", 297.18, 124.46, "GATE", "GND")
place("Transistor_FET:AO3400A", "Q1", "AO3400A", 317.5, 116.84, 0, "Package_TO_SOT_SMD:SOT-23",
      {"1": "GATE", "2": "GND", "3": "MOT_N"})
place("Device:D", "D1", "1N4148W", 345.44, 101.6, 0, "Diode_SMD:D_SOD-123",
      {"1": "VBAT", "2": "MOT_N"})
pad("TP3", "MOT+", 365.76, 104.14, "VBAT", rot=180)
pad("TP4", "MOT-", 375.92, 119.38, "MOT_N")
pad("TP5", "HEART+", 383.54, 104.14, "VBAT", rot=180)
pad("TP6", "HEART-", 393.7, 119.38, "MOT_N")
place("Switch:SW_Push", "SW1", "Side tact", 330.2, 142.24, 0,
      "Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010", {"1": "BTN", "2": "GND"})
text("Motor and heart perfboard (10 LEDs + resistors, v1) share Q1; D1 = flyback", 274.32, 152.4)
text("BTN: internal pull-up, GPIO sense wakes the nRF9151", 274.32, 154.94)

# ============================================================ G: debug pads
box(271.78, 162.56, 403.86, 238.76, "G. SWD programming + UART log pads (bottom side)")
for i, (ref, val, n) in enumerate([("TP7", "SWDIO", "SWDIO"), ("TP8", "SWDCLK", "SWDCLK"),
                                   ("TP9", "RST", "nRESET_PAD"), ("TP10", "VT", "+3V0"),
                                   ("TP11", "GND", "GND"), ("TP12", "TX", "UART_TX"),
                                   ("TP13", "RX", "UART_RX")]):
    pad(ref, val, 284.48 + i * 15.24, 195.58, n, 0.9, rot=180 if n != "GND" else 0)
text("Program with any SWD probe: J-Link, nRF91 DK, or a Pico debugprobe + pyOCD", 274.32, 220.98)
text("VT = 3.0 V target reference (do NOT power the board from the probe)", 274.32, 223.52)
text("TX/RX: 3.0 V UART log, 115200 8N1", 274.32, 226.06)

S.write("GSM touch keychain v3 - nRF9151 LTE-M board",
        ["nRF9151 SiP + TP4054 charger + nano-SIM + U.FL, 4-layer 1.0 mm, hand assembly (stencil + hot plate)",
         "Generated by v3/hardware/scripts/gen_schematic.py - edit the script, not this file"],
        os.path.join(HW, "sch_uuids.json"), paper="A3")
schlib.write_lib_tables(HW, PROJECT + ".kicad_sym", "keychain.pretty")
pro = os.path.join(HW, PROJECT + ".kicad_pro")
if not os.path.exists(pro):
    with open(pro, "w") as f:
        json.dump({"meta": {"filename": PROJECT + ".kicad_pro", "version": 3}}, f, indent=2)
os.makedirs(os.path.join(HW, "keychain.pretty"), exist_ok=True)
print("schematic:", SCH, "symbols:", len(S.uuids))
