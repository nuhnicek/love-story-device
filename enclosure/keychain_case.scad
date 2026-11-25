// GSM touch keychain — 3D-printable case (tray + lid), parametric.
// OpenSCAD 2026+.  Export:  enclosure/scripts/build.sh  (STL + preview + G-code)
//
// Stack, bottom to top (all from the KiCad boards in /hardware):
//   floor | LiPo 25x20x4 | carrier bottom-side parts (USB-C 3.2) | carrier PCB 0.8 |
//   SIM holder gap | SIM800L module | heart LED board + 0820 motor | lid with heart window
//
// Coordinates: interior origin = inner floor corner. +X = across the keychain
// (antenna channel on the left), +Y = from the USB-C end to the button / keyring end.

part = "assembly";   // "tray" | "lid" | "plate" (2 trays + 2 lids) | "assembly"

/* [Boards and parts] */
board_w = 25.2;        // carrier = SIM800L outline
board_l = 23.0;
pcb_t = 0.8;
bottom_parts_h = 3.2;  // tallest part under the carrier (USB-C receptacle)
sim_gap = 1.5;         // SIM holder under the SIM800L
module_h = 3.2;        // SIM800L PCB + shield
bat_w = 25; bat_l = 20; bat_h = 4.0;
heart_led_w = 12.5;    // LED-centre heart width on the heart board (build_heart.py WIDTH)
heart_edge = 1.9;      // LED centre -> heart board edge (build_heart.py EDGE)
heart_h = 1.5;         // heart PCB 0.8 + LEDs
motor_d = 8.0; motor_h = 2.0;   // 0820 coin motor
usb_x = 12.6;          // USB-C centre from the carrier's left edge
usb_w = 8.94; usb_h = 3.26;     // GCT USB4125 body
btn_x = 16.6;          // side switch actuator from the carrier's left edge
btn_below_pcb = 0.8;   // actuator centre below the carrier PCB (switch on the bottom side)
btn_protrusion = 0.55; // actuator tip beyond the carrier's top edge

/* [Case] */
wall = 1.6;            // outer wall = 0.8 tongue (tray) + 0.8 rim (lid)
floor_t = 1.2;
lid_t = 1.2;
corner_r = 2.5;
clr = 0.3;             // clearance around the boards
clr_top = 0.8;         // extra room at the button end (actuator sticks out)
fit = 0.15;            // tray/lid joint clearance
lip_h = 2.2;           // height of the tongue-and-groove joint
window_t = 0.6;        // heart window membrane (0 = open cut-out)
antenna = true;        // channel for the SIM800L spring antenna
antenna_w = 4.5;
loop_d = 4.2; loop_od = 9; loop_t = 3.6; loop_x = 5;

$fn = 64;

// ------------------------------------------------------------------ derived
ant = antenna ? antenna_w : 0;
iw = ant + board_w + 2 * clr;            // interior width  (X)
il = board_l + clr + clr_top;            // interior length (Y)
bx0 = ant + clr;                         // carrier left edge
by_usb = clr;                            // carrier USB-C edge
by_top = clr + board_l;                  // carrier button edge
z_pcb_bot = bat_h + bottom_parts_h + 0.2;
z_pcb_top = z_pcb_bot + pcb_t;
z_mod_top = z_pcb_top + sim_gap + module_h;
ih = z_mod_top + max(heart_h, motor_h) + 0.3;   // interior height
z_split = ih - lip_h;                    // tray outer wall ends here
tongue = wall / 2;

S = heart_led_w / 32;
function heart_pts(s, n = 240) =
  [for (i = [0 : n - 1]) let(t = 360 * i / n)
     [s * 16 * pow(sin(t), 3), s * (13 * cos(t) - 5 * cos(2 * t) - 2 * cos(3 * t) - cos(4 * t))]];
// heart board: LED curve centre relative to its bounding box top (lobes up, tip down)
heart_top_to_c = S * 11.84 + heart_edge;
heart_c = [iw / 2, il - clr - heart_top_to_c];
motor_c = [iw / 2, by_usb + motor_d / 2 + 0.1];

echo(str("Outer size: ", iw + 2 * wall, " x ", il + 2 * wall, " x ", ih + floor_t + lid_t, " mm"));

// ------------------------------------------------------------------ helpers
module rrect(w, l, r) {
  translate([r, r]) offset(r = r) square([max(w - 2 * r, 0.01), max(l - 2 * r, 0.01)]);
}
module interior2d(grow = 0) {            // interior outline, grown by `grow`
  translate([-grow, -grow]) rrect(iw + 2 * grow, il + 2 * grow, max(0.5 + grow, 0.5));
}
module outer2d() { translate([-wall, -wall]) rrect(iw + 2 * wall, il + 2 * wall, corner_r); }
module heart_board2d(grow = 0) { translate(heart_c) offset(r = heart_edge + grow) polygon(heart_pts(S)); }
module heart_window2d() { translate(heart_c) offset(r = 1.0) polygon(heart_pts(S)); }

// snap ridges on the long sides (tongue) and matching grooves (lid rim)
module snaps(h_extra = 0, d = 0.3) {
  for (sx = [0, 1]) {
    x = sx == 0 ? -tongue : iw + tongue;
    translate([x, il / 2, z_split + lip_h * 0.45])
      rotate([90, 0, 0]) linear_extrude(height = 8 + h_extra, center = true)
        polygon(sx == 0 ? [[0, -0.6], [-d, 0], [0, 0.6]] : [[0, -0.6], [d, 0], [0, 0.6]]);
  }
}

// ------------------------------------------------------------------ tray
module usb_cutout() {
  zc = z_pcb_bot - usb_h / 2;
  // opening for the receptacle
  translate([bx0 + usb_x, -wall - 1, zc]) rotate([-90, 0, 0])
    linear_extrude(height = wall + 2) offset(r = 1.2) square([usb_w + 0.6 - 2.4, usb_h + 0.6 - 2.4], center = true);
  // outside recess so the plug's overmold can sit close to the receptacle
  translate([bx0 + usb_x, -wall - 1, zc]) rotate([-90, 0, 0])
    linear_extrude(height = 1 + wall - 0.5) offset(r = 2.5) square([12.8 - 5, 7.0 - 5], center = true);
}

module button_tab(cut = true) {
  // U-shaped slot through the wall leaves a flexing tab hinged at the bottom
  tw = 4.6; th = 6.2; slot = 0.5;
  zc = z_pcb_bot - btn_below_pcb;
  x = bx0 + btn_x;
  z0 = zc - th / 2 - 1.2;          // hinge
  if (cut) {
    translate([x, il - 0.01, z0]) difference() {
      translate([-tw / 2 - slot, 0, 0]) cube([tw + 2 * slot, wall + 0.02, th + slot]);
      translate([-tw / 2, -0.01, -0.01]) cube([tw, wall + 0.04, th]);
    }
  } else {
    // nub on the inside of the tab, touching the actuator
    nub = clr_top - btn_protrusion - 0.05;
    translate([x - 1.0, il - nub, zc - 0.6]) cube([2.0, nub + 0.01, 1.2]);
  }
}

module keyring() {
  translate([loop_x, il + wall + loop_od / 2 - 1.2, -floor_t]) difference() {
    hull() {
      cylinder(d = loop_od, h = loop_t);
      translate([-loop_od / 2, -loop_od / 2 - 0.5, 0]) cube([loop_od, 0.1, loop_t]);
    }
    translate([0, 0, -1]) cylinder(d = loop_d, h = loop_t + 2);
  }
}

module tray() {
  difference() {
    union() {
      // floor + outer wall up to the split
      translate([0, 0, -floor_t]) linear_extrude(height = z_split + floor_t) outer2d();
      // tongue: inner half of the wall continues to the top
      translate([0, 0, z_split - 0.01]) linear_extrude(height = lip_h + 0.01)
        difference() { interior2d(tongue); interior2d(0); }
      snaps();
      keyring();
    }
    // interior
    linear_extrude(height = ih + 1) interior2d(0);
    usb_cutout();
    button_tab(cut = true);
  }
  button_tab(cut = false);
}

// ------------------------------------------------------------------ lid
module lid() {
  difference() {
    union() {
      // top plate
      translate([0, 0, ih]) linear_extrude(height = lid_t) outer2d();
      // rim: outer half of the wall, down to the split
      translate([0, 0, z_split]) linear_extrude(height = lip_h + 0.01)
        difference() { outer2d(); interior2d(tongue + fit); }
      // locating rings for the heart board and the motor
      translate([0, 0, ih - 0.8]) linear_extrude(height = 0.81) {
        difference() { heart_board2d(0.25 + 0.8); heart_board2d(0.25); }
        translate(motor_c) difference() { circle(d = motor_d + 0.5 + 1.6); circle(d = motor_d + 0.5); }
      }
    }
    // heart window: pocket from the inside, leaving a thin light-diffusing membrane
    translate([0, 0, ih - 1]) linear_extrude(height = 1 + lid_t - window_t + (window_t == 0 ? 1 : 0))
      heart_window2d();
    snaps(h_extra = 0.6, d = 0.35);
    // keep the rings out of the joint
    translate([0, 0, ih - 1]) linear_extrude(height = 1) difference() { interior2d(5); interior2d(0); }
  }
}

// ------------------------------------------------------------------ contents (preview only)
module contents() {
  color("silver", 0.8) translate([bx0, by_usb + (board_l - bat_l), 0]) cube([bat_w, bat_l, bat_h]);
  color("green") translate([bx0, by_usb, z_pcb_bot]) cube([board_w, board_l, pcb_t]);
  color("gainsboro") translate([bx0 + usb_x - usb_w / 2, by_usb - 0.5, z_pcb_bot - usb_h]) cube([usb_w, 7.4, usb_h]);
  color("firebrick") translate([bx0, by_usb, z_pcb_top + sim_gap]) cube([board_w, board_l, module_h]);
  color("darkgreen") translate([0, 0, z_mod_top]) linear_extrude(height = heart_h) heart_board2d();
  color("dimgray") translate([motor_c[0], motor_c[1], z_mod_top]) cylinder(d = motor_d, h = motor_h);
}

// ------------------------------------------------------------------ output
module lid_print() { translate([0, 0, ih + lid_t]) rotate([180, 0, 0]) translate([0, -il, 0]) lid(); }
pitch_x = iw + 2 * wall + 8;
pitch_y = il + 2 * wall + loop_od + 6;

if (part == "plate") {
  // a pair of keychains, everything flat on the bed, no supports needed
  for (i = [0, 1]) {
    translate([i * pitch_x, 0, floor_t]) tray();
    translate([i * pitch_x, pitch_y, 0]) lid_print();
  }
} else if (part == "tray") {
  tray();
} else if (part == "lid") {
  // printed upside down: the window face on the bed gives a smooth outer surface
  lid_print();
} else {
  tray();
  contents();
  color("white", 0.45) translate([0, 0, 6]) lid();   // lifted 6 mm so the inside is visible
}
