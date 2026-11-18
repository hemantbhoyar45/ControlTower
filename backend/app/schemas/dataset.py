from pydantic import BaseModel, ConfigDict, Field


class DatasetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=44)
    organization: str = Field(default="SEQUENTIAL", min_length=1, max_length=32)
    records: list[str] = Field(default_factory=list, max_length=100_000)


class DatasetRecordsUpdate(BaseModel):
    records: list[str] = Field(max_length=100_000)


class DatasetSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    organization: str
    record_count: int
    created_at: str
    updated_at: str


class DatasetDetailSchema(DatasetSchema):
    records: list[str]


class DatasetListSchema(BaseModel):
    items: list[DatasetSchema]
    total: int
