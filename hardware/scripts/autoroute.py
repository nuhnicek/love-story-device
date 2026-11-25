"""
Autoroute the carrier board with Freerouting, then fill the GND zones.

  KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
  $KPY hardware/scripts/autoroute.py /path/to/freerouting-2.5.0.jar [board.kicad_pcb]

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
jar = sys.argv[1]
PCB = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(HW, "keychain-carrier.kicad_pcb")

tmp = tempfile.mkdtemp(prefix="kc_route_")
dsn, ses = os.path.join(tmp, "board.dsn"), os.path.join(tmp, "board.ses")

board = pn.LoadBoard(PCB)
for z in list(board.Zones()):
    board.Remove(z)
if not pn.ExportSpecctraDSN(board, dsn):
    sys.exit("DSN export failed")

# Freerouting is not fully deterministic on tight boards: retry until every
# connection is routed, and fail loudly (stopping make_all.sh) if it never is.
import re
# Same input -> same result, so each attempt uses a different pass budget.
for attempt, passes in enumerate(("40", "60", "80", "120", "160"), 1):
    out = subprocess.run(["java", "-jar", jar,
                          "--gui.enabled=false",
                          "--usage_and_diagnostic_data.disable_analytics=true",
                          "-de", dsn, "-do", ses, "-mp", passes, "-mt", "1"],
                         check=True, capture_output=True, text=True)
    m = re.findall(r"Auto-routing stage completed.*?\((\d+) unrouted", out.stdout + out.stderr)
    unrouted = int(m[-1]) if m else -1
    print("freerouting attempt %d (%s passes): %s unrouted" % (attempt, passes, unrouted))
    if unrouted == 0:
        break
else:
    sys.exit("autoroute failed: connections left unrouted after 5 attempts")

board = pn.LoadBoard(PCB)
if not pn.ImportSpecctraSES(board, ses):
    sys.exit("SES import failed")

# Freerouting sometimes necks a track below the board minimum where it enters a
# fine-pitch pad; widen those stubs back to 0.127 mm (DRC re-checks clearance).
MIN_W = pn.FromMM(0.127)
for t in board.GetTracks():
    if t.GetClass() != "PCB_VIA" and t.GetWidth() < MIN_W:
        t.SetWidth(MIN_W)


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
if board.FindNet("GND"):
    gnd_zone(pn.F_Cu)
    gnd_zone(pn.B_Cu)
    pn.ZONE_FILLER(board).Fill(board.Zones())
pn.SaveBoard(PCB, board)
print("routed + zones filled:", PCB)
