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
box(15.24, 20.32, 142.24, 96.52, "A. USB-C (power + data) + LiPo charger (TP4054)")
place("Connector:USB_C_Receptacle_USB2.0_16P", "J1", "USB-C 16P", 33.02, 53.34, 0,
      "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
      {"A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS", "A1": "GND", "A12": "GND",
       "B1": "GND", "B12": "GND", "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP",
       "A7": "USB_DM", "B7": "USB_DM", "SH": "GND"}, nc=("A8", "B8"),
      field_at={"Reference": (0, -27.94), "Value": (0, -25.4)})
res("R1", "5.1k", 63.5, 68.58, "CC1", "GND", fp=FP_R04)
res("R2", "5.1k", 71.12, 68.58, "CC2", "GND", fp=FP_R04)
cap("C1", "4.7uF", 81.28, 60.96, "VBUS", "GND")
place("keychain:TP4054", "U2", "TP4054", 109.22, 58.42, 0, "Package_TO_SOT_SMD:SOT-23-5",
      {"2": "GND", "3": "VBAT", "4": "VBUS", "5": "PROG"}, nc=("1",),
      field_at={"Reference": (-10.16, -8.89), "Value": (-12.7, 10.16)})
res("R3", "4.7k", 93.98, 73.66, "PROG", "GND", fp=FP_R04)
cap("C2", "4.7uF", 134.62, 63.5, "VBAT", "GND")
place("power:PWR_FLAG", "#FLG01", "PWR_FLAG", 127.0, 30.48, 180, "", {"1": "VBUS"})
text("I_chg = 1000 V / R3: 4.7k = 213 mA (200-500 mAh cells), 3.3k = 300 mA (>= 300 mAh)", 20.32, 88.9)
text("CHRG not used: firmware sees USB_DET + battery voltage. Alternative part: MCP73832 (not MCP73831)", 20.32, 91.44)

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
           "62": "DRV", "49": "BTN", "11": "UART_TX", "12": "UART_RX",
           "50": "USB_DET", "63": "LED_DATA3V", "80": "LED_EN"}
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
text("P0.05 motor, P0.30 BTN, P0.31 USB_DET, P0.24/25 UART, P0.06 LED data, P0.19 LED_EN", 149.86, 248.92)

# ============================================================ D: SIM
box(15.24, 185.42, 142.24, 251.46, "D. Nano-SIM (1.8 V class C) + UICC ESD")
place("Connector:SIM_Card_Shielded", "J3", "nano-SIM hinged", 109.22, 220.98, 0,
      "Connector_Card:nanoSIM_GCT_SIM8060-6-0-14-00",
      {"1": "SIM_1V8", "2": "SIM_RST", "3": "SIM_CLK", "5": "GND", "7": "SIM_IO", "SH": "GND"}, nc=("6",),
      field_at={"Reference": (-5.08, -12.7), "Value": (-5.08, 12.7)})
place("Power_Protection:TPD4E05U06DQA", "U4", "TPD4E05U06DQA", 53.34, 218.44, 0,
      "Package_SON:USON-10_2.5x1.0mm_P0.5mm",
      {"1": "SIM_RST", "2": "SIM_CLK", "4": "SIM_IO", "5": "SIM_1V8", "3": "GND", "8": "GND"},
      nc=("6", "7", "9", "10"))
cap("C13", "100nF", 81.28, 220.98, "SIM_1V8", "GND")
text("U4 + C13 right at the SIM holder contacts. 1NCE SIMs: 1.8 V / 3 V multi-class", 20.32, 243.84)
text("J3 and C13 are on the BOTTOM side (hand-soldered after reflow)", 20.32, 246.38)

# ============================================================ E: antenna
box(271.78, 20.32, 403.86, 76.2, "E. LTE antenna: 50 ohm, U.FL")
place("Device:C", "C14", "DNP", 299.72, 50.8, 0, "keychain:C_0402_NoPaste", {"1": "LTE_ANT0", "2": "GND"}, dnp=True)
res("R6", "0R", 314.96, 40.64, "LTE_ANT0", "LTE_ANT", fp=FP_R04, rot=90)
place("Device:C", "C15", "DNP", 330.2, 50.8, 0, "keychain:C_0402_NoPaste", {"1": "LTE_ANT", "2": "GND"}, dnp=True)
place("Connector:Conn_Coaxial", "J2", "U.FL", 355.6, 40.64, 0,
      "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", {"1": "LTE_ANT", "2": "GND"})
text("Pi network for antenna tuning: R6 0R, C14/C15 not fitted", 274.32, 66.04)
text("Antenna: flexible LTE FPC with U.FL (700-2200 MHz, B3/B8/B20)", 274.32, 68.58)
text("RF trace: 0.35 mm on L1 over L2 GND (JLC04101H-7628), short", 274.32, 71.12)

# ============================================================ F: motor, heart, button
box(271.78, 81.28, 403.86, 157.48, "F. Vibration motor, side button")
res("R7", "100R", 284.48, 111.76, "DRV", "GATE", rot=90)
res("R8", "100k", 297.18, 124.46, "GATE", "GND")
place("Transistor_FET:AO3400A", "Q1", "AO3400A", 317.5, 116.84, 0, "Package_TO_SOT_SMD:SOT-23",
      {"1": "GATE", "2": "GND", "3": "MOT_N"})
place("Device:D", "D1", "1N4148W", 345.44, 101.6, 0, "Diode_SMD:D_SOD-123",
      {"1": "VBAT", "2": "MOT_N"})
pad("TP3", "MOT+", 365.76, 104.14, "VBAT", rot=180)
pad("TP4", "MOT-", 375.92, 119.38, "MOT_N")
place("Switch:SW_Push", "SW1", "Side tact", 330.2, 142.24, 0,
      "Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010", {"1": "BTN", "2": "GND"})
text("Q1 drives the 0820 coin motor (wired to MOT+/-); D1 = flyback", 274.32, 152.4)
text("BTN: internal pull-up, GPIO sense wakes the nRF9151", 274.32, 154.94)

# ============================================================ G: debug pads
box(271.78, 162.56, 403.86, 238.76, "G. SWD pads (bottom side): first bootloader flash only")
for i, (ref, val, n) in enumerate([("TP7", "SWDIO", "SWDIO"), ("TP8", "SWDCLK", "SWDCLK"),
                                   ("TP9", "RST", "nRESET_PAD"), ("TP10", "VT", "+3V0"),
                                   ("TP11", "GND", "GND")]):
    pad(ref, val, 284.48 + i * 15.24, 195.58, n, 0.9, rot=180 if n != "GND" else 0)
text("Program with any SWD probe: J-Link, nRF91 DK, or a Pico debugprobe + pyOCD", 274.32, 220.98)
text("VT = 3.0 V target reference (do NOT power the board from the probe)", 274.32, 223.52)
text("After that: firmware + log over USB-C (block H)", 274.32, 226.06)

# ============================================================ H: USB-serial + auto reset
box(408.94, 20.32, 581.66, 205.74, "H. USB-serial (CP2102N): flashing + log over USB-C")
U5_NC = ("1", "10", "11", "12", "13", "14", "15", "16", "17", "18", "22", "24")
place("Interface_USB:CP2102N-Axx-xQFN24", "U5", "CP2102N-A02-GQFN24", 482.6, 104.14, 0,
      "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm",
      {"3": "USB_DP", "4": "USB_DM", "5": "V3U", "6": "V3U", "7": "VBUS", "8": "USB_VSNS",
       "9": "CP_RST", "2": "GND", "25": "GND", "19": "CP_RTS", "20": "CP_RXD", "21": "CP_TXD",
       "23": "CP_DTR"}, nc=U5_NC, field_at={"Reference": (17.78, -33.02), "Value": (17.78, -30.48)})
cap("C16", "1uF", 424.18, 45.72, "VBUS", "GND", fp=FP_C04)
cap("C17", "1uF", 436.88, 45.72, "V3U", "GND", fp=FP_C04)
cap("C18", "100nF", 449.58, 45.72, "V3U", "GND", fp=FP_C04)
place("power:PWR_FLAG", "#FLG04", "PWR_FLAG", 462.28, 38.1, 180, "", {"1": "V3U"})
res("R9", "22.1k", 424.18, 81.28, "VBUS", "USB_VSNS", fp=FP_R04)
res("R10", "47.5k", 424.18, 116.84, "USB_VSNS", "GND", fp=FP_R04)
res("R11", "10k", 436.88, 81.28, "V3U", "CP_RST", fp=FP_R04)
res("R12", "4.7k", 528.32, 60.96, "UART_TX", "CP_RXD", fp=FP_R04)
res("R13", "4.7k", 541.02, 60.96, "CP_TXD", "UART_RX", fp=FP_R04)
place("Transistor_BJT:DTC114E", "Q2", "DTC114E", 548.64, 142.24, 0, "Package_TO_SOT_SMD:SOT-23",
      {"1": "CP_DTR", "2": "CP_RTS", "3": "nRESET"})
res("R15", "100k", 449.58, 154.94, "VBUS", "USB_DET", fp=FP_R04)
res("R16", "100k", 462.28, 172.72, "USB_DET", "GND", fp=FP_R04)
for i, t in enumerate([
        "CP2102N runs only from USB (VREGIN = VBUS), its I/O at its own 3.3 V (VIO = VDD).",
        "R12/R13: 4.7k series to the nRF9151 UART. The firmware turns the UART off",
        "  when USB_DET is low, so nothing leaks into the unpowered CP2102N on battery.",
        "Q2 (digital NPN, 10k/10k inside) auto-reset: nRESET is pulled low only when DTR is high",
        "  and RTS is low. Idle (both high), port open (both low) and USB unplugged: no reset.",
        "Flash: MCUboot (installed once over SWD) waits ~0.5 s after reset for mcumgr",
        "  over this UART, so the PC can reset the board and upload new firmware.",
        "USB_DET (P0.31): VBUS/2, high while USB-C is plugged in"]):
    text(t, 411.48, 185.42 + i * 2.54)

# ============================================================ I: RGB heart
box(15.24, 259.08, 403.86, 386.08, "I. Heart: 10 addressable RGB LEDs (WS2812B-2020), switched off when idle")
place("Power_Management:TPS22917DBV", "U6", "TPS22917DBV", 43.18, 289.56, 0, "Package_TO_SOT_SMD:SOT-23-6",
      {"1": "VBAT", "2": "GND", "3": "LED_EN", "6": "VLED"}, nc=("4", "5"),
      field_at={"Reference": (0, -10.16), "Value": (0, 10.16)})
cap("C19", "1uF", 22.86, 292.1, "VBAT", "GND", fp=FP_C04)
res("R17", "100k", 25.4, 312.42, "LED_EN", "GND", fp=FP_R04)
cap("C20", "10uF", 68.58, 292.1, "VLED", "GND")
place("Logic_LevelTranslator:SN74LV1T34DBV", "U7", "SN74LV1T34DBV", 104.14, 292.1, 0, "Package_TO_SOT_SMD:SOT-23-5",
      {"2": "LED_DATA3V", "3": "GND", "4": "LED_DIN", "5": "VLED"}, nc=("1",),
      field_at={"Reference": (0, -10.16), "Value": (0, 10.16)})
cap("C21", "100nF", 124.46, 292.1, "VLED", "GND", fp=FP_C04)
res("R18", "330R", 139.7, 287.02, "LED_DIN", "LED_D0", fp=FP_R04, rot=90)
for i in range(10):
    x = 40.64 + i * 34.29
    place("LED:WS2812B-2020", "D%d" % (3 + i), "WS2812B-2020", x, 340.36, 0,
          "LED_SMD:LED_WS2812B-2020_PLCC4_2.0x2.0mm",
          {"4": "VLED", "2": "GND", "3": "LED_D%d" % i, "1": ("LED_D%d" % (i + 1)) if i < 9 else None},
          nc=() if i < 9 else ("1",), field_at={"Reference": (-5.08, -10.16), "Value": (0, 10.16)})
    cap("C%d" % (22 + i), "100nF", x + 15.24, 340.36, "VLED", "GND", fp=FP_C04)
for i, t in enumerate([
        "U6 (load switch) powers the LEDs only while they light: WS2812-type LEDs draw ~1 mA each even when dark.",
        "U7 lifts the 3.0 V data from P0.06 to the LED supply level (WS2812 needs 0.7 x VDD). R18 damps the line.",
        "LEDs run from the battery: full colour above ~3.6 V; the firmware dims / skips the heart below that.",
        "P0.19 = LED_EN (R17 keeps it off during reset), P0.06 = data. Zephyr: ws2812 driver over SPI or I2S."]):
    text(t, 20.32, 365.76 + i * 2.54)

S.write("GSM touch keychain v3 - nRF9151 LTE-M board",
        ["nRF9151 SiP + TP4054 charger + nano-SIM + U.FL, 4-layer 1.0 mm, hand assembly (stencil + hot plate)",
         "Generated by v3/hardware/scripts/gen_schematic.py - edit the script, not this file"],
        os.path.join(HW, "sch_uuids.json"), paper="A2")
schlib.write_lib_tables(HW, PROJECT + ".kicad_sym", "keychain.pretty")
pro = os.path.join(HW, PROJECT + ".kicad_pro")
if not os.path.exists(pro):
    with open(pro, "w") as f:
        json.dump({"meta": {"filename": PROJECT + ".kicad_pro", "version": 3}}, f, indent=2)
os.makedirs(os.path.join(HW, "keychain.pretty"), exist_ok=True)
print("schematic:", SCH, "symbols:", len(S.uuids))
