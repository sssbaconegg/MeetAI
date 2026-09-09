# MeetAI

회의 녹음(mp3/wav)을 올리면 **완전히 로컬에서** STT로 텍스트를 뽑고, 로컬 LLM으로
구조화된 회의록을 만들어주는 FastAPI 서비스입니다. 외부 API 없이
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) + [Ollama](https://ollama.com/)만으로 동작합니다.

```
오디오 업로드 → faster-whisper STT → (긴 녹취록은 청크 분할) → Ollama LLM 요약 → 구조화된 회의록 JSON
```

---

## 빠른 시작

**준비물**: Python 3.11+, [Ollama](https://ollama.com/)

```bash
# 1. 요약용 모델 pull
ollama pull qwen2.5:3b-instruct

# 2. 가상환경 + 의존성 설치
python -m venv .venv
.venv\Scripts\activate        # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt

# 3. 서버 실행
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`web/index.html`을 브라우저로 열거나, API를 직접 호출하면 됩니다.

## 사용법

```bash
# 오디오 업로드 -> job_id 발급
curl -X POST http://127.0.0.1:8000/upload-audio \
  -F "audio_file=@meeting.mp3;type=audio/mpeg" \
  -F "memo=오늘 논의할 안건 메모"
# -> {"job_id": "...", "status": "processing", "status_url": "/jobs/..."}

# 처리 결과 조회 (완료될 때까지 폴링)
curl http://127.0.0.1:8000/jobs/<job_id>
```

결과 예시:

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

- **완전 로컬 처리** — 오디오/녹취록이 외부로 나가지 않음
- **긴 회의도 처리** — 녹취록이 길면 자동으로 청크로 나눠 요약 후 통합
- **정확한 담당업무 추출** — 담당자/업무는 LLM이 매번 재구성하지 않고 그대로 병합해 보여줌
- **믿을 수 있는 날짜** — 형식이 아닌 값은 채워 넣지 않고 `null`로 처리
- **처리 실패가 조용히 묻히지 않음** — 실패한 구간은 로그와 결과에 명시적으로 표시

동작 원리와 설계 이유는 [기술 원칙](#기술-원칙) 참고.

## 프로젝트 구조

```
app/
├── main.py                    FastAPI 앱 — POST /upload-audio(업로드+백그라운드 처리), GET /jobs/{job_id}(결과 조회)
├── config.py                  환경변수 기반 설정 (모델 크기, chunk 한도, timeout 등)
├── jobs.py                    작업 상태 저장/조회 (processing/completed/failed)
└── services/
    ├── transcription.py       faster-whisper STT — vad_filter로 무음 구간 제거, condition_on_previous_text=False로 환각(반복) 억제
    └── summarization.py       Ollama(LiteLLM) 기반 회의록 요약 — 청크 분할/병합, 담당업무 코드 레벨 병합, 날짜 검증, 파싱 실패 재시도
web/
├── index.html                 업로드 폼 + 결과 표시 페이지
├── script.js                  /upload-audio 호출, job 폴링, 결과 렌더링
└── style.css
requirements.txt              의존성 목록 (pip freeze 기반)
README.md
```

개발 중 만든 보조 스크립트(정식 앱 코드는 아님):

```
test_*.py            엔드투엔드/단위 검증용 스크립트 (요약 로직, 담당업무 병합 등)
trim_audio.py         테스트용 오디오를 특정 구간만 잘라내는 유틸 (ffmpeg 없이 PyAV 사용)
wav_to_mp3*.py        wav -> mp3 변환 유틸
streamlit_app.py      실험적으로 만들어본 Streamlit 대체 UI (web/이 기본 UI)
```

## 환경변수

전부 기본값이 있어 설정 없이도 동작합니다. 자세한 내용은 [`app/config.py`](app/config.py) 참고.

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

## 기술 원칙

- **LLM 호출은 전부 LiteLLM 경유** — 프로바이더 SDK를 직접 호출하지 않습니다. `OLLAMA_MODEL`만
  바꾸면 다른 Ollama 모델로, `app/services/summarization.py`의 `ollama_chat/` prefix를 바꾸면
  다른 프로바이더로도 전환할 수 있는 구조입니다.
- **정확도가 중요한 항목은 LLM에게 재해석을 맡기지 않습니다** — 담당업무(담당자/업무 매칭)는
  청크별로 LLM이 추출한 리스트를 코드가 그대로 병합(중복만 제거)합니다. 전체 맥락이 필요한
  회의 주제·핵심내용·결정사항만 LLM이 통합하도록 역할을 분리했습니다.
- **검증 가능한 값은 LLM 출력을 그대로 믿지 않습니다** — `일시`/`다음회의`는 정규식으로 실제
  날짜·요일·시간 형식인지 검증한 뒤, 아니면 무조건 `null`로 강제합니다.
- **실패는 조용히 넘어가지 않습니다** — 청크 요약이 JSON 파싱에 실패하면 로그를 남기고 1회
  재시도하며, 그래도 실패하면 최종 결과의 `처리_경고` 필드로 사용자에게 드러냅니다.
- **결과는 항상 구조화된 JSON** — 자유 텍스트 채팅이 아니라, 정해진 스키마(회의 주제/일시/
  핵심내용/결정사항/담당업무/다음회의)로만 응답하도록 프롬프트와 후처리를 강제합니다.

## 알려진 한계

- CPU 환경에서는 긴 녹음(수십 분)의 STT + 요약에 시간이 꽤 걸립니다 (모델 크기·CPU 성능에 따라 수 분~수십 분).
- 로컬 LLM 특성상 드물게 Ollama 호출이 비정상적으로 오래 걸리는 경우가 있어, 요약 호출에 넉넉한 timeout과
  `keep_alive` 옵션을 적용해 모델이 매 호출마다 재로드되지 않도록 하고 있습니다.
- STT 정확도는 모델 크기에 크게 좌우됩니다. 담당자 이름처럼 정확도가 중요한 정보는 `base` 이상 모델을 권장합니다.
