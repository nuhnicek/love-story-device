#!/bin/sh
# v2 case: STLs + previews + a sliced plate (2 trays + 2 lids) for the Ender-3 V2 / Pro.
#   v2/case/build.sh
set -e
cd "$(dirname "$0")"
OPENSCAD=${OPENSCAD:-openscad}
SLICER=${SLICER:-/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer}
mkdir -p out

# same heart perfboard as v1: regenerate the layout there and copy it in
(cd ../../enclosure && python3 heart_perfboard.py >/dev/null)
cp ../../enclosure/heart_layout.scad .
cp ../../enclosure/out/heart_perfboard.png ../../enclosure/out/heart_perfboard.txt out/

for p in tray lid plate; do
  $OPENSCAD -D "part=\"$p\"" -o out/case_v2_$p.stl keychain_case_v2.scad 2>&1 | grep -E "ECHO|WARNING|ERROR" || true
done
for spec in "assembly:0,0,0,60,0,210,0" "inside:0,0,0,50,0,210,0" "tray:0,0,0,55,0,30,0" "lid:0,0,0,40,0,20,0"; do
  n=${spec%%:*}; cam=${spec#*:}
  $OPENSCAD -D "part=\"$n\"" -o out/preview_$n.png --imgsize=1000,800 --camera=$cam \
    --viewall --autocenter keychain_case_v2.scad >/dev/null 2>&1
done

# ender3v2_pla_0.12.ini = Creality Ender-3 V2 (0.4 mm) + 0.12 mm DETAIL + Generic PLA,
# flattened from PrusaSlicer's vendor profiles by ../../enclosure/scripts/flatten_profile.py
"$SLICER" --load ender3v2_pla_0.12.ini --export-gcode --center 110,110 \
  --output out/keychain_v2_x2_ender3v2_PLA_0.12mm.gcode out/case_v2_plate.stl >/dev/null
grep -E "^; (estimated printing time \(normal mode\)|filament used \[g\])" \
  out/keychain_v2_x2_ender3v2_PLA_0.12mm.gcode
