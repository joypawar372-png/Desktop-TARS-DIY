# Mini AI TARS Desktop Companion 🤖

An ultra-compact, conversational, 3D-printed TARS robot (inspired by *Interstellar*). This project shrinks TARS down to a desk-friendly **96 mm × 96 mm × 26 mm** cinematic square profile while utilizing a distributed "split-brain" architecture to run local LLMs and audio.

---

## 🧠 System Architecture Overview

To achieve an incredibly compact footprint without sacrificing processing power, this project uses a two-part split system:

1. **The Edge Client (TARS):** Powered by an **ESP32 Node32S**, TARS handles raw physical inputs/outputs—streaming voice from an I2S microphone, outputting generated audio via an I2S amplifier/speaker, and driving two SG90 servos for animated "chuckles" and gestures.
2. **The Host Brain (Local PC):** Runs a local Python pipeline. It ingests the audio stream, processes Speech-to-Text via **Faster-Whisper**, queries a local LLM via **Ollama** using a customized TARS personality system prompt, synthesizes natural-sounding speech via **Piper TTS**, and streams the audio back to TARS over Wi-Fi.

---

## 🗂️ Distributed Payload Design (Space Optimization)

Rather than stuffing all electronics into the center body—which would cause severe component collisions—components and weight are strategically distributed across all three moving slabs:

```text
+────────────────────────+────────────────────────+────────────────────────+
|   SLAB 1: LEFT LEG     |  SLAB 2: CENTER BODY   |   SLAB 3: RIGHT LEG    |
|       (26 mm Wide)     |      (44 mm Wide)      |      (26 mm Wide)      |
+────────────────────────+────────────────────────+────────────────────────+
|                        |  [0.96" OLED Screen]   |                        |
|                        |                        |  [MT3608 Boost Mod.]   |
|  [SG90 Servo 1]        |  [ESP32 Node32S]       |                        |
|        +               |        +               |  [SG90 Servo 2]        |
|  [18650 Battery Cell]  |  [MAX98357A Amp]       |        +               |
|  (Mounted Vertically)  |        +               |  [TP4056 Charger]      |
|                        |  [Mic & Mini Speaker]  |                        |
+────────────────────────+────────────────────────+────────────────────────+

SCAD CODE

// ====================================================================
//        TARS MODEL-S (SIMPLE HOLLOW EDITION) - 120mm CHASSIS
// ====================================================================
// A simplified, wide-open layout with zero internal hardware slots.
// Features clean, hollow interiors for manual hardware placement.
// ====================================================================

$fn = 64; // High-resolution curves for professional printing

// --- Global Structural Dimensions ---
total_height = 120;
total_depth  = 38;
wall         = 2.0; // Rigid 2mm outer wall thickness

left_width   = 30;
center_width = 60;  // Easily fits Node32S + 18650 side-by-side
right_width  = 30;

foot_radius  = 5.0; // Smooth curved bottom edges
pivot_height = 60;  // Exact midpoint axis (vertical)
pivot_depth  = 19;  // Exactly centered depth (19mm) for perfect balance

// --- INTERACTIVE VIEW MODE CONTROL ---
// "assembled"   = Full visual mockup of the three slabs aligned
// "exploded"    = Spaced out parts showing alignment
// "center_body" = Main center chassis only
// "left_leg"    = Left leg outer segment only
// "right_leg"   = Right leg outer segment only
part_to_show = "exploded"; 

// --- Color Scheme ---
tars_color = [0.85, 0.85, 0.85]; // Matte industrial silver

// --- Rendering Director ---
if (part_to_show == "assembled") {
    color(tars_color) left_leg();
    translate([left_width, 0, 0]) color(tars_color) center_body();
    translate([left_width + center_width, 0, 0]) color(tars_color) right_leg();
} else if (part_to_show == "exploded") {
    translate([-25, 0, 0]) color(tars_color) left_leg();
    translate([0, 0, 0]) color(tars_color) center_body();
    translate([85, 0, 0]) color(tars_color) right_leg();
} else if (part_to_show == "center_body") {
    center_body();
} else if (part_to_show == "left_leg") {
    left_leg();
} else if (part_to_show == "right_leg") {
    right_leg();
}

// ====================================================================
// --- SYSTEM MODULES ---
// ====================================================================

// Generates the core iconic TARS geometric slab profile with rounded feet
module tars_slab_base(w, h, d, r) {
    hull() {
        translate([0, 0, r]) cube([w, d, h - r]);
        translate([0, r, r]) rotate([0, 90, 0]) cylinder(r=r, h=w);
        translate([0, d-r, r]) rotate([0, 90, 0]) cylinder(r=r, h=w);
    }
}

// Hollow core generator (Leaves a completely open back to insert components)
module hollow_slab(w, h, d, r, wall_t) {
    difference() {
        tars_slab_base(w, h, d, r);
        // Hollows out from the back, leaving a solid front face
        translate([wall_t, wall_t, wall_t]) 
            cube([w - (2 * wall_t), d - wall_t + 1, h - (2 * wall_t)]);
    }
}

// --- SLAB 1: SIMPLE LEFT LEG ---
module left_leg() {
    difference() {
        hollow_slab(left_width, total_height, total_depth, foot_radius, wall);
        // Axle connection socket on internal face (right wall)
        translate([left_width - wall - 1, pivot_depth, pivot_height])
            rotate([0, 90, 0]) cylinder(r=3.5, h=wall + 2);
    }
}

// --- SLAB 3: SIMPLE RIGHT LEG ---
module right_leg() {
    difference() {
        hollow_slab(right_width, total_height, total_depth, foot_radius, wall);
        // Axle connection socket on internal face (left wall)
        translate([-1, pivot_depth, pivot_height])
            rotate([0, 90, 0]) cylinder(r=3.5, h=wall + 2);
    }
}

// --- SLAB 2: SIMPLE CENTER CHASSIS ---
module center_body() {
    difference() {
        hollow_slab(center_width, total_height, total_depth, foot_radius, wall);
        
        // 1. OLED Screen Cutout (0.96" window size: 22.4mm x 11.5mm)
        // Perfectly centered horizontally, 15mm down from the top edge
        translate([(center_width - 22.4)/2, -1, total_height - 15 - 11.5])
            cube([22.4, wall + 2, 11.5]);
            
        // 2. Left Axle Pass-through Hole
        translate([-1, pivot_depth, pivot_height])
            rotate([0, 90, 0]) cylinder(r=3.5, h=wall + 2);
            
        // 3. Right Axle Pass-through Hole
        translate([center_width - wall - 1, pivot_depth, pivot_height])
            rotate([0, 90, 0]) cylinder(r=3.5, h=wall + 2);
    }
}
