"""
Autoroute the carrier board with Freerouting, then fill the GND zones.

  KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
  $KPY hardware/scripts/autoroute.py /path/to/freerouting-2.5.0.jar

Freerouting 2.5.0 (needs Java 25+):
  https://github.com/freerouting/freerouting/releases/download/v2.5.0/freerouting-2.5.0.jar
  sha256 f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7
"""
import os
import subprocess
import sys
import tempfile
import pcbnew as pn

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(HW, "keychain-carrier.kicad_pcb")
jar = sys.argv[1]
passes = sys.argv[2] if len(sys.argv) > 2 else "40"

tmp = tempfile.mkdtemp(prefix="kc_route_")
dsn, ses = os.path.join(tmp, "board.dsn"), os.path.join(tmp, "board.ses")

board = pn.LoadBoard(PCB)
for z in list(board.Zones()):
    board.Remove(z)
if not pn.ExportSpecctraDSN(board, dsn):
    sys.exit("DSN export failed")

subprocess.run(["java", "-jar", jar,
                "--gui.enabled=false",
                "--usage_and_diagnostic_data.disable_analytics=true",
                "-de", dsn, "-do", ses, "-mp", passes, "-mt", "1"],
               check=True)

board = pn.LoadBoard(PCB)
if not pn.ImportSpecctraSES(board, ses):
    sys.exit("SES import failed")


def gnd_zone(layer):
    z = pn.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet("GND"))
    z.SetLocalClearance(pn.FromMM(0.2))
    z.SetMinThickness(pn.FromMM(0.2))
    z.SetPadConnection(pn.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pn.ISLAND_REMOVAL_MODE_ALWAYS)
    ol = z.Outline()
    ol.NewOutline()
    bb = board.GetBoardEdgesBoundingBox()
    for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()),
                 (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
        ol.Append(x, y)
    board.Add(z)


for z in list(board.Zones()):
    board.Remove(z)
gnd_zone(pn.F_Cu)
gnd_zone(pn.B_Cu)
pn.ZONE_FILLER(board).Fill(board.Zones())
pn.SaveBoard(PCB, board)
print("routed + zones filled:", PCB)
