# Parts list: keychain v2 (XIAO ESP32-C3 + SIM800L, no custom PCB)

These quantities are for **one pair**, and include spares where parts come in packs or are easy
to lose. The prices are rough estimates from 2026-11-25 (~25 Kč/EUR, ~23 Kč/USD), not quotes.
Check the shop before ordering.

## Modules and battery

| # | Part | Qty | Approx. each | Where | Notes |
|---|---|---|---|---|---|
| U1 | **Seeed XIAO ESP32-C3** | 2 | 150–200 Kč | openelab.io/cs, TME, RS, Seeed ($4.90) | Built-in LiPo charger at **380 mA**, so a full charge takes ~1.5–2 h. You don't need the antenna it comes with |
| M1 | **SIM800L "red mini"** GSM module (25 × 23 mm, with spring antenna) | 2 | 80–120 Kč (AliExpress), 200–250 Kč (CZ) | AliExpress, GME, Hadex | 2G only. Takes a **micro-SIM** |
| BT1 | **LiPo 802530**, 3.7 V, ~500 mAh, **with protection board (PCM)** | 2 | 100–150 Kč | GME, AliExpress | 8 × 25 × 30 mm **including** the PCM. Measure it: the case is made for exactly this size |
| — | **1NCE IoT SIM** (500 MB + 250 SMS / 10 years) | 2 | €12 ≈ 300 Kč | 1nce.com | Check whether they sell to private customers. Comes as a punch-out card; use the micro-SIM size |

## Electronics (all through-hole except C1)

| # | Part | Qty (pair) | Approx. | Notes |
|---|---|---|---|---|
| C1 | **470 µF 6.3 V polymer tantalum**, 7343 size (e.g. KEMET T520D477M006ATE025) | 2 | 30–40 Kč each | Soldered with 2 short wires straight onto the SIM800L VCC/GND pins. It covers the 2 A GSM bursts. **Don't use the cheap MnO₂ type** |
| C2 | 100 nF ceramic | 2 | 1 Kč | Battery-measurement filter |
| R1 | 4.7 kΩ | 2 | | TX divider (3.3 V → 2.5 V) |
| R2 | 15 kΩ | 2 | | TX divider |
| R3 | 1 kΩ | 2 | | Modem reset line |
| R4 | 1 kΩ | 2 | | Transistor base |
| R5 | 100 kΩ | 2 | | Keeps the motor off while the board sleeps |
| R6, R7 | 220 kΩ | 4 | | Battery voltage divider |
| R8 | 470 Ω (pink/white/blue LEDs) or 1 kΩ (red) | 20 + spares | | One per heart LED |
| | *All resistors: 1/8 W or mini 1/4 W metal film. A mixed kit (E12, 10 of each) costs ~100 Kč and covers everything* | | | |
| Q1 | BC337-40 NPN transistor | 2 (buy 5) | 2 Kč | Drives the motor + heart |
| D1 | 1N4148 diode | 2 (buy 5) | 1 Kč | Flyback across the motor |
| D2 | **3 mm LED**, pink (or any colour) | 20 + 5 spare | 2–3 Kč | Measure the height flange→dome: the case assumes 5.3 mm |
| SW1 | **Tact switch 3 × 6 × 4.3 mm, 2-pin** | 2 (buy 10) | 1–2 Kč | Lies on its side behind the XIAO. The case's flexing tab presses it |
| MOT1 | **0820 coin vibration motor**, 3 V | 2 (buy 5) | 10–20 Kč | 8 mm × 2 mm, with self-adhesive back |
| — | Perfboard 2.54 mm, single-sided | 1 small board | 20–40 Kč | Cut two 11 × 9-hole pieces (27.9 × 22.9 mm) |

## Wire, tape, filament

| Part | Approx. | Notes |
|---|---|---|
| Silicone wire 26 AWG, red + black (~1 m) | 30 Kč | Battery → SIM800L / XIAO / motor: carries the 2 A bursts |
| Kynar / wire-wrap wire 30 AWG (~5 m) | 50 Kč | All signal wires |
| Heat-shrink 1.5 mm + 2.5 mm | 30 Kč | Covers the resistors that sit inline on wires |
| Kapton tape + thin double-sided foam tape | 50 Kč | Insulation between layers; holds the battery and switch in place |
| PLA, ~17 g for 2 cases | 10 Kč | The tray can be one colour and the lid another |

## Rough total for the pair

| | Kč |
|---|---|
| 2 × XIAO ESP32-C3 | 300–400 |
| 2 × SIM800L | 160–500 |
| 2 × LiPo 802530 | 200–300 |
| 2 × 1NCE SIM | ~600 |
| Small parts (C1, kit, LEDs, switches, motors, perfboard) | 200–300 |
| Wire, tape, heat-shrink, PLA | ~150 |
| **Total** | **≈ 1 600–2 250 Kč** + shipping (cheapest if you combine orders: AliExpress for modules/LiPos, one Czech shop for the rest) |

Running cost: **0 Kč for 10 years** on 1NCE (expected ~15–20 MB/year per keychain), plus
whatever your server costs (any small VPS or home server).

## Tools

- Soldering iron with a fine tip, solder, flux; a multimeter.
- Calipers: measure the battery, XIAO, LEDs and switch before the final print.
- Optional: a USB-C power meter (checks the charge current and the mAh used per day).
- A 3D printer: the G-code is ready for an Ender-3 V2 / Pro.
