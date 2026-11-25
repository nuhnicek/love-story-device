#!/bin/sh
# Export the case STLs + previews and slice a ready-to-print plate for the Ender-3 V2 / Pro.
#   enclosure/scripts/build.sh
set -e
cd "$(dirname "$0")/.."
OPENSCAD=${OPENSCAD:-openscad}
SLICER=${SLICER:-/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer}
mkdir -p out

for p in tray lid plate; do
  $OPENSCAD -D "part=\"$p\"" -o out/case_$p.stl keychain_case.scad 2>&1 | grep -E "ECHO|WARNING|ERROR" || true
done
for spec in "assembly:0,0,0,60,0,210,0" "tray:0,0,0,55,0,30,0" "lid:0,0,0,40,0,20,0"; do
  n=${spec%%:*}; cam=${spec#*:}
  $OPENSCAD -D "part=\"$n\"" -o out/preview_$n.png --imgsize=1000,800 --camera=$cam \
    --viewall --autocenter keychain_case.scad >/dev/null 2>&1
done

python3 scripts/flatten_profile.py "Creality Ender-3 V2 (0.4 mm nozzle)" \
  "0.12 mm DETAIL (0.4 mm nozzle) @CREALITY" "Generic PLA @CREALITY" > ender3v2_pla_0.12.ini

# one plate: 2 trays + 2 lids (a pair of keychains), laid out by OpenSCAD ("plate").
# (PrusaSlicer 2.9.7's CLI crashes on --merge + --duplicate, so arrange in the model.)
"$SLICER" --load ender3v2_pla_0.12.ini --export-gcode --center 110,110 \
  --output out/keychain_case_x2_ender3v2_PLA_0.12mm.gcode out/case_plate.stl
grep -E "^; (estimated printing time \(normal mode\)|filament used \[g\]|filament used \[mm\])" \
  out/keychain_case_x2_ender3v2_PLA_0.12mm.gcode
