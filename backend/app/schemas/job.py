from pydantic import BaseModel, ConfigDict, Field


class JobSubmission(BaseModel):
    content: str = Field(min_length=1, max_length=1_000_000)


class JobStepSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: str
    name: str
    program: str
    position: int
    status: str
    return_code: int | None
    stdout: str
    stderr: str
    executor: str | None
    started_at: str | None
    finished_at: str | None


class JobSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str
    jcl: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    return_code: int | None
    stdout: str
    stderr: str
    steps: list[JobStepSchema] = Field(default_factory=list)


class JobListSchema(BaseModel):
    items: list[JobSchema]
    total: int
    limit: int
    offset: int


class ParsedDDSchema(BaseModel):
    name: str
    dataset: str | None
    inline_data: list[str]


class ParsedStepSchema(BaseModel):
    name: str
    program: str
    datasets: list[ParsedDDSchema]


class ParsedJCLSchema(BaseModel):
    job_name: str
    steps: list[ParsedStepSchema]


class ProgramSchema(BaseModel):
    name: str
    source: str


class ProgramListSchema(BaseModel):
    executor: str
    items: list[str]


class HealthSchema(BaseModel):
    status: str
    executor: str
    gnucobol_available: bool
