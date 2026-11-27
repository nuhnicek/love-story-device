"""
v3 parts list (run with KiCad's bundled Python after build_pcb.py / route.py):
  v3/hardware/fab/keychain-v3-bom.csv   one line per value/footprint, with designators
  v3/hardware/BOM.md                    the same plus off-board parts and quantities for a pair
MPNs are suggestions; any equivalent part with the same footprint works.
"""
import collections
import csv
import os
import re

import pcbnew as pn

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(HW, "keychain-v3.kicad_pcb")

INFO = {
    "nRF9151-LACA": ("Nordic nRF9151 SiP: Cortex-M33 + LTE-M/NB-IoT modem + GNSS, LGA-80 12.1 x 11.1 mm",
                     "Nordic nRF9151-LACA (cut tape: nRF9151-LACA-R7)"),
    "TP4054": ("Li-ion/LiPo linear charger 4.2 V, SOT-23-5 (MCP73831 pinout), I = 1000 V / R3",
               "TP4054 (Nanjing Top Power) or MCP73832T-2ACI/OT (open-drain STAT; NOT the MCP73831, its STAT drives 5 V into the nRF9151)"),
    "XC6206P302MR": ("LDO 3.0 V 200 mA, Iq 1 uA, SOT-23 (VDD_GPIO)", "Torex XC6206P302MR"),
    "AO3400A": ("N-MOSFET 30 V 5.7 A, SOT-23 (motor + heart driver)", "AOS AO3400A"),
    "1N4148W": ("Switching diode, SOD-123 (motor flyback)", "Diodes 1N4148W-7-F"),
    "TPD4E05U06DQA": ("4-channel ESD array for the SIM lines, USON-10 2.5 x 1 mm",
                      "TI TPD4E05U06DQAR"),
    "USB-C 16P": ("USB-C receptacle, USB 2.0, 16 pin, top mount", "GCT USB4105-GF-A"),
    "CP2102N-A02-GQFN24": ("USB-UART bridge, QFN-24 4 x 4 (firmware updates + log over USB-C)",
                           "Silicon Labs CP2102N-A02-GQFN24R"),
    "DTC114E": ("Digital NPN 10k/10k, SOT-23 (USB auto-reset)", "Rohm DTC114EKAT146 or Nexperia PDTC114ET"),
    "WS2812B-2020": ("Addressable RGB LED 2.0 x 2.0 mm (heart)", "Worldsemi WS2812B-2020 or XL-2020RGBC-WS2812B"),
    "TPS22917DBV": ("Load switch 1-5.5 V, SOT-23-6 (LED power off when idle)", "TI TPS22917DBVR"),
    "SN74LV1T34DBV": ("Single buffer / level shifter, SOT-23-5 (LED data 3.0 V -> VLED)", "TI SN74LV1T34DBVR"),
    "22.1k": ("Resistor 22.1 k 1% 0402 (VBUS sense divider)", "UNI-ROYAL 0402WGF2212TCE"),
    "47.5k": ("Resistor 47.5 k 1% 0402 (VBUS sense divider)", "UNI-ROYAL 0402WGF4752TCE"),
    "330R": ("Resistor 330 R 1% 0402 (LED data line)", "UNI-ROYAL 0402WGF3300TCE"),
    "nano-SIM hinged": ("Nano-SIM holder, hinged, 6 contacts (bottom side)", "GCT SIM8060-6-0-14-00"),
    "U.FL": ("U.FL coaxial receptacle for the LTE antenna", "Hirose U.FL-R-SMT-1(10)"),
    "Side tact": ("Side-push tactile switch 3.5 x 2.9 mm", "Alps SKRTLAE010"),
    "22R@100MHz 6A": ("Ferrite bead 22 ohm @ 100 MHz, 6 A, 0805 (nRF9151 VDD)", "Murata BLM21PG220SN1D"),
    "DNP": ("Antenna tuning pad, NOT fitted (0402)", "-"),
    "WL-ICLED 2020": ("Addressable RGB LED 2.0 x 2.0 mm, WS2812 protocol, 3.3-5.5 V, 5.5 mA/colour (heart)",
                      "Wurth 1312020030000 (DigiKey 732-1312020030000CT-ND); alt. Dialight 587-1024-147F"),
}

# passives: description + MPN from value AND package (an 0402 footprint needs an 0402 part)
CAPS = {("100nF", "0402"): ("MLCC 100 nF 16 V X7R 0402", "Samsung CL05B104KO5NNNC"),
        ("100nF", "0603"): ("MLCC 100 nF 16 V X7R 0603", "Samsung CL10B104KO8NNNC"),
        ("1uF", "0402"): ("MLCC 1 uF 25 V X5R 0402", "Samsung CL05A105KA5NNNC"),
        ("1uF", "0603"): ("MLCC 1 uF 16 V X5R 0603", "Samsung CL10A105KO8NNNC"),
        ("4.7uF", "0603"): ("MLCC 4.7 uF 10 V X5R 0603", "Samsung CL10A475KP8NNNC"),
        ("10uF", "0603"): ("MLCC 10 uF 10 V X5R 0603", "Samsung CL10A106KP8NNNC")}
RCODE = {"0R": "0000", "100R": "1000", "330R": "3300", "1k": "1001", "4.7k": "4701", "5.1k": "5101",
         "10k": "1002", "22.1k": "2212", "47.5k": "4752", "100k": "1003"}
ROLE = {"R1": "USB-C CC", "R2": "USB-C CC", "R3": "charge current: 4.7 k = 213 mA, 3.3 k = 300 mA",
        "R4": "ENABLE pull-up", "R5": "reset series", "R6": "antenna series", "R7": "motor gate",
        "R8": "gate pull-down", "R9": "VBUS sense divider", "R10": "VBUS sense divider",
        "R11": "CP2102N reset pull-up", "R12": "UART series", "R13": "UART series",
        "R15": "USB_DET divider", "R16": "USB_DET divider", "R17": "LED_EN pull-down", "R18": "LED data line"}


def passive(val, fpn, refs):
    size = re.search(r"_(0402|0603|0805)_", fpn)
    size = size.group(1) if size else ""
    if fpn.startswith("C_") and (val, size) in CAPS:
        return CAPS[(val, size)]
    if fpn.startswith("R_") and val in RCODE:
        roles = sorted({ROLE[r] for r in refs if r in ROLE})
        mpn = "UNI-ROYAL %s%s%s" % ("0402WGF" if size == "0402" else "0603WAF", RCODE[val],
                                    "TCE" if size == "0402" else "T5E")
        return ("Resistor %s 1%% %s (%s)" % (val, size, "; ".join(roles)), mpn)
    return None


OFFBOARD = [
    ("BAT+/BAT-", 2, "LiPo 3.7 V with protection PCM: 502025 (~200 mAh, 5 x 20 x 25) or 802530 (~500 mAh)"),
    ("J2", 2, "LTE flexible FPC antenna, 698-2200 MHz (B3/B8/B20), as large as the case allows; cable plug must be U.FL = IPEX MHF1 (NOT MHF4, which looks similar but is smaller)"),
    ("J3", 2, "1NCE IoT SIM, nano size (1.8 V capable)"),
    ("MOT+/-", 2, "0820 coin vibration motor, 3 V"),
]


def natkey(r):
    m = re.match(r"([A-Z]+)(\d+)", r)
    return (m.group(1), int(m.group(2))) if m else (r, 0)


board = pn.LoadBoard(PCB)
groups = collections.OrderedDict()
for fp in sorted(board.GetFootprints(), key=lambda f: natkey(f.GetReference())):
    if fp.GetAttributes() & pn.FP_EXCLUDE_FROM_BOM:
        continue
    key = (fp.GetValue(), str(fp.GetFPID().GetLibItemName()))
    g = groups.setdefault(key, {"refs": [], "side": set(), "dnp": fp.IsDNP()})
    g["refs"].append(fp.GetReference())
    g["side"].add("bottom" if fp.IsFlipped() else "top")

os.makedirs(os.path.join(HW, "fab"), exist_ok=True)
rows = []
for (val, fpn), g in groups.items():
    desc, mpn = passive(val, fpn, g["refs"]) or INFO.get(val, ("", ""))
    rows.append([val, ", ".join(g["refs"]), len(g["refs"]), fpn, "/".join(sorted(g["side"])),
                 "DNP" if g["dnp"] else "", desc, mpn])
with open(os.path.join(HW, "fab", "keychain-v3-bom.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Value", "Designators", "Qty/board", "Footprint", "Side", "Fit", "Description", "Suggested MPN"])
    w.writerows(rows)

md = ["# keychain v3: parts list", "",
      "Generated by `scripts/bom.py` from the board. Quantities are per board; **order for 3 boards**",
      "(a pair + one spare) and extra passives, they get lost under tweezers.", "",
      "| Designators | Qty | Value | Package | Side | Description | Suggested MPN |",
      "|---|---|---|---|---|---|---|"]
for val, refs, n, fpn, side, fit, desc, mpn in rows:
    pkg = re.sub(r"_\d+Metric|_HandSolder", "", fpn)
    md.append("| %s | %d | %s%s | %s | %s | %s | %s |" % (refs, n, val, " (not fitted)" if fit else "",
                                                       pkg, side, desc, mpn))
md += ["", "## Off-board parts (per pair)", "", "| Connects to | Qty | Part |", "|---|---|---|"]
md += ["| %s | %d | %s |" % o for o in OFFBOARD]
md += ["", "Pads on the bottom side: BAT+/-, MOT+/- (wires), SWD (CK, IO, RST, VT, GND; first flash, see",
       "../PROGRAMMING.md) and 12 labelled test pads (see ../TESTING.md). Firmware updates and the log go over USB-C.", ""]
with open(os.path.join(HW, "BOM.md"), "w") as f:
    f.write("\n".join(md))
print("BOM:", len(rows), "lines,", sum(r[2] for r in rows), "parts per board")
