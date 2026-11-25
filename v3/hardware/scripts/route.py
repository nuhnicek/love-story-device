"""
Route the v3 board: inner layers are solid GND planes (exported to Freerouting
as planes, so it drops vias from GND pads straight into them), signals on L1/L4,
the hand-drawn RF path stays locked. Afterwards: GND pours on L1/L4, GND
stitching around the U.FL, zone fill.

  $KPY v3/hardware/scripts/route.py /path/to/freerouting-2.5.0.jar
"""
import math
import os
import re
import subprocess
import sys
import tempfile

import pcbnew as pn

HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(HW, "keychain-v3.kicad_pcb")
jar = sys.argv[1]
mm = pn.FromMM


def zone(board, layer, netname, clearance=0.2, priority=0):
    z = pn.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet(netname))
    z.SetLocalClearance(mm(clearance))
    z.SetMinThickness(mm(0.15))
    z.SetPadConnection(pn.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pn.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetAssignedPriority(priority)
    ol = z.Outline()
    ol.NewOutline()
    bb = board.GetBoardEdgesBoundingBox()
    for x, y in ((bb.GetLeft(), bb.GetTop()), (bb.GetRight(), bb.GetTop()),
                 (bb.GetRight(), bb.GetBottom()), (bb.GetLeft(), bb.GetBottom())):
        ol.Append(x, y)
    board.Add(z)
    return z


board = pn.LoadBoard(PCB)
for t in list(board.GetTracks()):
    if not t.IsLocked():
        board.Remove(t)
for z in list(board.Zones()):
    board.Remove(z)


# ---------------------------------------------------------------- GND fan-out
# Every GND pad gets its own via into the inner GND planes (Freerouting does not
# drop vias from SMD pads into planes by itself). Positions are searched around
# the pad and collision-checked against all other copper, holes and the edge.
VIA_D, VIA_DRILL, CLR = 0.6, 0.3, 0.15
GND = board.FindNet("GND")
EDGE = board.GetBoardEdgesBoundingBox()
placed = []            # (x, y) of vias we added


def obstacles():
    obs = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            obs.append(p)
    for t in board.GetTracks():
        obs.append(t)
    return obs


OBS = obstacles()
KEEPOUTS = [z for fp in board.GetFootprints() for z in fp.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
KEEPOUTS += [z for z in board.Zones() if z.GetIsRuleArea() and z.GetDoNotAllowVias()]


def free(x, y, src_pad, seg_from):
    c = pn.SHAPE_CIRCLE(pn.VECTOR2I(int(x), int(y)), mm(VIA_D / 2))
    seg = pn.SHAPE_SEGMENT(seg_from, pn.VECTOR2I(int(x), int(y)), mm(0.25))
    m = mm(0.6)
    if not (EDGE.GetLeft() + m < x < EDGE.GetRight() - m and EDGE.GetTop() + m < y < EDGE.GetBottom() - m):
        return False
    for kz in KEEPOUTS:
        if kz.Outline().Collide(pn.VECTOR2I(int(x), int(y)), mm(VIA_D / 2 + 0.05)):
            return False
    for px, py in placed:
        if (px - x) ** 2 + (py - y) ** 2 < mm(VIA_D + CLR) ** 2:
            return False
    for o in OBS:
        same = o.GetNetCode() == GND.GetNetCode() and o.GetNetCode() != 0
        if isinstance(o, pn.PAD):
            if o.GetDrillSize().x > 0:                       # any hole: keep 0.25 mm
                hp = o.GetPosition()
                hr = max(o.GetDrillSize().x, o.GetDrillSize().y) / 2
                if math.hypot(hp.x - x, hp.y - y) < hr + mm(VIA_D / 2 + 0.25):
                    return False
            for layer in (pn.F_Cu, pn.B_Cu):
                if not o.IsOnLayer(layer):
                    continue
                sh = o.GetEffectiveShape(layer)
                if not same and sh.Collide(c, mm(CLR)):
                    return False
                if not same and o.IsOnLayer(src_pad.GetLayer()) and layer == src_pad.GetLayer() \
                        and sh.Collide(seg, mm(CLR)):
                    return False
        else:
            if same:
                continue
            sh = o.GetEffectiveShape(o.GetLayer() if o.GetClass() != "PCB_VIA" else pn.F_Cu)
            if sh.Collide(c, mm(CLR)) or (o.GetLayer() == src_pad.GetLayer() and sh.Collide(seg, mm(CLR))):
                return False
    return True



missing = []
for fp in board.GetFootprints():
    for p in fp.Pads():
        if p.GetNetCode() != GND.GetNetCode() or p.GetDrillSize().x > 0:
            continue
        if fp.GetReference() == "J3" and p.GetNumber() == "SH":
            pass
        pc = p.GetPosition()
        bb = p.GetBoundingBox()
        half = max(bb.GetWidth(), bb.GetHeight()) / 2
        fc = fp.GetPosition()
        base = math.atan2(pc.y - fc.y, pc.x - fc.x) if (pc.x, pc.y) != (fc.x, fc.y) else 0
        ok = False
        if fp.GetReference() == "U1" and int(p.GetNumber()) >= 105:
            dists = [half + mm(0.62)]          # into the gap between the centre pads
        else:
            dists = [half + mm(0.5), half + mm(0.8), half + mm(1.2)]
        for d in dists:
            for k in range(16):
                a = base + (k // 2 + 1 if k % 2 else -(k // 2)) * math.pi / 8 if k else base
                x, y = pc.x + d * math.cos(a), pc.y + d * math.sin(a)
                if free(x, y, p, pc):
                    v = pn.PCB_VIA(board)
                    v.SetPosition(pn.VECTOR2I(int(x), int(y)))
                    v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(GND)
                    v.SetLocked(True)
                    board.Add(v)
                    t = pn.PCB_TRACK(board)
                    t.SetStart(pc); t.SetEnd(pn.VECTOR2I(int(x), int(y)))
                    t.SetWidth(mm(0.25)); t.SetLayer(p.GetLayer() if p.IsOnLayer(pn.F_Cu) else pn.B_Cu)
                    t.SetNet(GND); t.SetLocked(True)
                    board.Add(t)
                    placed.append((x, y))
                    OBS.append(t)
                    ok = True
                    break
            if ok:
                break
        if not ok:
            missing.append("%s.%s" % (fp.GetReference(), p.GetNumber()))
# extra GND stitching around the U.FL (same collision check as the fan-out)
j2 = board.FindFootprintByReference("J2")
c0 = j2.GetPosition()
for dx, dy in ((-2.2, -1.6), (2.2, -1.6), (-2.2, 1.6), (2.2, 1.6), (0, 2.4)):
    x, y = c0.x + mm(dx), c0.y + mm(dy)
    if free(x, y, j2.Pads()[0], pn.VECTOR2I(int(x), int(y))):
        v = pn.PCB_VIA(board)
        v.SetPosition(pn.VECTOR2I(int(x), int(y)))
        v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(GND); v.SetLocked(True)
        board.Add(v)
        placed.append((x, y))
print("GND fan-out vias:", len(placed), "pads without a via (left to the router):", missing)

zone(board, pn.In1_Cu, "GND")
pn.ZONE_FILLER(board).Fill(board.Zones())
pn.SaveBoard(PCB, board)

tmp = tempfile.mkdtemp(prefix="v3_route_")
dsn, ses = os.path.join(tmp, "board.dsn"), os.path.join(tmp, "board.ses")
if not pn.ExportSpecctraDSN(board, dsn):
    sys.exit("DSN export failed")

PASSES = ("40",) if "--quick" in sys.argv else ("60", "100", "150", "200", "300")
for attempt, passes in enumerate(PASSES, 1):
    out = subprocess.run(["java", "-jar", jar, "--gui.enabled=false",
                          "--usage_and_diagnostic_data.disable_analytics=true",
                          "-de", dsn, "-do", ses, "-mp", passes, "-mt", "1"],
                         check=True, capture_output=True, text=True)
    m = re.findall(r"Auto-routing stage completed.*?\((\d+) unrouted", out.stdout + out.stderr)
    unrouted = int(m[-1]) if m else -1
    print("freerouting attempt %d (%s passes): %s unrouted" % (attempt, passes, unrouted))
    if unrouted == 0:
        break
else:
    # What Freerouting still lists is normally GND, closed by the pours added
    # below; the DRC (make_all.sh) decides whether the board is complete.
    print("freerouting left %d connection(s); the GND pours close them, DRC checks" % unrouted)

board = pn.LoadBoard(PCB)
if not pn.ImportSpecctraSES(board, ses):
    sys.exit("SES import failed")
MIN_W = mm(0.09)
for t in board.GetTracks():
    if t.GetClass() != "PCB_VIA" and t.GetWidth() < MIN_W:
        t.SetWidth(MIN_W)

# drop vias the router left connected on one layer only
def via_layers(v):
    used = set()
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA" or t.GetNetCode() != v.GetNetCode():
            continue
        if v.GetPosition() in (t.GetStart(), t.GetEnd()):
            used.add(t.GetLayer())
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetCode() == v.GetNetCode() and p.HitTest(v.GetPosition()):
                used.update(l for l in (pn.F_Cu, pn.B_Cu) if p.IsOnLayer(l))
    return used


GNDC = board.FindNet("GND").GetNetCode()
for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
    if v.GetNetCode() != GNDC and len(via_layers(v)) < 2:
        board.Remove(v)

for z in list(board.Zones()):
    board.Remove(z)
zone(board, pn.In1_Cu, "GND")
zone(board, pn.In2_Cu, "GND")
zone(board, pn.F_Cu, "GND", clearance=0.25)
zone(board, pn.B_Cu, "GND", clearance=0.25)
pn.ZONE_FILLER(board).Fill(board.Zones())
pn.SaveBoard(PCB, board)
print("routed + zones filled:", PCB)
