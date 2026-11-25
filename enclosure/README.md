# 3D-printed case

![preview](out/preview_assembly.png)

Two parts per keychain, both printed **without supports**:

- **Tray:** floor, battery bay, carrier + SIM800L, USB-C opening, a flexing **button tab**
  printed into the wall, the keyring loop, and an **antenna channel** on the left for the
  SIM800L spring antenna.
- **Lid:** snaps onto the tray (tongue-and-groove with snap ridges). It has a **0.6 mm
  heart-shaped window** the LEDs shine through, plus locating rings that hold the heart
  board and the coin motor.

Outer size **33.5 × 27.3 × 17.6 mm** plus the keyring loop. It's bigger than the original
28 × 26 × 13 mm idea, because the 2G module, battery, charger parts and heart board are
stacked. Where the height goes: battery 4.0, carrier parts + PCB 4.2, SIM800L with its SIM
holder 4.7, heart board/motor 2.0, walls 2.4.

## Files

| File | |
|---|---|
| `keychain_case.scad` | Parametric OpenSCAD model; every dimension is at the top |
| `out/case_tray.stl`, `out/case_lid.stl` | One keychain (lid already flipped for printing) |
| `out/case_plate.stl` | Both keychains: 2 trays + 2 lids laid out on one plate |
| `out/keychain_case_x2_ender3v2_PLA_0.12mm.gcode` | **Ready to print** on an Ender-3 V2 / Ender-3 Pro: PLA, 0.12 mm layers, about 2 h, 12 g |
| `ender3v2_pla_0.12.ini` | The slicer settings used (Creality's official PrusaSlicer presets, flattened) |
| `scripts/build.sh` | Regenerates STLs, previews and G-code |

## Print

1. Copy the `.gcode` to the printer's microSD card and print it. It's sliced with
   PrusaSlicer's built-in **Creality Ender-3 V2 (0.4 mm nozzle)** printer, **0.12 mm
   DETAIL** print and **Generic PLA** filament presets. The Ender-3 Pro has the same
   220 × 220 bed, nozzle, Bowden extruder and Marlin firmware, so the file works on both.
2. Use **white or natural (translucent) PLA**, at least for the lids, so the heart glows
   through the window. To have coloured trays and white lids, open `case_tray.stl` and
   `case_lid.stl` separately in PrusaSlicer and print them as two jobs.
3. Clean bed, first layer well levelled: the window membrane is the first 5 layers.

### Using PrusaSlicer yourself

The installed PrusaSlicer has the Creality profiles. On first start, its Configuration
Wizard asks for printers: pick **Creality → Ender-3 V2** (or **Ender-3 Pro**), 0.4 mm
nozzle. Then open the STL, choose *0.12 mm DETAIL @CREALITY* and *Generic PLA @CREALITY*,
and slice. Alternatively, *File → Import → Import Config* loads `ender3v2_pla_0.12.ini`.

## Fit tuning (if needed after a test print)

All in `keychain_case.scad`, then run `scripts/build.sh`:

| Symptom | Parameter |
|---|---|
| Lid too tight / too loose | `fit` (0.15 mm; +0.05 looser) |
| Boards don't drop in | `clr` (0.3 mm) |
| Button needs too much / too little pressure | `clr_top` / `btn_protrusion` (nub length) |
| USB-C plug doesn't seat fully | `wall`, or the outside recess in `usb_cutout()` |
| No spring antenna (u.FL + flat antenna instead) | `antenna = false` (case gets 4.5 mm narrower) |
| Heart window too dim | `window_t` 0.4, or 0 for an open cut-out |

## Assembly

1. Battery into the bottom of the tray (a strip of double-sided foam tape), leads up the
   side.
2. A piece of Kapton or electrical tape on top of the battery. The carrier's bottom-side
   parts rest on it.
3. Carrier + SIM800L (already soldered together), USB-C into its opening. The side switch
   sits against the button tab. Lay the spring antenna in the left channel.
4. Coin motor (adhesive side up) into the round locating ring in the lid. Heart board,
   LEDs facing the window, into the heart ring. Route their thin wires down the antenna
   channel to the carrier pads.
5. Snap the lid on. To open, lever it at the USB-C end with a fingernail.
