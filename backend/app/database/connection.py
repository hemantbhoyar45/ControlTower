from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, CursorResult, Engine
from sqlalchemy.exc import IntegrityError

from .models import Base, Dataset, DatasetDetail, Job, JobStep


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DatasetAlreadyExists(Exception):
    pass


class _Row:
    def __init__(self, row: Any) -> None:
        self._row = row

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._row[key]
        return self._row._mapping[key]


class _Result:
    def __init__(self, result: CursorResult[Any]) -> None:
        self._result = result
        self.rowcount = result.rowcount

    def fetchone(self) -> Any:
        row = self._result.fetchone()
        return _Row(row) if row is not None else None

    def fetchall(self) -> list[Any]:
        return [_Row(row) for row in self._result.fetchall()]


class _SQLiteConnection:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def execute(self, statement: str, parameters: Sequence[Any] = ()) -> _Result:
        result = self._connection.exec_driver_sql(statement, tuple(parameters))
        return _Result(result)

    def executemany(
        self, statement: str, parameters: Sequence[Sequence[Any]]
    ) -> _Result:
        if not parameters:
            return _Result(self._connection.exec_driver_sql("SELECT 1 WHERE 1 = 0"))
        result = self._connection.exec_driver_sql(statement, list(parameters))
        return _Result(result)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self._connection.exec_driver_sql(statement)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.engine: Engine = create_engine(
            f"sqlite:///{path.resolve().as_posix()}",
            connect_args={"timeout": 10, "check_same_thread": False},
        )
        event.listen(self.engine, "connect", self._enable_foreign_keys)

    @staticmethod
    def _enable_foreign_keys(connection: Any, _: Any) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    @contextmanager
    def _connection(self) -> Iterator[_SQLiteConnection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.engine.begin() as connection:
            yield _SQLiteConnection(connection)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(self.engine)
        self._migrate_cancelled_job_status()

    def _migrate_cancelled_job_status(self) -> None:
        with self.engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
            ).fetchone()
            if row is None or "cancelled" in str(row[0]).lower():
                return
            connection.exec_driver_sql("PRAGMA foreign_keys = OFF")
            connection.commit()
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            connection.exec_driver_sql(
                """CREATE TABLE jobs_migrated (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN ('queued', 'running', 'completed', 'failed', 'cancelled')
                    ),
                    jcl TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    return_code INTEGER,
                    stdout TEXT NOT NULL DEFAULT '',
                    stderr TEXT NOT NULL DEFAULT ''
                )"""
            )
            connection.exec_driver_sql(
                """INSERT INTO jobs_migrated
                   SELECT id, name, status, jcl, created_at, started_at, finished_at,
                          return_code, stdout, stderr FROM jobs"""
            )
            connection.exec_driver_sql("DROP TABLE jobs")
            connection.exec_driver_sql("ALTER TABLE jobs_migrated RENAME TO jobs")
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at DESC)"
            )
            connection.commit()
            connection.exec_driver_sql("PRAGMA foreign_keys = ON")
            connection.commit()

    def create_job(self, job_id: str, name: str, jcl: str, steps: list[tuple[str, str]]) -> Job:
        created_at = utc_now()
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO jobs (id, name, status, jcl, created_at) VALUES (?, ?, 'queued', ?, ?)",
                (job_id, name, jcl, created_at),
            )
            connection.executemany(
                """INSERT INTO job_steps (job_id, name, program, position, status)
                   VALUES (?, ?, ?, ?, 'queued')""",
                [
                    (job_id, step_name, program, position)
                    for position, (step_name, program) in enumerate(steps)
                ],
            )
        job = self.get_job(job_id)
        if job is None:
            raise RuntimeError(f"Created job {job_id} could not be read from SQLite.")
        return job

    def get_job(self, job_id: str) -> Job | None:
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            steps = connection.execute(
                "SELECT * FROM job_steps WHERE job_id = ? ORDER BY position",
                (job_id,),
            ).fetchall()
        return _job_from_row(row, [_step_from_row(step) for step in steps])

    def list_jobs(self, limit: int, offset: int) -> tuple[list[Job], int]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC, id LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            total = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            jobs = []
            for row in rows:
                steps = connection.execute(
                    "SELECT * FROM job_steps WHERE job_id = ? ORDER BY position",
                    (row["id"],),
                ).fetchall()
                jobs.append(_job_from_row(row, [_step_from_row(step) for step in steps]))
        return jobs, total

    def job_report(self, start_date: str) -> dict[str, object]:
        with self._connection() as connection:
            totals = connection.execute(
                """SELECT
                       COUNT(*) AS total,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                       SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                       SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                       SUM(CASE WHEN status IN ('queued', 'running') THEN 1 ELSE 0 END) AS active,
                       AVG(CASE WHEN status = 'completed'
                                    AND started_at IS NOT NULL
                                    AND finished_at IS NOT NULL
                                    AND julianday(finished_at) >= julianday(started_at)
                                THEN (julianday(finished_at) - julianday(started_at)) * 86400
                           END) AS avg_duration_seconds
                   FROM jobs"""
            ).fetchone()
            daily_rows = connection.execute(
                """SELECT date(created_at) AS cycle_date,
                          COUNT(*) AS jobs,
                          SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                          SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                          SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                          AVG(CASE WHEN status = 'completed'
                                       AND started_at IS NOT NULL
                                       AND finished_at IS NOT NULL
                                       AND julianday(finished_at) >= julianday(started_at)
                                   THEN (julianday(finished_at) - julianday(started_at)) * 86400
                              END) AS avg_duration_seconds
                   FROM jobs
                   WHERE date(created_at) >= ?
                   GROUP BY date(created_at)""",
                (start_date,),
            ).fetchall()
        total = totals["total"]
        completed = totals["completed"] or 0
        failed = totals["failed"] or 0
        cancelled = totals["cancelled"] or 0
        terminal = completed + failed + cancelled
        return {
            "total_jobs": total,
            "completed_jobs": completed,
            "failed_jobs": failed,
            "cancelled_jobs": cancelled,
            "active_jobs": totals["active"] or 0,
            "success_rate": round(completed / terminal * 100, 1) if terminal else 0.0,
            "avg_duration_seconds": round(totals["avg_duration_seconds"] or 0, 1),
            "daily": [
                {
                    "date": row["cycle_date"],
                    "jobs": row["jobs"],
                    "completed": row["completed"] or 0,
                    "failed": row["failed"] or 0,
                    "cancelled": row["cancelled"] or 0,
                    "success_rate": round(
                        (row["completed"] or 0)
                        / (
                            (row["completed"] or 0)
                            + (row["failed"] or 0)
                            + (row["cancelled"] or 0)
                        )
                        * 100,
                        1,
                    )
                    if (row["completed"] or 0)
                    + (row["failed"] or 0)
                    + (row["cancelled"] or 0)
                    else 0.0,
                    "avg_duration_seconds": round(row["avg_duration_seconds"] or 0, 1),
                }
                for row in daily_rows
            ],
        }

    def mark_job_running(self, job_id: str) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE jobs SET status = 'running', started_at = ?
                   WHERE id = ? AND status = 'queued'""",
                (utc_now(), job_id),
            )
        return cursor.rowcount == 1

    def mark_step_running(self, step_id: int) -> None:
        with self._connection() as connection:
            connection.execute(
                "UPDATE job_steps SET status = 'running', started_at = ? WHERE id = ?",
                (utc_now(), step_id),
            )

    def finish_step(
        self,
        step_id: int,
        status: str,
        return_code: int,
        stdout: str,
        stderr: str,
        executor: str,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE job_steps
                   SET status = ?, return_code = ?, stdout = ?, stderr = ?,
                       executor = ?, finished_at = ?
                   WHERE id = ?""",
                (status, return_code, stdout, stderr, executor, utc_now(), step_id),
            )

    def finish_job(
        self, job_id: str, status: str, return_code: int, stdout: str, stderr: str
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE jobs
                   SET status = ?, return_code = ?, stdout = ?, stderr = ?, finished_at = ?
                   WHERE id = ?""",
                (status, return_code, stdout, stderr, utc_now(), job_id),
            )

    def cancel_queued_job(self, job_id: str) -> bool:
        finished_at = utc_now()
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE jobs
                   SET status = 'cancelled', return_code = 130, stderr = ?,
                       finished_at = ?
                   WHERE id = ? AND status = 'queued'""",
                ("Job cancelled before execution.", finished_at, job_id),
            )
            if cursor.rowcount:
                connection.execute(
                    """UPDATE job_steps SET status = 'blocked', return_code = 130,
                           stderr = 'Job cancelled before execution.', finished_at = ?
                       WHERE job_id = ? AND status = 'queued'""",
                    (finished_at, job_id),
                )
        return cursor.rowcount == 1

    def block_queued_steps(self, job_id: str) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE job_steps SET status = 'blocked'
                   WHERE job_id = ? AND status = 'queued'""",
                (job_id,),
            )

    def fail_job(self, job_id: str, message: str) -> None:
        finished_at = utc_now()
        with self._connection() as connection:
            connection.execute(
                """UPDATE job_steps
                   SET status = 'blocked', finished_at = ?
                   WHERE job_id = ? AND status = 'queued'""",
                (finished_at, job_id),
            )
            connection.execute(
                """UPDATE job_steps
                   SET status = 'failed', return_code = 1, stderr = ?, finished_at = ?
                   WHERE job_id = ? AND status = 'running'""",
                (message, finished_at, job_id),
            )
        job = self.get_job(job_id)
        if job is None:
            return
        stdout = "".join(
            f"== {step.name} ({step.program}) ==\n{step.stdout}" for step in job.steps if step.stdout
        )
        previous_stderr = "\n".join(step.stderr for step in job.steps if step.stderr)
        stderr = previous_stderr if message in previous_stderr else "\n".join(
            part for part in (previous_stderr, message) if part
        )
        with self._connection() as connection:
            connection.execute(
                """UPDATE jobs
                   SET status = 'failed', return_code = 1, stdout = ?, stderr = ?, finished_at = ?
                   WHERE id = ?""",
                (stdout, stderr, finished_at, job_id),
            )

    def queued_job_ids(self) -> list[str]:
        with self._connection() as connection:
            connection.execute(
                """UPDATE jobs SET status = 'queued', started_at = NULL
                   WHERE status = 'running'"""
            )
            connection.execute(
                """UPDATE job_steps SET status = 'queued', started_at = NULL
                   WHERE status = 'running'
                     AND job_id IN (SELECT id FROM jobs WHERE status = 'queued')"""
            )
            rows = connection.execute(
                "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at, id"
            ).fetchall()
        return [row["id"] for row in rows]

    def system_metrics(self) -> dict[str, int]:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) AS queued,
                          SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running,
                          SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed,
                          SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                          SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled
                   FROM jobs"""
            ).fetchone()
        return {
            "total_jobs": row["total"],
            "queued_jobs": row["queued"] or 0,
            "running_jobs": row["running"] or 0,
            "completed_jobs": row["completed"] or 0,
            "failed_jobs": row["failed"] or 0,
            "cancelled_jobs": row["cancelled"] or 0,
            "database_bytes": self.path.stat().st_size if self.path.exists() else 0,
        }

    def list_datasets(self) -> list[Dataset]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT d.name, d.organization, d.created_at, d.updated_at,
                          COUNT(r.position) AS record_count
                   FROM datasets d LEFT JOIN dataset_records r ON r.dataset_name = d.name
                   GROUP BY d.name ORDER BY d.name"""
            ).fetchall()
        return [_dataset_from_row(row) for row in rows]

    def get_dataset(self, name: str) -> DatasetDetail | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT d.name, d.organization, d.created_at, d.updated_at,
                          COUNT(r.position) AS record_count
                   FROM datasets d LEFT JOIN dataset_records r ON r.dataset_name = d.name
                   WHERE d.name = ? GROUP BY d.name""",
                (name,),
            ).fetchone()
            if row is None:
                return None
            records = connection.execute(
                """SELECT record FROM dataset_records WHERE dataset_name = ?
                   ORDER BY position""",
                (name,),
            ).fetchall()
        return DatasetDetail(
            dataset=_dataset_from_row(row),
            records=[record["record"] for record in records],
        )

    def create_dataset(self, name: str, organization: str, records: list[str]) -> DatasetDetail:
        created_at = utc_now()
        try:
            with self._connection() as connection:
                connection.execute(
                    """INSERT INTO datasets (name, organization, created_at, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (name, organization, created_at, created_at),
                )
                connection.executemany(
                    """INSERT INTO dataset_records (dataset_name, position, record)
                       VALUES (?, ?, ?)""",
                    [(name, position, record) for position, record in enumerate(records)],
                )
        except IntegrityError as exc:
            if self.get_dataset(name) is not None:
                raise DatasetAlreadyExists(name) from exc
            raise
        dataset = self.get_dataset(name)
        if dataset is None:
            raise RuntimeError(f"Created dataset {name} could not be read from SQLite.")
        return dataset

    def replace_dataset_records(self, name: str, records: list[str]) -> DatasetDetail | None:
        with self._connection() as connection:
            exists = connection.execute(
                "SELECT 1 FROM datasets WHERE name = ?", (name,)
            ).fetchone()
            if exists is None:
                return None
            connection.execute("DELETE FROM dataset_records WHERE dataset_name = ?", (name,))
            connection.executemany(
                """INSERT INTO dataset_records (dataset_name, position, record)
                   VALUES (?, ?, ?)""",
                [(name, position, record) for position, record in enumerate(records)],
            )
            connection.execute(
                "UPDATE datasets SET updated_at = ? WHERE name = ?", (utc_now(), name)
            )
        return self.get_dataset(name)


def _step_from_row(row: sqlite3.Row) -> JobStep:
    return JobStep(
        id=row["id"],
        job_id=row["job_id"],
        name=row["name"],
        program=row["program"],
        position=row["position"],
        status=row["status"],
        return_code=row["return_code"],
        stdout=row["stdout"],
        stderr=row["stderr"],
        executor=row["executor"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )


def _job_from_row(row: sqlite3.Row, steps: list[JobStep]) -> Job:
    return Job(
        id=row["id"],
        name=row["name"],
        status=row["status"],
        jcl=row["jcl"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        return_code=row["return_code"],
        stdout=row["stdout"],
        stderr=row["stderr"],
        steps=steps,
    )


def _dataset_from_row(row: sqlite3.Row) -> Dataset:
    return Dataset(
        name=row["name"],
        organization=row["organization"],
        record_count=row["record_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
