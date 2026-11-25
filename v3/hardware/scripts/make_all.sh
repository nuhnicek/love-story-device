#!/bin/sh
# keychain v3: schematic -> PCB -> route -> ERC/DRC/parity -> fab + assembly outputs
#   v3/hardware/scripts/make_all.sh /path/to/freerouting-2.5.0.jar
set -e
cd "$(dirname "$0")/.."
HW=$(pwd)
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
JAR=${1:?usage: make_all.sh /path/to/freerouting-2.5.0.jar}
N=keychain-v3

python3 scripts/gen_schematic.py
$KPY scripts/build_pcb.py 2>&1 | grep -v -E "wxApp|memory leak|image handler"
$KPY scripts/route.py "$JAR" 2>&1 | grep -E "GND|attempt|freerouting|routed"

kicad-cli sch erc --severity-all --exit-code-violations -o /tmp/v3_erc.rpt $N.kicad_sch >/dev/null \
  || { cat /tmp/v3_erc.rpt; exit 1; }
kicad-cli pcb drc --severity-all --schematic-parity --exit-code-violations --format json \
  -o /tmp/v3_drc.json $N.kicad_pcb >/dev/null \
  || { python3 "$HW/../../hardware/scripts/drc_summary.py" $N.kicad_pcb --schematic-parity; exit 1; }
echo "ERC, DRC, schematic parity: clean"

rm -rf fab && mkdir -p fab/gerbers
kicad-cli pcb export gerbers --layers F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts \
  --subtract-soldermask -o fab/gerbers/ $N.kicad_pcb >/dev/null
kicad-cli pcb export drill --format excellon --excellon-separate-th --generate-map --map-format pdf \
  -o fab/gerbers/ $N.kicad_pcb >/dev/null
(cd fab/gerbers && zip -q ../$N-gerbers.zip *)
kicad-cli pcb export pos --side front --format csv --units mm -o fab/$N-pos-top.csv $N.kicad_pcb >/dev/null
kicad-cli pcb export pdf --layers F.Fab,F.CrtYd,F.SilkS,Edge.Cuts --mode-single -o fab/assembly-top.pdf $N.kicad_pcb >/dev/null
kicad-cli pcb export pdf --layers B.Fab,B.CrtYd,B.SilkS,Edge.Cuts --mirror --mode-single -o fab/assembly-bottom.pdf $N.kicad_pcb >/dev/null
kicad-cli pcb export step --subst-models --force -o fab/$N.step $N.kicad_pcb >/dev/null 2>&1 || true
kicad-cli pcb render --side top --quality high -w 1400 -h 1700 -o fab/render-top.png $N.kicad_pcb >/dev/null
kicad-cli pcb render --side bottom --quality high -w 1400 -h 1700 -o fab/render-bottom.png $N.kicad_pcb >/dev/null
kicad-cli sch export pdf -o fab/schematic.pdf $N.kicad_sch >/dev/null
$KPY scripts/bom.py 2>&1 | grep -v -E "wxApp|memory leak|image handler"
echo "done -> v3/hardware/fab/"
