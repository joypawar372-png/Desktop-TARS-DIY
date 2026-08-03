# Mini AI TARS Desktop Companion 🤖

An ultra-compact, conversational, 3D-printed TARS robot (inspired by *Interstellar*). This project shrinks TARS down to a desk-friendly **96 mm × 96 mm × 26 mm** cinematic square profile while utilizing a distributed "split-brain" architecture to run local LLMs and audio.

---

## 🧠 System Architecture Overview

To achieve an incredibly compact footprint without sacrificing processing power, this project uses a two-part split system:

1. **The Edge Client (TARS):** Powered by an **ESP32 Node32S**, TARS handles raw physical inputs/outputs—streaming voice from an I2S microphone, outputting generated audio via an I2S amplifier/speaker, and driving two SG90 servos for animated "chuckles" and gestures.
2. **The Host Brain (Local PC):** Runs a local Python pipeline. It ingests the audio stream, processes Speech-to-Text via **Faster-Whisper**, queries a local LLM via **Ollama** using a customized TARS personality system prompt, synthesizes natural-sounding speech via **Piper TTS**, and streams the audio back to TARS over Wi-Fi.
3. Microcontroller (1x): ESP32 or Raspberry Pi Pico (selected for compact form factor).

Micro Servos (2x): SG90 Micro Servos (for leg articulation).

LiPo Battery (1x): 3.7V Lithium-Polymer (max 35mm width to fit internal guide rails).

OLED Display (1x): 0.96" I2C OLED Module.

Charging Module (1x): USB-C Charging/Protection Module (e.g., TP4056 with USB-C input).

Fasteners (16x): M2 x 5mm Self-Tapping Screws (for mounting components to internal standoffs).

Wiring (1x Set): Flexible silicone-insulated jumper wires (26-30 AWG recommended).

---
<img width="416" height="555" alt="images" src="https://github.com/user-attachments/assets/f3e853f6-c21b-484c-a28f-8f6542b22210" />


+────────────────────────+────────────────────────+────────────────────────+


# TARS AI Desktop Companion 🤖

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Arduino IDE](https://img.shields.io/badge/Arduino_IDE-C++-00979D?logo=arduino)](https://www.arduino.cc/)
[![Ollama](https://img.shields.io/badge/AI-Ollama_Llama_3.2-black)](https://ollama.ai/)
[![YouTube](https://img.shields.io/badge/YouTube-BRAVO__X1-red?logo=youtube)](https://www.youtube.com/)

An autonomous, voice-activated 3-legged desktop companion robot inspired by *Interstellar*. TARS features a local Python-based AI brain powered by Ollama, synced to an ESP32 hardware body via a high-speed TCP socket. 

## ✨ Core Features

* **🧠 Local LLM Brain:** Powered by Ollama (`llama3.2`) for fast, local, conversational AI.
* **🗣️ Voice & Acoustic Barge-in:** Real-time speech recognition with a dynamic pause engine and instant barge-in interruption.
* **👀 Animated OLED Interface:** 0.96" display featuring 30 FPS animated, wandering minus-sign eyes that yield to synchronized word-by-word text streaming when speaking.
* **🦿 3-Legged Kinematic Engine:** Custom 5-phase synchronous crutch-gait kinematics specifically engineered for mirrored servos. Supports multi-step pathing sequences (e.g., "Two steps forward, one right").
* **🌐 Web & OS Integration:** Can launch local Windows applications, read local PC files, fetch live DuckDuckGo web data (weather, news), and execute targeted site searches.
* **📱 Tactical Web Dashboard:** A responsive HTML dashboard hosted on the ESP32 for live PID tuning, servo trimming, inversion, and joystick control.

## 🛠️ Hardware Loadout

* **Microcontroller:** ESP32 (Wi-Fi enabled)
* **Actuators:** 2x Servos (SG90 or MG90S)
* **Display:** 0.96" I2C OLED (SSD1306)
* **Chassis:** Custom 3D-printed 3-legged upright body
* **Power:** 5V Buck Converter / LiPo Battery System

### Wiring Schematic
| Component | ESP32 Pin |
| :--- | :--- |
| Left Servo (PWM) | GPIO 18 |
| Right Servo (PWM) | GPIO 19 |
| OLED SDA | GPIO 21 |
| OLED SCL | GPIO 22 |

Core 0 will handle your servo kinematics, OLED parsing, web server, and TCP connections.

Core 1 will run two dedicated FreeRTOS tasks to stream raw 16kHz I2S audio over UDP sockets directly to the Python brain.

(Note: The Python Brain now has a USE_ESP32_AUDIO = True flag at the top. If you wired an I2S Mic and I2S Amp to the ESP32, leave it True. If you just stuffed a Bluetooth speaker inside his chassis, set it to False).

PART 1: The Hardware Interface (ESP32 Firmware)
You will need an INMP441 (Microphone) and a MAX98357A (Speaker Amp). Wire them to these specific ESP32 pins:

Mic: SCK to Pin 32, WS to Pin 33, SD to Pin 34, L/R to GND.

Speaker: BCLK to Pin 25, LRC to Pin 26, DIN to Pin 27.

## 💻 Software Dependencies

### 1. ESP32 Body (C++)
Install the following libraries via the Arduino Library Manager:
* `ESP32Servo`
* `Adafruit GFX Library`
* `Adafruit SSD1306`

### 2. Python AI Brain
Ensure Python 3.10+ is installed, then install the required modules:
```bash
pip install ollama pygame edge-tts numpy sounddevice SpeechRecognition ddgs psutil
}

Only the Paranoid Survive
