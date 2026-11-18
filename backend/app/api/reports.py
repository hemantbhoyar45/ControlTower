from fastapi import APIRouter, Request

from ..schemas.job import JobSchema
from ..schemas.report import ReportSummarySchema


router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/summary", response_model=ReportSummarySchema)
def get_report_summary(request: Request) -> ReportSummarySchema:
    return ReportSummarySchema.model_validate(request.app.state.report_service.summary())


@router.get("/jobs", response_model=list[JobSchema])
def list_cobol_reports(request: Request) -> list[JobSchema]:
    jobs, _ = request.app.state.database.list_jobs(500, 0)
    return [
        JobSchema.model_validate(job)
        for job in jobs
        if any(step.program == "REPORT" for step in job.steps)
    ]
