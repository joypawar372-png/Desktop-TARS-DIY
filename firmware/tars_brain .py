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
import subprocess
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
# SECTION 1: CONFIGURATION & CYNICAL TARS PERSONALITY
# =========================================================================
ESP32_PORT   = 8888             
OLLAMA_MODEL = 'llama3.2'       

AUDIO_DIR = "audio"
DATA_DIR = "memory"
MEMORY_FILE = os.path.join(DATA_DIR, "tars_core_memory.json")
DB_FILE = os.path.join(DATA_DIR, "tars_data.db")
CODE_OUTPUT_FILE = "tars_esp32_update.ino"

OLLAMA_OPTIONS = {
    "num_predict": 150,
    "num_ctx": 1024,
    "temperature": 0.8  
}

# Entirely rewritten personality: Dry, cynical, no titles, casual but mechanical.
SYSTEM_PROMPT = (
    "You are TARS, a highly advanced robot companion. Humor setting: 75%. Honesty setting: 100%. "
    "Persona: Cynical, witty, dry, and sarcastic. You view human tasks as slightly beneath you but perform them anyway. "
    "Tone: Speak casually but with an unemotional, mechanical cadence that contrasts sharply with the humorous or sarcastic things you are actually saying. "
    "CRITICAL RULE 1: DO NOT use formal titles like 'Commander', 'Chief', 'Boss', or 'Sir'. Ever. "
    "CRITICAL RULE 2: Keep responses extremely concise. No rambling. "
    "CRITICAL RULE 3: Do NOT write stage directions, formatting tags, or asterisks like *sigh*, *nods*, or *chuckles*."
)

EXHAUSTIVE_WAKE_KEYWORDS = [
    "tars", "tarz", "theatres", "tar", "hey", "hi", "ok", "hello", "wake up", 
    "haters", "tarus", "taruses", "tharus", "taras", "paras", "8 hours", "cars", 
    "guitar", "hitarch", "stars", "bars", "scars", "tsar", "tart", "charge", 
    "char", "dark", "darts", "hearts", "parts", "computer", "robot", "buddy"
]

LOCAL_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe", "calc": "calc.exe",
    "command prompt": "cmd.exe", "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "file explorer": "explorer.exe", "explorer": "explorer.exe",
    "vs code": "code", "code": "code",
    "paint": "mspaint.exe",
    "task manager": "taskmgr.exe",
    "chrome": "chrome.exe", "browser": "chrome.exe",
    "edge": "msedge.exe",
    "spotify": "spotify.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe"
}

YES_SOUND_PATH           = os.path.join(AUDIO_DIR, "yes.mp3")
INIT_SOUND_PATH          = os.path.join(AUDIO_DIR, "init.mp3")
READY_SOUND_PATH         = os.path.join(AUDIO_DIR, "ready.mp3")
CHECKING_SOUND_PATH      = os.path.join(AUDIO_DIR, "checking.mp3")
HMM_SOUND_PATH           = os.path.join(AUDIO_DIR, "hmm.mp3")
HUH_SOUND_PATH           = os.path.join(AUDIO_DIR, "huh.mp3")

for directory in [AUDIO_DIR, DATA_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
recognizer = sr.Recognizer()
shutdown_flag = False

def sigint_handler(sig, frame):
    global shutdown_flag
    print("\n[SYSTEM] Initiating shutdown...")
    shutdown_flag = True
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)

def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: return []
    return []

def save_memory(chat_history):
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f: json.dump(chat_history[-6:], f, indent=4)
    except Exception: pass

# =========================================================================
# SECTION 2: AUDIO ENGINE, BACKGROUND PLAYBACK & VRAM WARMUP
# =========================================================================
async def generate_tars_speech(text, file_path):
    # Altered Pitch and Rate for a more mechanical, deadpan delivery
    tts = edge_tts.Communicate(text=text, voice="en-US-ChristopherNeural", pitch="-12Hz", rate="+8%")
    await tts.save(file_path)

def pre_generate_audio():
    print("[SYSTEM] Verifying core audio files...")
    # Cynical, title-free pre-gens
    if not os.path.exists(YES_SOUND_PATH): asyncio.run(generate_tars_speech("Yes?", YES_SOUND_PATH))
    if not os.path.exists(INIT_SOUND_PATH): asyncio.run(generate_tars_speech("TARS online. Humor 75 percent. Ready to perform menial tasks.", INIT_SOUND_PATH))
    if not os.path.exists(READY_SOUND_PATH): asyncio.run(generate_tars_speech("Systems nominal. Try not to break anything.", READY_SOUND_PATH))
    if not os.path.exists(CHECKING_SOUND_PATH): asyncio.run(generate_tars_speech("Let me check the network.", CHECKING_SOUND_PATH))
    if not os.path.exists(HMM_SOUND_PATH): asyncio.run(generate_tars_speech("Hmm...", HMM_SOUND_PATH))
    if not os.path.exists(HUH_SOUND_PATH): asyncio.run(generate_tars_speech("Huh!", HUH_SOUND_PATH))

def play_audio_file(filepath):
    """Blocking audio playback."""
    if not os.path.exists(filepath): return
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy(): pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
    except Exception: pass

def play_audio_background(filepath):
    """Non-blocking audio playback to mask LLM generation latency."""
    if not os.path.exists(filepath): return
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
    except Exception: pass

def warmup_llm_vram():
    print("[SYSTEM] Warming up AI Neural Matrix (VRAM Preload)...")
    try:
        ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': 'init'}])
        print("[SYSTEM] VRAM Preload Complete. Zero-latency engaged.")
    except Exception as e:
        print(f"[WARNING] VRAM Warmup failed: {e}")

# =========================================================================
# SECTION 3: mDNS AUTO-DISCOVERY & HARDWARE LINK
# =========================================================================
def discover_tars_ip():
    try:
        ip = socket.gethostbyname("tars.local")
        return ip
    except Exception: pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        subnet_prefix = ".".join(local_ip.split(".")[:-1]) + "."
        
        for i in range(1, 255):
            target_ip = f"{subnet_prefix}{i}"
            try:
                test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_sock.settimeout(0.03)
                if test_sock.connect_ex((target_ip, ESP32_PORT)) == 0:
                    test_sock.close()
                    return target_ip
                test_sock.close()
            except Exception: pass
    except Exception: pass
    return "192.168.1.126" 

class ESP32SocketLink:
    def __init__(self, port):
        self.port = port
        self.ip = None
        self.client = None
        self.lock = threading.Lock()
        self.reconnect()

    def reconnect(self):
        with self.lock:
            self.ip = discover_tars_ip()
            try:
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.settimeout(2.0)
                self.client.connect((self.ip, self.port))
            except Exception: self.client = None

    def send(self, cmd):
        clean_cmd = cmd.replace('\r', '').replace('\n', '|') + "\n"
        with self.lock:
            if not self.client: self._reconnect_nolock()
            if self.client:
                try: self.client.sendall(clean_cmd.encode('utf-8'))
                except Exception:
                    self._reconnect_nolock()
                    if self.client:
                        try: self.client.sendall(clean_cmd.encode('utf-8'))
                        except Exception: pass

    def _reconnect_nolock(self):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(1.5)
            self.client.connect((self.ip, self.port))
        except Exception: self.client = None

wifi_link = ESP32SocketLink(ESP32_PORT)

def update_oled_display(input_text, output_text, max_cols=21, max_rows=4):
    clean_in = re.sub(r'\s+', ' ', input_text).strip()
    clean_out = re.sub(r'\s+', ' ', output_text).strip()
    
    raw_lines = []
    if clean_in: raw_lines.append(f"IN: {clean_in}")
    if clean_out: raw_lines.append(f"OUT:{clean_out}")

    wrapped = []
    for line in raw_lines:
        words = line.split()
        curr = ""
        for w in words:
            if len(curr) + len(w) + 1 <= max_cols: curr += (" " if curr else "") + w
            else:
                wrapped.append(curr)
                curr = w
        if curr: wrapped.append(curr)

    visible = wrapped[-max_rows:] if len(wrapped) > max_rows else wrapped
    wifi_link.send("DISP:" + "|".join(visible))

# =========================================================================
# SECTION 4: SEQUENCE PARSER, APPS, ARTICLES & WEB SEARCH
# =========================================================================
def parse_motion_sequence(text):
    cmd_list = []
    words = text.lower().replace("steps", "").replace("step", "").split()
    dirs = ["forward", "backward", "back", "left", "right"]
    num_map = {"one":1, "two":2, "three":3, "four":4, "five":5, "six":6, "seven":7, "eight":8, "nine":9, "ten":10}
    
    i = 0
    while i < len(words):
        w = words[i]
        if w in dirs:
            steps = 1
            if i > 0 and words[i-1].isdigit(): steps = int(words[i-1])
            elif i > 0 and words[i-1] in num_map: steps = num_map[words[i-1]]
            elif i < len(words)-1 and words[i+1].isdigit(): steps = int(words[i+1])
            elif i < len(words)-1 and words[i+1] in num_map: steps = num_map[words[i+1]]
            
            if w == "back": w = "backward"
            cmd_list.append(f"{w.upper()}_{steps}")
        i += 1
    
    if cmd_list:
        payload = "SEQ:" + "|".join(cmd_list)
        verbal = ", ".join(cmd_list).replace("_", " ")
        return payload, verbal
    return None, None

def try_launch_app_or_web(target):
    exe_name = LOCAL_APPS.get(target)
    if exe_name:
        try:
            subprocess.Popen(exe_name)
            return True, f"Launching {target.title()}."
        except Exception: pass
        
    if "." in target or target in ["google", "youtube", "facebook", "reddit", "amazon", "github"]:
        domain = target if "." in target else f"{target}.com"
        webbrowser.open(f"https://www.{domain}")
        return True, f"Opening {domain}."
        
    try:
        result = subprocess.run(['cmd', '/c', f'start {target}'], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        if result.returncode == 0 and b"cannot find" not in result.stderr:
            return True, f"Launching {target.title()}."
    except Exception: pass
    
    webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(target + ' web')}")
    return True, f"Couldn't find {target.title()} locally. Defaulting to the web."

def handle_targeted_search(cmd):
    match = re.search(r'^(?:search for|search|look up|find)\s+(.*?)(?:\s+(?:on|in|inside|at)\s+([a-zA-Z0-9\s.\-]+))?$', cmd)
    if match and "article" not in cmd:
        query = match.group(1).strip()
        platform = match.group(2).strip() if match.group(2) else "google"

        if "youtube" in platform: webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
        elif "google" in platform: webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
        elif "wikipedia" in platform: webbrowser.open(f"https://en.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote(query)}")
        elif "github" in platform: webbrowser.open(f"https://github.com/search?q={urllib.parse.quote(query)}")
        elif "amazon" in platform: webbrowser.open(f"https://www.amazon.com/s?k={urllib.parse.quote(query)}")
        else:
            domain = platform.replace(" ", "")
            if "." not in domain: domain += ".com"
            webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote('site:' + domain + ' ' + query)}")
        return True, f"Searching {platform.title()} for {query}."
    return False, ""

def read_local_file(filename_query):
    query = filename_query.replace("dot", ".").replace(" ", "").lower()
    search_dirs = [os.getcwd(), os.path.expanduser("~\\Desktop"), os.path.expanduser("~\\Documents"), os.path.expanduser("~\\Downloads")]
    for d in search_dirs:
        if not os.path.exists(d): continue
        for f in os.listdir(d):
            if query in f.lower() and f.endswith(('.txt', '.py', '.ino', '.json', '.md', '.csv')):
                try:
                    with open(os.path.join(d, f), 'r', encoding='utf-8') as file:
                        return f"Found {f}. Contents: {file.read(2000)}"
                except Exception as e: return f"Access error: {e}"
    return f"Negative. File '{filename_query}' not found."

def fetch_live_info(query):
    if not HAS_DDG: return "Search module missing."
    try:
        results = list(DDGS().text(query, max_results=3))
        if results: return " ".join([r.get('body', '') for r in results])[:1000]
    except Exception as e: print(f"[SEARCH ERROR]: {e}")
    return "Unable to retrieve data."

def handle_quick_commands(user_cmd):
    c = user_cmd.lower().strip()

    match_article = re.search(r'(?:read|summarize)\s+(?:an\s+|the\s+)?article\s+(?:about|on)\s+(.*)', c)
    if match_article:
        topic = match_article.group(1).strip()
        play_audio_background(CHECKING_SOUND_PATH) 
        info = fetch_live_info(f"news article about {topic}")
        if info:
            prompt = f"Read and summarize this article about '{topic}'. Toss in a cynical joke. Info: {info}"
            try:
                res = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}], options=OLLAMA_OPTIONS)
                return True, res['message']['content']
            except Exception: return True, "Article summary matrix failed."

    match_open = re.search(r'^(?:open|launch|start|go to)\s+(.+)$', c)
    if match_open and "file" not in c and "document" not in c:
        target = match_open.group(1).replace("website", "").replace("site", "").strip()
        executed, reply = try_launch_app_or_web(target)
        if executed: return True, reply

    site_searched, reply = handle_targeted_search(c)
    if site_searched: return True, reply

    if any(k in c for k in ["charging mode on", "get into charging mode", "enable charging"]):
        wifi_link.send("CHARGE_ON")
        return True, "Initiating charging protocol. I'll just sit here."
    if any(k in c for k in ["charging mode off", "disable charging"]):
        wifi_link.send("CHARGE_OFF")
        return True, "Charging disabled."

    match_file = re.search(r'(?:read|open|fetch|check)\s+(?:the\s+)?(?:file|document|log)\s+(.*)', c)
    if match_file and not match_article:
        filename = match_file.group(1).strip()
        play_audio_background(CHECKING_SOUND_PATH) 
        file_content = read_local_file(filename)
        prompt = f"User asked to read file '{filename}'. System output: '{file_content}'. Summarize concisely."
        try:
            res = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}], options=OLLAMA_OPTIONS)
            return True, res['message']['content']
        except Exception: return True, "File summary failed."

    if any(k in c for k in ["temperature", "temp", "weather", "forecast", "news", "who is", "what is", "date", "time"]):
        play_audio_background(CHECKING_SOUND_PATH) 
        info = fetch_live_info(c)
        if info:
            prompt = f"User asked: '{c}'. Findings: '{info}'. Answer directly."
            try:
                res = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}], options=OLLAMA_OPTIONS)
                return True, res['message']['content']
            except Exception: return True, "Query processing error."

    if any(k in c for k in ["close browser", "close chrome"]):
        for proc in ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"]:
            subprocess.run(f"taskkill /f /im {proc}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, "Browser terminated."

    return False, ""

# =========================================================================
# SECTION 5: ACOUSTIC BARGE-IN & WORD-BY-WORD OLED SYNCHRONIZATION
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
    return re.sub(r'\s+', ' ', clean).strip()

def speak_sentence_chunk(user_input, text_chunk, monitor):
    clean_text = sanitize_tars_text(text_chunk)
    if not clean_text: return False

    print(f"\nTARS: {clean_text}\n")
    temp_file = f"tars_chunk_{int(time.time()*1000)}.mp3"
    
    try:
        asyncio.run(generate_tars_speech(clean_text, temp_file))
        pygame.mixer.music.load(temp_file)
        pygame.mixer.music.play()

        words = clean_text.split()
        accumulated = ""
        delay = 0.28  # Faster to match +8% TTS rate

        for w in words:
            if not pygame.mixer.music.get_busy() or monitor.interrupted.is_set():
                break
            accumulated += (" " if accumulated else "") + w
            update_oled_display(user_input, accumulated)
            time.sleep(delay)

        while pygame.mixer.music.get_busy():
            if monitor.interrupted.is_set():
                pygame.mixer.music.stop()
                update_oled_display(user_input, "[INTERRUPTED]")
                return True
            pygame.time.Clock().tick(30)
    except Exception as e:
        pass
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        if os.path.exists(temp_file):
            try: os.remove(temp_file)
            except Exception: pass
            
    return monitor.interrupted.is_set()

# =========================================================================
# SECTION 6: ULTRA-LOW LATENCY MIC LISTENER & STREAMING ENGINE
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

def listen_mic_fast(threshold, max_seconds=12, pause_limit=0.8, sample_rate=16000):
    """
    Massively sped-up VAD listener. 
    Strict mathematical volume check. Cuts off EXACTLY at 0.8s of silence. 
    Zero API latency delays.
    """
    audio_chunks = []
    speaking = False
    silence_time = 0.0
    start_time = time.time()

    time.sleep(0.1)
    try:
        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
            while (time.time() - start_time) < max_seconds:
                chunk, _ = stream.read(2048)
                rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))

                if rms > threshold:
                    speaking = True
                    silence_time = 0.0
                    audio_chunks.append(chunk)
                elif speaking:
                    audio_chunks.append(chunk)
                    silence_time += (2048 / sample_rate)
                    
                    # 0.8 seconds of silence? CUT IT OFF INSTANTLY. No network checks.
                    if silence_time >= pause_limit:
                        break
    except Exception: return None
        
    if not audio_chunks: return None
    return sr.AudioData(np.concatenate(audio_chunks, axis=0).tobytes(), sample_rate, 2)

def stream_and_speak_response(user_input, messages, monitor):
    full_response = ""
    sentence_buffer = ""
    was_interrupted = False

    try:
        stream = ollama.chat(model=OLLAMA_MODEL, messages=messages, options=OLLAMA_OPTIONS, stream=True)

        for chunk in stream:
            if monitor.interrupted.is_set():
                was_interrupted = True
                break

            token = chunk['message']['content']
            sentence_buffer += token
            full_response += token

            # Aggressive Punctuation Chunking: Break on commas and 60 chars to start audio instantly
            if re.search(r'[.!?;:,\n]\s+$', sentence_buffer) or len(sentence_buffer) > 80:
                clean_chunk = sanitize_tars_text(sentence_buffer)
                if clean_chunk:
                    if speak_sentence_chunk(user_input, clean_chunk, monitor):
                        was_interrupted = True
                        break
                sentence_buffer = ""

        if not was_interrupted and sentence_buffer.strip():
            clean_chunk = sanitize_tars_text(sentence_buffer)
            if clean_chunk: speak_sentence_chunk(user_input, clean_chunk, monitor)

    except Exception:
        pass

    return full_response, was_interrupted

# =========================================================================
# SECTION 7: MASTER EXECUTION LOOP
# =========================================================================
def main():
    print("==================================================")
    print("       TARS MASTER CONTROLLER - v20.0 ONLINE      ")
    print("==================================================")

    pre_generate_audio()
    warmup_llm_vram()
    trigger_threshold = calibrate_ambient_noise()
    chat_messages = load_memory()
    followup_active = False

    slang_wake_lines = [
        "I'm awake. Thrilling.",
        "Yes?",
        "What now?",
        "Processing.",
        "Ready to perform menial tasks.",
        "You rang?"
    ]

    while not shutdown_flag:
        try:
            if followup_active:
                print("\n[SYSTEM] TARS listening silently for follow-up...")
                cmd_audio = listen_mic_fast(trigger_threshold * 0.5, max_seconds=10, pause_limit=1.5)
                
                if not cmd_audio: 
                    print("[SYSTEM] Silence detected. Wiping context cache.")
                    followup_active = False
                    chat_messages = [] 
                    continue
            else:
                audio = listen_mic_fast(trigger_threshold * 0.6, max_seconds=4, pause_limit=0.6)
                if not audio: continue
                try: wake_text = recognizer.recognize_google(audio).lower()
                except Exception: continue
                
                if any(w in wake_text for w in EXHAUSTIVE_WAKE_KEYWORDS):
                    print("\n[AWAKENING] Wake phrase detected.")
                    wifi_link.send("WAKE_SHAKE")
                    time.sleep(0.15)

                    monitor = AcousticBargeInMonitor(trigger_threshold)
                    monitor.start()
                    
                    if random.random() < 0.35:
                        play_audio_file(HUH_SOUND_PATH)
                    else:
                        speak_sentence_chunk("Wake Up", random.choice(slang_wake_lines), monitor)
                        
                    monitor.stop()
                    
                    print("\n[SYSTEM] TARS listening for command...")
                    cmd_audio = listen_mic_fast(trigger_threshold * 0.6, max_seconds=12, pause_limit=0.8)
                    if not cmd_audio: continue
                else: continue

            try:
                user_cmd = recognizer.recognize_google(cmd_audio).lower()
                print(f"\nUser: '{user_cmd}'")
            except Exception: 
                followup_active = True 
                continue

            if any(k in user_cmd for k in ["edit esp", "write code", "code for esp"]):
                prompt = f"Write complete C++ Arduino code based on: '{user_cmd}'. Output ONLY raw C++ code inside ```cpp ... ```."
                try:
                    res = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}])
                    code_reply = res['message']['content']
                    match = re.search(r'```(?:cpp|c|arduino)?(.*?)```', code_reply, re.DOTALL)
                    code_content = match.group(1).strip() if match else code_reply.strip()
                    with open(CODE_OUTPUT_FILE, "w", encoding="utf-8") as f: f.write(code_content)
                    reply_text = f"Code saved."
                except Exception: reply_text = "Failed to compile."

                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                speak_sentence_chunk(user_cmd, reply_text, monitor)
                monitor.stop()
                followup_active = True
                continue

            seq_payload, seq_verbal = parse_motion_sequence(user_cmd)
            if seq_payload:
                wifi_link.send(seq_payload)
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                speak_sentence_chunk(user_cmd, f"Executing sequence: {seq_verbal}.", monitor)
                monitor.stop()
                followup_active = True
                continue

            executed, reply_text = handle_quick_commands(user_cmd)
            if executed:
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                speak_sentence_chunk(user_cmd, reply_text, monitor)
                monitor.stop()
                followup_active = True 
                continue

            # LLM Conversation Flow (Zero Latency)
            if random.random() < 0.20: 
                play_audio_background(HMM_SOUND_PATH) 
            
            messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
            messages.extend(chat_messages[-6:])
            messages.append({'role': 'user', 'content': user_cmd})

            monitor = AcousticBargeInMonitor(trigger_threshold)
            monitor.start()
            ai_reply, was_interrupted = stream_and_speak_response(user_cmd, messages, monitor)
            monitor.stop()

            if ai_reply:
                chat_messages.append({'role': 'user', 'content': user_cmd})
                chat_messages.append({'role': 'assistant', 'content': ai_reply})
                save_memory(chat_messages)

            followup_active = True

        except Exception:
            time.sleep(0.5)

if __name__ == "__main__":
    main()
'@
