from pydantic import BaseModel, Field


class CustomerWrite(BaseModel):
    name: str = Field(min_length=1, max_length=40, pattern=r"^[^|\r\n]+$")


class CustomerSchema(BaseModel):
    customer_id: str = Field(min_length=1, max_length=8, pattern=r"^[A-Za-z0-9]+$")
    name: str = Field(min_length=1, max_length=40, pattern=r"^[^|\r\n]+$")
