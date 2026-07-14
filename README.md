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
