# MeetAI

회의 녹음(mp3/wav)을 올리면 **로컬에서** STT로 텍스트를 뽑고, 로컬 LLM으로 구조화된
회의록을 만들어주는 FastAPI 서비스입니다. 외부 API 없이 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) +
[Ollama](https://ollama.com/)만으로 동작합니다.

```
오디오 업로드 → faster-whisper STT → (긴 녹취록은 청크 분할) → Ollama LLM 요약 → 구조화된 회의록 JSON
```

## 결과 예시

```json
{
  "회의 주제": "...",
  "일시": "2027년 9월 16일",
  "핵심내용": ["...", "..."],
  "결정사항": ["...", "..."],
  "담당업무": [{"담당자": "김철수", "업무": "..."}],
  "다음회의": null
}
```

## 특징

- **완전 로컬 처리** — 오디오/녹취록이 외부로 나가지 않음 (STT: faster-whisper, 요약: 로컬 Ollama)
- **긴 회의도 처리** — 녹취록이 길면 자동으로 청크로 나눠 요약 후 통합 ([`SUMMARY_CHUNK_CHAR_LIMIT`](#환경변수))
- **담당업무는 코드가 병합** — 담당자/업무 매칭은 정확도가 중요하기 때문에, 청크별로 뽑은 담당업무 리스트를
  LLM이 다시 재구성하지 않고 코드에서 그대로 합쳐서(중복만 제거) 보여줍니다. 전체 맥락이 필요한
  회의 주제·핵심내용·결정사항만 LLM이 통합합니다.
- **날짜 검증** — `일시`/`다음회의`는 실제 날짜·요일·시간 형식일 때만 채우고, 아니면 `null`로 강제합니다.
- **청크 처리 실패 시 재시도 + 표시** — 청크 하나가 JSON 파싱에 실패하면 1회 재시도하고,
  그래도 실패하면 로그에 남기고 최종 결과에 `처리_경고` 필드로 표시합니다 (조용히 누락되지 않음).

## 준비물

- Python 3.11+
- [Ollama](https://ollama.com/) 설치 후 요약용 모델 pull
  ```bash
  ollama pull qwen2.5:3b-instruct
  ```

## 설치 및 실행

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`web/index.html`을 브라우저로 열거나, 아래처럼 직접 호출할 수 있습니다.

```bash
curl -X POST http://127.0.0.1:8000/upload-audio \
  -F "audio_file=@meeting.mp3;type=audio/mpeg" \
  -F "memo=오늘 논의할 안건 메모"
# -> {"job_id": "...", "status": "processing", "status_url": "/jobs/..."}

curl http://127.0.0.1:8000/jobs/<job_id>
```

## 구성

| 경로 | 역할 |
|---|---|
| `app/main.py` | FastAPI 앱. `POST /upload-audio`(업로드 + 백그라운드 처리), `GET /jobs/{job_id}`(결과 조회) |
| `app/services/transcription.py` | faster-whisper STT (`vad_filter`, `condition_on_previous_text=False`로 환각/반복 억제) |
| `app/services/summarization.py` | LiteLLM(Ollama) 기반 요약. 청크 분할·병합, 담당업무 코드 레벨 병합, 날짜 검증, 재시도 로직 |
| `web/` | 정적 프론트엔드 (업로드 폼 + 결과 표시) |

## 환경변수

전부 기본값이 있어 설정 없이도 동작합니다. `app/config.py` 참고.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `base` | faster-whisper 모델 크기 (tiny/base/small/medium/large). tiny는 빠르지만 담당자 등 고유명사 오인식이 늘어남 |
| `WHISPER_DEVICE` | `cpu` | |
| `WHISPER_COMPUTE_TYPE` | `int8` | |
| `OLLAMA_MODEL` | `qwen2.5:3b-instruct` | |
| `OLLAMA_API_BASE` | `http://localhost:11434` | |
| `OLLAMA_NUM_CTX` | `4096` | |
| `SUMMARY_CHUNK_CHAR_LIMIT` | `5000` | 이보다 긴 녹취록은 청크로 나눠 요약 후 통합 |
| `MAX_UPLOAD_MB` | `1024` | |

## 알려진 한계

- CPU 환경에서는 긴 녹음(수십 분)의 STT + 요약에 시간이 꽤 걸립니다(모델 크기·CPU 성능에 따라 수 분~수십 분).
- 로컬 LLM 특성상 드물게 Ollama 호출이 비정상적으로 오래 걸리는 경우가 있어, 요약 호출에 넉넉한 timeout과
  `keep_alive` 옵션을 적용해 모델이 매 호출마다 재로드되지 않도록 하고 있습니다.
- STT 정확도는 모델 크기에 크게 좌우됩니다. 담당자 이름처럼 정확도가 중요한 정보는 `base` 이상 모델을 권장합니다.
