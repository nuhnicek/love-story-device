# Cost estimate — one pair of keychains

Estimate from 2026-11-25. **Check the live JLCPCB quote**: upload the two gerber zips
plus the BOM/POS CSVs and it prices everything exactly. Currency: ~23 Kč per USD
(assumed; check the current rate).

## Option A: JLCPCB makes and assembles both boards (recommended)

Order 5 PCBs of each design (the minimum) and have **2 of each assembled**
("Economic PCBA", single side, which is why the heart has every part on its front).

| Item | Carrier | Heart | Notes |
|---|---|---|---|
| Bare PCBs (5 pcs, 2-layer, 0.8 mm) | ~$2–5 | ~$2–5 | $2 base price for ≤100×100 mm; the heart outline is just routed |
| PCBA setup + stencil | ~$9.50 | ~$9.50 | $8 setup + ~$1.50 stencil, per design |
| Extended-part feeder fees | ~$9–21 | ~$3–6 | ~$1.50–3 per *unique* non-basic part (carrier ≈ 6–7: ATtiny85, MCP73831, USB-C, side switch, polymer tantalum, diode; heart ≈ 2: pink LED, resistor array) |
| Components for 2 boards | ~$8–12 | ~$1–2 | ATtiny85 ≈ $1–1.5, polymer tantalum ≈ $1–2 and USB-C/switch ≈ $0.5 each, the rest are cents |
| **Subtotal** | **~$30–48** | **~$16–23** | |

| Order-level | |
|---|---|
| Shipping to CZ | ~$8–20 depending on speed |
| VAT 21 % | collected by JLCPCB at checkout (IOSS); a small EU customs duty may still apply since the July 2026 reform |
| **Total, both boards × 2 keychains** | **≈ $65–110 ≈ 1 500–2 500 Kč** |

Part availability decides the real number. If JLCPCB doesn't stock the Alps SKRT switch or
the GCT USB-C, pick their in-stock equivalent with the same land pattern, or hand-solder that
part.

## Option B: bare PCBs only, you solder everything

| Item | Cost |
|---|---|
| 5 + 5 bare PCBs + shipping | ~$10–20 |
| Parts from LCSC for 2–3 sets (+ shipping) | ~$20–35 |
| **Total** | **≈ 700–1 300 Kč** |

Cheaper, but you'd be hand-soldering 0402 parts, 4 × 0402 resistor arrays (0.5 mm pitch) and
0603 LEDs, which needs a fine iron or hot air, flux and a microscope or loupe.

## Off-board parts, per keychain (Czech retail, rough)

| Item | Approx. |
|---|---|
| SIM800L red mini module | 150–250 Kč |
| LiPo 250–300 mAh pouch with PCM | 100–150 Kč |
| 0820 coin vibration motor | 30–60 Kč |
| Prepaid SIM (2G) | 0–200 Kč (often comes with credit) |
| Wire, header pins | ~10 Kč |
| **Per keychain** | **≈ 300–650 Kč** → **pair ≈ 600–1 300 Kč** |

## Total for the pair

| | |
|---|---|
| Option A (assembled) + off-board parts | **≈ 2 100–3 800 Kč** |
| Option B (DIY solder) + off-board parts | **≈ 1 300–2 600 Kč** |

Plus the 3D-printed enclosures (a few grams of filament).

## Running cost

- **Missed-call ping (short press):** free. The other keychain rejects the call with `ATH`
  before it is answered, so no call is billed.
- **SMS tap patterns (long press):** your operator's SMS price for each pattern sent, typically
  ~1–2.5 Kč on Czech prepaid tariffs (check yours). Some prepaid SIMs expire unless topped up
  or used every few months.
