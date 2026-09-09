# stt-service

회의 녹음(mp3/wav)을 업로드하면 faster-whisper로 STT를 돌리고, 로컬 Ollama LLM으로
구조화된 회의록(주제/일시/핵심내용/결정사항/담당업무/다음회의)을 생성하는 FastAPI 서비스.

## 구성

- `app/main.py` — FastAPI 앱, `/upload-audio`(업로드+비동기 처리), `/jobs/{job_id}`(결과 조회)
- `app/services/transcription.py` — faster-whisper STT
- `app/services/summarization.py` — LiteLLM(Ollama) 기반 회의록 요약 (긴 녹취록은 청크로 나눠 처리)
- `web/` — 정적 프론트엔드 (업로드 폼 + 결과 표시)

## 준비물

- Python 3.11+ (venv 사용)
- [Ollama](https://ollama.com/) 설치 후 요약용 모델 pull
  ```bash
  ollama pull qwen2.5:3b-instruct
  ```

## 설치 및 실행

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

uvicorn app.main:app --host 127.0.0.1 --port 8000
```

브라우저에서 `web/index.html`을 열거나, `POST /upload-audio`로 오디오 파일과 메모를 보내면 됩니다.

## 환경변수 (선택)

`app/config.py` 참고. 전부 기본값이 있어 별도 설정 없이도 동작합니다.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `base` | faster-whisper 모델 크기 (tiny/base/small/...) |
| `WHISPER_DEVICE` | `cpu` | |
| `WHISPER_COMPUTE_TYPE` | `int8` | |
| `OLLAMA_MODEL` | `qwen2.5:3b-instruct` | |
| `OLLAMA_API_BASE` | `http://localhost:11434` | |
| `OLLAMA_NUM_CTX` | `4096` | |
| `SUMMARY_CHUNK_CHAR_LIMIT` | `5000` | 이보다 긴 녹취록은 청크로 나눠 요약 후 통합 |
| `MAX_UPLOAD_MB` | `1024` | |
