import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class JobStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    status: JobStatus = JobStatus.PROCESSING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


_jobs: Dict[str, Job] = {}


def create_job() -> str:
    job_id = uuid.uuid4().hex
    _jobs[job_id] = Job()
    return job_id


def get_job(job_id: str) -> Optional[Job]:
    return _jobs.get(job_id)


def set_completed(job_id: str, result: Dict[str, Any]) -> None:
    _jobs[job_id] = Job(status=JobStatus.COMPLETED, result=result)


def set_failed(job_id: str, error: str) -> None:
    _jobs[job_id] = Job(status=JobStatus.FAILED, error=error)
