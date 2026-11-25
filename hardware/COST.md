# Cost estimate — one pair, self-assembled, 1NCE data SIMs

Estimate from 2026-11-25, assuming ~23 Kč/USD and ~25 Kč/EUR. Prices move, so get a live
JLCPCB quote (upload the two gerber zips) and an LCSC cart from `BOM.md` before ordering.

## Where the money goes, and what was cut

| Change | Saving | Quality impact |
|---|---|---|
| Charger MCP73831 → **TP4054** (pin-compatible, same 213 mA) | ~$0.45 per board | none: standard standalone Li-ion charger with thermal regulation |
| Q1 2N7002 → **AO3400A** | ~0 | better: no LED dimming |
| No SMT assembly, no stencil (hand solder) | ~$40–60 | you need flux, a fine tip, and patience for the 0.5 mm arrays |
| SIM800L, LiPo, motors from **AliExpress** instead of local shops | ~300–500 Kč | same Chinese modules; buy LiPos only with a built-in protection board |
| **1NCE SIM**: €12 once for 10 years (500 MB + 250 SMS) | no monthly fees | needs your relay server (included in `/server`) |

Kept on purpose: the **polymer** 470 µF tantalum (≈ $1–1.5), the SIM800L's 2 A burst buffer.
The cheap MnO₂ type can fail short on a 4.2 V cell. Also kept: per-LED resistors on the heart.

## One-time cost

| Item | Approx. |
|---|---|
| Carrier PCB × 5 + heart PCB × 5 (JLCPCB, 2-layer, 0.8 mm) | ~$4–8 |
| PCB shipping to CZ (one combined order, VAT collected at checkout) | ~$8–15 |
| Electronic parts from LCSC for **3 sets** (1 spare) | ~$12–20 |
| LCSC shipping to CZ (or choose "ship with JLCPCB order" if offered at checkout) | ~$0–20 |
| **Boards + electronics** | **≈ 550–1 450 Kč** |
| SIM800L red mini × 2 (AliExpress ~$3–5 each; Hadex/GM ~150–250 Kč) | ~150–500 Kč |
| LiPo 250–300 mAh with PCM × 2 (AliExpress ~$2–4) | ~100–300 Kč |
| 0820 coin motors (AliExpress 5–10 pack) | ~30–60 Kč |
| 1NCE SIM × 2 (€12 each, 10 years; shipping not included) | ~600 Kč |
| PLA for 2 cases (~6 g) | ~5 Kč |
| **Total for the pair** | **≈ 1 450–2 900 Kč**, the low end with AliExpress parts and combined shipping |

The fixed costs (shipping, PCB minimum order, 1NCE) are most of the bill. The ATtiny85 is
the single most expensive chip at ~$1–1.5. Swapping it would save under 100 Kč for the
pair but would need a different programmer, so it stays.

## Running cost

| | |
|---|---|
| SIM | **0 Kč for 10 years** with 1NCE, as long as you stay under 500 MB per SIM (expected ~15–20 MB/year each) |
| Server | your own server (Python, any small Linux box or VPS you already have) |

## Check before buying 1NCE

- **Private customers:** as far as I know, 1NCE has been business-only. Check their shop terms.
- **2G in Czechia:** the SIM800L is 2G-only, and 2G is being switched off across Europe.
- **SIM size:** the SIM800L takes a **micro-SIM**.
