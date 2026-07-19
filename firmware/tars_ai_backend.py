import os
import time
import queue
import random
import threading
import numpy as np
import requests
import sounddevice as sd
import scipy.io.wavfile as wavfile
import whisper
import ollama
import pyttsx3

# --- Configuration Profiles ---
ESP32_IP = "192.168.1.XX"  # <--- Change to your TARS ESP32 Local IP address
LLM_MODEL = "llama3.2:3b"   # Local Ollama model execution engine
SAMPLE_RATE = 16000         # Whisper optimal performance audio rate
VAD_THRESHOLD = 0.03        # Mic sensitivity threshold for voice detection
SILENCE_DURATION = 1.5      # Seconds of silence before concluding speech chunk

# --- Physical Motion Presets (Mapped to ESP32 Web Endpoints) ---
ANGLE_CENTER = 90
ANGLE_LEAN_L = 94
ANGLE_LEAN_R = 86
SWAY_MIN = 88
SWAY_MAX = 92

# --- Core Subsystem Initializations ---
print("[INIT] Loading OpenAI Whisper model ('base') locally...")
stt_model = whisper.load_model("base")

print("[INIT] Initializing Text-to-Speech engine...")
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 150)  # Slightly slower, distinct mechanical cadence

audio_queue = queue.Queue()
motion_loop_active = False

# --- Network Command Dispatcher ---
def transmit_motion(left_angle, right_angle):
    """Sends background HTTP requests to the ESP32 phone controller server."""
    url = f"http://{ESP32_IP}/move?left={left_angle}&right={right_angle}"
    try:
        # Low timeout ensures network lag doesn't block the main thread
        requests.get(url, timeout=0.5)
    except requests.exceptions.RequestException:
        pass # Silently drop connection misses to keep loop spinning smoothly

def speech_animation_worker():
    """Generates continuous minor leg sways while TARS is talking."""
    global motion_loop_active
    while motion_loop_active:
        l_sway = random.randint(SWAY_MIN, SWAY_MAX)
        r_sway = random.randint(SWAY_MIN, SWAY_MAX)
        transmit_motion(l_sway, r_sway)
        time.sleep(0.25)
    # Reset to baseline upright stance upon completion
    transmit_motion(ANGLE_CENTER, ANGLE_CENTER)

# --- Primary AI Processing Pipeline ---
def execute_ai_pipeline(audio_frame_data):
    global motion_loop_active
    
    # 1. Save temporary raw audio data for transcription
    temp_filename = "tars_input.wav"
    wavfile.write(temp_filename, SAMPLE_RATE, audio_frame_data)
    
    print("\n[STT] Transcribing voice block...")
    try:
        result = stt_model.transcribe(temp_filename, fp16=False)
        user_prompt = result["text"].strip()
        print(f"User: {user_prompt}")
        
        if not user_prompt:
            print("[STT] Empty phrase detected. Re-entering listen loop.")
            return

        # 2. Query Local LLM via Ollama API
        print(f"[LLM] Processing text through {LLM_MODEL}...")
        system_instructions = (
            "You are TARS from Interstellar. Maintain a dry, honest, slightly sarcastic, "
            "and highly military personality. Keep your answers capped at a max of 2 short sentences."
        )
        
        response = ollama.chat(model=LLM_MODEL, messages=[
            {'role': 'system', 'content': system_instructions},
            {'role': 'user', 'content': user_prompt}
        ])
        tars_reply = response['message']['content']
        print(f"TARS: {tars_reply}")

        # 3. Synchronized Physical Physical Execution & Audio Output
        print("[ROBOT] Initiating motor synchronization sequence...")
        
        # Safe forward lean step to simulate active interaction engagement
        transmit_motion(ANGLE_LEAN_L, ANGLE_LEAN_R)
        time.sleep(0.2)

        # Fire off the asynchronous speech animation thread
        motion_loop_active = True
        anim_thread = threading.Thread(target=speech_animation_worker)
        anim_thread.start()

        # Vocalize output through host machine audio driver layers
        tts_engine.say(tars_reply)
        tts_engine.runAndWait()

        # Terminate speech animation routine cleanly
        motion_loop_active = False
        anim_thread.join()

    except Exception as e:
        print(f"[ERROR] Pipeline fault occurred: {e}")
        transmit_motion(ANGLE_CENTER, ANGLE_CENTER)
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

# --- Background Continuous Microphone Monitor ---
def audio_capture_callback(indata, frames, time_info, status):
    """Pushes audio frames into processing queue synchronously."""
    audio_queue.put(indata.copy())

def main_listen_loop():
    print("\n[SYSTEM] TARS Local AI Engine Fully Operational.")
    print("-> Speak clearly toward your PC's microphone assembly.")
    
    recording_buffer = []
    voice_detected = False
    silent_blocks_limit = int((SILENCE_DURATION * SAMPLE_RATE) / 1024)
    silent_block_counter = 0

    # Start audio input listening stream via sounddevice framework
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=audio_capture_callback, blocksize=1024):
        while True:
            try:
                block = audio_queue.get(timeout=0.1)
                # Calculate root-mean-square amplitude to catch speech activity
                volume_norm = np.linalg.norm(block) / np.sqrt(len(block))

                if volume_norm > VAD_THRESHOLD:
                    if not voice_detected:
                        print("\n[VAD] Voice capture triggered...")
                        voice_detected = True
                    recording_buffer.append(block)
                    silent_block_counter = 0
                elif voice_detected:
                    recording_buffer.append(block)
                    silent_block_counter += 1
                    
                    # Conclude sampling routine when silence timeout limit hits
                    if silent_block_counter > silent_blocks_limit:
                        print("[VAD] Finished tracking speech pattern.")
                        complete_audio = np.concatenate(recording_buffer, axis=0).flatten()
                        
                        # Execute heavy pipeline processing on an isolated thread
                        pipeline_thread = threading.Thread(target=execute_ai_pipeline, args=(complete_audio,))
                        pipeline_thread.start()
                        
                        # Wipe cache clean and reset flags for next loop sequence
                        recording_buffer.clear()
                        voice_detected = False
                        silent_block_counter = 0
            except queue.Empty:
                continue

if __name__ == "__main__":
    main_listen_loop()
