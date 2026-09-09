"""faster-whisper 설치/동작 확인용 스크립트.
base 모델로 짧은 mp3 파일을 텍스트로 변환해본다.
"""
from faster_whisper import WhisperModel
import time

AUDIO_PATH = "test_sample.mp3"

print("Loading base model (CPU, int8)...")
t0 = time.time()
model = WhisperModel("base", device="cpu", compute_type="int8")
print(f"Model loaded in {time.time() - t0:.1f}s")

print(f"Transcribing {AUDIO_PATH} ...")
t0 = time.time()
segments, info = model.transcribe(AUDIO_PATH, beam_size=5)

print(f"Detected language: {info.language} (probability {info.language_probability:.2f})")
for segment in segments:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")

print(f"Transcription finished in {time.time() - t0:.1f}s")
