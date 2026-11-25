#!/bin/sh
# Full pipeline: generate board -> autoroute -> DRC -> fab outputs.
#   hardware/scripts/make_all.sh /path/to/freerouting-2.5.0.jar
set -e
cd "$(dirname "$0")/.."
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
JAR=${1:?usage: make_all.sh /path/to/freerouting-2.5.0.jar}
PCB=keychain-carrier.kicad_pcb

$KPY scripts/build_pcb.py
$KPY scripts/autoroute.py "$JAR"
python3 scripts/drc_summary.py $PCB

rm -rf fab && mkdir -p fab/gerbers
kicad-cli pcb export gerbers --layers F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
  --subtract-soldermask -o fab/gerbers/ $PCB
kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map --map-format pdf \
  -o fab/gerbers/ $PCB
(cd fab/gerbers && zip -q ../keychain-carrier-gerbers.zip *)
kicad-cli pcb export pos --side back --format csv --units mm --exclude-dnp -o fab/keychain-carrier-pos-bottom.csv $PCB
kicad-cli pcb export pdf --layers B.Fab,B.CrtYd,Edge.Cuts --mirror --mode-single -o fab/assembly-bottom.pdf $PCB
kicad-cli pcb export step --subst-models --force -o fab/keychain-carrier.step $PCB >/dev/null
kicad-cli pcb render --side bottom --quality high -w 1600 -h 1400 -o fab/render-bottom.png $PCB
kicad-cli pcb render --side top --quality high -w 1600 -h 1400 -o fab/render-top.png $PCB
$KPY scripts/bom.py
echo "done -> hardware/fab/"
