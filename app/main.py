import asyncio
import os
import tempfile
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_AUDIO_EXTENSIONS, MAX_UPLOAD_MB
from app.jobs import JobStatus, create_job, get_job, set_completed, set_failed
from app.services.summarization import summarize_meeting
from app.services.transcription import load_model, transcribe_audio

MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


app = FastAPI(title="Meeting STT + Summary API", lifespan=lifespan)

# 로컬 정적 프론트엔드(file:// 또는 다른 포트의 static 서버)에서
# 이 API를 바로 호출할 수 있도록 개발 편의상 모든 origin을 허용한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _save_upload_to_temp(file: UploadFile, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    size = 0
    with os.fdopen(fd, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                os.remove(path)
                raise HTTPException(
                    status_code=413,
                    detail=f"파일이 너무 큽니다 (최대 {MAX_UPLOAD_MB}MB).",
                )
            out.write(chunk)
    if size == 0:
        os.remove(path)
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    return path


def _process_job(
    job_id: str, audio_path: str, language: Optional[str], memo: Optional[str]
) -> None:
    try:
        t0 = time.time()
        transcript = transcribe_audio(audio_path, language=language)
        stt_seconds = time.time() - t0
        print(f"[TIMING] job={job_id} stt_seconds={stt_seconds:.1f} transcript_chars={len(transcript)}", flush=True)
        if not transcript:
            set_failed(job_id, "오디오에서 텍스트를 추출하지 못했습니다.")
            return

        t1 = time.time()
        summary = summarize_meeting(transcript, memo=memo)
        summary_seconds = time.time() - t1
        print(f"[TIMING] job={job_id} summary_seconds={summary_seconds:.1f} total_seconds={(time.time() - t0):.1f}", flush=True)
        set_completed(job_id, {"transcript": transcript, "memo": memo, "summary": summary})
    except Exception as exc:  # noqa: BLE001 - 백그라운드 작업 결과를 job 상태로 전달
        set_failed(job_id, str(exc))
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


async def _run_job(
    job_id: str, audio_path: str, language: Optional[str], memo: Optional[str]
) -> None:
    await asyncio.to_thread(_process_job, job_id, audio_path, language, memo)


@app.post("/upload-audio", status_code=202)
async def upload_audio(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    memo: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
):
    ext = os.path.splitext(audio_file.filename or "")[1].lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다: {ext or '(확장자 없음)'} "
            f"(허용: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))})",
        )

    audio_path = await _save_upload_to_temp(audio_file, ext)

    job_id = create_job()
    background_tasks.add_task(_run_job, job_id, audio_path, language, memo)

    return {"job_id": job_id, "status": JobStatus.PROCESSING, "status_url": f"/jobs/{job_id}"}


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 job_id입니다.")

    if job.status == JobStatus.PROCESSING:
        return {"status": job.status}
    if job.status == JobStatus.FAILED:
        return {"status": job.status, "error": job.error}
    return {"status": job.status, **job.result}
