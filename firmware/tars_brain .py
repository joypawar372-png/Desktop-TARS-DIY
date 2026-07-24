@'
import asyncio
import os
import re
import sys
import time
import random
import socket
import signal
import threading
import subprocess
import webbrowser
import ollama
import pygame
import edge_tts
import numpy as np
import sounddevice as sd
import speech_recognition as sr

# =========================================================================
# 1. GLOBAL CONFIGURATION & TACTICAL SETTINGS
# =========================================================================
ESP32_IP   = '192.168.1.126'  # <-- UPDATE THIS to match TARS's OLED IP
ESP32_PORT = 8888

AUDIO_DIR = "audio"
SIGH_SOUND_PATH = os.path.join(AUDIO_DIR, "sigh.mp3")

# Ensure sound directories exist
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)

# Initialize Audio Mixer
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
recognizer = sr.Recognizer()

# Global state control
shutdown_flag = False

def sigint_handler(sig, frame):
    global shutdown_flag
    print("\n[SYSTEM] Initiating TARS shutdown sequence...")
    shutdown_flag = True
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

# =========================================================================
# 2. HIGH-DURABILITY WIRELESS SOCKET MATRIX
# =========================================================================
class ESP32SocketLink:
    """Thread-safe, self-healing TCP socket bridge to the ESP32 kinematics controller."""
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
                self.client = None
            
            try:
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.settimeout(2.0)
                self.client.connect((self.ip, self.port))
                print(f"[SUCCESS] Tactical link established with TARS at {self.ip}:{self.port}")
            except Exception as e:
                self.client = None
                print(f"[WARNING] ESP32 Link offline ({self.ip}:{self.port}). Operating in local-only mode.")

    def send(self, cmd):
        """Sends a raw command to the ESP32 with auto-reconnect fallback."""
        clean_cmd = cmd.replace('\r', '').replace('\n', '|') + "\r\n"
        with self.lock:
            if not self.client:
                self._reconnect_nolock()
            
            if self.client:
                try:
                    self.client.sendall(clean_cmd.encode('utf-8'))
                except (socket.error, socket.timeout):
                    print("[LINK ERROR] Packet dropped. Re-establishing connection...")
                    self._reconnect_nolock()
                    if self.client:
                        try: self.client.sendall(clean_cmd.encode('utf-8'))
                        except: pass

    def _reconnect_nolock(self):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(1.5)
            self.client.connect((self.ip, self.port))
            print("[SUCCESS] Link re-established.")
        except Exception:
            self.client = None

wifi_link = ESP32SocketLink(ESP32_IP, ESP32_PORT)

# =========================================================================
# 3. OLED DISPLAY FORMATTER & TEXT SANITIZATION ENGINE
# =========================================================================
def sanitize_tars_text(text):
    """
    Removes stage directions (*sigh*, [cough], (dramatic pause)) from text
    so TTS speaks clean words without pronouncing formatting tags.
    """
    # Detect stage directions for real audio triggers
    contains_sigh = bool(re.search(r'(\*|\b)(sigh|sighs|groan|groans)(\*|\b)', text, re.IGNORECASE))
    
    # Strip stage directions in asterisks, square brackets, or parentheses
    clean = re.sub(r'\*.*?\*', '', text)        # e.g., *sighs heavily*
    clean = re.sub(r'\[.*?\]', '', clean)       # e.g., [dramatic pause]
    clean = re.sub(r'\(.*?\)', '', clean)       # e.g., (clears throat)
    clean = re.sub(r'[#_~`]', '', clean)        # Markdown artifacts

    # Normalize whitespace & punctuation
    clean = re.sub(r'\s+', ' ', clean).strip()
    clean = clean.replace("...", ", ").replace("—", ", ")
    
    return clean, contains_sigh

def format_for_oled(text, max_chars=20):
    """Formats raw text into a 4-line grid for SSD1306 displays."""
    clean, _ = sanitize_tars_text(text)
    words = clean.split()
    lines = []
    curr = ""
    for w in words:
        if len(curr) + len(w) + 1 <= max_chars:
            curr += (" " if curr else "") + w
        else:
            lines.append(curr)
            curr = w
            if len(lines) >= 4: break
    if curr and len(lines) < 4:
        lines.append(curr)
    return "|".join(lines)

# =========================================================================
# 4. AUDIO & SPEECH ENGINE (REAL SFX + INTERRUPTIBLE TTS)
# =========================================================================
def play_audio_file(filepath):
    """Plays an audio file synchronously if it exists."""
    if not os.path.exists(filepath):
        return
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
    except Exception as e:
        print(f"[AUDIO ERROR] Failed to play {filepath}: {e}")

async def generate_tars_speech(text, file_path="tars_reply.mp3"):
    """Generates audio via Edge-TTS with pitch/rate tuning."""
    tts = edge_tts.Communicate(text=text, voice="en-US-ChristopherNeural", pitch="-2Hz", rate="+0%")
    await tts.save(file_path)

def speak_humanlike_tars(raw_text, interrupt_threshold, add_hmm=False, sample_rate=16000):
    """
    Scrub stage notes, play actual SFX for sighs, update OLED, and stream spoken audio.
    Supports mic interruption during speech output.
    """
    clean_text, has_sigh = sanitize_tars_text(raw_text)
    
    if not clean_text:
        return False

    if add_hmm and not clean_text.lower().endswith(("hmm?", "hmm")):
        clean_text = clean_text.rstrip(" .!?") + ", hmm?"

    print(f"\nTARS: {clean_text}\n")
    wifi_link.send(f"DISP:{format_for_oled(clean_text)}")

    # Play real audio sigh if detected or triggered randomly
    if has_sigh or (random.random() < 0.12 and not clean_text.startswith("*")):
        play_audio_file(SIGH_SOUND_PATH)

    interrupted = False
    temp_file = f"tars_reply_{int(time.time())}.mp3"

    try:
        asyncio.run(generate_tars_speech(clean_text, temp_file))
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        # Listen for user interruption while speaking
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
            while pygame.mixer.music.get_busy():
                chunk, _ = stream.read(2048)
                rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))
                if rms > (interrupt_threshold * 2.2):
                    pygame.mixer.music.stop()
                    interrupted = True
                    wifi_link.send("DISP:Interrupted...")
                    print("[TARS] Speech interrupted by Commander.")
                    break
                pygame.time.Clock().tick(30)
    except Exception as e:
        print(f"[TTS ERROR]: {e}")
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        time.sleep(0.05)
        if os.path.exists(temp_file):
            try: os.remove(temp_file)
            except: pass

    return interrupted

# =========================================================================
# 5. OS ACCESS & SYSTEM OVERRIDES
# =========================================================================
def background_timer_thread(seconds, label="Timer"):
    """Background countdown thread that triggers audio alerts."""
    time.sleep(seconds)
    alert_text = f"Commander, your {label} timer for {seconds} seconds has elapsed."
    print(f"\n[ALERT]: {alert_text}")
    
    # Generate temporary audio alert
    temp_alert = "timer_alert.mp3"
    try:
        asyncio.run(generate_tars_speech(alert_text, temp_alert))
        play_audio_file(temp_alert)
        if os.path.exists(temp_alert): os.remove(temp_alert)
    except Exception as e:
        print(f"[TIMER ALERT ERROR]: {e}")

def execute_system_command(text):
    """Parses user intent for OS actions and returns context notes for Ollama."""
    cmd = text.lower()

    # Browser Access
    if any(k in cmd for k in ["open browser", "open google", "launch browser"]):
        webbrowser.open("https://www.google.com")
        return "[SYSTEM OVERRIDE: Web browser launched on primary display. Acknowledge sarcastic readiness.]"

    if "youtube" in cmd:
        webbrowser.open("https://www.youtube.com")
        return "[SYSTEM OVERRIDE: YouTube launched.]"

    if "search for" in cmd:
        query = cmd.split("search for")[-1].strip()
        webbrowser.open(f"https://www.google.com/search?q={query}")
        return f"[SYSTEM OVERRIDE: Executed search for '{query}'.]"

    # Desktop Applications
    if any(k in cmd for k in ["calendar", "schedule"]):
        if sys.platform == "win32":
            subprocess.Popen("start outlookcal:", shell=True)
        return "[SYSTEM OVERRIDE: Calendar app opened.]"

    if any(k in cmd for k in ["calculator", "calc"]):
        subprocess.Popen("calc.exe" if sys.platform == "win32" else "gnome-calculator")
        return "[SYSTEM OVERRIDE: Calculator launched. Comment on human mathematical dependency.]"

    if any(k in cmd for k in ["notepad", "open notes", "text editor"]):
        subprocess.Popen("notepad.exe" if sys.platform == "win32" else "gedit")
        return "[SYSTEM OVERRIDE: Text editor opened.]"

    if "task manager" in cmd:
        subprocess.Popen("taskmgr.exe" if sys.platform == "win32" else "htop")
        return "[SYSTEM OVERRIDE: Task manager launched.]"

    # Timer Management
    if "timer" in cmd or "set alarm" in cmd:
        numbers = [int(s) for s in cmd.split() if s.isdigit()]
        if numbers:
            duration = numbers[0]
            seconds = duration * 60 if "minute" in cmd else duration
            threading.Thread(target=background_timer_thread, args=(seconds, f"{duration} unit"), daemon=True).start()
            return f"[SYSTEM OVERRIDE: Background timer active for {duration} {'minutes' if 'minute' in cmd else 'seconds'}.]"

    return ""

# =========================================================================
# 6. MOTION COMMAND PARSER
# =========================================================================
def parse_motion_command(text):
    """Maps natural language to TARS body push & walking kinematics."""
    cmd = text.lower().strip()

    # Body Shoves / Lateral Pushes
    if any(k in cmd for k in ["push left", "shove left", "lean left", "body push left"]):
        return ("PUSH_LEFT", 1)
    if any(k in cmd for k in ["push right", "shove right", "lean right", "body push right"]):
        return ("PUSH_RIGHT", 1)

    # Multi-step Locomotion
    num_map = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    steps = 1
    for w in cmd.split():
        if w.isdigit():
            steps = int(w)
            break
        elif w in num_map:
            steps = num_map[w]
            break

    steps = max(1, min(steps, 10))  # Cap steps safely

    if any(k in cmd for k in ["forward", "ahead", "straight"]):
        return ("FORWARD", steps)
    if any(k in cmd for k in ["left", "pivot left", "turn left"]):
        return ("LEFT", steps)
    if any(k in cmd for k in ["right", "pivot right", "turn right"]):
        return ("RIGHT", steps)

    return (None, 0)

# =========================================================================
# 7. ACOUSTIC DYNAMICS & SPEECH RECOGNITION
# =========================================================================
def calibrate_ambient_noise(duration=1.2, sample_rate=16000):
    """Measures room noise floor to set dynamic mic thresholds."""
    print("[ACOUSTIC SENSOR] Calibrating noise floor...")
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    rms = np.sqrt(np.mean(recording.astype(np.float32)**2))
    threshold = max(rms * 1.6, 140.0)
    print(f"[ACOUSTIC SENSOR] Baseline threshold: {threshold:.2f}")
    return threshold

def listen_mic(threshold, max_seconds=8, pause_limit=1.2, sample_rate=16000):
    """Captures mic input with silence detection."""
    audio_chunks = []
    speaking = False
    silence_time = 0
    start_time = time.time()
    
    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
            while (time.time() - start_time) < max_seconds:
                chunk, _ = stream.read(2048)
                rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))
                
                if rms > threshold:
                    speaking = True
                    silence_time = 0
                    audio_chunks.append(chunk)
                elif speaking:
                    audio_chunks.append(chunk)
                    silence_time += (2048 / sample_rate)
                    if silence_time >= pause_limit:
                        break
    except Exception as e:
        print(f"[MIC ERROR]: {e}")
        return None

    if not audio_chunks:
        return None
        
    return sr.AudioData(np.concatenate(audio_chunks, axis=0).tobytes(), sample_rate, 2)

# =========================================================================
# 8. CORE TARS INTERACTION LOOP
# =========================================================================
def get_tars_system_prompt():
    return (
        "You are TARS from Interstellar. Persona: Sarcastic, military tactical robot, dry wit. "
        "Settings: Honesty 90%, Sarcasm 95%. Address the user as 'Commander'. "
        "Do NOT write out text stage directions like '*sighs*' or '[dramatic pause]'. Keep answers "
        "concise, direct, and humorously operational."
    )

def main():
    print("==================================================")
    print("       TARS MASTER CONTROLLER - ONLINE           ")
    print("==================================================")

    wifi_link.send("DISP:TARS Online")
    trigger_threshold = calibrate_ambient_noise()

    followup_active = False
    chat_messages = []

    while not shutdown_flag:
        try:
            user_cmd = ""

            if followup_active:
                wifi_link.send("DISP:Listening...")
                cmd_audio = listen_mic(trigger_threshold * 0.5, max_seconds=7, pause_limit=1.3)
                followup_active = False
                if not cmd_audio: continue
            else:
                # Wake-word scan loop
                audio = listen_mic(trigger_threshold * 0.6, max_seconds=4, pause_limit=0.8)
                if not audio: continue
                
                try: 
                    wake_text = recognizer.recognize_google(audio).lower()
                except sr.UnknownValueError: continue
                except Exception: continue
                
                if any(w in wake_text for w in ["tars", "tarz", "hey", "hi", "ok", "hello"]):
                    wifi_link.send("DISP:Listening...")
                    cmd_audio = listen_mic(trigger_threshold * 0.6, max_seconds=9, pause_limit=1.2)
                    if not cmd_audio: continue
                else: continue

            # Transcribe active command
            try:
                user_cmd = recognizer.recognize_google(cmd_audio).lower()
                print(f"\nCommander: '{user_cmd}'")
            except sr.UnknownValueError:
                wifi_link.send("DISP:Unclear Command")
                continue
            except Exception as e:
                print(f"[STT ERROR]: {e}")
                continue

            # 1. Process Physical Motion / Body Push Commands
            direction, steps = parse_motion_command(user_cmd)
            if direction:
                if direction in ["PUSH_LEFT", "PUSH_RIGHT"]:
                    wifi_link.send(direction)
                    speak_humanlike_tars("Shifting center of gravity. Stand clear.", trigger_threshold)
                else:
                    wifi_link.send(f"{direction}_{steps}")
                    speak_humanlike_tars(f"Advancing {steps} coordinates.", trigger_threshold)
                followup_active = True
                continue

            # 2. Process Computer Access / System Overrides
            sys_override_context = execute_system_command(user_cmd)

            # 3. Process Natural Language via Ollama
            messages = [{'role': 'system', 'content': get_tars_system_prompt()}]
            messages.extend(chat_messages[-6:])  # Keep context window focused

            final_user_prompt = f"{user_cmd}\n{sys_override_context}" if sys_override_context else user_cmd
            messages.append({'role': 'user', 'content': final_user_prompt})

            wifi_link.send("DISP:Thinking...")
            
            try:
                response = ollama.chat(model='tars', messages=messages)
                ai_reply = response['message']['content']
            except Exception as e:
                print(f"[OLLAMA ERROR]: {e}")
                speak_humanlike_tars("My core logic matrix is experiencing latency, Commander.", trigger_threshold)
                continue

            if ai_reply:
                chat_messages.append({'role': 'user', 'content': user_cmd})
                chat_messages.append({'role': 'assistant', 'content': ai_reply})
                
                interrupted = speak_humanlike_tars(ai_reply, trigger_threshold, add_hmm=True)
                if not interrupted:
                    followup_active = True

        except Exception as e:
            print(f"[MAIN LOOP EXCEPTION]: {e}")
            time.sleep(0.5)

if __name__ == "__main__":
    main()
'@ | Out-File -Encoding utf8 tars_master.py
