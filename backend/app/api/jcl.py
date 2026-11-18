from fastapi import APIRouter, HTTPException, Request

from ..core.jcl_parser import parse_jcl
from ..schemas.job import (
    ParsedDDSchema,
    ParsedJCLSchema,
    ParsedStepSchema,
    ProgramListSchema,
    ProgramSchema,
    JobSubmission,
)


router = APIRouter(tags=["jcl", "programs"])


@router.post("/api/jcl/parse", response_model=ParsedJCLSchema)
def parse_submission(submission: JobSubmission) -> ParsedJCLSchema:
    try:
        parsed = parse_jcl(submission.content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ParsedJCLSchema(
        job_name=parsed.job_name,
        steps=[
            ParsedStepSchema(
                name=step.name,
                program=step.program,
                datasets=[
                    ParsedDDSchema(
                        name=dd.name,
                        dataset=dd.dataset,
                        inline_data=dd.inline_data,
                    )
                    for dd in step.datasets
                ],
            )
            for step in parsed.steps
        ],
    )


@router.post("/api/jcl/validate", response_model=ParsedJCLSchema)
def validate_submission(submission: JobSubmission, request: Request) -> ParsedJCLSchema:
    parsed = parse_submission(submission)
    available = set(request.app.state.cobol_executor.list_programs())
    unavailable = sorted(
        {step.program for step in parsed.steps if step.program not in available}
    )
    if unavailable:
        raise HTTPException(
            status_code=422,
            detail=f"COBOL program(s) are not in the approved library: {', '.join(unavailable)}.",
        )
    missing_input_datasets = sorted(
        {
            dd.dataset
            for step in parsed.steps
            for dd in step.datasets
            if dd.name == "SYSIN"
            and dd.dataset
            and request.app.state.database.get_dataset(dd.dataset) is None
        }
    )
    if missing_input_datasets:
        raise HTTPException(
            status_code=422,
            detail=f"SYSIN dataset(s) do not exist: {', '.join(missing_input_datasets)}.",
        )
    return parsed


@router.get("/api/programs", response_model=ProgramListSchema, tags=["programs"])
def list_programs(request: Request) -> ProgramListSchema:
    executor = request.app.state.cobol_executor
    return ProgramListSchema(executor=executor.engine_name, items=executor.list_programs())


@router.get(
    "/api/programs/{program_name}",
    response_model=ProgramSchema,
    tags=["programs"],
)
def get_program(program_name: str, request: Request) -> ProgramSchema:
    source = request.app.state.cobol_executor.get_program_source(program_name)
    if source is None:
        raise HTTPException(status_code=404, detail="COBOL program not found.")
    return ProgramSchema(name=program_name.upper(), source=source)
