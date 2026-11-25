"""
Tiny schematic writer for KiCad 10 (.kicad_sch), shared by the keychain boards.

Style: every pin gets a short stub ending in a power symbol or a net label, so
symbols never need hand-drawn wires and the drawing reads like the netlist.
Usage: sheet = Sheet(project, out_path, power={...}); sheet.place(...); sheet.write(...)
"""
import copy
import json
import math
import uuid

import sexpr
from sexpr import Q, first, find

SYMDIR = "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/"
STUB = 2.54
_libs = {}


def stock(name):
    if name not in _libs:
        _libs[name] = sexpr.load_library(SYMDIR + name + ".kicad_sym")
    return _libs[name]


def font(size=1.27, hide=False, justify=None, bold=False):
    f = ["font", ["size", size, size]]
    if bold:
        f.append(["bold", "yes"])
    e = ["effects", f]
    if justify:
        e.append(["justify"] + justify)
    if hide:
        e.append(["hide", "yes"])
    return e


def prop(name, value, x=0.0, y=0.0, hide=False):
    return ["property", Q(name), Q(value), ["at", x, y, 0], font(hide=hide)]


def xform(px, py, X, Y, rot):
    """symbol coords (y up) -> sheet coords (y down)."""
    x, y = px, -py
    a = math.radians(rot)
    c, s = round(math.cos(a)), round(math.sin(a))
    return X + x * c + y * s, Y - x * s + y * c


def snap(v):
    return round(v / 1.27) * 1.27


class Sheet:
    def __init__(self, project, out_path, power, custom=None, seed=None):
        self.project, self.out = project, out_path
        self.power = power                    # net name -> power symbol lib_id
        self.custom = custom or {}            # "keychain" symbols by name
        self.ns = uuid.UUID(seed or "6b0d1c4e-3f7a-4c55-9a51-2e1f6a7c9b10")
        self.root = self.uid("root")
        self.items, self.lib_symbols, self.uuids = [], {}, {}
        self.pwr = 0

    def uid(self, *k):
        return Q(str(uuid.uuid5(self.ns, "/".join(map(str, k)))))

    def libsym(self, lib_id):
        if lib_id not in self.lib_symbols:
            ln, name = lib_id.split(":")
            if ln == "keychain":
                s = copy.deepcopy(self.custom[name])
                s[1] = Q(lib_id)
            else:
                s = sexpr.flatten(stock(ln), name, ln)
            self.lib_symbols[lib_id] = s
        return self.lib_symbols[lib_id]

    # -------------------------------------------------------- drawing items
    def wire(self, a, b):
        self.items.append(["wire", ["pts", ["xy", a[0], a[1]], ["xy", b[0], b[1]]],
                           ["stroke", ["width", 0], ["type", "default"]], ["uuid", self.uid("w", a, b)]])

    def label(self, name, at, direction):
        ang = {"right": 0, "up": 90, "left": 180, "down": 270}[direction]
        just = ["left", "bottom"] if direction in ("right", "up") else ["right", "bottom"]
        self.items.append(["label", Q(name), ["at", at[0], at[1], ang], font(justify=just),
                           ["uuid", self.uid("l", name, at)]])

    def text(self, s, x, y, size=1.27, bold=False):
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", x, y, 0],
                           font(size, justify=["left", "bottom"], bold=bold),
                           ["uuid", self.uid("t", s[:40], x, y)]])

    def box(self, x1, y1, x2, y2, title):
        self.items.append(["rectangle", ["start", x1, y1], ["end", x2, y2],
                           ["stroke", ["width", 0.2], ["type", "dash"]], ["fill", ["type", "none"]],
                           ["uuid", self.uid("r", title)]])
        self.text(title, x1 + 1.27, y1 + 3.81, 2.0, True)

    # -------------------------------------------------------- symbols
    def place(self, lib_id, ref, value, x, y, rot=0, footprint="", nets=None, nc=(),
              on_board=True, in_bom=True, extra=None, field_at=None, dnp=False):
        nets = nets or {}
        sym = self.libsym(lib_id)
        X, Y = snap(x), snap(y)
        u = self.uid("s", ref)
        if not ref.startswith("#"):
            self.uuids[ref] = str(u)
        inst = ["symbol", ["lib_id", Q(lib_id)], ["at", X, Y, rot], ["unit", 1],
                ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"],
                ["on_board", "yes" if on_board else "no"], ["dnp", "yes" if dnp else "no"], ["uuid", u]]
        values = {"Reference": ref, "Value": value, "Footprint": footprint}
        values.update(extra or {})
        for p in find(sym, "property"):
            name = p[1]
            if name.startswith("ki_"):
                continue                  # library search metadata, not instance fields
            at = first(p, "at")
            px, py = xform(float(at[1]), float(at[2]), X, Y, rot)
            pang = (float(at[3]) if len(at) > 3 else 0.0) + rot
            if field_at and name in field_at:
                px, py = X + field_at[name][0], Y + field_at[name][1]
                pang = 0
            eff = copy.deepcopy(first(p, "effects")) or font()
            hidden = (first(p, "hide") is not None and first(p, "hide")[1] == "yes") or \
                first(eff, "hide") is not None or ref.startswith("#") and name == "Reference" or \
                name in ("Footprint", "Datasheet", "Description") or name not in values
            for h in find(eff, "hide"):
                eff.remove(h)
            if hidden:
                eff.append(["hide", "yes"])
            inst.append(["property", Q(name), Q(values.get(name, p[2])),
                         ["at", px, py, pang % 180], eff])          # keep text upright
        for name, val in (extra or {}).items():
            if not any(pp[1] == name for pp in find(sym, "property")):
                inst.append(["property", Q(name), Q(val), ["at", X, Y, 0], font(hide=True)])
        seen = set()
        for num, pname, px, py, ang, ptype in sexpr.pins(sym):
            inst.append(["pin", Q(num), ["uuid", self.uid("p", ref, num)]])
            ex, ey = xform(px, py, X, Y, rot)
            ex, ey = round(ex, 2), round(ey, 2)
            if (ex, ey) in seen:
                continue
            seen.add((ex, ey))
            oa = math.radians(ang + 180)          # outward = away from the body
            dx, dy = round(math.cos(oa)), -round(math.sin(oa))
            a = math.radians(rot)
            c, s = round(math.cos(a)), round(math.sin(a))
            dx, dy = dx * c + dy * s, -dx * s + dy * c
            direction = {(1, 0): "right", (-1, 0): "left", (0, -1): "up", (0, 1): "down"}[(dx, dy)]
            if num in nc:
                self.items.append(["no_connect", ["at", ex, ey], ["uuid", self.uid("nc", ref, num)]])
                continue
            n = nets.get(num)
            if not n:
                continue
            end = (round(ex + dx * STUB, 2), round(ey + dy * STUB, 2))
            self.wire((ex, ey), end)
            if n in self.power:
                self.pwr += 1
                if n == "GND":
                    prot = 180 if direction == "up" else 0
                else:
                    prot = 180 if direction == "down" else 0
                self.place(self.power[n], "#PWR%02d" % self.pwr, n, end[0], end[1], prot)
            else:
                self.label(n, end, direction)
        inst.append(["instances", ["project", Q(self.project),
                                   ["path", Q("/" + self.root), ["reference", Q(ref)], ["unit", 1]]]])
        self.items.append(inst)

    # -------------------------------------------------------- output
    def write(self, title, comments, uuids_path, date="2026-11-25", rev="1", paper="A4"):
        tb = ["title_block", ["title", Q(title)], ["date", Q(date)], ["rev", Q(rev)]]
        for i, c in enumerate(comments, 1):
            tb.append(["comment", i, Q(c)])
        sch = ["kicad_sch", ["version", 20250114], ["generator", Q("eeschema")],
               ["generator_version", Q("10.0")], ["uuid", self.root], ["paper", Q(paper)], tb,
               ["lib_symbols"] + list(self.lib_symbols.values())]
        sch += self.items
        sch.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
        sch.append(["embedded_fonts", "no"])
        with open(self.out, "w") as f:
            f.write(sexpr.dump(sch) + "\n")
        with open(uuids_path, "w") as f:
            json.dump({"root": str(self.root), "symbols": self.uuids}, f, indent=1, sort_keys=True)


def write_lib_tables(folder, sym_uri, fp_uri):
    for name, uri in (("sym-lib-table", sym_uri), ("fp-lib-table", fp_uri)):
        kind = "sym_lib_table" if name.startswith("sym") else "fp_lib_table"
        with open(folder + "/" + name, "w") as f:
            f.write('(%s\n  (version 7)\n  (lib (name "keychain")(type "KiCad")(uri "${KIPRJMOD}/%s")'
                    '(options "")(descr "Project parts"))\n)\n' % (kind, uri))
