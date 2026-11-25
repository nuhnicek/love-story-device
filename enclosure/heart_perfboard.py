#!/usr/bin/env python3
"""
Heart LED board on a universal (perf) board: 10 x 3 mm through-hole LEDs on the
2.54 mm grid, one resistor per LED, the 0820 motor in the middle.

Writes:
  heart_layout.scad          positions used by keychain_case.scad (lid holes, posts)
  out/heart_perfboard.png    build drawing (component side + wiring side)
  out/heart_perfboard.txt    hole-by-hole build list

Grid: column c (left..right), row r (bottom..top), origin = heart centre, pitch 2.54 mm.
All LEDs stand with their two legs in vertically adjacent holes, so an LED whose legs are
in holes (c, r) and (c, r+1) has its centre at (c, r+0.5).

  python3 enclosure/heart_perfboard.py
"""
import itertools
import math
import os

from PIL import Image, ImageDraw, ImageFont

P = 2.54
COLS = range(-5, 6)          # 11 holes wide  -> cut board 27.9 mm
ROWS = range(-4, 5)          # 9 holes tall   -> cut board 22.9 mm
LED_FLANGE_R = 1.95          # 3 mm LED flange (3.8-3.9 mm) / 2
MOTOR_C = (0.0, 0.0)         # motor centre, mm (in the middle of the heart)
MOTOR_R = 4.0 + 0.35         # 0820 motor radius + margin
RES_R = 0.95                 # 1/8 W resistor body radius (lying flat)
RES_LEN = 3.4                # 1/8 W body length

# LED lower-leg holes: a heart, symmetric about column 0
LEDS = [(0, 2), (2, 3), (4, 2), (4, 0), (2, -2), (0, -3), (-2, -2), (-4, 0), (-4, 2), (-2, 3)]
LED_C = [(c * P, (r + 0.5) * P) for c, r in LEDS]
LED_HOLES = {(c, r) for c, r in LEDS} | {(c, r + 1) for c, r in LEDS}
ALL_HOLES = {(c, r) for c in COLS for r in ROWS}


def mm(h):
    return (h[0] * P, h[1] * P)


def seg_point_dist(a, b, p):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


def body(e1, e2):
    """resistor body segment (centred between its two lead holes)"""
    a, b = mm(e1), mm(e2)
    cx, cy = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    ux, uy = (b[0] - a[0]) / (2 * P), (b[1] - a[1]) / (2 * P)
    h = RES_LEN / 2 - RES_R
    return (cx - ux * h, cy - uy * h), (cx + ux * h, cy + uy * h)


def seg_seg_dist(s, t):
    return min(seg_point_dist(s[0], s[1], t[0]), seg_point_dist(s[0], s[1], t[1]),
               seg_point_dist(t[0], t[1], s[0]), seg_point_dist(t[0], t[1], s[1]))


def candidates(i):
    """resistor options for LED i: (anode hole, cathode hole, R end at anode side, R far end)"""
    c, r = LEDS[i]
    out = []
    for anode, cathode in (((c, r), (c, r + 1)), ((c, r + 1), (c, r))):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            e1 = (anode[0] + dx, anode[1] + dy)       # next to the anode: a solder bridge
            for ex, ey in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                mid = (e1[0] + ex, e1[1] + ey)
                e2 = (e1[0] + 2 * ex, e1[1] + 2 * ey)
                holes = (e1, mid, e2)
                if any(h not in ALL_HOLES or h in LED_HOLES for h in holes):
                    continue
                s = body(e1, e2)
                if any(seg_point_dist(s[0], s[1], lc) < LED_FLANGE_R + RES_R for lc in LED_C):
                    continue
                if seg_point_dist(s[0], s[1], MOTOR_C) < MOTOR_R + RES_R:
                    continue
                # prefer resistors outside the heart, away from the centre
                score = -math.hypot(*mm(mid))
                out.append((score, anode, cathode, e1, mid, e2, s))
    return sorted(out)


def solve():
    cand = [candidates(i) for i in range(len(LEDS))]
    order = sorted(range(len(LEDS)), key=lambda i: len(cand[i]))
    chosen = {}

    def ok(x):
        used = set()
        for y in chosen.values():
            used |= {y[3], y[4], y[5], y[1], y[2]}
        if {x[3], x[4], x[5]} & used:
            return False
        return all(seg_seg_dist(x[6], y[6]) >= 2 * RES_R + 0.2 for y in chosen.values())

    def rec(k):
        if k == len(order):
            return True
        i = order[k]
        for x in cand[i]:
            if ok(x):
                chosen[i] = x
                if rec(k + 1):
                    return True
                del chosen[i]
        return False

    if not rec(0):
        raise SystemExit("no resistor placement found")
    return [chosen[i] for i in range(len(LEDS))]


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(here, "out"), exist_ok=True)
    sol = solve()
    used = LED_HOLES | {h for x in sol for h in (x[3], x[4], x[5])}

    # lid hold-down posts: free spots anywhere on the board (not only holes), away from
    # LEDs, resistor bodies and leads, the motor and any used hole; one per quadrant,
    # as far out as possible so the board can't rock.
    POST_R = 1.1
    xs = [i * 0.25 for i in range(int(COLS[0] * P / 0.25) - 4, int(COLS[-1] * P / 0.25) + 5)]
    ys = [j * 0.25 for j in range(int(ROWS[0] * P / 0.25) - 4, int(ROWS[-1] * P / 0.25) + 5)]
    edge_x = (COLS[-1] + 0.5) * P - POST_R - 0.3
    edge_lo, edge_hi = (ROWS[0] - 0.5) * P + POST_R + 0.3, (ROWS[-1] + 0.5) * P - POST_R - 0.3
    def clear(x, y):
        if abs(x) > edge_x or not (edge_lo <= y <= edge_hi):
            return False
        if any(math.hypot(x - lc[0], y - lc[1]) < LED_FLANGE_R + POST_R + 0.2 for lc in LED_C):
            return False
        if math.hypot(x - MOTOR_C[0], y - MOTOR_C[1]) < MOTOR_R + POST_R + 0.2:
            return False
        for q in sol:
            if seg_point_dist(mm(q[3]), mm(q[5]), (x, y)) < RES_R + POST_R + 0.2:
                return False
        return all(math.hypot(x - mm(h)[0], y - mm(h)[1]) >= POST_R + 0.6 for h in used)
    posts = []
    for sx, sy in ((-1, 1), (1, 1), (-1, -1), (1, -1)):
        best = None
        for x in xs:
            for y in ys:
                if x * sx > 0 and y * sy > 0 and clear(x, y):
                    score = abs(x) + 1.3 * abs(y)
                    if best is None or score > best[0]:
                        best = (score, x, y)
        if best:
            posts.append((best[1], best[2]))
    if len(posts) < 3:
        raise SystemExit("not enough room for lid posts")

    board_w = (len(COLS) - 1) * P + P
    board_h = (len(ROWS) - 1) * P + P
    board_c = ((COLS[0] + COLS[-1]) / 2 * P, (ROWS[0] + ROWS[-1]) / 2 * P)

    with open(os.path.join(here, "heart_layout.scad"), "w") as f:
        f.write("// generated by heart_perfboard.py, do not edit\n")
        f.write("hb_w = %.2f; hb_h = %.2f;\n" % (board_w, board_h))
        f.write("hb_centre = [%.3f, %.3f];  // board centre relative to heart centre\n" % board_c)
        f.write("hb_leds = [%s];\n" % ", ".join("[%.3f, %.3f]" % c for c in LED_C))
        f.write("hb_posts = [%s];\n" % ", ".join("[%.3f, %.3f]" % p for p in posts))
        f.write("hb_motor = [%.3f, %.3f];\n" % MOTOR_C)

    # ---------------------------------------------------------------- drawing
    S, M = 26, 70                     # px per mm, margin
    W = int(board_w * S + 2 * M)
    H = int(board_h * S + 2 * M + 70)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 22)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 17)
    except OSError:
        font = small = ImageFont.load_default()

    def view(title, mirror):
        im = Image.new("RGB", (W, H), "white")
        d = ImageDraw.Draw(im)

        def px(x, y):
            x = -x if mirror else x
            return (M + (x - (board_c[0] - board_w / 2) if not mirror else x + board_c[0] + board_w / 2) * S,
                    M + 70 + ((board_c[1] + board_h / 2) - y) * S)

        x0, y0 = px(board_c[0] - board_w / 2 if not mirror else board_c[0] + board_w / 2, board_c[1] + board_h / 2)
        d.rectangle([x0, y0, x0 + board_w * S, y0 + board_h * S], fill="#f3e2b8", outline="#8a6d2e", width=3)
        for k, line in enumerate(title.split("\n")):
            d.text((M, 8 + 28 * k), line, fill="black", font=font)
        for h in ALL_HOLES:
            x, y = px(*mm(h))
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill="#c98f3a" if mirror else "#e0c48a")
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill="white")
        if not mirror:
            mx, my = px(*MOTOR_C)
            d.ellipse([mx - 4 * S, my - 4 * S, mx + 4 * S, my + 4 * S], outline="#555", width=3)
            d.text((mx - 40, my - 10), "MOTOR", fill="#555", font=small)
            for i, x in enumerate(sol):
                a, b = (px(*p) for p in x[6])
                d.line([a, b], fill="#3a6fd8", width=int(2 * RES_R * S))
                e1, e2 = px(*mm(x[3])), px(*mm(x[5]))
                d.line([e1, e2], fill="#3a6fd8", width=3)
                mx2, my2 = px(*mm(x[4]))
                d.text((mx2 - 10, my2 - 10), "R%d" % (i + 1), fill="white", font=small)
            for i, (lc, x) in enumerate(zip(LED_C, sol)):
                cx, cy = px(*lc)
                r = LED_FLANGE_R * S
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#ff8fc8", outline="#b0306e", width=3)
                ax, ay = px(*mm(x[1]))
                kx, ky = px(*mm(x[2]))
                d.text((ax - 6, ay - 11), "+", fill="black", font=font)
                d.line([kx - 8, ky, kx + 8, ky], fill="black", width=3)    # flat side = cathode
                d.text((cx + r - 4, cy - r - 18), "D%d" % (i + 1), fill="#b0306e", font=small)
            for p in posts:
                x, y = px(*p)
                r = 1.1 * S
                d.ellipse([x - r, y - r, x + r, y + r], outline="#2a9d2a", width=4)
        else:
            plus = [mm(x[5]) for x in sol]
            minus = [mm(x[2]) for x in sol]
            for x in sol:     # anode -> resistor: solder bridge between neighbouring pads
                a, b = px(*mm(x[1])), px(*mm(x[3]))
                d.line([a, b], fill="#999", width=10)

            def chain(pts, colour):
                # one wire visiting the points in order around the heart, starting at the
                # bottom (next to the carrier's HEART pads), so it never crosses itself
                def ang(q):
                    return (math.atan2(q[1], q[0]) + math.pi / 2) % (2 * math.pi)
                path = sorted(set(pts), key=ang)
                d.line([px(*p) for p in path], fill=colour, width=5)
                for p in path:
                    x, y = px(*p)
                    d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=colour)
                return path[0]

            s_plus = chain(plus, "#d62828")
            s_minus = chain(minus, "#222")
            for p, label, col in ((s_plus, "HEART + (carrier HT1)", "#d62828"),
                                  (s_minus, "HEART - (carrier HT2)", "#222")):
                x, y = px(*p)
                d.text((x + 12, y + 10), label, fill=col, font=small)
        return im

    top = view("COMPONENT SIDE (LEDs, resistors, motor)\n+ = LED anode (long leg)   bar = cathode (flat side)   green = lid post", False)
    bot = view("WIRING SIDE (board flipped, mirrored)\nred = + wire   black = - wire   grey = solder bridge", True)
    out = Image.new("RGB", (W * 2 + 30, H), "white")
    out.paste(top, (0, 0)); out.paste(bot, (W + 30, 0))
    out.save(os.path.join(here, "out", "heart_perfboard.png"))

    with open(os.path.join(here, "out", "heart_perfboard.txt"), "w") as f:
        f.write("Heart perfboard: cut a %d x %d-hole piece (%.1f x %.1f mm).\n" % (
            len(COLS), len(ROWS), board_w, board_h))
        f.write("Holes are (column, row): columns %d..%d left to right, rows %d..%d bottom to top,\n"
                "(0,0) = the hole under the motor centre. Component side up.\n\n" % (
                    COLS[0], COLS[-1], ROWS[0], ROWS[-1]))
        for i, x in enumerate(sol):
            f.write("D%-2d anode (long leg) %-8s cathode %-8s | R%-2d %s - %s (body over %s)\n" % (
                i + 1, x[1], x[2], i + 1, x[3], x[5], x[4]))
        f.write("\nUnderside: bridge each LED anode to the resistor end next to it; join all far "
                "resistor ends with the + wire (to carrier HEART +), all cathodes with the - wire "
                "(to carrier HEART -).\n")
        f.write("Lid hold-down posts press on the board at (mm from the motor-centre hole): %s.\n"
                "Keep those spots (green circles in the drawing) free of wires and solder blobs.\n"
                "Use insulated wire (e.g. 0.1-0.2 mm enamelled or Kynar) for the + and - wires; "
                "crossings are fine.\n" % ", ".join("(%.1f, %.1f)" % p for p in posts))
    print("heart layout: %d LEDs, %d resistors, %d posts, board %.1f x %.1f mm" % (
        len(LEDS), len(sol), len(posts), board_w, board_h))


if __name__ == "__main__":
    main()
