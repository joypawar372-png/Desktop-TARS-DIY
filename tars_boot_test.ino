import socket
import threading
import numpy as np
import whisper
import ollama
import pyttsx3
import wave
import tempfile
import os
import time
import random
import sounddevice as sd
from scipy.io import wavfile

# --- Configurations ---
HOST_PORT = 5000
LLM_MODEL = "llama3.2:3b"
SAMPLE_RATE = 16000
VAD_THRESHOLD = 0.02     # Microphone amplitude threshold (0.0 to 1.0)
SILENCE_TIMEOUT = 1.5    # Seconds of silence before processing speech

# --- Physical Servo Safety Limits ---
SERVO_CENTER = 90        
WAKE_TILT_L = 93         
WAKE_TILT_R = 87         
SWAY_MIN = 88            
SWAY_MAX = 92            

print("Loading Local OpenAI Whisper Model (base)...")
whisper_model = whisper.load_model("base")
print("Whisper ready!")

esp_conn = None

def send_packet(type_byte, payload):
    global esp_conn
    if esp_conn is None:
        return
    header = bytearray([0xAA, 0xBB, type_byte])
    length = len(payload)
    header.append((length >> 8) & 0xFF)
    header.append(length & 0xFF)
    try:
        esp_conn.sendall(header + payload)
    except OSError:
        print("[NET] Connection to ESP32 lost.")
        esp_conn = None

def resample_audio(data, orig_sr, target_sr=16000):
    if orig_sr == target_sr:
        return data
    num_samples = int(len(data) * target_sr / orig_sr)
    return np.interp(
        np.linspace(0, len(data), num_samples),
        np.arange(len(data)),
        data
    ).astype(np.int16)

def process_and_respond(audio_data):
    send_packet(0x03, b"THINKING...")
    
    temp_wav_path = tempfile.mktemp(suffix=".wav")
    wavfile.write(temp_wav_path, SAMPLE_RATE, audio_data)

    try:
        print("\n[STT] Transcribing computer microphone input...")
        result = whisper_model.transcribe(temp_wav_path)
        user_text = result["text"].strip()
        print(f"User: '{user_text}'")

        if not user_text:
            send_packet(0x03, b"IDLE")
            return

        clean_text = user_text.lower().translate(str.maketrans('', '', '.,!?')).strip()
        wake_words = ["hey tars", "hi tars", "tars", "hello tars"]
        is_wake_word_only = clean_text in wake_words
        tars_text = ""

        if is_wake_word_only:
            tars_text = random.choice(["Yes?", "Hmm?", "Listening.", "Go ahead."])
            send_packet(0x02, bytes([WAKE_TILT_L, WAKE_TILT_R])) 
        else:
            query_text = user_text
            for wake in wake_words:
                if clean_text.startswith(wake):
                    query_text = user_text[len(wake):].strip().lstrip(",.?! ")
                    break

            print(f"[LLM] Querying {LLM_MODEL}...")
            system_prompt = "You are TARS from Interstellar. Keep answers brief and dry (max 2 sentences)."
            response = ollama.chat(model=LLM_MODEL, messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': query_text if query_text else user_text}
            ])
            tars_text = response['message']['content']

        print(f"TARS: {tars_text}")

        # TTS Generation
        temp_out_wav = tempfile.mktemp(suffix=".wav")
        engine = pyttsx3.init()
        engine.setProperty('rate', 145)
        engine.save_to_file(tars_text, temp_out_wav)
        engine.runAndWait()

        with wave.open(temp_out_wav, 'rb') as wf:
            params = wf.getparams()
            frames = wf.readframes(params.nframes)
            data = np.frombuffer(frames, dtype=np.int16)
            if params.nchannels == 2:
                data = data[0::2]//2 + data[1::2]//2
            data_resampled = resample_audio(data, params.framerate, 16000)
            pcm_bytes = data_resampled.tobytes()

        # Stream back down to ESP32 hardware
        send_packet(0x03, b"TALKING")
        chunk_size = 1024
        for i in range(0, len(pcm_bytes), chunk_size):
            chunk = pcm_bytes[i:i+chunk_size]
            send_packet(0x01, chunk)

            if not is_wake_word_only and (i // chunk_size) % 8 == 0:
                send_packet(0x02, bytes([random.randint(SWAY_MIN, SWAY_MAX), random.randint(SWAY_MIN, SWAY_MAX)]))
            time.sleep(0.028)

        send_packet(0x02, bytes([SERVO_CENTER, SERVO_CENTER]))
        send_packet(0x03, b"IDLE")

    except Exception as e:
        print(f"[ERROR] Logic fault: {e}")
        send_packet(0x02, bytes([SERVO_CENTER, SERVO_CENTER]))
        send_packet(0x03, b"IDLE")
    finally:
        if os.path.exists(temp_wav_path): os.remove(temp_wav_path)
        if os.path.exists(temp_out_wav): os.remove(temp_out_wav)

def mic_listener_loop():
    print("[MIC] PC Local Microphone Monitor Active.")
    audio_buffer = []
    is_recording = False
    silence_frames = 0
    
    # Calculate frames relative to timing
    block_size = 1024
    max_silence_frames = int((SILENCE_TIMEOUT * SAMPLE_RATE) / block_size)

    def callback(indata, frames, time_info, status):
        nonlocal audio_buffer, is_recording, silence_frames
        volume_norm = np.linalg.norm(indata) / np.sqrt(len(indata))
        
        if volume_norm > VAD_THRESHOLD:
            if not is_recording:
                print("[VAD] Listening via PC mic...")
                send_packet(0x03, b"LISTENING")
                is_recording = True
            audio_buffer.append(indata.copy())
            silence_frames = 0
        elif is_recording:
            audio_buffer.append(indata.copy())
            silence_frames += 1
            if silence_frames > max_silence_frames:
                print("[VAD] Processing speech entry...")
                is_recording = False
                recorded_audio = np.concatenate(audio_buffer, axis=0).flatten()
                audio_buffer.clear()
                threading.Thread(target=process_and_respond, args=(recorded_audio,)).start()

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=callback, blocksize=block_size):
        while True:
            time.sleep(0.1)

def main():
    global esp_conn
    threading.Thread(target=mic_listener_loop, daemon=True).start()
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', HOST_PORT))
    server.listen(1)
    print(f"TARS Brain listening for ESP32 hardware on port {HOST_PORT}...")
    
    while True:
        conn, addr = server.accept()
        print(f"TARS chassis connected from IP: {addr}")
        esp_conn = conn
        send_packet(0x03, b"IDLE")

if __name__ == "__main__":
    main()
