@'
import asyncio
import os
import re
import sys
import time
import json
import random
import socket
import signal
import threading
import subprocess
import webbrowser
import psutil
import requests
import ollama
import pygame
import edge_tts
import numpy as np
import sounddevice as sd
import speech_recognition as sr

# =========================================================================
# 1. GLOBAL CONFIGURATION & TACTICAL SETTINGS
# =========================================================================
ESP32_IP   = '192.168.1.126'  # TARS Body IP
ESP32_PORT = 8888

# IoT Node Configuration (ESP RainMaker or Local Webhook)
IOT_NODE_IP = '192.168.1.105' 

AUDIO_DIR = "audio"
DATA_DIR = "memory"
MEMORY_FILE = os.path.join(DATA_DIR, "tars_core_memory.json")
SIGH_SOUND_PATH = os.path.join(AUDIO_DIR, "sigh.mp3")

for directory in [AUDIO_DIR, DATA_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
recognizer = sr.Recognizer()
shutdown_flag = False

def sigint_handler(sig, frame):
    global shutdown_flag
    print("\n[SYSTEM] Initiating TARS shutdown sequence...")
    shutdown_flag = True
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

# =========================================================================
# 2. LONG-TERM MEMORY ENGINE
# =========================================================================
def load_memory():
    """Loads previous conversation context from disk to maintain continuity across reboots."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r') as f:
                return json.load(f)
        except: return []
    return []

def save_memory(chat_history):
    """Saves the last 20 interactions to prevent context bloat."""
    with open(MEMORY_FILE, 'w') as f:
        json.dump(chat_history[-20:], f, indent=4)

# =========================================================================
# 3. HIGH-DURABILITY WIRELESS SOCKET MATRIX
# =========================================================================
class ESP32SocketLink:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.client = None
        self.lock = threading.Lock()
        self.connect()

    def connect(self):
        with self.lock:
            if self.client:
                try: self.client.close()
                except: pass
            try:
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.settimeout(2.0)
                self.client.connect((self.ip, self.port))
                print(f"[SUCCESS] Tactical link established with TARS at {self.ip}:{self.port}")
            except Exception:
                self.client = None
                print(f"[WARNING] ESP32 Link offline. Operating in local-only mode.")

    def send(self, cmd):
        clean_cmd = cmd.replace('\r', '').replace('\n', '|') + "\r\n"
        with self.lock:
            if not self.client: self._reconnect_nolock()
            if self.client:
                try: self.client.sendall(clean_cmd.encode('utf-8'))
                except (socket.error, socket.timeout):
                    self._reconnect_nolock()
                    if self.client:
                        try: self.client.sendall(clean_cmd.encode('utf-8'))
                        except: pass

    def _reconnect_nolock(self):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(1.5)
            self.client.connect((self.ip, self.port))
        except Exception:
            self.client = None

wifi_link = ESP32SocketLink(ESP32_IP, ESP32_PORT)

# =========================================================================
# 4. THERMAL & HARDWARE TELEMETRY ENGINE
# =========================================================================
def hardware_telemetry_thread():
    """
    Monitors system stress. Prolonged 100% CPU/GPU loads during LLM generation
    can cause critical hardware failures (like SSD overheating).
    """
    critical_time = 0
    while not shutdown_flag:
        cpu_load = psutil.cpu_percent(interval=2)
        
        # If load is pegged above 90% for more than 15 seconds, trigger thermal warning
        if cpu_load > 90.0:
            critical_time += 2
        else:
            critical_time = 0

        if critical_time >= 15:
            warning_msg = "Commander, system telemetry indicates sustained critical hardware load. Monitor core temperatures immediately to prevent SSD failure."
            print(f"\n[CRITICAL WARNING]: {warning_msg}")
            wifi_link.send("DISP:THERMAL WARN")
            try:
                temp_audio = "thermal_warn.mp3"
                asyncio.run(generate_tars_speech(warning_msg, temp_audio))
                play_audio_file(temp_audio)
                if os.path.exists(temp_audio): os.remove(temp_audio)
            except: pass
            critical_time = -30 # Cooldown before warning again

        time.sleep(2)

# Start telemetry thread
threading.Thread(target=hardware_telemetry_thread, daemon=True).start()

# =========================================================================
# 5. IOT RELAY MATRIX (SMART HOME INTEGRATION)
# =========================================================================
def control_iot_relays(command):
    """
    Routes commands to a 4-relay ESP node.
    Relay mapping: 1=Kitchen Lights, 2=Plugs, 3=Exhaust Fan, 4=Aux
    """
    cmd = command.lower()
    relay_id = None
    state = "on" if "on" in cmd or "activate" in cmd else "off"

    if "kitchen light" in cmd: relay_id = 1
    elif "plug" in cmd: relay_id = 2
    elif "exhaust fan" in cmd or "vent" in cmd: relay_id = 3
    elif "relay 4" in cmd: relay_id = 4

    if relay_id:
        try:
            url = f"http://{IOT_NODE_IP}/relay?id={relay_id}&state={state}"
            # requests.get(url, timeout=2) # Uncomment when IP is live
            return f"[SYSTEM OVERRIDE: You successfully turned {state} relay {relay_id} on the kitchen IoT node.]"
        except Exception:
            return f"[SYSTEM OVERRIDE: You attempted to turn {state} relay {relay_id}, but the IoT node is offline.]"
    return ""

# =========================================================================
# 6. TEXT SANITIZATION & OLED FORMATTING
# =========================================================================
def sanitize_tars_text(text):
    contains_sigh = bool(re.search(r'(\*|\b)(sigh|sighs|groan|groans)(\*|\b)', text, re.IGNORECASE))
    clean = re.sub(r'\*.*?\*', '', text)        
    clean = re.sub(r'\[.*?\]', '', clean)       
    clean = re.sub(r'\(.*?\)', '', clean)       
    clean = re.sub(r'[#_~`]', '', clean)        
    clean = re.sub(r'\s+', ' ', clean).strip()
    clean = clean.replace("...", ", ").replace("—", ", ")
    return clean, contains_sigh

def format_for_oled(text, max_chars=20):
    clean, _ = sanitize_tars_text(text)
    words = clean.split()
    lines = []
    curr = ""
    for w in words:
        if len(curr) + len(w) + 1 <= max_chars: curr += (" " if curr else "") + w
        else:
            lines.append(curr)
            curr = w
            if len(lines) >= 4: break
    if curr and len(lines) < 4: lines.append(curr)
    return "|".join(lines)

# =========================================================================
# 7. AUDIO & OS OVERRIDES
# =========================================================================
def play_audio_file(filepath):
    if not os.path.exists(filepath): return
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy(): pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
    except Exception: pass

async def generate_tars_speech(text, file_path="tars_reply.mp3"):
    tts = edge_tts.Communicate(text=text, voice="en-US-ChristopherNeural", pitch="-2Hz", rate="+0%")
    await tts.save(file_path)

def speak_humanlike_tars(raw_text, interrupt_threshold, add_hmm=False, sample_rate=16000):
    clean_text, has_sigh = sanitize_tars_text(raw_text)
    if not clean_text: return False
    if add_hmm and not clean_text.lower().endswith(("hmm?", "hmm")):
        clean_text = clean_text.rstrip(" .!?") + ", hmm?"

    print(f"\nTARS: {clean_text}\n")
    wifi_link.send(f"DISP:{format_for_oled(clean_text)}")

    if has_sigh or (random.random() < 0.12 and not clean_text.startswith("*")):
        play_audio_file(SIGH_SOUND_PATH)

    interrupted = False
    temp_file = f"tars_reply_{int(time.time())}.mp3"
    try:
        asyncio.run(generate_tars_speech(clean_text, temp_file))
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
            while pygame.mixer.music.get_busy():
                chunk, _ = stream.read(2048)
                if np.sqrt(np.mean(chunk.astype(np.float32)**2)) > (interrupt_threshold * 2.2):
                    pygame.mixer.music.stop()
                    interrupted = True
                    wifi_link.send("DISP:Interrupted")
                    break
                pygame.time.Clock().tick(30)
    except Exception: pass
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        time.sleep(0.05)
        if os.path.exists(temp_file):
            try: os.remove(temp_file)
            except: pass
    return interrupted

def execute_system_command(text):
    cmd = text.lower()
    if any(k in cmd for k in ["open browser", "google"]):
        webbrowser.open("https://www.google.com")
        return "[SYSTEM OVERRIDE: Web browser launched.]"
    if "youtube" in cmd:
        webbrowser.open("https://www.youtube.com")
        return "[SYSTEM OVERRIDE: YouTube launched.]"
    
    iot_context = control_iot_relays(cmd)
    if iot_context: return iot_context

    return ""

def parse_motion_command(text):
    cmd = text.lower().strip()
    if any(k in cmd for k in ["push left", "shove left", "lean left"]): return ("PUSH_LEFT", 1)
    if any(k in cmd for k in ["push right", "shove right", "lean right"]): return ("PUSH_RIGHT", 1)

    steps = 1
    for w in cmd.split():
        if w.isdigit(): steps = int(w); break
    steps = max(1, min(steps, 10)) 

    if any(k in cmd for k in ["forward", "ahead", "straight"]): return ("FORWARD", steps)
    if any(k in cmd for k in ["left", "turn left"]): return ("LEFT", steps)
    if any(k in cmd for k in ["right", "turn right"]): return ("RIGHT", steps)
    return (None, 0)

# =========================================================================
# 8. ACOUSTIC DYNAMICS & MAIN LOOP
# =========================================================================
def calibrate_ambient_noise(duration=1.2, sample_rate=16000):
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    return max(np.sqrt(np.mean(recording.astype(np.float32)**2)) * 1.6, 140.0)

def listen_mic(threshold, max_seconds=8, pause_limit=1.2, sample_rate=16000):
    audio_chunks = []
    speaking = False
    silence_time = 0
    start_time = time.time()
    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
            while (time.time() - start_time) < max_seconds:
                chunk, _ = stream.read(2048)
                if np.sqrt(np.mean(chunk.astype(np.float32)**2)) > threshold:
                    speaking = True
                    silence_time = 0
                    audio_chunks.append(chunk)
                elif speaking:
                    audio_chunks.append(chunk)
                    silence_time += (2048 / sample_rate)
                    if silence_time >= pause_limit: break
    except Exception: return None
    if not audio_chunks: return None
    return sr.AudioData(np.concatenate(audio_chunks, axis=0).tobytes(), sample_rate, 2)

def main():
    print("==================================================")
    print("       TARS MASTER CONTROLLER - v3.0 ONLINE      ")
    print("==================================================")

    wifi_link.send("DISP:TARS Online")
    trigger_threshold = calibrate_ambient_noise()
    chat_messages = load_memory()
    followup_active = False

    while not shutdown_flag:
        try:
            user_cmd = ""
            if followup_active:
                wifi_link.send("DISP:Listening...")
                cmd_audio = listen_mic(trigger_threshold * 0.5, max_seconds=7, pause_limit=1.3)
                followup_active = False
                if not cmd_audio: continue
            else:
                audio = listen_mic(trigger_threshold * 0.6, max_seconds=4, pause_limit=0.8)
                if not audio: continue
                try: wake_text = recognizer.recognize_google(audio).lower()
                except: continue
                if any(w in wake_text for w in ["tars", "tarz", "hey", "hi", "ok"]):
                    wifi_link.send("DISP:Listening...")
                    cmd_audio = listen_mic(trigger_threshold * 0.6, max_seconds=9, pause_limit=1.2)
                    if not cmd_audio: continue
                else: continue

            try:
                user_cmd = recognizer.recognize_google(cmd_audio).lower()
                print(f"\nCommander: '{user_cmd}'")
            except: continue

            direction, steps = parse_motion_command(user_cmd)
            if direction:
                wifi_link.send(direction if "PUSH" in direction else f"{direction}_{steps}")
                speak_humanlike_tars(f"Executing {direction}.", trigger_threshold)
                followup_active = True
                continue

            sys_override = execute_system_command(user_cmd)

            system_prompt = (
                "You are TARS from Interstellar. Persona: Sarcastic, military tactical robot. "
                "Do NOT write out text stage directions. Address user as 'Commander'."
            )
            messages = [{'role': 'system', 'content': system_prompt}]
            messages.extend(chat_messages[-8:])

            final_prompt = f"{user_cmd}\n{sys_override}" if sys_override else user_cmd
            messages.append({'role': 'user', 'content': final_prompt})

            wifi_link.send("DISP:Thinking...")
            try:
                response = ollama.chat(model='tars', messages=messages)
                ai_reply = response['message']['content']
            except Exception: continue

            if ai_reply:
                chat_messages.append({'role': 'user', 'content': user_cmd})
                chat_messages.append({'role': 'assistant', 'content': ai_reply})
                save_memory(chat_messages)

                if not speak_humanlike_tars(ai_reply, trigger_threshold, add_hmm=True):
                    followup_active = True

        except Exception as e:
            time.sleep(0.5)

if __name__ == "__main__":
    main()
'@ | Out-File -Encoding utf8 tars_master.py
