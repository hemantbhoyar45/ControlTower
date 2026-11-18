from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import datasets, jcl, jobs, metrics, reports, vsam
from .config import (
    DEFAULT_COBOL_DIRECTORY,
    DEFAULT_VSAM_DIRECTORY,
    cors_origins,
    database_path as configured_database_path,
)
from .core.cobol_executor import CobolExecutor
from .core.job_scheduler import JobScheduler
from .database.connection import Database
from .schemas.job import HealthSchema
from .services.dataset_service import DatasetService
from .services.job_service import JobService
from .services.report_service import ReportService
from .services.vsam_service import VsamService


def create_app(
    database_path: Path | None = None,
    programs_directory: Path | None = None,
    execution_timeout: int = 10,
    vsam_directory: Path | None = None,
) -> FastAPI:
    database = Database(database_path or configured_database_path())
    executor = CobolExecutor(
        programs_directory or DEFAULT_COBOL_DIRECTORY,
        timeout_seconds=execution_timeout,
    )
    scheduler = JobScheduler(database, executor)
    dataset_service = DatasetService(database)
    job_service = JobService(database, scheduler)
    report_service = ReportService(database)
    vsam_service = VsamService(
        executor, vsam_directory or DEFAULT_VSAM_DIRECTORY
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        database.initialize()
        scheduler.start()
        try:
            yield
        finally:
            scheduler.stop()

    app = FastAPI(
        title="Mainframe Control Tower API",
        description="SQLite-backed batch job, COBOL execution, and dataset services.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),
        allow_methods=["DELETE", "GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )
    app.state.database = database
    app.state.job_scheduler = scheduler
    app.state.cobol_executor = executor
    app.state.dataset_service = dataset_service
    app.state.job_service = job_service
    app.state.report_service = report_service
    app.state.vsam_service = vsam_service

    @app.get("/health", response_model=HealthSchema, tags=["health"])
    def health() -> HealthSchema:
        return HealthSchema(
            status="ok",
            executor=executor.engine_name,
            gnucobol_available=executor.compiler is not None,
        )

    app.include_router(jcl.router)
    app.include_router(jobs.router)
    app.include_router(datasets.router)
    app.include_router(reports.router)
    app.include_router(metrics.router)
    app.include_router(vsam.router)
    return app


app = create_app()
