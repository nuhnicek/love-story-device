"""Shared pcbnew helpers for the keychain boards (run with KiCad's bundled Python)."""
import json
import os
import subprocess
import sys
import tempfile

import pcbnew as pn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sexpr  # noqa: E402


def mm(v):
    return pn.FromMM(v)


def V(x, y):
    return pn.VECTOR2I(mm(x), mm(y))


class Nets:
    def __init__(self, board):
        self.board, self.items = board, {}

    def __call__(self, name):
        if name not in self.items:
            ni = pn.NETINFO_ITEM(self.board, name)
            self.board.Add(ni)
            self.items[name] = ni
        return self.items[name]


def wirepad(board, net, ref, val, x, y, size, n, bottom=True):
    """Small rounded SMD solder pad for a wire (battery, motor, ISP, LEDs)."""
    fp = pn.FOOTPRINT(board)
    fp.SetFPID(pn.LIB_ID("keychain", "WirePad_%.1fmm" % size))
    fp.SetReference(ref); fp.SetValue(val)
    fp.SetAttributes(pn.FP_SMD | pn.FP_EXCLUDE_FROM_BOM | pn.FP_EXCLUDE_FROM_POS_FILES)
    fp.SetPosition(V(x, y))
    board.Add(fp)
    p = pn.PAD(fp)
    p.SetNumber("1"); p.SetAttribute(pn.PAD_ATTRIB_SMD)
    p.SetShape(pn.PAD_SHAPE_ROUNDRECT); p.SetRoundRectRadiusRatio(0.2)
    p.SetSize(V(size, size)); p.SetLayerSet(p.SMDMask())
    p.SetPosition(V(x, y)); fp.Add(p)
    p.SetNet(net(n))
    cy = pn.PCB_SHAPE(fp); cy.SetShape(pn.SHAPE_T_RECT)
    h = size / 2 + 0.15
    cy.SetStart(V(x - h, y - h)); cy.SetEnd(V(x + h, y + h))
    cy.SetLayer(pn.F_CrtYd); cy.SetWidth(mm(0.05)); fp.Add(cy)
    if bottom:
        fp.Flip(V(x, y), pn.FLIP_DIRECTION_LEFT_RIGHT)
    fp.Reference().SetTextSize(V(0.5, 0.5)); fp.Reference().SetTextThickness(mm(0.08))
    fp.Reference().SetPosition(V(x, y))
    return fp


def silk(board, text, x, y, size=0.8, layer=pn.B_SilkS, angle=0, justify=None):
    """Silkscreen text. 0.8 mm / 0.15 mm stroke is about the smallest JLCPCB prints legibly."""
    t = pn.PCB_TEXT(board)
    t.SetText(text); t.SetPosition(V(x, y)); t.SetLayer(layer)
    t.SetTextSize(V(size, size)); t.SetTextThickness(mm(max(0.15, size * 0.15)))
    t.SetMirrored(layer in (pn.B_SilkS, pn.B_Fab))
    t.SetTextAngleDegrees(angle)
    if justify == "left":
        t.SetHorizJustify(pn.GR_TEXT_H_ALIGN_LEFT)
    elif justify == "right":
        t.SetHorizJustify(pn.GR_TEXT_H_ALIGN_RIGHT)
    board.Add(t)
    return t


def refs_to_fab(board, top_refs=()):
    """Hide silk refs/values; keep one reference per part on the Fab layer."""
    for fp in board.GetFootprints():
        fp.Value().SetVisible(False)
        ref = fp.Reference()
        if fp.GetReference() in top_refs or not fp.IsFlipped():
            ref.SetLayer(pn.F_Fab); ref.SetMirrored(False)
        else:
            ref.SetLayer(pn.B_Fab); ref.SetMirrored(True)
        ref.SetTextSize(V(0.5, 0.5)); ref.SetTextThickness(mm(0.08))
        for item in fp.GraphicalItems():
            if isinstance(item, pn.PCB_TEXT) and item.GetText() == "${REFERENCE}":
                item.SetVisible(False)


def sync_from_schematic(board, net, sch_path, allow_dropped=()):
    """Cross-check every pad against the schematic netlist (fail on mismatch),
    then adopt schematic net names and symbol fields. `allow_dropped` lists
    script net names that the schematic marks no-connect."""
    nl_path = os.path.join(tempfile.mkdtemp(), "board.net")
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
                    "-o", nl_path, sch_path], check=True, capture_output=True)
    nl = sexpr.parse(open(nl_path).read())
    netmap = {}
    for n in sexpr.find(sexpr.first(nl, "nets"), "net"):
        name = sexpr.first(n, "name")[1]
        for node in sexpr.find(n, "node"):
            netmap[(sexpr.first(node, "ref")[1], sexpr.first(node, "pin")[1])] = name
    comps = {sexpr.first(c, "ref")[1]: c for c in sexpr.find(sexpr.first(nl, "components"), "comp")}

    def norm(n):
        return "" if not n or n.startswith("unconnected-") else n.lstrip("/")

    errors = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref not in comps:
            errors.append("%s missing from schematic" % ref)
            continue
        for p in fp.Pads():
            if not p.GetNumber():
                continue
            sch = netmap.get((ref, p.GetNumber()), "")
            if norm(sch) != norm(p.GetNetname()) and not (p.GetNetname() in allow_dropped and not norm(sch)):
                errors.append("%s.%s: pcb=%s sch=%s" % (ref, p.GetNumber(), p.GetNetname(), sch))
            p.SetNet(net(sch) if sch else pn.NETINFO_LIST.OrphanedItem())
        comp = comps[ref]
        fp.SetValue(sexpr.first(comp, "value")[1])
        fields = sexpr.find(sexpr.first(comp, "fields") or [], "field")
        names = {sexpr.first(f, "name")[1] for f in fields}
        for fld in list(fp.GetFields()):
            if not fld.IsMandatory() and fld.GetName() not in names:
                fp.Remove(fld)
        for f in fields:
            name = sexpr.first(f, "name")[1]
            if name == "Footprint" or name.startswith("ki_"):
                continue
            fp.SetField(name, f[2] if len(f) > 2 else "")
            fp.GetField(name).SetVisible(False)
    if errors:
        sys.exit("schematic/PCB mismatch:\n  " + "\n  ".join(errors))
    used = set(netmap.values())
    for name in list(net.items):
        if name not in used:
            board.Remove(net.items.pop(name))


def link_symbols(board, uuids_json, sch_file):
    link = json.load(open(uuids_json))
    for fp in board.GetFootprints():
        u = link["symbols"].get(fp.GetReference())
        if not u:
            sys.exit("footprint %s has no schematic symbol" % fp.GetReference())
        fp.SetPath(pn.KIID_PATH("/" + u))
        fp.SetSheetname("/")
        fp.SetSheetfile(sch_file)


def save_custom_footprints(board, pretty):
    os.makedirs(pretty, exist_ok=True)
    io = pn.PCB_IO_KICAD_SEXPR()
    done = set()
    for fp in board.GetFootprints():
        fid = fp.GetFPID()
        if fid.GetLibNickname() == "keychain" and str(fid.GetLibItemName()) not in done:
            lf = pn.FOOTPRINT(fp)
            if lf.IsFlipped():
                lf.Flip(lf.GetPosition(), pn.FLIP_DIRECTION_LEFT_RIGHT)
            lf.SetOrientationDegrees(0)
            lf.Move(pn.VECTOR2I(-lf.GetPosition().x, -lf.GetPosition().y))
            lf.SetPath(pn.KIID_PATH())
            lf.Reference().SetVisible(True)
            lf.Reference().SetLayer(pn.F_SilkS); lf.Reference().SetMirrored(False)
            io.FootprintSave(pretty, lf)
            done.add(str(fid.GetLibItemName()))


def write_project(pro_path, netclasses, patterns, extra_rules=None):
    """pcbnew's SaveBoard() does not reliably rewrite an existing .kicad_pro, so
    net classes and minimum rules are written into the project JSON explicitly.
    netclasses: [(name, track, clearance, via_dia, via_drill, priority)]"""
    pro = json.load(open(pro_path)) if os.path.exists(pro_path) else \
        {"meta": {"filename": os.path.basename(pro_path), "version": 3}}
    nsj = pro.setdefault("net_settings", {"meta": {"version": 5}})
    nsj["classes"] = [{"name": n, "track_width": t, "clearance": c, "via_diameter": vd,
                       "via_drill": vr, "priority": pr, "bus_width": 12, "wire_width": 6,
                       "line_style": 0, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
                       "diff_pair_width": 0.2, "microvia_diameter": 0.3, "microvia_drill": 0.1,
                       "pcb_color": "rgba(0, 0, 0, 0.000)",
                       "schematic_color": "rgba(0, 0, 0, 0.000)", "tuning_profile": ""}
                      for n, t, c, vd, vr, pr in netclasses]
    nsj["netclass_patterns"] = [{"netclass": c, "pattern": p} for p, c in patterns]
    nsj.setdefault("netclass_assignments", {})
    rules = pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {})
    rules.update({"min_clearance": 0.127, "min_track_width": 0.127, "min_hole_clearance": 0.25,
                  "min_through_hole_diameter": 0.3, "min_via_diameter": 0.5,
                  "min_copper_edge_clearance": 0.25, "min_hole_to_hole": 0.25})
    rules.update(extra_rules or {})
    json.dump(pro, open(pro_path, "w"), indent=2)


def apply_rules(board, netclasses, patterns, thickness=0.8):
    """Same rules in the in-memory board (used by DSN export in this process)."""
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(thickness))
    ds.m_TrackMinWidth = mm(0.127)
    ds.m_MinClearance = mm(0.127)
    ds.m_ViasMinSize = mm(0.5)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_HoleToHoleMin = mm(0.25)
    ds.m_CopperEdgeClearance = mm(0.25)
    ns = ds.m_NetSettings
    for n, t, c, vd, vr, pr in netclasses:
        nc = ns.GetDefaultNetclass() if n == "Default" else pn.NETCLASS(n)
        nc.SetTrackWidth(mm(t)); nc.SetClearance(mm(c))
        nc.SetViaDiameter(mm(vd)); nc.SetViaDrill(mm(vr))
        if n != "Default":
            ns.SetNetclass(n, nc)
    for p, c in patterns:
        ns.SetNetclassPatternAssignment(p, c)
