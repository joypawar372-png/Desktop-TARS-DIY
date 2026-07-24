@'
import asyncio
import os
import re
import time
import random
import socket
import threading
import subprocess
import webbrowser
import ollama
import pygame
import edge_tts
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import shutil
import sys

# =========================================================================
# 1. WIRELESS SOCKET MATRIX
# =========================================================================
ESP32_IP = '192.168.1.100'  # UPDATE THIS TO MATCH OLED IP
ESP32_PORT = 8888
tcp_client = None

def connect_wireless():
    global tcp_client
    try:
        if tcp_client: tcp_client.close()
        tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_client.settimeout(1.5)
        tcp_client.connect((ESP32_IP, ESP32_PORT))
        print(f"\n[SUCCESS] Wireless tactical link active: {ESP32_IP}:{ESP32_PORT}\n")
    except Exception:
        tcp_client = None

connect_wireless()

def send_wifi_cmd(cmd):
    global tcp_client
    clean_cmd = cmd.replace('\r', '').replace('\n', '|') + "\r\n"
    if tcp_client:
        try: tcp_client.sendall(clean_cmd.encode('utf-8'))
        except Exception:
            connect_wireless()
            if tcp_client:
                try: tcp_client.sendall(clean_cmd.encode('utf-8'))
                except: pass

def format_for_oled(text, max_chars=20):
    clean = re.sub(r'[*_~#`]', '', text).strip()
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
# 2. VOICE & AUDIO ENGINE
# =========================================================================
pygame.mixer.init()
recognizer = sr.Recognizer()

async def generate_tars_speech(text, file_path="tars_reply.mp3"):
    clean = re.sub(r'[*_~#`]', '', text).replace("...", ", ").replace("—", ", ")
    tts = edge_tts.Communicate(text=clean, voice="en-US-ChristopherNeural", pitch="-2Hz")
    await tts.save(file_path)

def play_instant_sound(filename):
    try:
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy(): pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
    except Exception: pass

def speak_humanlike_tars(text, interrupt_threshold, add_hmm=False, sample_rate=16000):
    if add_hmm:
        clean_text = text.rstrip(" .!?")
        if not clean_text.endswith("hmm"): text = clean_text + ", hmm?"

    print(f"\nTARS: {text}\n")
    send_wifi_cmd(f"DISP:{format_for_oled(text)}")

    if random.random() < 0.15 and not text.startswith("*"): play_instant_sound("audio/sigh.mp3")

    interrupted = False
    try:
        asyncio.run(generate_tars_speech(text, "tars_reply.mp3"))
        pygame.mixer.music.load("tars_reply.mp3")
        pygame.mixer.music.play()

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
            while pygame.mixer.music.get_busy():
                chunk, _ = stream.read(2048)
                if np.sqrt(np.mean(chunk.astype(np.float32)**2)) > (interrupt_threshold * 2.2):
                    pygame.mixer.music.stop()
                    interrupted = True
                    send_wifi_cmd("DISP:Interrupted")
                    break
                pygame.time.Clock().tick(30)
    except Exception: pass
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        time.sleep(0.1)
        try: os.remove("tars_reply.mp3")
        except: pass
    return interrupted

# =========================================================================
# 3. PC INTEGRATION & SYSTEM OVERRIDES
# =========================================================================
def background_timer(seconds):
    time.sleep(seconds)
    # Re-using the generate speech function directly to alert the user
    alert_text = "Commander, your timer has elapsed."
    print(f"\n[SYSTEM ALERT]: {alert_text}")
    try:
        asyncio.run(generate_tars_speech(alert_text, "tars_alarm.mp3"))
        play_instant_sound("tars_alarm.mp3")
        os.remove("tars_alarm.mp3")
    except: pass

def parse_system_commands(text):
    """Executes local PC commands and returns context to inject into TARS's brain."""
    text = text.lower()
    
    # 1. Browser Routing
    if "browser" in text or "internet" in text:
        webbrowser.open("https://www.google.com")
        return "[SYSTEM OVERRIDE: You just successfully opened the web browser on the Commander's PC. Acknowledge this action sarcastically.]"
    
    if "youtube" in text:
        webbrowser.open("https://www.youtube.com")
        return "[SYSTEM OVERRIDE: You just opened YouTube on the Commander's PC. Acknowledge this action.]"

    # 2. Local Apps (Windows Specific)
    if "calendar" in text:
        subprocess.Popen("start outlookcal:", shell=True) # Opens Win11 Calendar
        return "[SYSTEM OVERRIDE: You just opened the Calendar app on the Commander's PC.]"
        
    if "calculator" in text:
        subprocess.Popen("calc.exe")
        return "[SYSTEM OVERRIDE: You just opened the Calculator. Make a joke about human math skills.]"
        
    if "notepad" in text or "notes" in text:
        subprocess.Popen("notepad.exe")
        return "[SYSTEM OVERRIDE: You just opened Notepad.]"

    # 3. Timer Routing
    if "timer" in text:
        nums = [int(s) for s in text.split() if s.isdigit()]
        if nums:
            val = nums[0]
            sec = val * 60 if "minute" in text else val
            threading.Thread(target=background_timer, args=(sec,), daemon=True).start()
            return f"[SYSTEM OVERRIDE: You just set a background timer for {val} units. Confirm this to the Commander.]"
            
    return ""

def parse_motion_command(text):
    text = text.lower().strip()
    
    # Check for body pushes first
    if any(k in text for k in ["push left", "shove left", "lean left"]): return ("PUSH_LEFT", 1)
    if any(k in text for k in ["push right", "shove right", "lean right"]): return ("PUSH_RIGHT", 1)

    # Check for steps
    num_map = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    steps = 1
    for w in text.split():
        if w.isdigit(): steps = int(w); break
        elif w in num_map: steps = num_map[w]; break

    if any(k in text for k in ["forward", "ahead", "straight"]): return ("FORWARD", max(1, min(steps, 8)))
    if any(k in text for k in ["left", "pivot left", "turn left"]): return ("LEFT", max(1, min(steps, 8)))
    if any(k in text for k in ["right", "pivot right", "turn right"]): return ("RIGHT", max(1, min(steps, 8)))
    return (None, 0)

# =========================================================================
# 4. ACOUSTIC SENSORS & MAIN LOOP
# =========================================================================
def calibrate_ambient_noise(duration=1.0, sample_rate=16000):
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
                rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))
                if rms > threshold:
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

send_wifi_cmd("DISP:TARS Online")
trigger_threshold = calibrate_ambient_noise()

def get_system_prompt():
    return (
        "You are TARS from Interstellar. Persona: highly sarcastic, military tactical robot, dry wit. "
        "Address the user as 'Commander'. Keep responses punchy, focused on operational readiness."
    )

followup_active = False
chat_messages = []

while True:
    try:
        user_cmd = ""
        if followup_active:
            send_wifi_cmd("DISP:Listening...")
            cmd_audio = listen_mic(trigger_threshold * 0.5, max_seconds=7, pause_limit=1.3)
            followup_active = False
            if not cmd_audio: continue
        else:
            audio = listen_mic(trigger_threshold * 0.6, max_seconds=5, pause_limit=0.8)
            if not audio: continue
            try: wake_text = recognizer.recognize_google(audio).lower()
            except Exception: continue
            
            if any(w in wake_text for w in ["tars", "tarz", "hey", "hi", "ok", "hello"]):
                send_wifi_cmd("DISP:Listening...")
                cmd_audio = listen_mic(trigger_threshold * 0.6, max_seconds=9, pause_limit=1.2)
                if not cmd_audio: continue
            else: continue

        try:
            user_cmd = recognizer.recognize_google(cmd_audio).lower()
            print(f"Commander: '{user_cmd}'")
        except Exception: continue

        # 1. Check for Motion Commands (Including new Body Pushes)
        direction, count = parse_motion_command(user_cmd)
        if direction:
            if direction in ["PUSH_LEFT", "PUSH_RIGHT"]:
                send_wifi_cmd(direction)
                speak_humanlike_tars("Shifting center of gravity. Stand clear.", trigger_threshold, add_hmm=True)
            else:
                send_wifi_cmd(f"{direction}_{count}")
                speak_humanlike_tars(f"Advancing {count} coordinates.", trigger_threshold, add_hmm=True)
            followup_active = True
            continue

        # 2. Check for PC System Commands (Injects Context to LLM)
        system_context = parse_system_commands(user_cmd)
        
        # 3. LLM Processing
        messages = [{'role': 'system', 'content': get_system_prompt()}]
        messages.extend(chat_messages[-4:])
        
        # If a system action occurred, hide it from the user but show it to the AI
        final_prompt = f"{user_cmd}\n{system_context}" if system_context else user_cmd
        messages.append({'role': 'user', 'content': final_prompt})

        send_wifi_cmd("DISP:Thinking...")
        response = ollama.chat(model='tars', messages=messages)
        ai_reply = response['message']['content']

        if ai_reply:
            chat_messages.append({'role': 'user', 'content': user_cmd})
            chat_messages.append({'role': 'assistant', 'content': ai_reply})
            interrupted = speak_humanlike_tars(ai_reply, trigger_threshold, add_hmm=True)
            if not interrupted:
                followup_active = True

    except Exception as e:
        print(f"[Main Loop Exception]: {e}")
'@ | Out-File -Encoding utf8 tars_master.py
