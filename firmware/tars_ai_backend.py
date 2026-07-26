Set-Content -Path "tars_master.py" -Encoding UTF8 -Value @'
import asyncio
import os
import re
import sys
import time
import json
import random
import socket
import signal
import sqlite3
import threading
import webbrowser
import urllib.parse
import psutil
import ollama
import pygame
import edge_tts
import numpy as np
import sounddevice as sd
import speech_recognition as sr

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

# =========================================================================
# 1. GLOBAL CONFIGURATION & OPTIMIZATIONS
# =========================================================================
ESP32_IP   = '192.168.1.126'
ESP32_PORT = 8888
OLLAMA_MODEL = 'llama3.2'  

AUDIO_DIR = "audio"
DATA_DIR = "memory"
MEMORY_FILE = os.path.join(DATA_DIR, "tars_core_memory.json")
DB_FILE = os.path.join(DATA_DIR, "tars_data.db")
CODE_OUTPUT_FILE = "tars_esp32_update.ino"

OLLAMA_OPTIONS = {
    "num_predict": 50,
    "num_ctx": 512,
    "temperature": 0.4
}

YES_SOUND_PATH = os.path.join(AUDIO_DIR, "yes.mp3")
INIT_SOUND_PATH = os.path.join(AUDIO_DIR, "init.mp3")
READY_SOUND_PATH = os.path.join(AUDIO_DIR, "ready.mp3")
ANYTHING_ELSE_SOUND_PATH = os.path.join(AUDIO_DIR, "anything_else.mp3")

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

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY, task TEXT, time_str TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS calendar (id INTEGER PRIMARY KEY, event TEXT, date_str TEXT)''')
conn.commit()

# =========================================================================
# 2. AUDIO ENGINE & PRE-GENERATED SOUNDS
# =========================================================================
async def generate_tars_speech(text, file_path="tars_reply.mp3"):
    tts = edge_tts.Communicate(text=text, voice="en-US-ChristopherNeural", pitch="-2Hz", rate="+0%")
    await tts.save(file_path)

def pre_generate_audio():
    print("[SYSTEM] Verifying core audio files...")
    if not os.path.exists(YES_SOUND_PATH): 
        asyncio.run(generate_tars_speech("Yes?", YES_SOUND_PATH))
    if not os.path.exists(INIT_SOUND_PATH): 
        asyncio.run(generate_tars_speech("TARS system initiated. Acoustic sensors active.", INIT_SOUND_PATH))
    if not os.path.exists(READY_SOUND_PATH): 
        asyncio.run(generate_tars_speech("Systems nominal. Standing by.", READY_SOUND_PATH))
    if not os.path.exists(ANYTHING_ELSE_SOUND_PATH):
        asyncio.run(generate_tars_speech("Anything else?", ANYTHING_ELSE_SOUND_PATH))

def play_audio_file(filepath):
    if not os.path.exists(filepath): return
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy(): pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
    except Exception: pass

# =========================================================================
# 3. MEMORY & HARDWARE LINKS
# =========================================================================
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r') as f: return json.load(f)
        except: return []
    return []

def save_memory(chat_history):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(chat_history[-4:], f, indent=4) 

class ESP32SocketLink:
    def __init__(self, ip, port):
        self.ip = ip; self.port = port; self.client = None; self.lock = threading.Lock()
        self.connect()
    def connect(self):
        with self.lock:
            try:
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.settimeout(2.0)
                self.client.connect((self.ip, self.port))
            except Exception:
                self.client = None
    def send(self, cmd):
        clean_cmd = cmd.replace('\r', '').replace('\n', '|') + "\r\n"
        with self.lock:
            if not self.client: return
            try: self.client.sendall(clean_cmd.encode('utf-8'))
            except: pass

wifi_link = ESP32SocketLink(ESP32_IP, ESP32_PORT)

# =========================================================================
# 4. LIVE INFORMATION RETRIEVAL & BROWSER COMMANDS
# =========================================================================
def fetch_live_info(query):
    print(f"[SEARCH] Fetching live info for: {query}")
    if not HAS_DDG:
        return "Search engine module not installed. Please run pip install duckduckgo-search."
    try:
        results = list(DDGS().text(query, max_results=2))
        if results:
            snippets = " ".join([r.get('body', '') for r in results])
            return snippets[:400]
    except Exception as e:
        print(f"[SEARCH ERROR]: {e}")
    return "Unable to retrieve live data."

def handle_quick_commands(cmd):
    c = cmd.lower().strip()

    if any(k in c for k in ["temperature", "temp", "weather", "forecast", "news", "who is", "what is", "how hot", "how cold"]):
        info = fetch_live_info(c)
        if info:
            prompt = f"User asked: '{c}'. Here is the web info: '{info}'. Answer the user directly and concisely in 1 or 2 sentences."
            try:
                res = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': prompt}], options=OLLAMA_OPTIONS)
                return True, res['message']['content']
            except Exception:
                return True, "Unable to query language model."

    if "whatsapp" in c:
        webbrowser.open("https://web.whatsapp.com")
        return True, "Opening WhatsApp Web."

    if "spotify" in c:
        match = re.search(r'(?:play|search)\s+(.*?)\s+(?:on|in)?\s*spotify', c)
        if match and match.group(1):
            q = match.group(1)
            webbrowser.open(f"https://open.spotify.com/search/{urllib.parse.quote(q)}")
            return True, f"Searching Spotify for {q}."
        webbrowser.open("https://open.spotify.com")
        return True, "Opening Spotify."

    if any(k in c for k in ["open chrome", "open youtube", "open browser", "open website"]):
        if "youtube" in c:
            webbrowser.open("https://www.youtube.com")
            return True, "Opening YouTube."
        webbrowser.open("https://www.google.com")
        return True, "Opening Web Browser."

    return False, ""

# =========================================================================
# 5. BARGE-IN MONITOR & AUDIO PLAYER
# =========================================================================
class AcousticBargeInMonitor:
    def __init__(self, threshold, sample_rate=16000):
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.stop_requested = threading.Event()
        self.interrupted = threading.Event()
        self.thread = None

    def start(self):
        self.stop_requested.clear()
        self.interrupted.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
                while not self.stop_requested.is_set():
                    chunk, _ = stream.read(2048)
                    rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))
                    if rms > (self.threshold * 2.2):
                        print("\n[SYSTEM] --> BARGE-IN DETECTED!")
                        self.interrupted.set()
                        break
        except Exception: pass

    def stop(self):
        self.stop_requested.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)

def sanitize_tars_text(text):
    clean = re.sub(r'\*.*?\*', '', text)        
    clean = re.sub(r'\[.*?\]', '', clean)       
    clean = re.sub(r'\(.*?\)', '', clean)       
    clean = re.sub(r'[#_~`]', '', clean)        
    return re.sub(r'\s+', ' ', clean).strip()

def speak_humanlike_tars(raw_text, monitor):
    clean_text = sanitize_tars_text(raw_text)
    if not clean_text: return False

    print(f"\nTARS: {clean_text}\n")
    wifi_link.send(f"DISP:{clean_text[:20]}")

    temp_file = f"tars_reply_{int(time.time())}.mp3"
    try:
        asyncio.run(generate_tars_speech(clean_text, temp_file))
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            if monitor.interrupted.is_set():
                pygame.mixer.music.stop()
                wifi_link.send("DISP:Interrupted")
                return True
            pygame.time.Clock().tick(30)
    except Exception: pass
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        time.sleep(0.05)
        if os.path.exists(temp_file):
            try: os.remove(temp_file)
            except: pass
            
    return monitor.interrupted.is_set()

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
# 6. SAFE MIC LISTENER
# =========================================================================
def calibrate_ambient_noise(duration=3.0, sample_rate=16000):
    play_audio_file(INIT_SOUND_PATH)
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    rms = np.sqrt(np.mean(recording.astype(np.float32)**2))
    threshold = max(rms * 1.8, 20.0) 
    print(f"[SYSTEM] Baseline RMS: {rms:.2f} | Wake Threshold: {threshold:.2f}")
    play_audio_file(READY_SOUND_PATH)
    return threshold

def listen_mic_safe(threshold, max_seconds=7, pause_limit=1.2, sample_rate=16000):
    audio_chunks, speaking, silence_time = [], False, 0
    start_time = time.time()
    time.sleep(0.1)
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
                    if silence_time >= pause_limit: break
    except Exception as e:
        print(f"[MIC WARNING]: Audio stream timeout: {e}")
        return None
        
    if not audio_chunks: return None
    return sr.AudioData(np.concatenate(audio_chunks, axis=0).tobytes(), sample_rate, 2)

# =========================================================================
# 7. MAIN LOGIC
# =========================================================================
def main():
    print("==================================================")
    print("       TARS MASTER CONTROLLER - v7.0 ONLINE       ")
    print("==================================================")

    pre_generate_audio()
    wifi_link.send("DISP:Booting...")
    trigger_threshold = calibrate_ambient_noise()
    chat_messages = load_memory()
    followup_active = False

    wake_keywords = [
        "tars", "tarz", "theatres", "tar", "hey", "hi", "ok", "hello", "wake up", 
        "haters", "tarus", "8 hours", "cars", "guitar", "hitarch", "stars", "bars"
    ]

    while not shutdown_flag:
        try:
            if followup_active:
                print("\n[SYSTEM] TARS listening for 5 seconds...")
                wifi_link.send("DISP:Listening...")
                # EXACT 5-SECOND TIMEOUT FOR FOLLOW-UPS
                cmd_audio = listen_mic_safe(trigger_threshold * 0.5, max_seconds=5, pause_limit=1.2)
                if not cmd_audio: 
                    print("[SYSTEM] 5-second silence. Closing mic and returning to standby.")
                    followup_active = False
                    continue
            else:
                audio = listen_mic_safe(trigger_threshold * 0.6, max_seconds=4, pause_limit=0.8)
                if not audio: continue
                try: wake_text = recognizer.recognize_google(audio).lower()
                except: continue
                
                if any(w in wake_text for w in wake_keywords):
                    print("\n[AWAKENING] Tactical wake phrase detected.")
                    monitor = AcousticBargeInMonitor(trigger_threshold)
                    monitor.start()
                    speak_humanlike_tars("State your orders.", monitor)
                    monitor.stop()
                    
                    print("\n[SYSTEM] TARS listening for command...")
                    wifi_link.send("DISP:Listening...")
                    cmd_audio = listen_mic_safe(trigger_threshold * 0.6, max_seconds=8, pause_limit=1.2)
                    if not cmd_audio: continue
                else: continue

            # Recognize user input
            try:
                user_cmd = recognizer.recognize_google(cmd_audio).lower()
                print(f"\nCommander: '{user_cmd}'")
            except: 
                followup_active = True 
                continue

            # --- 1. LOCAL ESP32 CODE EDITOR ---
            if any(k in user_cmd for k in ["edit esp", "write code", "code for esp", "code for esp32", "program the esp"]):
                wifi_link.send("DISP:Coding...")
                print("[SYSTEM] Generating local ESP32 code file...")
                prompt = f"Write complete C++ Arduino code for ESP32 based on this request: '{user_cmd}'. Output ONLY the raw C++ code inside ```cpp ... ``` blocks."
                
                try:
                    res = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': prompt}])
                    code_reply = res['message']['content']
                    
                    match = re.search(r'```(?:cpp|c|arduino)?(.*?)```', code_reply, re.DOTALL)
                    code_content = match.group(1).strip() if match else code_reply.strip()
                    
                    with open(CODE_OUTPUT_FILE, "w", encoding="utf-8") as f:
                        f.write(code_content)
                    
                    reply_text = f"Code generated and saved locally to {CODE_OUTPUT_FILE}."
                except Exception as e:
                    print(f"[CODE GEN ERROR]: {e}")
                    reply_text = "I encountered an error while writing the code."

                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                was_interrupted = speak_humanlike_tars(reply_text, monitor)
                monitor.stop()
                
                if was_interrupted: play_audio_file(YES_SOUND_PATH)
                else: play_audio_file(ANYTHING_ELSE_SOUND_PATH)
                
                followup_active = True
                continue


            # --- 2. MOTION COMMANDS ---
            direction, steps = parse_motion_command(user_cmd)
            if direction:
                wifi_link.send(direction if "PUSH" in direction else f"{direction}_{steps}")
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                was_interrupted = speak_humanlike_tars(f"Executing {direction}.", monitor)
                monitor.stop()
                
                if was_interrupted: play_audio_file(YES_SOUND_PATH)
                else: play_audio_file(ANYTHING_ELSE_SOUND_PATH)
                followup_active = True
                continue


            # --- 3. DIRECT INFORMATION & QUICK BROWSER ACTIONS ---
            executed, reply_text = handle_quick_commands(user_cmd)
            if executed:
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                was_interrupted = speak_humanlike_tars(reply_text, monitor)
                monitor.stop()
                
                if was_interrupted: play_audio_file(YES_SOUND_PATH)
                else: play_audio_file(ANYTHING_ELSE_SOUND_PATH)
                followup_active = True 
                continue


            # --- 4. GENERAL LLM CONVERSATION ---
            wifi_link.send("DISP:Thinking...")
            print(f"[OLLAMA] Processing request...")

            system_prompt = (
                "You are TARS from Interstellar. Sarcastic, military tactical robot. "
                "CRITICAL: Do NOT write stage directions or asterisks. Be extremely brief (max 2 sentences)."
            )
            
            messages = [{'role': 'system', 'content': system_prompt}]
            messages.extend(chat_messages[-4:])
            messages.append({'role': 'user', 'content': user_cmd})

            try:
                response = ollama.chat(model=OLLAMA_MODEL, messages=messages, options=OLLAMA_OPTIONS)
                ai_reply = response['message']['content']
            except Exception as e:
                print(f"[OLLAMA ERROR]: {e}")
                ai_reply = "Cognitive error."

            if ai_reply:
                chat_messages.append({'role': 'user', 'content': user_cmd})
                chat_messages.append({'role': 'assistant', 'content': ai_reply})
                save_memory(chat_messages)

                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                was_interrupted = speak_humanlike_tars(ai_reply, monitor)
                monitor.stop()

                if was_interrupted: 
                    print("[TARS] Yes?")
                    play_audio_file(YES_SOUND_PATH)
                else:
                    play_audio_file(ANYTHING_ELSE_SOUND_PATH)

                followup_active = True

        except Exception as e:
            time.sleep(0.5)

if __name__ == "__main__":
    main()
'@
