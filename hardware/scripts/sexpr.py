"""Minimal S-expression reader/writer for KiCad files (no dependencies)."""
import re

_TOK = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)


class Q(str):
    """A string that must be written quoted."""


def parse(text):
    stack, cur = [], []
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOK.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError("parse error at %d" % pos)
        pos = m.end()
        op, cl, qs, atom = m.groups()
        if op:
            stack.append(cur)
            cur = []
        elif cl:
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif qs is not None:
            cur.append(Q(qs.replace('\\"', '"').replace("\\\\", "\\")))
        elif atom is not None:
            cur.append(atom)
    return cur[0]


def dump(x, indent=0):
    if isinstance(x, list):
        if not x:
            return "()"
        simple = all(not isinstance(e, list) for e in x)
        if simple:
            return "(" + " ".join(dump(e) for e in x) + ")"
        out = "(" + dump(x[0])
        for e in x[1:]:
            if isinstance(e, list):
                out += "\n" + "\t" * (indent + 1) + dump(e, indent + 1)
            else:
                out += " " + dump(e)
        return out + "\n" + "\t" * indent + ")"
    if isinstance(x, Q):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(x, float):
        s = ("%.4f" % x).rstrip("0").rstrip(".")
        return s if s not in ("-0", "") else "0"
    return str(x)


def find(node, key):
    return [e for e in node if isinstance(e, list) and e and e[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None


def load_library(path):
    lib = parse(open(path, encoding="utf-8").read())
    return {s[1]: s for s in find(lib, "symbol")}


def flatten(symbols, name, libname):
    """Return a self-contained copy of symbol `name` named 'libname:name',
    resolving (extends ...) by pulling the parent's units/graphics."""
    import copy
    sym = copy.deepcopy(symbols[name])
    ext = first(sym, "extends")
    if ext:
        parent = flatten(symbols, ext[1], libname)
        pname = ext[1]
        sym.remove(ext)
        # copy parent's flags / pin settings that the child lacks
        for k in ("pin_numbers", "pin_names", "exclude_from_sim", "in_bom", "on_board", "power"):
            if not first(sym, k) and first(parent, k):
                sym.insert(2, copy.deepcopy(first(parent, k)))
        for unit in find(parent, "symbol"):
            u = copy.deepcopy(unit)
            u[1] = Q(u[1].replace(pname, name, 1))
            sym.append(u)
    sym[1] = Q("%s:%s" % (libname, name)) if ":" not in sym[1] else sym[1]
    return sym


def pins(sym):
    """[(number, name, x, y, angle, type)] in symbol coordinates (y up)."""
    out = []
    for unit in find(sym, "symbol"):
        for p in find(unit, "pin"):
            at = first(p, "at")
            out.append((first(p, "number")[1], first(p, "name")[1],
                        float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0, p[1]))
    return out
