import logging
from uuid import uuid4

from ..core.job_scheduler import JobScheduler
from ..core.jcl_parser import parse_jcl
from ..database.connection import Database
from ..database.models import Job


logger = logging.getLogger(__name__)


class JobQueueUnavailable(RuntimeError):
    pass


class JobService:
    def __init__(self, database: Database, scheduler: JobScheduler) -> None:
        self.database = database
        self.scheduler = scheduler

    def submit(self, content: str) -> Job:
        parsed = parse_jcl(content)
        job = self.database.create_job(
            job_id=str(uuid4()),
            name=parsed.job_name,
            jcl=content,
            steps=[(step.name, step.program) for step in parsed.steps],
        )
        try:
            self.scheduler.enqueue(job.id)
        except Exception as exc:
            logger.exception("Could not enqueue submitted job %s", job.id)
            self.database.fail_job(job.id, f"Could not enqueue job: {exc}")
            raise JobQueueUnavailable from exc
        return job

    def retry(self, job_id: str) -> Job:
        job = self.database.get_job(job_id)
        if job is None:
            raise LookupError("Job not found.")
        if job.status != "failed":
            raise ValueError("Only failed jobs can be retried.")
        return self.submit(job.jcl)
