from fastapi import APIRouter, HTTPException, Request

from ..core.jcl_validator import validate_jcl_content
from ..schemas.job import (
    JobSubmission,
    ParsedDDSchema,
    ParsedJCLSchema,
    ParsedStepSchema,
    ProgramListSchema,
    ProgramSchema,
    ValidationDiagnosticSchema,
)


router = APIRouter(tags=["jcl", "programs"])


def _to_schema(val_result) -> ParsedJCLSchema:
    return ParsedJCLSchema(
        job_name=val_result.job_name or "UNNAMED",
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
            for step in val_result.steps
        ],
        is_valid=val_result.is_valid,
        errors=val_result.errors,
        warnings=val_result.warnings,
        diagnostics=[
            ValidationDiagnosticSchema(
                severity=d.severity,
                rule=d.rule,
                message=d.message,
                statement=d.statement,
                line_number=d.line_number,
            )
            for d in val_result.diagnostics
        ],
        structure_summary=val_result.structure_summary,
    )


@router.post("/api/jcl/parse", response_model=ParsedJCLSchema)
def parse_submission(submission: JobSubmission) -> ParsedJCLSchema:
    val_result = validate_jcl_content(submission.content)
    if not val_result.is_valid:
        raise HTTPException(status_code=422, detail="; ".join(val_result.errors))
    return _to_schema(val_result)


@router.post("/api/jcl/validate", response_model=ParsedJCLSchema)
def validate_submission(submission: JobSubmission, request: Request) -> ParsedJCLSchema:
    executor = request.app.state.cobol_executor
    database = request.app.state.database
    val_result = validate_jcl_content(submission.content, executor=executor, database=database)
    if not val_result.is_valid:
        raise HTTPException(
            status_code=422,
            detail="; ".join(val_result.errors),
        )
    return _to_schema(val_result)


@router.post("/api/jcl/inspect", response_model=ParsedJCLSchema)
def inspect_submission(submission: JobSubmission, request: Request) -> ParsedJCLSchema:
    executor = request.app.state.cobol_executor
    database = request.app.state.database
    val_result = validate_jcl_content(submission.content, executor=executor, database=database)
    return _to_schema(val_result)


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
