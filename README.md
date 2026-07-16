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

// =========================================================================
// CODE 1: TARS REPLICA - CHASSIS & CYLINDRICAL SKID LEGS WITH DETENT POCKETS
// Features: Completely sharp center body, legs with front/back bottom roll edges,
//           wide-open internal cavity, and space-saving female detent lock tracks.
// =========================================================================

$fn = 64;

// --- Core Mechanical Geometry (mm) ---
body_w      = 60;   
body_d      = 40;   
body_h      = 120;  
wall        = 2.5;  // Rugged uniform side walls
cover_thick = 2;    
leg_r       = 6;    // Front/Back bottom edge roll radius

leg_w       = 20;   
print_gap   = 25;   

// Internal Workspace Extents
int_w = body_w - (2 * wall);
int_h = body_h - (2 * wall);
int_d = body_d - wall - cover_thick;

// --- Slicing Build Deck Grid Array ---
translate([0, 0, 0]) 
    main_chassis_cabinet();

translate([-(body_w/2 + leg_w/2 + print_gap), 0, 0])
    tars_skid_leg(side="left");

translate([(body_w/2 + leg_w/2 + print_gap), 0, 0])
    tars_skid_leg(side="right");

// =========================================================================
// HELPER: LEGS WITH SHARP SIDES AND CYLINDRICAL FRONT/BACK BOTTOM EDGES
// =========================================================================
module leg_skid_monolith(w, d, h, r) {
    hull() {
        // Sharp Top Plate Boundary
        translate([-w/2, -d/2, h - 0.1]) 
            cube([w, d, 0.1]);
        
        // Bottom Front Cylindrical Skid Edge
        translate([-w/2, -d/2 + r, r]) 
            rotate([0, 90, 0]) cylinder(r=r, h=w);
            
        // Bottom Back Cylindrical Skid Edge
        translate([-w/2, d/2 - r, r]) 
            rotate([0, 90, 0]) cylinder(r=r, h=w);
    }
}

// =========================================================================
// COMPONENT 1: ELECTRONICS CHASSIS CABINET (WITH DETENT RECESSES)
// =========================================================================
module main_chassis_cabinet() {
    difference() {
        // Sharp rectangular outer hull
        translate([-body_w/2, -body_d/2, 0]) 
            cube([body_w, body_d, body_h]);
        
        // 1. Clean Open Internal Cavity
        translate([-int_w/2, -body_d/2 + wall, wall]) 
            cube([int_w, int_d + 0.1, int_h]);
        
        // 2. Inset Lip Frame Border Step for Flush Seating
        translate([-(body_w - 2.5)/2, body_d/2 - cover_thick, 1.5]) 
            cube([body_w - 2.5, cover_thick + 0.1, body_h - 3]);
        
        // 3. Center Concentric Pass-Through Axle Holes
        translate([0, 0, body_h/2]) 
            rotate([0, 90, 0]) cylinder(r=3.5, h=body_w + 2, center=true);
        
        // 4. SPACE-SAVING DETENT LOCKING RECESSES (Horizontal retention grooves)
        for (z_pos = [25, 95]) {
            // Left Side Wall Grooves
            translate([-int_w/2 - 0.5, body_d/2 - cover_thick - 2.5, z_pos]) 
                cube([0.6, 5.2, 1.2], center=true);
            // Right Side Wall Grooves
            translate([int_w/2 + 0.5, body_d/2 - cover_thick - 2.5, z_pos]) 
                cube([0.6, 5.2, 1.2], center=true);
        }
        
        // 5. 0.96" OLED Screen Bezel
        translate([-22.4/2, -body_d/2 - 0.1, 98]) cube([22.4, wall + 0.2, 11.5]);
        
        // 6. TP4056 USB-C Interface Entry Port
        translate([-body_w/2 - 0.1, -body_d/2 + wall + 4, wall + 5]) cube([wall + 0.2, 5.0, 11.0]);
    }
}

// =========================================================================
// COMPONENT 2: OUTER LEGS (SHARP SIDES, CYLINDRICAL BOTTOM EDGES)
// =========================================================================
module tars_skid_leg(side="left") {
    leg_int_w = leg_w - (2 * wall);
    difference() {
        // Main Solid Leg Structure
        leg_skid_monolith(leg_w, body_d, body_h, leg_r);
        
        // 1. Deep Cavity Extraction
        translate([0, 0, 0])
            difference() {
                translate([-leg_int_w/2, -body_d/2 + wall, wall]) 
                    cube([leg_int_w, int_d + 0.1, int_h]);
                translate([-leg_w/2, -body_d/2 + leg_r, leg_r])
                    rotate([0,90,0]) cylinder(r=leg_r - wall, h=leg_w);
                translate([-leg_w/2, body_d/2 - leg_r, leg_r])
                    rotate([0,90,0]) cylinder(r=leg_r - wall, h=leg_w);
            }
        
        // 2. Rear Recessed Step Lip for Back Cover Seating
        translate([-(leg_w - 2.5)/2, body_d/2 - cover_thick, 1.5]) 
            cube([leg_w - 2.5, cover_thick + 0.1, body_h - 3]);
        
        // 3. SPACE-SAVING LEG DETENT RECESSES
        for (z_pos = [25, 95]) {
            translate([-leg_int_w/2 - 0.5, body_d/2 - cover_thick - 2.5, z_pos]) 
                cube([0.6, 5.2, 1.2], center=true);
            translate([leg_int_w/2 + 0.5, body_d/2 - cover_thick - 2.5, z_pos]) 
                cube([0.6, 5.2, 1.2], center=true);
        }
        
        // 4. Blind Pivot Axle Hole (Sealed completely on the exterior face)
        if (side == "left") {
            translate([0, 0, body_h/2]) rotate([0, 90, 0]) cylinder(r=3.5, h=leg_w/2 + 2);
        } else {
            translate([-(leg_w/2 + 2), 0, body_h/2]) rotate([0, 90, 0]) cylinder(r=3.5, h=leg_w/2 + 2);
        }
        
        // 5. Visual Segment Detail Paneling Lines
        translate([side == "left" ? leg_w/2 - 0.5 : -leg_w/2 - 0.1, -body_d/2 - 0.1, body_h/2]) cube([0.6, body_d + 0.2, 0.6]);
        translate([side == "left" ? leg_w/2 - 0.5 : -leg_w/2 - 0.1, -body_d/2 - 0.1, body_h/2 + 30]) cube([0.6, body_d + 0.2, 0.6]);
        translate([side == "left" ? leg_w/2 - 0.5 : -leg_w/2 - 0.1, -body_d/2 - 0.1, body_h/2 - 30]) cube([0.6, body_d + 0.2, 0.6]);
    }
}
