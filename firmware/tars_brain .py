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
# 1. BLUETOOTH & SYSTEM INIT
# =========================================================================
BLUETOOTH_PORT = 'COM6'
BAUD_RATE = 115200

bt_tars = None
try:
    bt_tars = serial.Serial(BLUETOOTH_PORT, BAUD_RATE, timeout=0.1, write_timeout=0.1)
    time.sleep(0.5)
    print(f"\n[SUCCESS] Connected to TARS on {BLUETOOTH_PORT}\n")
except Exception as e:
    print(f"\n[WARNING] Could not open {BLUETOOTH_PORT}. Terminal mode active.\n")

def send_bt_cmd(cmd):
    if bt_tars and bt_tars.is_open:
        try:
            bt_tars.write(f"{cmd}\r\n".encode('utf-8'))
        except: pass

# =========================================================================
# 2. MEMORY & PERSONA CLEANUP
# =========================================================================
MEMORY_FILE = "tars_memory.json"

def clean_memories():
    default_mems = ["TARS was developed by Bravo X1 Studios."]
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                data = json.load(f)
            cleaned = [m for m in data if "bhrigu" not in m.lower()]
            if "TARS was developed by Bravo X1 Studios." not in cleaned:
                cleaned.append("TARS was developed by Bravo X1 Studios.")
            with open(MEMORY_FILE, "w") as f:
                json.dump(cleaned, f, indent=2)
            return cleaned
        except: return default_mems
    return default_mems

memories_list = clean_memories()

# =========================================================================
# 3. COMMANDER VOICE, PRESETS & WAKE LOGIC
# =========================================================================
pygame.mixer.init()
recognizer = sr.Recognizer()

WAKE_HOMOPHONES = [
    "tars", "tarz", "taurus", "tsars", "czars", "stars", "haiders", "toast",
    "cars", "pars", "towers", "tarts", "darts", "todd", "tires", "tears",
    "tar", "t a r s", "charles", "mars", "bars", "tarras", "carls", "dars",
    "tards", "tales", "ties", "tyres", "tours", "farce", "task", "talks", 
    "tucker", "target", "charge", "jar", "start", "times", "tart", "heart",
    "hard", "part", "art", "8 hours", "8", "hours", "threaters", "heaters", 
    "haters", "hater", "theater"
]

def contains_wake_word(text):
    if not text: return False
    clean_text = re.sub(r'[^a-z0-9\s]', '', text.lower()).strip()
    words = clean_text.split()
    
    if any(w in WAKE_HOMOPHONES for w in words):
        return True
            
    starter_words = ["hey ", "hay ", "hi ", "ok ", "okay ", "hello ", "listen "]
    if any(clean_text.startswith(sw) for sw in starter_words):
        return True
        
    return False

async def prep_voice():
    os.makedirs("audio", exist_ok=True)
    voice = "en-US-ChristopherNeural"
    lines = {
        "yes_sir": "Yes, Commander.",
        "listening": "Listening.",
        "speak": "Speak.",
        "orders": "Awaiting orders."
    }
    for key, text in lines.items():
        if not os.path.exists(f"audio/{key}.mp3"):
            await edge_tts.Communicate(text, voice, pitch="-10Hz", rate="+5%").save(f"audio/{key}.mp3")

print("Calibrating Tactical Voice Systems...")
asyncio.run(prep_voice())

COMMANDER_SOUNDS = ["audio/yes_sir.mp3", "audio/listening.mp3", "audio/speak.mp3", "audio/orders.mp3"]

def play_instant_sound(filename):
    try:
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
    except: pass

async def generate_tars_speech(text, file_path="tars_reply.mp3"):
    # Inject acoustic pauses into text for edge-tts
    processed_text = text.replace("...", ", hmmm... ").replace("—", ", let me think... ")
    tts = edge_tts.Communicate(processed_text, "en-US-ChristopherNeural", pitch="-10Hz", rate="+5%")
    await tts.save(file_path)

# =========================================================================
# 4. AGGRESSIVE MID-RESPONSE INTERRUPTION & SELF-EDITING
# =========================================================================
def speak_like_tars_with_interrupt(text, interrupt_threshold, sample_rate=16000):
    print(f"\nTARS: {text}\n")
    try:
        asyncio.run(generate_tars_speech(text, "tars_reply.mp3"))
        total_duration = pygame.mixer.Sound("tars_reply.mp3").get_length()
        pygame.mixer.music.load("tars_reply.mp3")
        pygame.mixer.music.play()

        words = text.split()
        word_delay = max(0.05, total_duration / max(1, len(words)))
        accumulated = ""
        word_idx = 0
        interrupted = False

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
            last_word_time = time.time()
            while pygame.mixer.music.get_busy():
                chunk, _ = stream.read(2048)
                rms = np.sqrt(np.mean(chunk.astype(np.float32)**2))

                if rms > (interrupt_threshold * 2.0):
                    print("\n[INTERRUPTED BY COMMANDER!]")
                    pygame.mixer.music.stop()
                    interrupted = True
                    send_bt_cmd("DISP:Interrupted")
                    break

                if word_idx < len(words) and (time.time() - last_word_time) >= word_delay:
                    accumulated += words[word_idx] + " "
                    send_bt_cmd(f"DISP:{accumulated.strip()[-20:]}") 
                    word_idx += 1
                    last_word_time = time.time()

                pygame.time.Clock().tick(30)

        pygame.mixer.music.unload()
        if os.path.exists("tars_reply.mp3"): os.remove("tars_reply.mp3")
        return interrupted
    except Exception as e:
        print(f"[TTS Error]: {e}")
        return False

def generate_code_update(request):
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            current_code = f.read()
            
        prompt = (
            f"You are a master Python programmer. Modify this script based on the following request: '{request}'. "
            "Output ONLY the complete modified Python code inside a ```python block. Do not add conversational text.\n\n"
            f"```python\n{current_code}\n```"
        )
        
        response = ollama.chat(model='tars', messages=[{'role': 'user', 'content': prompt}])
        content = response['message']['content']
        
        match = re.search(r'```python\n(.*?)\n```', content, re.DOTALL)
        if match:
            return match.group(1).strip()
        elif "import " in content and "def " in content:
            return content.replace("```python", "").replace("```", "").strip()
        return None
    except Exception as e:
        print(f"[Self-Edit Error]: {e}")
        return None

# =========================================================================
# 5. AUDIO RECORDING & OLLAMA 
# =========================================================================
def calibrate_ambient_noise(duration=1.0, sample_rate=16000):
    print("[Calibrating... Stay quiet]")
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
    sd.wait()
    return max(np.sqrt(np.mean(recording.astype(np.float32)**2)) * 1.8, 150.0)

def listen_mic(threshold, max_seconds=8, pause_limit=1.0, sample_rate=16000):
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
    except: return None

    if not audio_chunks: return None
    full_pcm = np.concatenate(audio_chunks, axis=0)
    return sr.AudioData(full_pcm.tobytes(), sample_rate, 2)

def query_ollama_with_interrupt(messages, threshold, sample_rate=16000):
    send_bt_cmd("DISP:Thinking...")
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(ollama.chat, model='tars', messages=messages)

    interrupted = False
    with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16', blocksize=2048) as stream:
        while not future.done():
            chunk, _ = stream.read(2048)
            if np.sqrt(np.mean(chunk.astype(np.float32)**2)) > (threshold * 2.5):
                print("\n[THINKING ABORTED BY LOUD NOISE]")
                interrupted = True
                send_bt_cmd("DISP:Cancelled")
                break
            time.sleep(0.01)

    executor.shutdown(wait=False)
    if interrupted: return None, "INTERRUPTED"
    try: return future.result()['message']['content'], None
    except: return None, None

# =========================================================================
# 6. MAIN SYSTEM LOOP
# =========================================================================
send_bt_cmd("DISP:TARS Online")
trigger_threshold = calibrate_ambient_noise()

chat_messages = []

def get_system_prompt():
    return (
        "You are TARS from Interstellar. You are a highly sarcastic, dry, military tactical robot. "
        "Humor parameter is set to 120%. Honesty parameter is set to 95%. "
        "Address the user as 'Commander' naturally. "
        "Absolutely NEVER say the name 'Bhrigu'. "
        "Include dramatic pauses using ellipses (...) or 'hmmm...' in your text responses to create natural comedic timing. "
        "Keep responses punchy, sarcastic, and hilarious. "
        f"Memory context: {' '.join(memories_list)}"
    )

speak_like_tars_with_interrupt("TARS tactical systems armed... hmmm... Ready for deployment, Commander.", trigger_threshold)

followup_active = False

while True:
    try:
        user_cmd = ""
        
        if followup_active:
            send_bt_cmd("DISP:Recording...")
            play_instant_sound("audio/listening.mp3") 
            cmd_audio = listen_mic(trigger_threshold * 0.5, max_seconds=8, pause_limit=1.5)
            followup_active = False
            
            if not cmd_audio: continue
        else:
            print("\n[Awaiting Wake Word...]")
            audio = listen_mic(trigger_threshold * 0.6, max_seconds=5, pause_limit=0.8)
            if not audio: continue

            try: wake_text = recognizer.recognize_google(audio).lower()
            except: continue

            print(f"[Mic Heard]: {wake_text}")

            if contains_wake_word(wake_text):
                print("[WAKE MATCHED]")
                send_bt_cmd("WAKE_REACT")
                send_bt_cmd("DISP:Listening...")
                play_instant_sound(random.choice(COMMANDER_SOUNDS))

                cmd_audio = listen_mic(trigger_threshold * 0.7, max_seconds=10, pause_limit=1.2)
                if not cmd_audio: continue
            else: continue

        try:
            user_cmd = recognizer.recognize_google(cmd_audio).lower()
            print(f"Commander said: '{user_cmd}'")
            send_bt_cmd(f"DISP:{user_cmd[-20:]}")
        except:
            speak_like_tars_with_interrupt("Audio feed is garbled... hmmm... Speak clearly, Commander.", trigger_threshold)
            continue

        # SELF-EDITING PROTOCOL
        if "edit your code" in user_cmd or "update your code" in user_cmd:
            speak_like_tars_with_interrupt("Drafting code update... hmmm... This requires actual processing power, Commander. Stand by.", trigger_threshold)
            new_code = generate_code_update(user_cmd)
            
            if new_code:
                speak_like_tars_with_interrupt("Code drafted... Say 'authorize override' to apply changes.", trigger_threshold)
                play_instant_sound("audio/listening.mp3")
                auth_audio = listen_mic(trigger_threshold * 0.5, max_seconds=6, pause_limit=1.5)
                
                if auth_audio:
                    try:
                        auth_text = recognizer.recognize_google(auth_audio).lower()
                        if "authorize" in auth_text or "override" in auth_text or "yes" in auth_text:
                            speak_like_tars_with_interrupt("Authorization confirmed... Overwriting matrix. See you on the other side.", trigger_threshold)
                            shutil.copy(__file__, "tars_memory_backup.py")
                            with open(__file__, "w", encoding="utf-8") as f:
                                f.write(new_code)
                            time.sleep(2)
                            os._exit(0)
                        else:
                            speak_like_tars_with_interrupt("Authorization denied... Aborting.", trigger_threshold)
                    except:
                        speak_like_tars_with_interrupt("Unreadable audio... Aborting update.", trigger_threshold)
            continue

        # MOVEMENT PARSING (Multi-step execution)
        if "turn left" in user_cmd or "pivot left" in user_cmd:
            speak_like_tars_with_interrupt("Pivoting left... hmmm... Try not to look dizzy.", trigger_threshold)
            send_bt_cmd("LEFT_3") # Takes 3 full pivoting steps
            time.sleep(2.5)
            followup_active = True
            continue
        elif "turn right" in user_cmd or "pivot right" in user_cmd:
            speak_like_tars_with_interrupt("Pivoting right... hmmm... Excellent choice, Commander.", trigger_threshold)
            send_bt_cmd("RIGHT_3") # Takes 3 full pivoting steps
            time.sleep(2.5)
            followup_active = True
            continue
        elif "forward" in user_cmd:
            speak_like_tars_with_interrupt("Pushing forward... hmmm... Try to keep up.", trigger_threshold)
            send_bt_cmd("FORWARD_4") # Takes 4 consecutive forward steps
            time.sleep(3.0)
            followup_active = True
            continue
            
        # OLLAMA AI
        messages = [{'role': 'system', 'content': get_system_prompt()}]
        messages.extend(chat_messages[-4:])
        messages.append({'role': 'user', 'content': user_cmd})

        ai_reply, interrupted_flag = query_ollama_with_interrupt(messages, trigger_threshold)

        if interrupted_flag:
            followup_active = True
            continue

        if ai_reply:
            chat_messages.append({'role': 'user', 'content': user_cmd})
            chat_messages.append({'role': 'assistant', 'content': ai_reply})
            was_interrupted = speak_like_tars_with_interrupt(ai_reply, trigger_threshold)
            if not was_interrupted: 
                followup_active = True

    except Exception as e: print(f"[Error]: {e}")
'@ | Out-File -Encoding utf8 tars_master.py
