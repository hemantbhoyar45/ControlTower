from fastapi import APIRouter, Request


router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("")
def get_system_metrics(request: Request) -> dict[str, int | str | bool]:
    scheduler = request.app.state.job_scheduler
    metrics = request.app.state.database.system_metrics()
    return {
        **metrics,
        "queue_depth": scheduler.queue_depth,
        "executor": request.app.state.cobol_executor.engine_name,
        "gnucobol_available": request.app.state.cobol_executor.compiler is not None,
    }
