# Cost estimate — one pair of keychains, self-assembled

Estimate from 2026-11-25, assuming ~23 Kč/USD and ~25 Kč/EUR. Prices move, so get the live
JLCPCB quote (upload the two gerber zips) and an LCSC cart from `BOM.md` before ordering.

## One-time cost (you solder and assemble)

| Item | Qty | Approx. |
|---|---|---|
| Carrier PCB, 2-layer 0.8 mm (JLCPCB) | 5 pcs | ~$2–4 |
| Heart PCB, 2-layer 0.8 mm (JLCPCB) | 5 pcs | ~$2–4 |
| PCB shipping to CZ (one combined order, incl. VAT via IOSS) | | ~$8–15 |
| Electronic parts from LCSC for **3 sets** (1 spare; tiny parts come in cut-tape minimums of 10–100) | | ~$15–25 |
| LCSC shipping to CZ | | ~$8–20 |
| *Optional:* SMT stencils for both boards (makes 0402s and the 0.5 mm resistor arrays far easier) | 2 | ~$7–15 |
| **Boards + parts** | | **≈ 800–1 300 Kč** (+ ~250 Kč with stencils) |

Most expensive parts per set: ATtiny85 ≈ $1–1.5, polymer tantalum ≈ $1–2, MCP73831 ≈ $0.5,
USB-C and side switch ≈ $0.2–0.5 each. The other ~30 parts are cents each.

| Off-board, per keychain (Czech retail) | Approx. |
|---|---|
| SIM800L red mini module | 150–250 Kč |
| LiPo 250–300 mAh pouch with protection PCM | 100–150 Kč |
| 0820 coin vibration motor | 30–60 Kč |
| Wire, header pins | ~10 Kč |
| **Per keychain** | **≈ 300–470 Kč → pair ≈ 600–950 Kč** |

**Hardware total for the pair: ≈ 1 400–2 250 Kč**, plus the SIM cards (below) and a few grams
of filament for the enclosures.

Tools assumed: fine-tip iron, flux, tweezers, solder wick, a loupe. A hot-air station or hot
plate helps a lot with the 0.5 mm-pitch resistor arrays and the USB-C.

## SIM cards: two options

| | A. Czech prepaid SIM (current design) | B. M2M data SIM, e.g. 1NCE |
|---|---|---|
| Price | ~0–200 Kč per SIM, then top-ups as your operator requires | **~€12 per SIM, one-time, for 10 years** (500 MB + 250 SMS) |
| Pair, 10 years | depends on tariff (top-ups / SMS fees) | **≈ 600 Kč total** |
| Voice calls | yes → free missed-call ping | **no** |
| SMS to the other keychain | yes (~1–2.5 Kč each) | **no**: 1NCE blocks SIM-to-SIM/P2P SMS; SMS only to/from their API |
| Server needed | **no**, the keychains call/text each other directly | **yes**: both keychains talk through an MQTT broker over GPRS |
| Hardware change | none | none (SIM800L does 2G GPRS/TCP) |
| Firmware | missed call + SMS (as planned) | MQTT over GPRS (different firmware) |
| Battery | best: SIM800L sleeps until a call/SMS arrives | a bit worse: a TCP keep-alive every few minutes keeps the connection open |

### How option B would work
- Each keychain opens a GPRS TCP connection to an MQTT broker. Use a free hosted tier (e.g.
  HiveMQ Cloud), or a Raspberry Pi / small VPS you run. Each keychain subscribes to its
  partner's topic.
- **Short press** publishes a "ping"; **long press** publishes the tap timings as a few bytes.
  The other keychain gets it within about a second, plays it, and goes back to sleep.
- **Data use** is tiny. A keep-alive every ~5 min is roughly 15–20 MB/year per keychain, and
  messages are a few hundred bytes each, so 500 MB lasts the 10 years.
- **Battery**: expect noticeably shorter life than option A because of the keep-alives.
  This is still to be measured; the keep-alive interval is the main setting to play with.

### Check before buying 1NCE
- That they sell to you as a private person. As far as I know, 1NCE has been business-only
  (B2B), so check their shop terms.
- That their SIM can use **2G in Czechia**. 1NCE lists 2G support, but the SIM800L is 2G-only,
  and 2G is being switched off across Europe.
- The SIM size (the SIM800L takes **micro-SIM**).

## Running cost summary

| | A. Czech prepaid | B. 1NCE + free MQTT tier |
|---|---|---|
| Per year | top-ups + ~1–2.5 Kč per tap-pattern SMS; missed-call pings free | **0 Kč** (prepaid 10 years) as long as you stay within 500 MB |
| Extra infrastructure | none | MQTT broker (free tier or your own) |
