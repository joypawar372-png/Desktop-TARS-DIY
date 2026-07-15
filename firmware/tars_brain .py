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

# --- Configurations ---
HOST_PORT = 5000
VAD_THRESHOLD = 600      # Sound sensitivity. Higher = less sensitive.
SILENCE_TIMEOUT = 1.5    # How long to wait before deciding you finished talking (seconds)
LLM_MODEL = "llama3.2:3b" # The model you pulled via Ollama

# --- Initialize Engines ---
print("Loading Local OpenAI Whisper Model (base)...")
whisper_model = whisper.load_model("base")
print("Whisper ready!")

# Shared pipeline variables
raw_audio_buffer = bytearray()
is_recording = False
silence_counter = 0.0

def recv_all(sock, num_bytes):
    data = bytearray()
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

def send_packet(conn, type_byte, payload):
    header = bytearray([0xAA, 0xBB, type_byte])
    length = len(payload)
    header.append((length >> 8) & 0xFF)
    header.append(length & 0xFF)
    try:
        conn.sendall(header + payload)
    except OSError:
        pass

def resample_audio(data, orig_sr, target_sr=16000):
    if orig_sr == target_sr:
        return data
    num_samples = int(len(data) * target_sr / orig_sr)
    return np.interp(
        np.linspace(0, len(data), num_samples),
        np.arange(len(data)),
        data
    ).astype(np.int16)

def process_and_respond(conn, audio_bytes):
    send_packet(conn, 0x03, b"THINKING...")
    
    # Save incoming audio stream as a temporary standard WAV file
    temp_wav_path = ""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
        with wave.open(temp_wav.name, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2) # 16-bit
            wav_file.setframerate(16000) # 16kHz
            wav_file.writeframes(bytes(audio_bytes))
        temp_wav_path = temp_wav.name

    try:
        # 1. Speech-To-Text (Whisper)
        print("\n[STT] Transcribing speech...")
        result = whisper_model.transcribe(temp_wav_path)
        user_text = result["text"].strip()
        print(f"User: '{user_text}'")

        if not user_text:
            print("[STT] No words recognized.")
            send_packet(conn, 0x03, b"IDLE")
            return

        # --- WAKE WORD DETECTION & GESTURE LOGIC ---
        # Normalize the incoming string (lowercase, remove punctuation)
        clean_text = user_text.lower().translate(str.maketrans('', '', '.,!?')).strip()
        wake_words = ["hey tars", "hi tars", "tars", "hello tars"]

        is_wake_word_only = clean_text in wake_words
        tars_text = ""

        if is_wake_word_only:
            # INSTANT BYPASS PATH: Respond immediately without querying Ollama
            print("[WAKE] Standalone wake word recognized! Triggering quick physical perk up.")
            tars_text = random.choice(["Yes?", "Hmm?", "Listening.", "Go ahead.", "I'm active."])
            
            # Physical Reaction: Tilt the body forward/left slightly to "look" up
            # Left Leg: 100 degrees, Right Leg: 80 degrees (subtle, non-destructive offset)
            send_packet(conn, 0x02, bytes([100, 80])) 
            
        else:
            # Query path: If they said "Hey TARS, what time is it?", clean the prefix
            query_text = user_text
            for wake in wake_words:
                if clean_text.startswith(wake):
                    query_text = user_text[len(wake):].strip().lstrip(",.?! ")
                    break
            
            if not query_text:
                query_text = user_text # Fallback

            # 2. Query Local Ollama LLM
            print(f"[LLM] Querying {LLM_MODEL} with: '{query_text}'...")
            system_prompt = (
                "You are TARS, the witty, slightly sarcastic robot from Interstellar. "
                "Maintain a humor setting of 75% and honesty setting of 90%. "
                "Keep answers brief, smart, dry, and direct (max 2 sentences)."
            )
            response = ollama.chat(model=LLM_MODEL, messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': query_text}
            ])
            tars_text = response['message']['content']

        print(f"TARS: {tars_text}")

        # 3. Text-to-Speech (Local offline TTS)
        print("[TTS] Synthesizing speech...")
        temp_out_wav = tempfile.mktemp(suffix=".wav")
        engine = pyttsx3.init()
        engine.setProperty('rate', 145) # Classic dry, mechanical pace
        engine.save_to_file(tars_text, temp_out_wav)
        engine.runAndWait()

        # Load synthesized WAV and format for ESP32
        with wave.open(temp_out_wav, 'rb') as wf:
            params = wf.getparams()
            frames = wf.readframes(params.nframes)
            
            if params.sampwidth == 2:
                data = np.frombuffer(frames, dtype=np.int16)
            elif params.sampwidth == 1:
                data = (np.frombuffer(frames, dtype=np.uint8).astype(np.int16) - 128) * 256
                
            if params.nchannels == 2:
                data = data[0::2]//2 + data[1::2]//2
                data = data.astype(np.int16)

            # Standardize output to matches our ESP32 16kHz setting
            data_resampled = resample_audio(data, params.framerate, 16000)
            pcm_bytes = data_resampled.tobytes()

        # 4. Stream Audio Chunks back to TARS
        print("[STREAM] Transmitting voice and animating...")
        send_packet(conn, 0x03, b"TALKING")
        
        chunk_size = 1024 # ~32ms of audio
        for i in range(0, len(pcm_bytes), chunk_size):
            chunk = pcm_bytes[i:i+chunk_size]
            send_packet(conn, 0x01, chunk)

            # If it wasn't a wake-word-only event, do dynamic sways while talking
            if not is_wake_word_only and (i // chunk_size) % 8 == 0:
                left_angle = random.randint(84, 96)
                right_angle = random.randint(84, 96)
                send_packet(conn, 0x02, bytes([left_angle, right_angle]))

            # Throttle stream speed to respect the ESP32's hardware buffer
            time.sleep(0.028)

        # 5. Return to Centered Home Position
        print("[IDLE] Resettling chassis.")
        send_packet(conn, 0x02, bytes([90, 90])) # Return both legs to flush alignment
        send_packet(conn, 0x03, b"IDLE")
        print("[DONE] Cycle complete.\n")

    except Exception as e:
        print(f"[ERROR] Pipeline breakdown: {e}")
        send_packet(conn, 0x02, bytes([90, 90]))
        send_packet(conn, 0x03, b"ERROR")
        time.sleep(1.5)
        send_packet(conn, 0x03, b"IDLE")
    finally:
        # File System Cleanup
        if os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)
        if os.path.exists(temp_out_wav):
            os.remove(temp_out_wav)

def client_handler(conn, addr):
    global raw_audio_buffer, is_recording, silence_counter
    print(f"TARS connected from {addr}!")
    send_packet(conn, 0x03, b"IDLE")

    while True:
        try:
            magic = conn.recv(2)
            if not magic:
                break
            if magic != b'\xAA\xBB':
                continue # Realign stream alignment

            header = recv_all(conn, 3)
            if not header:
                break

            packet_type = header[0]
            length = (header[1] << 8) | header[2]

            payload = recv_all(conn, length)
            if not payload:
                break

            # Process inbound raw audio packets
            if packet_type == 0x01:
                audio_data = np.frombuffer(payload, dtype=np.int16)
                amplitude = np.abs(audio_data).mean() if len(audio_data) > 0 else 0

                if amplitude > VAD_THRESHOLD:
                    if not is_recording:
                        print("[VAD] Voice Activity Detected...")
                        is_recording = True
                        send_packet(conn, 0x03, b"LISTENING")
                    raw_audio_buffer.extend(payload)
                    silence_counter = 0.0
                else:
                    if is_recording:
                        raw_audio_buffer.extend(payload)
                        silence_counter += len(payload) / 32000.0 # 32,000 bytes/sec bandwidth
                        
                        if silence_counter >= SILENCE_TIMEOUT:
                            print("[VAD] Speech ended. Analyzing voice...")
                            is_recording = False
                            # Spawn off-thread processing so socket receiver remains non-blocking
                            threading.Thread(target=process_and_respond, args=(conn, list(raw_audio_buffer))).start()
                            raw_audio_buffer.clear()
        except ConnectionResetError:
            break
    print(f"TARS disconnected.")
    conn.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', HOST_PORT))
    server.listen(1)
    print(f"TARS Brain listening on port {HOST_PORT}...")
    
    while True:
        conn, addr = server.accept()
        threading.Thread(target=client_handler, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
