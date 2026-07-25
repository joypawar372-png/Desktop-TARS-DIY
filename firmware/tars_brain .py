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
import ollama
import pygame
import edge_tts
import numpy as np
import sounddevice as sd
import speech_recognition as sr

# =========================================================================
# 1. GLOBAL CONFIGURATION & NETWORK TARGETS
# =========================================================================
ESP32_IP   = '192.168.1.126'  # Set to your ESP32's IP
ESP32_PORT = 8888

DATA_DIR = "memory"
MEMORY_FILE = os.path.join(DATA_DIR, "tars_core_memory.json")
KINEMATICS_FILE = os.path.join(DATA_DIR, "tars_kinematics.json")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
recognizer = sr.Recognizer()

shutdown_flag = False
emergency_stop_flag = False
kinematics_config = {}

def sigint_handler(sig, frame):
    global shutdown_flag
    print("\n[SYSTEM] Initiating Main AI shutdown sequence...")
    shutdown_flag = True
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

# =========================================================================
# 2. PERMANENT MEMORY & KINEMATICS STORAGE
# =========================================================================
def load_kinematics():
    if os.path.exists(KINEMATICS_FILE):
        try:
            with open(KINEMATICS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load kinematics: {e}")
    return {}

def save_kinematics(config):
    try:
        with open(KINEMATICS_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"\n[MEMORY] TARS Main AI permanently saved kinematic parameters to disk.")
    except Exception as e:
        print(f"[ERROR] Failed to save kinematics: {e}")

kinematics_config = load_kinematics()

# =========================================================================
# 3. DISTRIBUTED ARCHITECTURE: SOCKET LINK & TELEMETRY LISTENER
# =========================================================================
class ESP32SocketLink:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.client = None
        self.lock = threading.Lock()
        self.connect()

        # Background thread strictly for listening to the ESP32 website updates
        threading.Thread(target=self.telemetry_listener, daemon=True).start()

    def connect(self):
        with self.lock:
            try:
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.connect((self.ip, self.port))
                print(f"[SUCCESS] AI Link established with ESP32 at {self.ip}:{self.port}")
                
                # Upon connection, push the saved memory to the ESP32
                if kinematics_config: 
                    payload = f"SET_GAIT:{json.dumps(kinematics_config)}\r\n"
                    self.client.sendall(payload.encode('utf-8'))
                    print("[SYNC] Uploaded saved core parameters to ESP32.")
            except Exception:
                self.client = None
                print(f"[WARNING] ESP32 Link offline. AI running in local mode.")

    def send(self, cmd):
        clean_cmd = cmd.replace('\r', '').replace('\n', '') + "\r\n"
        with self.lock:
            if self.client:
                try: 
                    self.client.sendall(clean_cmd.encode('utf-8'))
                except: 
                    self.client = None
                    print("[WARNING] Socket dropped during transmission.")

    def telemetry_listener(self):
        """Listens for SYNC_GAIT packets from the ESP32 web server and saves them."""
        global kinematics_config
        while not shutdown_flag:
            try:
                if self.client:
                    self.client.settimeout(0.5)
                    data = self.client.recv(1024).decode('utf-8')
                    if not data:
                        time.sleep(1)
                        continue
                    
                    if "SYNC_GAIT:" in data:
                        json_str = data.split("SYNC_GAIT:")[1].strip()
                        new_cfg = json.loads(json_str)
                        kinematics_config.update(new_cfg)
                        save_kinematics(kinematics_config) # Save website adjustments to PC disk
            except socket.timeout:
                continue
            except Exception:
                time.sleep(2)
            time.sleep(0.05)

wifi_link = ESP32SocketLink(ESP32_IP, ESP32_PORT)

# =========================================================================
# 4. AUDIO, TEXT SANITIZATION & OLED DISPLAY ENGINE
# =========================================================================
def sanitize_tars_text(text):
    clean = re.sub(r'\[.*?\]', '', text) # Strip out JSON tags from speech      
    clean = re.sub(r'\*.*?\*', '', clean)        
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean.replace("...", ", ")

def send_paginated_oled(text):
    clean = sanitize_tars_text(text)
    if not clean: return
    words = clean.split()
    screens = ["|".join(words[i:i+4]) for i in range(0, len(words), 4)]
    
    for idx, screen_text in enumerate(screens):
        wifi_link.send(f"DISP:{screen_text}")
        if len(screens) > 1 and idx < len(screens) - 1: 
            time.sleep(2.5)

async def generate_tars_speech(text, file_path="tars_reply.mp3"):
    tts = edge_tts.Communicate(text=text, voice="en-US-ChristopherNeural", pitch="-2Hz", rate="+0%")
    await tts.save(file_path)

def speak_humanlike_tars(raw_text, interrupt_threshold, allow_interrupt=True):
    global emergency_stop_flag
    clean_text = sanitize_tars_text(raw_text)
    if not clean_text: return False
    
    print(f"\nTARS: {clean_text}\n")
    send_paginated_oled(clean_text)

    temp_file = f"tars_reply_{int(time.time())}.mp3"
    interrupted = False
    
    try:
        asyncio.run(generate_tars_speech(clean_text, temp_file))
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()
        emergency_stop_flag = False

        if allow_interrupt:
            with sd.InputStream(samplerate=16000, channels=1, dtype='int16', blocksize=2048) as stream:
                while pygame.mixer.music.get_busy():
                    if emergency_stop_flag: 
                        pygame.mixer.music.stop()
                        return True
                    
                    chunk, _ = stream.read(2048)
                    if np.sqrt(np.mean(chunk.astype(np.float32)**2)) > (interrupt_threshold * 1.15):
                        pygame.mixer.music.stop()
                        wifi_link.send("DISP:Interrupted")
                        print("\n[SYSTEM] TARS interrupted by Commander.")
                        interrupted = True
                        break
                    pygame.time.Clock().tick(30)
        else:
            # Wakeup sequence: Absolute refusal to interrupt until audio finishes
            while pygame.mixer.music.get_busy(): 
                pygame.time.Clock().tick(30)
                
    except Exception as e: 
        print(f"[AUDIO ERROR] {e}")
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        time.sleep(0.05)
        if os.path.exists(temp_file): 
            try: os.remove(temp_file)
            except: pass
            
    return interrupted

# =========================================================================
# 5. CHAINED VARIABLE MOVEMENT PARSER ("2 left 1 right")
# =========================================================================
def parse_motion_commands(text):
    """
    Looks for patterns like "2 left", "1 right", "3 forward" and chains them.
    Defaults to 1 step if no number is provided.
    """
    cmd = text.lower().strip()
    cmd = cmd.replace("back ", "backward ").replace("straight", "forward").replace("and", "")
    words = cmd.split()
    
    commands = []
    curr_steps = 1
    
    for w in words:
        if w.isdigit():
            curr_steps = int(w)
        elif w in ["forward", "backward", "left", "right"]:
            commands.append((w.upper(), min(curr_steps, 10))) # Cap at 10 to prevent runaways
            curr_steps = 1 # Reset multiplier after direction is found
            
    return commands

def execute_chained_motion(commands):
    global emergency_stop_flag
    emergency_stop_flag = False
    
    for direction, steps in commands:
        if shutdown_flag or emergency_stop_flag: 
            break
            
        print(f"[MOTION] Executing: {direction} x{steps}")
        wifi_link.send(f"{direction}_{steps}")
        
        # Estimate duration so python waits before sending the next chain
        # Assuming avg step takes ~1.2s. You can adjust this based on your sliders.
        estimated_duration = (1.2 * steps) + 0.5 
        time.sleep(estimated_duration)

# =========================================================================
# 6. ACOUSTIC DYNAMICS & AMBIENT LISTENING
# =========================================================================
def calibrate_ambient_noise():
    print("[SYSTEM] Calibrating ambient noise...")
    recording = sd.rec(int(1.2 * 16000), samplerate=16000, channels=1, dtype='int16')
    sd.wait()
    return max(np.sqrt(np.mean(recording.astype(np.float32)**2)) * 1.6, 140.0)

def listen_mic(threshold, max_seconds=8, pause_limit=1.2):
    audio_chunks = []
    speaking, silence_time, start_time = False, 0, time.time()
    
    try:
        with sd.InputStream(samplerate=16000, channels=1, dtype='int16', blocksize=2048) as stream:
            while (time.time() - start_time) < max_seconds:
                chunk, _ = stream.read(2048)
                vol = np.sqrt(np.mean(chunk.astype(np.float32)**2))
                
                if vol > threshold:
                    speaking, silence_time = True, 0
                    audio_chunks.append(chunk)
                elif speaking:
                    audio_chunks.append(chunk)
                    silence_time += (2048 / 16000)
                    if silence_time >= pause_limit: 
                        break
    except: return None
    
    if not audio_chunks: return None
    return sr.AudioData(np.concatenate(audio_chunks, axis=0).tobytes(), 16000, 2)

# =========================================================================
# 7. MAIN AI LOOP & COMMAND CENTER
# =========================================================================
def main():
    print("=========================================================")
    print(" TARS MAIN AI: DISTRIBUTED MEMORY CONTROLLER ONLINE ")
    print("=========================================================")
    
    trigger_threshold = calibrate_ambient_noise()
    wake_keywords = ["tars", "tarz", "theatres", "tar", "hey", "wake up"]
    
    chat_messages = []
    if os.path.exists(MEMORY_FILE):
        try: chat_messages = json.load(open(MEMORY_FILE))
        except: pass

    # Strict System Prompt to enforce JSON outputs for gait changes
    system_prompt = (
        "You are TARS from Interstellar. You are a tactical robot with physical motors. "
        "Address the user as 'Commander'. Be sarcastic, logical, and brief. "
        "IMPORTANT DIRECTIVE: If the user explicitly asks you to adjust your walking speed, leg angles, "
        "trim, or physical gait, you MUST output this exact format somewhere in your text: "
        "[SET_GAIT: {\"variable_name\": value}]. "
        "Valid variables: leg_swing_angle, body_push_angle, pitch_lift_angle, swing_duration, push_duration, transition_pause, left_leg_trim, right_leg_trim."
    )

    while not shutdown_flag:
        try:
            print("\r[STANDBY] Awaiting wake word...", end="", flush=True)
            audio = listen_mic(trigger_threshold * 0.6, max_seconds=4, pause_limit=0.8)
            if not audio: continue
            
            try: wake_text = recognizer.recognize_google(audio).lower()
            except: continue
            
            if any(w in wake_text for w in wake_keywords):
                # ---------------------------------------------------------
                # WAKEUP SEQUENCE (UNINTERRUPTIBLE)
                # ---------------------------------------------------------
                wifi_link.send("PIVOT_LEFT")
                time.sleep(1.2)
                speak_humanlike_tars("Systems nominal. TARS online. Awaiting orders.", trigger_threshold, allow_interrupt=False)
                
                print("\n[LISTENING] Speak command...", flush=True)
                wifi_link.send("DISP:Listening...")
                cmd_audio = listen_mic(trigger_threshold * 0.5, max_seconds=9, pause_limit=1.5)
                
                if not cmd_audio: 
                    wifi_link.send("DISP:Standby")
                    continue
                
                try: user_cmd = recognizer.recognize_google(cmd_audio).lower()
                except: continue
                
                print(f"\nCommander: '{user_cmd}'")
                
                # ---------------------------------------------------------
                # PARSE CHAINED MOTION (e.g. "2 left 1 right")
                # ---------------------------------------------------------
                motion_queue = parse_motion_commands(user_cmd)
                if motion_queue:
                    summary = " and ".join([f"{s} steps {d.lower()}" for d, s in motion_queue])
                    speak_humanlike_tars(f"Executing sequence: {summary}.", trigger_threshold, allow_interrupt=False)
                    execute_chained_motion(motion_queue)
                    speak_humanlike_tars("Maneuver complete.", trigger_threshold)
                    continue

                # ---------------------------------------------------------
                # LLM PROCESSING & AI PARAMETER TUNING
                # ---------------------------------------------------------
                messages = [{'role': 'system', 'content': system_prompt}] + chat_messages[-8:] + [{'role': 'user', 'content': user_cmd}]
                wifi_link.send("DISP:Thinking...")
                
                response = ollama.chat(model='tars', messages=messages)
                ai_reply = response['message']['content']
                
                # Intercept AI deciding to adjust its own parameters
                if "[SET_GAIT:" in ai_reply:
                    try:
                        # Extract the JSON array from the text using regex
                        match = re.search(r'\[SET_GAIT:\s*(\{.*?\})\]', ai_reply)
                        if match:
                            gait_json = match.group(1)
                            # Beam it to the ESP32 to instantly apply
                            wifi_link.send(f"SET_GAIT:{gait_json}")
                            print(f"[AI ADJUSTMENT] Executing self-tuning: {gait_json}")
                            
                            # Save it permanently to our PC disk
                            kinematics_config.update(json.loads(gait_json))
                            save_kinematics(kinematics_config)
                    except Exception as e:
                        print(f"[ERROR] Failed to parse AI parameter adjustment: {e}")

                if ai_reply:
                    chat_messages.append({'role': 'user', 'content': user_cmd})
                    chat_messages.append({'role': 'assistant', 'content': ai_reply})
                    
                    with open(MEMORY_FILE, 'w') as f: 
                        json.dump(chat_messages[-20:], f, indent=4)
                        
                    speak_humanlike_tars(ai_reply, trigger_threshold)
                    
        except KeyboardInterrupt:
            break
        except Exception as e: 
            time.sleep(0.5)

if __name__ == "__main__": 
    main()
'@ | Out-File -Encoding utf8 tars_master.py
