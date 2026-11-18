from dataclasses import dataclass, field

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class JobModel(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')"
        ),
        Index("idx_jobs_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    jcl: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[str | None] = mapped_column(String)
    finished_at: Mapped[str | None] = mapped_column(String)
    return_code: Mapped[int | None] = mapped_column(Integer)
    stdout: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    stderr: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    steps: Mapped[list["JobStepModel"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobStepModel(Base):
    __tablename__ = "job_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "name"),
        UniqueConstraint("job_id", "position"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'blocked')"
        ),
        Index("idx_job_steps_job_position", "job_id", "position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    program: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    return_code: Mapped[int | None] = mapped_column(Integer)
    stdout: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    stderr: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    executor: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[str | None] = mapped_column(String)
    finished_at: Mapped[str | None] = mapped_column(String)
    job: Mapped[JobModel] = relationship(back_populates="steps")


class DatasetModel(Base):
    __tablename__ = "datasets"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    organization: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    records: Mapped[list["DatasetRecordModel"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class DatasetRecordModel(Base):
    __tablename__ = "dataset_records"

    dataset_name: Mapped[str] = mapped_column(
        ForeignKey("datasets.name", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, primary_key=True)
    record: Mapped[str] = mapped_column(Text, nullable=False)
    dataset: Mapped[DatasetModel] = relationship(back_populates="records")


@dataclass(slots=True)
class JobStep:
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


@dataclass(slots=True)
class Job:
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
    steps: list[JobStep] = field(default_factory=list)


@dataclass(slots=True)
class Dataset:
    name: str
    organization: str
    record_count: int
    created_at: str
    updated_at: str


@dataclass(slots=True)
class DatasetDetail:
    dataset: Dataset
    records: list[str]
