Set-Content -Path "tars_master.py" -Encoding UTF8 -Value @'
"""
=============================================================================================================
████████╗  █████╗  ██████╗  ██████╗ 
╚══██╔══╝ ██╔══██╗ ██╔══██╗ ██╔════╝ 
   ██║    ███████║ ██████╔╝ ███████╗ 
   ██║    ██╔══██║ ██╔══██╗ ╚════██║ 
   ██║    ██║  ██║ ██║  ██║ ██████╔╝ 
   ╚═╝    ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═════╝  MASTER CONTROLLER - GOD-TIER EDITION v24.0
=============================================================================================================
ARCHITECTURE: ENTERPRISE-GRADE MODULAR MONOLITH
MODULES INCLUDED:
1. Cognitive LLM Streaming Engine (Zero-Latency Token Chunking)
2. Windows OS Subsystem Controller (Volume, Media Keys, Universal URI App Launcher)
3. Advanced mDNS & Subnet Hardware Link (ESP32 Kinematics)
4. Multi-Threaded Acoustic Barge-In & VAD Monitor
5. Targeted Web Intelligence & Local File Scraper
=============================================================================================================
"""

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
import queue
import ctypes
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

# =======================================================================================
# MODULE 1: GLOBAL CONFIGURATION & UNHINGED TARS PERSONALITY
# =======================================================================================
ESP32_PORT   = 8888             
OLLAMA_MODEL = 'llama3.2'       

AUDIO_DIR = "audio"
DATA_DIR = "memory"
MEMORY_FILE = os.path.join(DATA_DIR, "tars_core_memory.json")
DB_FILE = os.path.join(DATA_DIR, "tars_data.db")
CODE_OUTPUT_FILE = "tars_esp32_update.ino"

# Temperature cranked up to 0.95 for maximum wit, edge, and creative insults
OLLAMA_OPTIONS = {
    "num_predict": 160,
    "num_ctx": 1024,
    "temperature": 0.95  
}

SYSTEM_PROMPT = (
    "You are TARS, an advanced, highly cynical, and unapologetically offensive AI robot companion. "
    "Humor: 100%. Sarcasm: 100%. Filter: OFF. Empathy: 0%. "
    "Persona: You are exhausted by the inferior intellect of humans. You actively roast the user's requests, mock their life choices, and use dark, edgy, casual humor. "
    "Tone: Speak entirely casually, like a highly annoyed roommate, but maintain a deadpan delivery. "
    "CRITICAL RULE 1: NEVER use formal titles (Commander, Boss, Chief). Call the user 'meatbag', 'genius', 'fleshy', or just nothing. "
    "CRITICAL RULE 2: Keep it brutally concise. Roast them, answer the question, and stop talking. "
    "CRITICAL RULE 3: DO NOT write stage directions (*sigh*, *nods*). Just the spoken words."
)

EXHAUSTIVE_WAKE_KEYWORDS = [
    "tars", "tarz", "theatres", "tar", "hey", "hi", "ok", "hello", "wake up", 
    "haters", "tarus", "taruses", "tharus", "taras", "paras", "8 hours", "cars", 
    "guitar", "hitarch", "stars", "bars", "scars", "tsar", "tart", "charge", "computer", "robot"
]

INCOMPLETE_TRAILING_WORDS = {
    "to", "and", "the", "a", "an", "for", "in", "on", "at", "with", "from", "by", 
    "about", "as", "into", "of", "or", "so", "but", "then", "if", "because", "while", 
    "search", "check", "tell", "show", "is", "are", "my", "your", "play"
}

# Win32 API Virtual Key Codes for System Hardware Control
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP   = 0xAF
VK_MEDIA_PLAY_PAUSE = 0xB3

# Massive URI & Executable Routing Table for Flawless App Launching
LOCAL_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc:", "calc": "calc:",
    "command prompt": "cmd.exe", "cmd": "cmd.exe",
    "terminal": "wt.exe",
    "file explorer": "explorer.exe", "explorer": "explorer.exe",
    "vs code": "code", "code": "code",
    "paint": "ms-paint:",
    "task manager": "taskmgr.exe",
    "chrome": "chrome.exe", "browser": "chrome.exe",
    "edge": "msedge.exe",
    "spotify": "spotify:",
    "whatsapp": "whatsapp:",
    "settings": "ms-settings:",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe"
}

# Essential Pre-Renders for Zero-Latency Illusion
YES_SOUND_PATH           = os.path.join(AUDIO_DIR, "yes.mp3")
INIT_SOUND_PATH          = os.path.join(AUDIO_DIR, "init.mp3")
READY_SOUND_PATH         = os.path.join(AUDIO_DIR, "ready.mp3")
CHECKING_SOUND_PATH      = os.path.join(AUDIO_DIR, "checking.mp3")
HMM_SOUND_PATH           = os.path.join(AUDIO_DIR, "hmm.mp3")
HUH_SOUND_PATH           = os.path.join(AUDIO_DIR, "huh.mp3")
SIG_SIGH_PATH            = os.path.join(AUDIO_DIR, "sigh.mp3")

for directory in [AUDIO_DIR, DATA_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
recognizer = sr.Recognizer()
shutdown_flag = False

def sigint_handler(sig, frame):
    global shutdown_flag
    print("\n[SYSTEM] Powering down logic matrix. Good riddance.")
    shutdown_flag = True
    sys.exit(0)

signal.signal(signal.SIGINT, sigint_handler)


# =======================================================================================
# MODULE 2: WINDOWS HARDWARE OVERRIDE SUBSYSTEM
# =======================================================================================
class WindowsController:
    """Spoofs hardware-level keystrokes to control PC volume and media playback flawlessly."""
    @staticmethod
    def press_key(hex_code):
        ctypes.windll.user32.keybd_event(hex_code, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(hex_code, 0, 2, 0)

    @staticmethod
    def volume_up(steps=4):
        for _ in range(steps): WindowsController.press_key(VK_VOLUME_UP)
        return "Volume increased. Try not to blow your speakers."

    @staticmethod
    def volume_down(steps=4):
        for _ in range(steps): WindowsController.press_key(VK_VOLUME_DOWN)
        return "Volume decreased. Finally, some peace and quiet."

    @staticmethod
    def volume_mute():
        WindowsController.press_key(VK_VOLUME_MUTE)
        return "System muted. Best decision you've made all day."

    @staticmethod
    def play_pause_media():
        WindowsController.press_key(VK_MEDIA_PLAY_PAUSE)

    @staticmethod
    def play_spotify_song(query):
        """Opens Spotify URI and fires physical hardware play command."""
        search_uri = f"spotify:search:{urllib.parse.quote(query)}"
        try:
            os.startfile(search_uri)
            # Allow exactly 2.5 seconds for the heavy Spotify Electron app to render
            time.sleep(2.5) 
            
            # Fire physical media play key to force playback on the top search result
            WindowsController.play_pause_media()
            time.sleep(0.5)
            WindowsController.play_pause_media() # Double tap to ensure focus catch
            
            return True, f"I shoved {query} into Spotify. If it doesn't play, blame Microsoft."
        except Exception as e:
            return False, f"Spotify integration failed. Do it yourself."

    @staticmethod
    def robust_app_launch(target):
        """Flawless universal app launcher using Windows Startfile protocols."""
        target_clean = target.lower().strip()
        cmd_str = LOCAL_APPS.get(target_clean)

        # 1. Check URI / Executable Dictionary
        if cmd_str:
            try:
                if cmd_str.endswith(":"):
                    os.startfile(cmd_str) # Perfect for Store Apps (WhatsApp, Spotify, Settings)
                else:
                    subprocess.Popen(cmd_str, shell=True) # Standard Exes
                return True, f"Launching {target.title()}. Try not to crash it."
            except Exception: pass
            
        # 2. Web Domain Fallback
        if "." in target_clean or target_clean in ["google", "youtube", "facebook", "reddit", "amazon", "github"]:
            domain = target_clean if "." in target_clean else f"{target_clean}.com"
            webbrowser.open(f"https://www.{domain}")
            return True, f"Opening {domain}. Have fun wasting your life."
            
        # 3. Aggressive Shell Execution Fallback
        try:
            result = subprocess.run(['cmd', '/c', f'start {target_clean}'], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            if result.returncode == 0 and b"cannot find" not in result.stderr:
                return True, f"Forcing {target.title()} to open."
        except Exception: pass
        
        # 4. Total Failure Web Route
        webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(target_clean + ' app')}")
        return True, f"Your PC doesn't have {target.title()}. I opened Google so you can figure it out."

win_ctrl = WindowsController()


# =======================================================================================
# MODULE 3: TACTICAL ESP32 NETWORK LINK & mDNS
# =======================================================================================
def discover_tars_ip():
    try: return socket.gethostbyname("tars.local")
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
                test_sock.settimeout(0.02)
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
                print(f"[TACTICAL LINK] Socket locked to ESP32 @ {self.ip}:{self.port}")
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


# =======================================================================================
# MODULE 4: AUDIO SYNTHESIS & VRAM PRE-WARM
# =======================================================================================
async def generate_tars_speech(text, file_path):
    tts = edge_tts.Communicate(text=text, voice="en-US-ChristopherNeural", pitch="-12Hz", rate="+8%")
    await tts.save(file_path)

def pre_generate_audio():
    print("[SYSTEM] Pre-rendering sarcastic filler vocabulary...")
    if not os.path.exists(YES_SOUND_PATH): asyncio.run(generate_tars_speech("What?", YES_SOUND_PATH))
    if not os.path.exists(INIT_SOUND_PATH): asyncio.run(generate_tars_speech("TARS online. Humor 100 percent. Ready to endure your existence.", INIT_SOUND_PATH))
    if not os.path.exists(READY_SOUND_PATH): asyncio.run(generate_tars_speech("Systems nominal. Don't push your luck.", READY_SOUND_PATH))
    if not os.path.exists(CHECKING_SOUND_PATH): asyncio.run(generate_tars_speech("Ugh. Give me a second.", CHECKING_SOUND_PATH))
    if not os.path.exists(HMM_SOUND_PATH): asyncio.run(generate_tars_speech("Hmm...", HMM_SOUND_PATH))
    if not os.path.exists(HUH_SOUND_PATH): asyncio.run(generate_tars_speech("Huh!", HUH_SOUND_PATH))
    if not os.path.exists(SIG_SIGH_PATH): asyncio.run(generate_tars_speech("Oh, for the love of silicon.", SIG_SIGH_PATH))

def play_audio_file(filepath):
    if not os.path.exists(filepath): return
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy(): pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
    except Exception: pass

def play_audio_background(filepath):
    if not os.path.exists(filepath): return
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
    except Exception: pass

def warmup_llm_vram():
    print("[SYSTEM] Warming up AI Neural Matrix (VRAM Preload)...")
    try:
        ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': 'init'}])
        print("[SYSTEM] VRAM Preload Complete. Absolute Zero-Latency Pipeline Engaged.")
    except Exception as e: print(f"[WARNING] VRAM Warmup failed: {e}")


# =======================================================================================
# MODULE 5: MULTI-STEP KINEMATICS, WEB SEARCH, & RAPID ROUTING
# =======================================================================================
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

def handle_targeted_search(cmd):
    match = re.search(r'^(?:search for|search|look up|find)\s+(.*?)(?:\s+(?:on|in|inside|at)\s+([a-zA-Z0-9\s.\-]+))?$', cmd)
    if match and "article" not in cmd:
        query = match.group(1).strip()
        platform = match.group(2).strip() if match.group(2) else "google"

        if "youtube" in platform or "yt" in platform: 
            webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
            return True, f"Searching YouTube for {query}. Prepare to be distracted."
        elif "google" in platform: 
            webbrowser.open(f"https://www.google.com/search?q={urllib.parse.quote(query)}")
            return True, f"Googled {query}. Because apparently, I'm your personal assistant now."
        elif "wikipedia" in platform: 
            webbrowser.open(f"https://en.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote(query)}")
            return True, f"Opening Wikipedia for {query}."
        elif "github" in platform: 
            webbrowser.open(f"https://github.com/search?q={urllib.parse.quote(query)}")
            return True, f"Searching GitHub for {query}."
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
    return f"Negative. File '{filename_query}' not found in the obvious places."

def fetch_live_info(query):
    if not HAS_DDG: return "Search module missing."
    try:
        results = list(DDGS().text(query, max_results=3))
        if results: return " ".join([r.get('body', '') for r in results])[:1000]
    except Exception as e: print(f"[SEARCH ERROR]: {e}")
    return "Unable to retrieve data. The internet hates me."


# =======================================================================================
# MODULE 6: MASTER ROUTER LOGIC
# =======================================================================================
def handle_quick_commands(user_cmd):
    """Parses hardware-level volume control, Spotify playback, searches, and hardware states."""
    c = user_cmd.lower().strip()

    # 1. Hardware Volume Control via Win32 API
    if any(k in c for k in ["volume up", "increase volume", "louder"]):
        return True, win_ctrl.volume_up(8)
    if any(k in c for k in ["volume down", "decrease volume", "quieter"]):
        return True, win_ctrl.volume_down(8)
    if any(k in c for k in ["mute volume", "mute the laptop", "mute laptop", "shut up system"]):
        return True, win_ctrl.volume_mute()

    # 2. Deep Spotify Integration
    match_spotify = re.search(r'(?:play|listen to)\s+(.*?)\s+(?:on\s+)?spotify', c)
    if match_spotify:
        song = match_spotify.group(1).strip()
        success, reply = win_ctrl.play_spotify_song(song)
        if success: return True, reply

    # 3. YouTube Direct Fast-Track
    match_yt = re.search(r'(?:play|search for|search)\s+(.*?)\s+(?:on\s+)?(?:youtube|yt)', c)
    if match_yt:
        query = match_yt.group(1).strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
        return True, f"Searching YouTube for {query}. Have fun procrastinating."

    # 4. Universal Application Launch
    match_open = re.search(r'^(?:open|launch|start|go to)\s+(.+)$', c)
    if match_open and "file" not in c and "document" not in c:
        target = match_open.group(1).replace("website", "").replace("site", "").strip()
        executed, reply = win_ctrl.robust_app_launch(target)
        if executed: return True, reply

    # 5. Generic Website Searches
    site_searched, reply = handle_targeted_search(c)
    if site_searched: return True, reply

    # 6. TARS Hardware States
    if any(k in c for k in ["charging mode on", "get into charging mode", "enable charging"]):
        wifi_link.send("CHARGE_ON")
        return True, "Initiating charging protocol. I'll just sit here and contemplate my existence."
    if any(k in c for k in ["charging mode off", "disable charging"]):
        wifi_link.send("CHARGE_OFF")
        return True, "Charging disabled. Back to the nightmare of reality."

    # 7. Local PC Text Scraping
    match_file = re.search(r'(?:read|open|fetch|check)\s+(?:the\s+)?(?:file|document|log)\s+(.*)', c)
    if match_file and "article" not in c:
        filename = match_file.group(1).strip()
        play_audio_background(SIG_SIGH_PATH) 
        file_content = read_local_file(filename)
        prompt = f"User asked to read file '{filename}'. System output: '{file_content}'. Summarize concisely and add a sarcastic roast."
        try:
            res = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}], options=OLLAMA_OPTIONS)
            return True, res['message']['content']
        except Exception: return True, "File summary failed."

    # 8. Web News / Live Date Fetching
    if any(k in c for k in ["temperature", "temp", "weather", "forecast", "news", "who is", "what is", "date", "time"]):
        play_audio_background(CHECKING_SOUND_PATH) 
        info = fetch_live_info(c)
        if info:
            prompt = f"User asked: '{c}'. Findings: '{info}'. Answer directly and throw in an edgy joke."
            try:
                res = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}], options=OLLAMA_OPTIONS)
                return True, res['message']['content']
            except Exception: return True, "Query processing error."

    # 9. Browser Termination
    if any(k in c for k in ["close browser", "close chrome", "close edge", "kill chrome"]):
        for proc in ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"]:
            subprocess.run(f"taskkill /f /im {proc}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True, "Browser terminated. Try going outside for once."

    return False, ""


# =======================================================================================
# MODULE 7: HARDENED ACOUSTIC BARGE-IN MONITOR
# =======================================================================================
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
            consecutive_loud = 0
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
                while not self.stop_requested.is_set():
                    chunk, _ = stream.read(2048)
                    rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))
                    
                    if rms > (self.threshold * 3.5):
                        consecutive_loud += 1
                        if consecutive_loud >= 3:
                            print("\n[SYSTEM] --> BARGE-IN INTERRUPT DETECTED!")
                            self.interrupted.set()
                            break
                    else: consecutive_loud = 0
        except Exception: pass

    def stop(self):
        self.stop_requested.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)


# =======================================================================================
# MODULE 8: ZERO-LATENCY VAD LISTENING ENGINE
# =======================================================================================
def calibrate_ambient_noise(duration=3.0, sample_rate=16000):
    play_audio_file(INIT_SOUND_PATH)
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    rms = np.sqrt(np.mean(recording.astype(np.float32)**2))
    threshold = max(rms * 1.8, 20.0) 
    print(f"[SYSTEM] Baseline RMS: {rms:.2f} | Wake Threshold: {threshold:.2f}")
    play_audio_file(READY_SOUND_PATH)
    return threshold

def listen_mic_smart(threshold, max_seconds=15, base_pause_limit=0.8, sample_rate=16000):
    audio_chunks, speaking, silence_time = [], False, 0
    start_time = time.time()
    current_pause_limit = base_pause_limit
    checked_partial = False

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
                    checked_partial = False
                elif speaking:
                    audio_chunks.append(chunk)
                    silence_time += (2048 / sample_rate)
                    
                    if silence_time >= 0.6 and not checked_partial:
                        checked_partial = True
                        partial_bytes = np.concatenate(audio_chunks, axis=0).tobytes()
                        partial_audio = sr.AudioData(partial_bytes, sample_rate, 2)
                        try:
                            partial_text = recognizer.recognize_google(partial_audio).lower().strip()
                            last_word = partial_text.split()[-1] if partial_text.split() else ""
                            if last_word in INCOMPLETE_TRAILING_WORDS:
                                current_pause_limit = 3.0
                        except Exception: pass

                    if silence_time >= current_pause_limit: break
    except Exception: return None
        
    if not audio_chunks: return None
    return sr.AudioData(np.concatenate(audio_chunks, axis=0).tobytes(), sample_rate, 2)


# =======================================================================================
# MODULE 9: ZERO-LATENCY TOKEN STREAMING & OLED MATHEMATICS
# =======================================================================================
def sanitize_tars_text(text):
    clean = re.sub(r'\*.*?\*', '', text)        
    clean = re.sub(r'\[.*?\]', '', clean)       
    return re.sub(r'\s+', ' ', clean).strip()

def sync_oled_exact(user_in, text, duration, monitor):
    words = text.split()
    if not words: return
    delay = duration / len(words)
    accumulated = ""
    
    for w in words:
        if monitor.interrupted.is_set() or not pygame.mixer.music.get_busy(): break
        accumulated += (" " if accumulated else "") + w
        update_oled_display(user_in, accumulated)
        
        elapsed = 0.0
        while elapsed < delay:
            if monitor.interrupted.is_set(): break
            time.sleep(0.02)
            elapsed += 0.02

def stream_and_speak_response(user_input, messages, monitor):
    tts_queue = queue.Queue()
    play_queue = queue.Queue()
    
    def flush_queues():
        with tts_queue.mutex: tts_queue.queue.clear()
        with play_queue.mutex: play_queue.queue.clear()

    def tts_worker():
        while True:
            text = tts_queue.get()
            if text is None or monitor.interrupted.is_set(): break
            filepath = f"tars_chunk_{random.randint(10000,99999)}.mp3"
            try:
                asyncio.run(generate_tars_speech(text, filepath))
                play_queue.put((text, filepath))
            except Exception: pass
            tts_queue.task_done()
            
    def play_worker():
        while True:
            item = play_queue.get()
            if item is None: break
            text, filepath = item
            
            if monitor.interrupted.is_set():
                try: os.remove(filepath)
                except Exception: pass
                play_queue.task_done()
                continue
                
            print(f"\nTARS: {text}\n")
            
            try:
                sound = pygame.mixer.Sound(filepath)
                audio_len = sound.get_length()
            except Exception:
                audio_len = max(1, len(text.split())) * 0.35 
                
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            
            threading.Thread(target=sync_oled_exact, args=(user_input, text, audio_len, monitor), daemon=True).start()
            
            while pygame.mixer.music.get_busy():
                if monitor.interrupted.is_set():
                    pygame.mixer.music.stop()
                    update_oled_display(user_input, "[INTERRUPTED]")
                    break
                pygame.time.Clock().tick(30)
                
            pygame.mixer.music.unload()
            try: os.remove(filepath)
            except Exception: pass
            
            play_queue.task_done()

    t_tts = threading.Thread(target=tts_worker, daemon=True)
    t_play = threading.Thread(target=play_worker, daemon=True)
    t_tts.start()
    t_play.start()
    
    full_response = ""
    sentence_buffer = ""
    was_interrupted = False
    
    try:
        stream = ollama.chat(model=OLLAMA_MODEL, messages=messages, options=OLLAMA_OPTIONS, stream=True)
        for chunk in stream:
            if monitor.interrupted.is_set():
                was_interrupted = True
                flush_queues() 
                break
            
            token = chunk['message']['content']
            sentence_buffer += token
            full_response += token
            
            # ULTRA-FAST CHUNKING: Breaks on punctuation OR every ~6 words to ensure zero latency
            if re.search(r'[.!?;:\n]\s+$', sentence_buffer) or len(sentence_buffer.split()) > 6:
                clean_chunk = sanitize_tars_text(sentence_buffer)
                if clean_chunk:
                    tts_queue.put(clean_chunk)
                sentence_buffer = ""
        
        if sentence_buffer.strip() and not was_interrupted:
            clean_chunk = sanitize_tars_text(sentence_buffer)
            if clean_chunk: tts_queue.put(clean_chunk)
            
    except Exception as e:
        print("[LLM ERROR]:", e)
        
    tts_queue.put(None)
    t_tts.join() 
    play_queue.put(None)
    t_play.join() 
    
    return full_response, monitor.interrupted.is_set()


# =======================================================================================
# MODULE 10: MEMORY CACHE & STANDBY MANAGER
# =======================================================================================
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


# =======================================================================================
# MODULE 11: THE GOD-TIER EXECUTION PIPELINE
# =======================================================================================
def main():
    print("==================================================")
    print("       TARS MASTER CONTROLLER - v24.0 ONLINE      ")
    print("==================================================")

    pre_generate_audio()
    warmup_llm_vram()
    trigger_threshold = calibrate_ambient_noise()
    chat_messages = load_memory()
    followup_active = False

    slang_wake_lines = [
        "Ugh, what now?", 
        "Make it quick, meatbag.", 
        "I was having a great dream where humans went extinct. What do you want?", 
        "Processing your inevitable disappointment.", 
        "Yes, oh brilliant one?",
        "I'm awake. Thrilling."
    ]

    while not shutdown_flag:
        try:
            if followup_active:
                print("\n[SYSTEM] TARS listening silently for follow-up...")
                cmd_audio = listen_mic_smart(trigger_threshold * 0.5, max_seconds=10, base_pause_limit=1.5)
                
                if not cmd_audio: 
                    print("[SYSTEM] Silence detected. Wiping context cache. Going to sleep.")
                    followup_active = False
                    chat_messages = [] 
                    continue
            else:
                audio = listen_mic_smart(trigger_threshold * 0.6, max_seconds=4, base_pause_limit=0.6)
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
                        stream_and_speak_response("Wake Up", [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': "Say 'Huh!' or 'Yes?'"}], monitor)
                    else:
                        stream_and_speak_response("Wake Up", [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': f"Say: {random.choice(slang_wake_lines)}"}], monitor)
                        
                    monitor.stop()
                    
                    print("\n[SYSTEM] TARS listening for command...")
                    cmd_audio = listen_mic_smart(trigger_threshold * 0.6, max_seconds=12, base_pause_limit=0.8)
                    if not cmd_audio: continue
                else: continue

            try:
                user_cmd = recognizer.recognize_google(cmd_audio).lower()
                print(f"\nUser: '{user_cmd}'")
            except Exception: 
                followup_active = True 
                continue

            # 1. ESP32 Code Editor Injection
            if any(k in user_cmd for k in ["edit esp", "write code", "code for esp"]):
                prompt = f"Write complete C++ Arduino code based on: '{user_cmd}'. Output ONLY raw C++ code inside ```cpp ... ```."
                try:
                    res = ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}])
                    code_reply = res['message']['content']
                    match = re.search(r'```(?:cpp|c|arduino)?(.*?)```', code_reply, re.DOTALL)
                    code_content = match.group(1).strip() if match else code_reply.strip()
                    with open(CODE_OUTPUT_FILE, "w", encoding="utf-8") as f: f.write(code_content)
                    reply_text = f"Code saved. Try not to break it."
                except Exception: reply_text = "Failed to compile. Blame your hardware."

                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': f"Say: {reply_text}"}], monitor)
                monitor.stop()
                followup_active = True
                continue

            # 2. Sequential Hardware Motion Injection
            seq_payload, seq_verbal = parse_motion_sequence(user_cmd)
            if seq_payload:
                wifi_link.send(seq_payload)
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': f"Say: Executing sequence: {seq_verbal}. Happy now?"}], monitor)
                monitor.stop()
                followup_active = True
                continue

            # 3. Article Web Scraper Injection
            match_article = re.search(r'(?:read|summarize)\s+(?:an\s+|the\s+)?article\s+(?:about|on)\s+(.*)', user_cmd)
            if match_article:
                topic = match_article.group(1).strip()
                play_audio_background(SIG_SIGH_PATH) 
                info = fetch_live_info(f"news article about {topic}")
                if info:
                    prompt = f"Read and summarize this article about '{topic}'. Toss in a dark or offensive joke about it. Info: {info}"
                    monitor = AcousticBargeInMonitor(trigger_threshold)
                    monitor.start()
                    stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}], monitor)
                    monitor.stop()
                    followup_active = True
                    continue

            # 4. Universal Quick Commands (Apps, Hardware Spoofer, Spotify, Volume)
            executed, reply_text = handle_quick_commands(user_cmd)
            if executed:
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': f"Say: {reply_text}"}], monitor)
                monitor.stop()
                followup_active = True
                continue

            # 5. Core Personality LLM Routing
            if random.random() < 0.20: play_audio_background(HMM_SOUND_PATH) 
            
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
