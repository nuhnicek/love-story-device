#!/usr/bin/env python3
"""
Flatten PrusaSlicer's bundled Creality vendor presets into one .ini for the CLI.

The GUI uses the same presets once you pick "Creality Ender-3 V2" (or "Ender-3 Pro") in
the Configuration Wizard. The CLI only knows presets the wizard has registered, so this
script resolves the vendor file's `inherits` chains itself:

  python3 flatten_profile.py "Creality Ender-3 V2 (0.4 mm nozzle)" \
      "0.12 mm DETAIL (0.4 mm nozzle) @CREALITY" "Generic PLA @CREALITY" > ender3v2.ini
"""
import configparser
import sys

VENDOR = "/Applications/PrusaSlicer.app/Contents/Resources/profiles/Creality.ini"
SKIP = {"inherits", "renamed_from", "alias", "compatible_printers", "compatible_printers_condition",
        "compatible_prints", "compatible_prints_condition", "printer_model", "printer_variant",
        "default_print_profile", "default_filament_profile", "printer_vendor", "thumbnails_format"}


def load():
    cp = configparser.RawConfigParser(strict=False, interpolation=None, delimiters=("=",))
    cp.optionxform = str
    with open(VENDOR) as f:
        cp.read_file(f)
    return cp


def resolve(cp, kind, name, seen=()):
    sec = "%s:%s" % (kind, name)
    if sec not in cp:
        sys.exit("preset not found: [%s]" % sec)
    if sec in seen:
        sys.exit("inheritance loop at %s" % sec)
    out = {}
    parents = cp[sec].get("inherits", "").strip()
    for p in [p.strip().strip('"') for p in parents.split(";") if p.strip()]:
        out.update(resolve(cp, kind, p, seen + (sec,)))      # later parents override earlier
    out.update({k: v for k, v in cp[sec].items()})
    return out


def main():
    printer, print_, filament = sys.argv[1:4]
    cp = load()
    cfg = {}
    for kind, name in (("printer", printer), ("print", print_), ("filament", filament)):
        cfg.update(resolve(cp, kind, name))
    print("# Flattened from %s" % VENDOR)
    print("# printer = %s\n# print = %s\n# filament = %s" % (printer, print_, filament))
    for k in sorted(cfg):
        if k not in SKIP:
            print("%s = %s" % (k, cfg[k]))


if __name__ == "__main__":
    main()
