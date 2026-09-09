import os

WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b-instruct")
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434")
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav"}
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "1024"))

# 이 글자 수를 넘는 녹취록은 청크로 나눠 부분 요약 후 통합한다 (LLM 컨텍스트 초과 방지).
SUMMARY_CHUNK_CHAR_LIMIT = int(os.getenv("SUMMARY_CHUNK_CHAR_LIMIT", "5000"))
