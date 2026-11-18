from pydantic import BaseModel


class DailyReportSchema(BaseModel):
    date: str
    jobs: int
    completed: int
    failed: int
    cancelled: int
    success_rate: float
    avg_duration_seconds: float


class ReportSummarySchema(BaseModel):
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    cancelled_jobs: int
    active_jobs: int
    success_rate: float
    avg_duration_seconds: float
    daily: list[DailyReportSchema]
