@'
import asyncio
import json
import os
import re
import time
import random
import serial
import ollama
import pygame
import edge_tts
import numpy as np
import sounddevice as sd
import speech_recognition as sr
import concurrent.futures
import shutil
import sys

# =========================================================================
# 1. BLUETOOTH & OLED SYSTEM MATRIX
# =========================================================================
BLUETOOTH_PORT = 'COM6'
BAUD_RATE = 115200

bt_tars = None
try:
    bt_tars = serial.Serial(BLUETOOTH_PORT, BAUD_RATE, timeout=0.1, write_timeout=0.1)
    time.sleep(0.5)
    print(f"\n[SUCCESS] Bluetooth link active on {BLUETOOTH_PORT}\n")
except Exception as e:
    print(f"\n[WARNING] Could not open {BLUETOOTH_PORT}. Running in terminal mode.\n")

def send_bt_cmd(cmd):
    """Sends clean packets to ESP32 over Bluetooth."""
    if bt_tars and bt_tars.is_open:
        try:
            # Strip any internal carriage returns/newlines from the payload
            clean_cmd = cmd.replace('\r', '').replace('\n', '|')
            bt_tars.write(f"{clean_cmd}\r\n".encode('utf-8'))
            bt_tars.flush()
            print(f"[BT TRANSMIT] -> {clean_cmd}")
        except Exception as e:
            print(f"[BT ERROR]: {e}")
    else:
        print(f"[BT OFFLINE] Packet skipped: {cmd}")

def format_for_oled(text, max_chars=20):
    """Formats text using pipe delimiters (|) instead of newlines."""
    clean = re.sub(r'[*_~#`]', '', text).strip()
    words = clean.split()
    lines = []
    curr_line = ""
    for w in words:
        if len(curr_line) + len(w) + 1 <= max_chars:
            curr_line += (" " if curr_line else "") + w
        else:
            lines.append(curr_line)
            curr_line = w
            if len(lines) >= 4: break
    if curr_line and len(lines) < 4:
        lines.append(curr_line)
    return "|".join(lines)

# =========================================================================
# 2. VOICE SYNTHESIS & TACTICAL AUDIO
# =========================================================================
pygame.mixer.init()
recognizer = sr.Recognizer()

async def generate_tars_speech(text, file_path="tars_reply.mp3"):
    clean = re.sub(r'[*_~#`]', '', text)
    clean = clean.replace("...", ", ").replace("—", ", ")
    
    tts = edge_tts.Communicate(
        text=clean,
        voice="en-US-ChristopherNeural",
        pitch="-2Hz",
        rate="+0%"
    )
    await tts.save(file_path)

async def prep_tactical_audio():
    os.makedirs("audio", exist_ok=True)
    voice = "en-US-ChristopherNeural"
    phrases = {
        "yes_sir": "Yes, Commander.",
        "listening": "Listening.",
        "speak": "Speak.",
        "orders": "Awaiting orders.",
        "sigh": "Sigh..."
    }
    for key, text in phrases.items():
        filepath = f"audio/{key}.mp3"
        if not os.path.exists(filepath):
            tts = edge_tts.Communicate(text, voice, pitch="-2Hz")
            await tts.save(filepath)

asyncio.run(prep_tactical_audio())

def play_instant_sound(filename):
    try:
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
    except Exception:
        pass

def speak_humanlike_tars(text, interrupt_threshold, sample_rate=16000):
    print(f"\nTARS: {text}\n")
    
    # Send formatted line string to OLED using pipe delimiters
    oled_text = format_for_oled(text)
    send_bt_cmd(f"DISP:{oled_text}")

    if random.random() < 0.15 and not text.startswith("*"):
        play_instant_sound("audio/sigh.mp3")

    interrupted = False
    try:
        asyncio.run(generate_tars_speech(text, "tars_reply.mp3"))
        pygame.mixer.music.load("tars_reply.mp3")
        pygame.mixer.music.play()

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
            while pygame.mixer.music.get_busy():
                chunk, _ = stream.read(2048)
                rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))

                if rms > (interrupt_threshold * 2.2):
                    print("\n[COMMANDER INTERRUPTED]")
                    pygame.mixer.music.stop()
                    interrupted = True
                    send_bt_cmd("DISP:Interrupted")
                    break
                pygame.time.Clock().tick(30)

    except Exception as e:
        print(f"[Speech Generation Error]: {e}")
    finally:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        if os.path.exists("tars_reply.mp3"):
            try:
                os.remove("tars_reply.mp3")
            except Exception:
                pass

    return interrupted

# =========================================================================
# 3. SELF-CODE EDITING OVERRIDE PIPELINE
# =========================================================================
def generate_code_update(request):
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            current_code = f.read()

        prompt = (
            f"You are modifying a Python script based on user request: '{request}'.\n"
            "1. First line MUST be: SUMMARY: <1 clear sentence stating exactly what function/section you are changing>\n"
            "2. Then provide the FULL updated script inside a ```python ``` code block.\n\n"
            f"```python\n{current_code}\n```"
        )

        response = ollama.chat(model='tars', messages=[{'role': 'user', 'content': prompt}])
        content = response['message']['content']

        summary = "Modifying internal logic based on your request."
        summary_match = re.search(r'SUMMARY:\s*(.*)', content)
        if summary_match:
            summary = summary_match.group(1).strip()

        code_match = re.search(r'```python\n(.*?)\n```', content, re.DOTALL)
        if code_match:
            code = code_match.group(1).strip()
            compile(code, '<string>', 'exec')
            return summary, code
    except Exception as e:
        print(f"[Self-Edit Compilation Error]: {e}")
    return None, None

# =========================================================================
# 4. AUDIO & MOTION INTENT PARSER
# =========================================================================
WAKE_HOMOPHONES = [
    "tars", "tarz", "taurus", "tsars", "czars", "stars", "haiders", "toast",
    "cars", "pars", "towers", "tarts", "darts", "todd", "tires", "tears",
    "8 hours", "threaters", "heaters", "haters", "hater", "theater"
]

def contains_wake_word(text):
    if not text: return False
    clean_text = re.sub(r'[^a-z0-9\s]', '', text.lower()).strip()
    words = clean_text.split()
    return any(w in WAKE_HOMOPHONES for w in words) or any(clean_text.startswith(sw) for sw in ["hey ", "hi ", "ok ", "hello "])

def parse_motion_command(text):
    text = text.lower().strip()
    num_map = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    steps = 1
    for w in text.split():
        if w.isdigit(): steps = int(w); break
        elif w in num_map: steps = num_map[w]; break

    if any(k in text for k in ["forward", "ahead", "straight", "step forward", "move"]):
        if not any(k in text for k in ["left", "right", "back"]):
            return ("FORWARD", max(1, min(steps, 8)))
    if any(k in text for k in ["left", "pivot left", "turn left"]):
        return ("LEFT", max(1, min(steps, 8)))
    if any(k in text for k in ["right", "pivot right", "turn right"]):
        return ("RIGHT", max(1, min(steps, 8)))
    return (None, 0)

def calibrate_ambient_noise(duration=1.0, sample_rate=16000):
    print("[Calibrating acoustics...]")
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
    except Exception:
        return None

    if not audio_chunks: return None
    full_pcm = np.concatenate(audio_chunks, axis=0)
    return sr.AudioData(full_pcm.tobytes(), sample_rate, 2)

# =========================================================================
# 5. MAIN SYSTEM MATRIX
# =========================================================================
send_bt_cmd("DISP:TARS Online")
trigger_threshold = calibrate_ambient_noise()

def get_system_prompt():
    return (
        "You are TARS from Interstellar talking directly to your Commander over a tactical link. "
        "Your persona: highly sarcastic, military tactical robot, dry wit, 100% humor, 95% honesty. "
        "Address the user as 'Commander'. "
        "Keep responses punchy, concise, and focused on operational readiness."
    )

speak_humanlike_tars("TARS core operational... Ready for deployment, Commander.", trigger_threshold)

followup_active = False
chat_messages = []

while True:
    try:
        user_cmd = ""

        if followup_active:
            send_bt_cmd("DISP:Listening...")
            play_instant_sound("audio/listening.mp3")
            cmd_audio = listen_mic(trigger_threshold * 0.5, max_seconds=7, pause_limit=1.3)
            followup_active = False
            if not cmd_audio: continue
        else:
            print("\n[Awaiting Wake Word...]")
            audio = listen_mic(trigger_threshold * 0.6, max_seconds=5, pause_limit=0.8)
            if not audio: continue

            try: wake_text = recognizer.recognize_google(audio).lower()
            except Exception: continue

            print(f"[Heard]: {wake_text}")
            if contains_wake_word(wake_text):
                send_bt_cmd("DISP:Listening...")
                play_instant_sound(random.choice(["audio/yes_sir.mp3", "audio/listening.mp3", "audio/orders.mp3"]))
                cmd_audio = listen_mic(trigger_threshold * 0.6, max_seconds=9, pause_limit=1.2)
                if not cmd_audio: continue
            else: continue

        try:
            user_cmd = recognizer.recognize_google(cmd_audio).lower()
            print(f"Commander: '{user_cmd}'")
        except Exception:
            speak_humanlike_tars("Audio feed garbled... Repeat the directive, Commander.", trigger_threshold)
            continue

        # SELF-EDITING PROTOCOL WITH SPECIFIC APPROVAL
        if any(k in user_cmd for k in ["edit your code", "update your code", "modify your code"]):
            speak_humanlike_tars("Analyzing proposed updates... Stand by, Commander.", trigger_threshold)
            summary, new_code = generate_code_update(user_cmd)

            if new_code:
                print("\n" + "="*60)
                print(" [PROPOSED CODE MODIFICATION SUMMARY]")
                print(f" -> {summary}")
                print("="*60 + "\n")

                send_bt_cmd(f"DISP:Edit Req:|{summary[:25]}")

                approval_prompt = f"I plan to edit the code to {summary}. Do you authorize me to edit this part of my code?"
                speak_humanlike_tars(approval_prompt, trigger_threshold)

                play_instant_sound("audio/listening.mp3")
                auth_audio = listen_mic(trigger_threshold * 0.5, max_seconds=7, pause_limit=1.5)

                if auth_audio:
                    try:
                        auth_text = recognizer.recognize_google(auth_audio).lower()
                        print(f"Authorization response: '{auth_text}'")
                        if any(k in auth_text for k in ["authorize", "override", "yes", "confirm", "proceed", "edit", "allow", "do it"]):
                            speak_humanlike_tars("Authorization confirmed. Updating code and rebooting core.", trigger_threshold)
                            shutil.copy(__file__, f"tars_backup_{int(time.time())}.py")
                            with open(__file__, "w", encoding="utf-8") as f:
                                f.write(new_code)
                            time.sleep(1.5)
                            os._exit(0)
                        else:
                            speak_humanlike_tars("Authorization denied. Aborting code edit.", trigger_threshold)
                    except Exception:
                        speak_humanlike_tars("Voice approval ambiguous. Aborting update.", trigger_threshold)
            else:
                speak_humanlike_tars("Could not synthesize valid code modifications... Aborting.", trigger_threshold)
            continue

        # MOTION PARSING
        direction, count = parse_motion_command(user_cmd)
        if direction:
            bt_cmd = f"{direction}_{count}"
            send_bt_cmd(bt_cmd)
            quips = [
                f"Advancing {count} steps... Try to keep up, Commander.",
                f"Executing {count} step movement... Watch my balance.",
                f"Pivoting {count} paces... Stand clear."
            ]
            speak_humanlike_tars(random.choice(quips), trigger_threshold)
            followup_active = True
            continue

        # CONVERSATIONAL LLM
        messages = [{'role': 'system', 'content': get_system_prompt()}]
        messages.extend(chat_messages[-4:])
        messages.append({'role': 'user', 'content': user_cmd})

        send_bt_cmd("DISP:Thinking...")
        response = ollama.chat(model='tars', messages=messages)
        ai_reply = response['message']['content']

        if ai_reply:
            chat_messages.append({'role': 'user', 'content': user_cmd})
            chat_messages.append({'role': 'assistant', 'content': ai_reply})
            interrupted = speak_humanlike_tars(ai_reply, trigger_threshold)
            if not interrupted:
                followup_active = True

    except Exception as e:
        print(f"[Main Loop Exception]: {e}")
'@ | Out-File -Encoding utf8 tars_master.py
