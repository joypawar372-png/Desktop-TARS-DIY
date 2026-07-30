Set-Content -Path "tars_master.py" -Encoding UTF8 -Value @'
"""
=========================================================================================
TARS MASTER CONTROLLER - v22.0 (MODULAR MONOLITH)
=========================================================================================
This script acts as the central brain for the TARS robotic companion. It handles
LLM generation, multi-threaded audio synthesis, TCP socket communications to the ESP32,
barge-in interruption, web scraping, and local OS commands.
=========================================================================================
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
# MODULE 1: CONFIGURATION & CONSTANTS
# =======================================================================================
ESP32_PORT   = 8888             
OLLAMA_MODEL = 'llama3.2'       

AUDIO_DIR = "audio"
DATA_DIR = "memory"
MEMORY_FILE = os.path.join(DATA_DIR, "tars_core_memory.json")
DB_FILE = os.path.join(DATA_DIR, "tars_data.db")
CODE_OUTPUT_FILE = "tars_esp32_update.ino"

OLLAMA_OPTIONS = {
    "num_predict": 180,
    "num_ctx": 1024,
    "temperature": 0.82  # Tuned for high cynicism and wit
}

# The core brain prompt. Forces cynical, mechanical, and witty behavior without titles.
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

# Words that indicate the user hasn't finished speaking yet
INCOMPLETE_TRAILING_WORDS = {
    "to", "and", "the", "a", "an", "for", "in", "on", "at", "with", "from", "by", 
    "about", "as", "into", "of", "or", "so", "but", "then", "if", "because", "while", 
    "where", "when", "how", "what", "which", "who", "move", "turn", "set", "open", 
    "play", "search", "check", "tell", "show", "is", "are", "was", "were", "my", "your"
}

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

# Ensure required directories exist
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


# =======================================================================================
# MODULE 2: MEMORY & DATABASE MANAGEMENT
# =======================================================================================
def load_memory():
    """Loads the short-term contextual memory."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except Exception: return []
    return []

def save_memory(chat_history):
    """Saves the last 6 lines of conversation to maintain context."""
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f: json.dump(chat_history[-6:], f, indent=4)
    except Exception: pass


# =======================================================================================
# MODULE 3: AUDIO SYNTHESIS & TTS ENGINE
# =======================================================================================
async def generate_tars_speech(text, file_path):
    """Mechanical, deadpan TTS generation (-12Hz pitch, +8% speed)."""
    tts = edge_tts.Communicate(text=text, voice="en-US-ChristopherNeural", pitch="-12Hz", rate="+8%")
    await tts.save(file_path)

def pre_generate_audio():
    """Builds cache of filler words to eliminate generation latency."""
    print("[SYSTEM] Verifying core audio files...")
    if not os.path.exists(YES_SOUND_PATH): asyncio.run(generate_tars_speech("Yes?", YES_SOUND_PATH))
    if not os.path.exists(INIT_SOUND_PATH): asyncio.run(generate_tars_speech("TARS online. Humor 75 percent. Ready to perform menial tasks.", INIT_SOUND_PATH))
    if not os.path.exists(READY_SOUND_PATH): asyncio.run(generate_tars_speech("Systems nominal. Try not to break anything.", READY_SOUND_PATH))
    if not os.path.exists(CHECKING_SOUND_PATH): asyncio.run(generate_tars_speech("Let me check the network.", CHECKING_SOUND_PATH))
    if not os.path.exists(HMM_SOUND_PATH): asyncio.run(generate_tars_speech("Hmm...", HMM_SOUND_PATH))
    if not os.path.exists(HUH_SOUND_PATH): asyncio.run(generate_tars_speech("Huh!", HUH_SOUND_PATH))

def play_audio_file(filepath):
    """Plays an audio file and blocks the thread until finished."""
    if not os.path.exists(filepath): return
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy(): pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
    except Exception: pass

def play_audio_background(filepath):
    """Plays audio seamlessly in the background (used for masking latency)."""
    if not os.path.exists(filepath): return
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
    except Exception: pass

def warmup_llm_vram():
    """Forces Ollama to load the model into VRAM on startup."""
    print("[SYSTEM] Warming up AI Neural Matrix (VRAM Preload)...")
    try:
        ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': 'init'}])
        print("[SYSTEM] VRAM Preload Complete. Zero-latency engaged.")
    except Exception as e:
        print(f"[WARNING] VRAM Warmup failed: {e}")


# =======================================================================================
# MODULE 4: ESP32 HARDWARE LINK & OLED SYNC
# =======================================================================================
def discover_tars_ip():
    """Resolves the ESP32 IP address via mDNS or subnet pinging."""
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
                test_sock.settimeout(0.03)
                if test_sock.connect_ex((target_ip, ESP32_PORT)) == 0:
                    test_sock.close()
                    return target_ip
                test_sock.close()
            except Exception: pass
    except Exception: pass
    return "192.168.1.126" 

class ESP32SocketLink:
    """Maintains a persistent, fault-tolerant TCP link to the robot."""
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
    """Translates Python strings into ESP32 OLED pipe payloads."""
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
# MODULE 5: LOCAL APP & OS CONTROL
# =======================================================================================
def try_launch_app_or_web(target):
    """Attempts to open a local Windows app, falling back to a web search if uninstalled."""
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
    return True, f"Couldn't find {target.title()} locally. Opening the web."

def read_local_file(filename_query):
    """Scans the user's local directories for matching text files."""
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


# =======================================================================================
# MODULE 6: WEB SCRAPING & SEARCH ENGINE
# =======================================================================================
def handle_targeted_search(cmd):
    """Parses requests to search specific websites."""
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

def fetch_live_info(query):
    """Uses DuckDuckGo to extract raw text snippets for the LLM to summarize."""
    if not HAS_DDG: return "Search module missing."
    try:
        results = list(DDGS().text(query, max_results=3))
        if results: return " ".join([r.get('body', '') for r in results])[:1000]
    except Exception as e: print(f"[SEARCH ERROR]: {e}")
    return "Unable to retrieve data."


# =======================================================================================
# MODULE 7: KINEMATICS & MOTION PARSER
# =======================================================================================
def parse_motion_sequence(text):
    """Converts natural language ('two steps forward and one left') into ESP32 queue data."""
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


# =======================================================================================
# MODULE 8: HARDENED BARGE-IN & ECHO AWARENESS
# =======================================================================================
class AcousticBargeInMonitor:
    """
    Listens to the microphone while TARS is speaking. If it detects a sudden
    spike in volume (indicating the user is interrupting), it fires a global event.
    """
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
                    
                    # Hardened Logic: Needs 3.0x threshold sustained for 4 chunks to bypass self-echo
                    if rms > (self.threshold * 3.0):
                        consecutive_loud += 1
                        if consecutive_loud >= 4:
                            print("\n[SYSTEM] --> BARGE-IN INTERRUPT DETECTED!")
                            self.interrupted.set()
                            break
                    else:
                        consecutive_loud = 0
        except Exception: pass

    def stop(self):
        self.stop_requested.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.5)


# =======================================================================================
# MODULE 9: SMART VAD MIC LISTENER
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
    """
    Rapid volume-based listening algorithm. Cuts off quickly (0.8s) for fast response,
    but dynamically extends to 3.0s if the user pauses on an incomplete word.
    """
    audio_chunks = []
    speaking = False
    silence_time = 0.0
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
                    
                    # At 0.6 seconds of silence, check if they are trailing off
                    if silence_time >= 0.6 and not checked_partial:
                        checked_partial = True
                        partial_bytes = np.concatenate(audio_chunks, axis=0).tobytes()
                        partial_audio = sr.AudioData(partial_bytes, sample_rate, 2)
                        try:
                            partial_text = recognizer.recognize_google(partial_audio).lower().strip()
                            last_word = partial_text.split()[-1] if partial_text.split() else ""
                            if last_word in INCOMPLETE_TRAILING_WORDS:
                                print(f"[SMART PAUSE] Detected trailing word '{last_word}'. Extending listen window.")
                                current_pause_limit = 3.0
                        except Exception: pass

                    if silence_time >= current_pause_limit: break
    except Exception: return None
        
    if not audio_chunks: return None
    return sr.AudioData(np.concatenate(audio_chunks, axis=0).tobytes(), sample_rate, 2)


# =======================================================================================
# MODULE 10: ZERO-LATENCY LLM STREAMING QUEUE
# =======================================================================================
def sanitize_tars_text(text):
    clean = re.sub(r'\*.*?\*', '', text)        
    clean = re.sub(r'\[.*?\]', '', clean)       
    return re.sub(r'\s+', ' ', clean).strip()

def sync_oled_exact(user_in, text, duration, monitor):
    """Calculates exact milliseconds per word to push to the ESP32 OLED cleanly."""
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
    """
    Advanced Triple-Buffered Generator.
    Thread 1 (Main): Streams tokens from Ollama, building sentences.
    Thread 2 (TTS): Converts completed sentences into MP3s.
    Thread 3 (Play): Plays MP3s back-to-back with zero gap.
    """
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
                flush_queues() # INSTANTLY DUMP EVERYTHING
                break
            
            token = chunk['message']['content']
            sentence_buffer += token
            full_response += token
            
            if re.search(r'[.!?;]\s+$', sentence_buffer):
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
# MODULE 11: CORE EXECUTION LOOP
# =======================================================================================
def main():
    print("==================================================")
    print("       TARS MASTER CONTROLLER - v22.0 ONLINE      ")
    print("==================================================")

    pre_generate_audio()
    warmup_llm_vram()
    trigger_threshold = calibrate_ambient_noise()
    chat_messages = load_memory()
    followup_active = False

    slang_wake_lines = ["I'm awake. Thrilling.", "Yes?", "What now?", "Processing.", "You rang?"]

    while not shutdown_flag:
        try:
            if followup_active:
                print("\n[SYSTEM] TARS listening silently for follow-up...")
                # Allow 8 seconds of silence for followups
                cmd_audio = listen_mic_smart(trigger_threshold * 0.5, max_seconds=10, base_pause_limit=1.5)
                
                if not cmd_audio: 
                    print("[SYSTEM] Silence detected. Wiping context cache.")
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

            # Code Editor
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
                stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': f"Say: {reply_text}"}], monitor)
                monitor.stop()
                followup_active = True
                continue

            # Sequential Motion
            seq_payload, seq_verbal = parse_motion_sequence(user_cmd)
            if seq_payload:
                wifi_link.send(seq_payload)
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': f"Say: Executing sequence: {seq_verbal}."}], monitor)
                monitor.stop()
                followup_active = True
                continue

            # Article Reader
            match_article = re.search(r'(?:read|summarize)\s+(?:an\s+|the\s+)?article\s+(?:about|on)\s+(.*)', user_cmd)
            if match_article:
                topic = match_article.group(1).strip()
                play_audio_background(CHECKING_SOUND_PATH) 
                info = fetch_live_info(f"news article about {topic}")
                if info:
                    prompt = f"Read and summarize this article about '{topic}'. Toss in a cynical joke. Info: {info}"
                    monitor = AcousticBargeInMonitor(trigger_threshold)
                    monitor.start()
                    stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}], monitor)
                    monitor.stop()
                    followup_active = True
                    continue

            # Quick Commands (Apps, Web, File Reading, Hardware Charging)
            match_open = re.search(r'^(?:open|launch|start|go to)\s+(.+)$', user_cmd)
            if match_open and "file" not in user_cmd and "document" not in user_cmd:
                target = match_open.group(1).replace("website", "").replace("site", "").strip()
                executed, reply = try_launch_app_or_web(target)
                if executed:
                    monitor = AcousticBargeInMonitor(trigger_threshold)
                    monitor.start()
                    stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': f"Say: {reply}"}], monitor)
                    monitor.stop()
                    followup_active = True
                    continue

            site_searched, reply = handle_targeted_search(user_cmd)
            if site_searched:
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': f"Say: {reply}"}], monitor)
                monitor.stop()
                followup_active = True
                continue

            if any(k in user_cmd for k in ["charging mode on", "get into charging mode"]):
                wifi_link.send("CHARGE_ON")
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': "Say: Initiating charging protocol. I'll just sit here."}], monitor)
                monitor.stop()
                followup_active = True
                continue

            if any(k in user_cmd for k in ["charging mode off", "disable charging"]):
                wifi_link.send("CHARGE_OFF")
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': "Say: Charging disabled."}], monitor)
                monitor.stop()
                followup_active = True
                continue

            match_file = re.search(r'(?:read|open|fetch|check)\s+(?:the\s+)?(?:file|document|log)\s+(.*)', user_cmd)
            if match_file and not match_article:
                filename = match_file.group(1).strip()
                play_audio_background(CHECKING_SOUND_PATH) 
                file_content = read_local_file(filename)
                prompt = f"User asked to read file '{filename}'. System output: '{file_content}'. Summarize concisely."
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}], monitor)
                monitor.stop()
                followup_active = True
                continue

            if any(k in user_cmd for k in ["temperature", "temp", "weather", "forecast", "news", "who is", "what is", "date", "time"]):
                play_audio_background(CHECKING_SOUND_PATH) 
                info = fetch_live_info(user_cmd)
                if info:
                    prompt = f"User asked: '{user_cmd}'. Findings: '{info}'. Answer directly."
                    monitor = AcousticBargeInMonitor(trigger_threshold)
                    monitor.start()
                    stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': prompt}], monitor)
                    monitor.stop()
                    followup_active = True
                    continue

            if any(k in user_cmd for k in ["close browser", "close chrome"]):
                for proc in ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"]:
                    subprocess.run(f"taskkill /f /im {proc}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                monitor = AcousticBargeInMonitor(trigger_threshold)
                monitor.start()
                stream_and_speak_response(user_cmd, [{'role': 'system', 'content': SYSTEM_PROMPT}, {'role': 'user', 'content': "Say: Browser terminated."}], monitor)
                monitor.stop()
                followup_active = True
                continue

            # Pure LLM Conversation Flow 
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
