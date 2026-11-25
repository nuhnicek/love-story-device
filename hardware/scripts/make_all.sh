#!/bin/sh
# Full pipeline for both boards: schematic -> PCB -> autoroute -> ERC/DRC/parity -> fab outputs.
#   hardware/scripts/make_all.sh /path/to/freerouting-2.5.0.jar
set -e
cd "$(dirname "$0")/.."
HW=$(pwd)
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
JAR=${1:?usage: make_all.sh /path/to/freerouting-2.5.0.jar}

# fab_outputs <dir> <name> <assembly side: front|back>
fab_outputs() {
  dir=$1; name=$2; side=$3
  cd "$dir"
  pcb=$name.kicad_pcb
  python3 "$HW/scripts/drc_summary.py" $pcb --schematic-parity
  kicad-cli sch erc --severity-all --exit-code-violations -o /tmp/kc_erc.rpt $name.kicad_sch \
    || { cat /tmp/kc_erc.rpt; exit 1; }
  rm -rf fab && mkdir -p fab/gerbers
  kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
    --subtract-soldermask -o fab/gerbers/ $pcb >/dev/null
  kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map --map-format pdf \
    -o fab/gerbers/ $pcb >/dev/null
  (cd fab/gerbers && zip -q ../$name-gerbers.zip *)
  if [ "$side" = back ]; then
    kicad-cli pcb export pos --side back --format csv --units mm --exclude-dnp -o fab/$name-pos-bottom.csv $pcb >/dev/null
    kicad-cli pcb export pdf --layers B.Fab,B.CrtYd,Edge.Cuts --mirror --mode-single -o fab/assembly-bottom.pdf $pcb >/dev/null
  else
    kicad-cli pcb export pos --side front --format csv --units mm --exclude-dnp -o fab/$name-pos-top.csv $pcb >/dev/null
    kicad-cli pcb export pdf --layers F.Fab,F.CrtYd,Edge.Cuts --mode-single -o fab/assembly-top.pdf $pcb >/dev/null
  fi
  kicad-cli pcb export step --subst-models --force -o fab/$name.step $pcb >/dev/null 2>&1
  kicad-cli pcb render --side bottom --quality high -w 1600 -h 1400 -o fab/render-bottom.png $pcb >/dev/null
  kicad-cli pcb render --side top --quality high -w 1600 -h 1400 -o fab/render-top.png $pcb >/dev/null
  kicad-cli sch export pdf -o fab/schematic.pdf $name.kicad_sch >/dev/null
  kicad-cli sch export svg -o fab/ $name.kicad_sch >/dev/null && mv fab/$name.svg fab/schematic.svg
  cd "$HW"
}

echo "== carrier"
python3 scripts/gen_schematic.py
$KPY scripts/build_pcb.py
$KPY scripts/autoroute.py "$JAR" keychain-carrier.kicad_pcb > /tmp/kc_route.log 2>&1 \
  || { grep -E "attempt|failed" /tmp/kc_route.log; exit 1; }
grep -E "attempt" /tmp/kc_route.log
fab_outputs "$HW" keychain-carrier back

echo "== heart"
python3 scripts/gen_heart.py
$KPY scripts/build_heart.py
$KPY scripts/autoroute.py "$JAR" heart/heart-led.kicad_pcb > /tmp/kc_route.log 2>&1 \
  || { grep -E "attempt|failed" /tmp/kc_route.log; exit 1; }
grep -E "attempt" /tmp/kc_route.log
fab_outputs "$HW/heart" heart-led front

$KPY scripts/bom.py
echo "done -> hardware/fab/ and hardware/heart/fab/"
