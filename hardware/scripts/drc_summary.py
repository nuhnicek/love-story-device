"""Run kicad-cli DRC and print a compact summary (ignores cosmetic silk issues)."""
import json, subprocess, sys, collections, tempfile, os
pcb = sys.argv[1]
out = os.path.join(tempfile.gettempdir(), "kc_drc.json")
subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json",
                "-o", out, pcb] + sys.argv[2:], check=True, capture_output=True)
d = json.load(open(out))
COSMETIC = {"silk_overlap", "silk_over_copper", "silk_edge_clearance",
            "lib_footprint_issues", "lib_footprint_mismatch",
            "nonmirrored_text_on_back_layer", "text_height", "text_thickness"}
c = collections.Counter(v["type"] for v in d["violations"])
print("all:", dict(c))
print("unconnected:", len(d.get("unconnected_items", [])))
for v in d["violations"]:
    if v["type"] not in COSMETIC:
        print(" ", v["severity"], v["type"], "|", " / ".join(i["description"] for i in v["items"]))
