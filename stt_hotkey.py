"""
PC voice dictation to Memoria Server using Whisper (offline).

Usage:
1) Copy .env.example to .env and fill AUTH_TOKEN, SERVER_URL, WHISPER_MODEL.
2) pip install -r requirements.txt
3) Run: python stt_hotkey.py
4) Press Enter to START recording, press Enter again to STOP.
   It will transcribe and POST to /capture (server decides memory vs reminder).
"""
import os
import queue
import sys
import threading
import time
from dotenv import load_dotenv
import requests
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

load_dotenv()
SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8000").rstrip("/")
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "")
MODEL_SIZE = os.getenv("WHISPER_MODEL", "small.en")

def post_capture(text: str):
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["x-auth-token"] = AUTH_TOKEN
    resp = requests.post(f"{SERVER_URL}/capture", json={"text": text}, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json()

def record_wav(filename: str, samplerate=16000, channels=1):
    q = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        q.put(bytes(indata))

    print("Recording... Press Enter to stop.")
    with sf.SoundFile(filename, mode='x', samplerate=samplerate, channels=channels, subtype='PCM_16') as file:
        with sd.RawInputStream(samplerate=samplerate, channels=channels, dtype='int16', callback=callback):
            while True:
                if stop_event.is_set():
                    break
                file.write(q.get())

def transcribe(file_path: str, model: WhisperModel):
    segments, info = model.transcribe(file_path, vad_filter=True, vad_parameters=dict(min_silence_duration_ms=300))
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return text

if __name__ == "__main__":
    print(f"Loading Whisper model: {MODEL_SIZE} (first run may take a minute)...")
    model = WhisperModel(MODEL_SIZE, device="auto", compute_type="auto")

    while True:
        try:
            input("Press Enter to START recording, then Enter again to STOP...")
            stop_event = threading.Event()
            fname = f"memoria_{int(time.time())}.wav"
            t = threading.Thread(target=record_wav, args=(fname,), daemon=True)
            t.start()
            input()  # wait for Enter to stop
            stop_event.set()
            t.join()
            print("Transcribing...")
            text = transcribe(fname, model)
            os.remove(fname)
            if not text:
                print("No speech detected.")
                continue
            print(f"TEXT: {text}")
            resp = post_capture(text)
            print("Posted:", resp)
        except KeyboardInterrupt:
            print("\nBye.")
            break
        except Exception as e:
            print("Error:", e)
            time.sleep(1)