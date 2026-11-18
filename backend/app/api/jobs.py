from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status

from ..schemas.job import JobListSchema, JobSchema, JobStepSchema, JobSubmission
from ..services.job_service import JobQueueUnavailable


router = APIRouter(prefix="/api/jobs", tags=["jobs"])
MAX_JCL_BYTES = 1_000_000


def _submit(content: str, request: Request) -> JobSchema:
    try:
        job = request.app.state.job_service.submit(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except JobQueueUnavailable as exc:
        raise HTTPException(status_code=503, detail="The job queue is unavailable.") from exc
    return JobSchema.model_validate(job)


@router.post("", response_model=JobSchema, status_code=status.HTTP_202_ACCEPTED)
def submit_json_job(submission: JobSubmission, request: Request) -> JobSchema:
    return _submit(submission.content, request)


@router.post("/upload", response_model=JobSchema, status_code=status.HTTP_202_ACCEPTED)
async def submit_file_job(request: Request, file: UploadFile = File(...)) -> JobSchema:
    if file.filename and Path(file.filename).suffix.lower() not in {".jcl", ".txt"}:
        raise HTTPException(status_code=415, detail="Upload a .jcl or .txt file.")
    content_bytes = await file.read(MAX_JCL_BYTES + 1)
    if len(content_bytes) > MAX_JCL_BYTES:
        raise HTTPException(status_code=413, detail="JCL file exceeds the 1 MB limit.")
    try:
        content = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="JCL file must use UTF-8 encoding.") from exc
    return _submit(content, request)


@router.get("", response_model=JobListSchema)
def list_jobs(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> JobListSchema:
    jobs, total = request.app.state.database.list_jobs(limit, offset)
    return JobListSchema(items=jobs, total=total, limit=limit, offset=offset)


@router.get("/{job_id}/steps", response_model=list[JobStepSchema])
def list_job_steps(job_id: str, request: Request) -> list[JobStepSchema]:
    job = request.app.state.database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.steps


@router.get("/{job_id}/spool")
def get_job_spool(job_id: str, request: Request) -> dict[str, object]:
    job = request.app.state.database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id": job.id,
        "stdout": job.stdout,
        "stderr": job.stderr,
        "steps": [
            {
                "step": step.name,
                "program": step.program,
                "return_code": step.return_code,
                "stdout": step.stdout,
                "stderr": step.stderr,
            }
            for step in job.steps
        ],
    }


@router.post("/{job_id}/retry", response_model=JobSchema, status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: str, request: Request) -> JobSchema:
    try:
        job = request.app.state.job_service.retry(job_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except JobQueueUnavailable as exc:
        raise HTTPException(status_code=503, detail="The job queue is unavailable.") from exc
    return JobSchema.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobSchema)
def cancel_job(job_id: str, request: Request) -> JobSchema:
    job = request.app.state.database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not request.app.state.job_scheduler.cancel(job_id):
        raise HTTPException(status_code=409, detail="Only queued or running jobs can be cancelled.")
    updated = request.app.state.database.get_job(job_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobSchema.model_validate(updated)


@router.get("/{job_id}", response_model=JobSchema)
def get_job(job_id: str, request: Request) -> JobSchema:
    job = request.app.state.database.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobSchema.model_validate(job)
