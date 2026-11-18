import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.cobol_executor import CobolExecutor
from app.core.cobol_executor import ExecutionResult
from app.core.jcl_parser import parse_jcl
from app.main import create_app
from app.database.connection import Database


BACKEND = Path(__file__).resolve().parents[1]
PROGRAMS = BACKEND / "cobol"
JCL_DIRECTORY = BACKEND / "jcl"
GREET_JCL = (JCL_DIRECTORY / "GREET.jcl").read_text(encoding="utf-8")
INCR_JCL = (JCL_DIRECTORY / "INCR.jcl").read_text(encoding="utf-8")


def test_parser_extracts_job_steps_and_inline_input() -> None:
    parsed = parse_jcl(INCR_JCL)

    assert parsed.job_name == "INCRJOB"
    assert parsed.steps[0].program == "INCR"
    assert parsed.steps[0].datasets[0].inline_data == ["0041"]


def test_parser_rejects_jcl_without_a_job_or_exec() -> None:
    with pytest.raises(ValueError, match="JOB statement"):
        parse_jcl("//STEP01 EXEC PGM=GREET")
    with pytest.raises(ValueError, match="EXEC PGM"):
        parse_jcl("//EMPTY JOB (ACCT),'EMPTY'\n")
    with pytest.raises(ValueError, match="non-JCL line"):
        parse_jcl("//EMPTY JOB (ACCT),'EMPTY'\nINVALID")


def test_subset_executor_runs_cobol_statements() -> None:
    executor = CobolExecutor(PROGRAMS)
    result = executor.execute("INCR", stdin="0041\n")

    assert result.return_code == 0
    assert "NEXT COUNT: 0042" in result.stdout
    assert result.executor == "cobol-subset-interpreter"


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.02)
    raise AssertionError(f"Job {job_id} did not finish in time.")


def test_api_end_to_end_and_sqlite_persistence(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    app = create_app(database_path=database_path, programs_directory=PROGRAMS)

    with TestClient(app) as client:
        cors = client.options(
            "/api/jobs",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert cors.status_code == 200
        assert cors.headers["access-control-allow-origin"] == "http://localhost:5173"

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        programs = client.get("/api/programs")
        assert programs.status_code == 200
        assert {"GREET", "INCR"} <= set(programs.json()["items"])
        assert client.get("/api/programs/GREET").json()["source"].startswith(
            "       IDENTIFICATION"
        )
        assert client.get("/api/programs/MISSING").status_code == 404

        parsed = client.post("/api/jcl/parse", json={"content": INCR_JCL})
        assert parsed.status_code == 200
        assert parsed.json()["steps"][0]["datasets"][0]["inline_data"] == ["0041"]
        assert client.post("/api/jcl/parse", json={"content": "not JCL"}).status_code == 422
        assert client.post("/api/jcl/validate", json={"content": GREET_JCL}).status_code == 200
        assert client.post(
            "/api/jcl/validate",
            json={"content": "//BADJOB JOB (ACCT),'BAD'\n//BADSTEP EXEC PGM=MISSING"},
        ).status_code == 422

        created_dataset = client.post(
            "/api/datasets",
            json={
                "name": "np.batch.input",
                "organization": "sequential",
                "records": ["first", "second"],
            },
        )
        assert created_dataset.status_code == 201
        assert created_dataset.json()["name"] == "NP.BATCH.INPUT"
        assert client.post(
            "/api/datasets",
            json={"name": "NP.BATCH.INPUT", "records": []},
        ).status_code == 409
        assert client.get("/api/datasets").json()["total"] == 1
        assert client.get("/api/datasets/NP.BATCH.INPUT/records").json() == [
            "first",
            "second",
        ]
        assert client.get("/api/datasets/NP.BATCH.INPUT").json()["records"] == [
            "first",
            "second",
        ]
        replaced = client.put(
            "/api/datasets/NP.BATCH.INPUT/records",
            json={"records": ["0041"]},
        )
        assert replaced.status_code == 200
        assert replaced.json()["records"] == ["0041"]
        assert client.get("/api/datasets/NO.SUCH.DATA").status_code == 404
        assert client.put(
            "/api/datasets/NO.SUCH.DATA/records", json={"records": []}
        ).status_code == 404
        assert client.post(
            "/api/datasets",
            json={"name": "INVALID NAME", "records": []},
        ).status_code == 422

        submitted = client.post("/api/jobs", json={"content": GREET_JCL})
        assert submitted.status_code == 202
        job = _wait_for_job(client, submitted.json()["id"])
        assert job["status"] == "completed"
        assert job["return_code"] == 0
        assert "HELLO FROM COBOL" in job["stdout"]
        assert "RECORDS PROCESSED: 0025" in job["stdout"]
        assert job["steps"][0]["executor"] in {
            "gnucobol",
            "cobol-subset-interpreter",
        }
        assert client.get("/api/jobs").json()["total"] == 1
        assert client.get(f"/api/jobs/{job['id']}/steps").json()[0]["status"] == "completed"
        assert client.get("/api/jobs/not-a-job").status_code == 404

        upload = client.post(
            "/api/jobs/upload",
            files={"file": ("INCR.jcl", INCR_JCL, "text/plain")},
        )
        assert upload.status_code == 202
        increment_job = _wait_for_job(client, upload.json()["id"])
        assert increment_job["status"] == "completed"
        assert "NEXT COUNT: 0042" in increment_job["stdout"]

        dataset_jcl = (
            "//DATAJOB JOB (ACCT),'DATASET INPUT'\n"
            "//STEP001 EXEC PGM=INCR\n"
            "//SYSIN DD DSN=NP.BATCH.INPUT,DISP=SHR\n"
        )
        dataset_submission = client.post("/api/jobs", json={"content": dataset_jcl})
        assert dataset_submission.status_code == 202
        dataset_job = _wait_for_job(client, dataset_submission.json()["id"])
        assert dataset_job["status"] == "completed"
        assert "NEXT COUNT: 0042" in dataset_job["stdout"]

        bad_program_jcl = "//BADJOB JOB (ACCT),'BAD'\n//STEP001 EXEC PGM=MISSING"
        failed_submission = client.post("/api/jobs", json={"content": bad_program_jcl})
        failed_job = _wait_for_job(client, failed_submission.json()["id"])
        assert failed_job["status"] == "failed"
        assert "not available" in failed_job["stderr"]

        report = client.get("/api/reports/summary")
        assert report.status_code == 200
        assert report.json()["total_jobs"] == 4
        assert report.json()["completed_jobs"] == 3
        assert report.json()["failed_jobs"] == 1
        assert report.json()["success_rate"] == 75.0
        assert report.json()["daily"][0]["jobs"] == 4

        assert client.post(
            "/api/jobs/upload",
            files={"file": ("bad.pdf", "not JCL", "application/pdf")},
        ).status_code == 415
        assert client.get("/api/jobs?limit=1&offset=0").json()["limit"] == 1

    with sqlite3.connect(database_path) as connection:
        stored = connection.execute(
            "SELECT status, return_code, stdout FROM jobs WHERE id = ?",
            (job["id"],),
        ).fetchone()
        uploaded = connection.execute(
            "SELECT status, return_code, stdout FROM jobs WHERE id = ?",
            (increment_job["id"],),
        ).fetchone()
        step = connection.execute(
            "SELECT status, executor, stdout FROM job_steps WHERE job_id = ?",
            (job["id"],),
        ).fetchone()
        uploaded_step = connection.execute(
            "SELECT status, executor, stdout FROM job_steps WHERE job_id = ?",
            (increment_job["id"],),
        ).fetchone()
        records = connection.execute(
            """SELECT record FROM dataset_records WHERE dataset_name = ?
               ORDER BY position""",
            ("NP.BATCH.INPUT",),
        ).fetchall()
    assert stored[0:2] == ("completed", 0)
    assert "RECORDS PROCESSED: 0025" in stored[2]
    assert uploaded[0:2] == ("completed", 0)
    assert "NEXT COUNT: 0042" in uploaded[2]
    assert step[0] == "completed"
    assert step[1] in {"gnucobol", "cobol-subset-interpreter"}
    assert "HELLO FROM COBOL" in step[2]
    assert uploaded_step[0] == "completed"
    assert uploaded_step[1] in {"gnucobol", "cobol-subset-interpreter"}
    assert "NEXT COUNT: 0042" in uploaded_step[2]
    assert records == [("0041",)]


def test_jes_controls_metrics_spool_and_cobol_report(tmp_path: Path) -> None:
    app = create_app(
        database_path=tmp_path / "jobs.sqlite3",
        programs_directory=PROGRAMS,
        vsam_directory=tmp_path / "vsam",
    )

    with TestClient(app) as client:
        cancelled = app.state.database.create_job(
            "cancel-before-queue",
            "CANCEL",
            GREET_JCL,
            [("HELLO", "GREET")],
        )
        cancel_response = client.post(f"/api/jobs/{cancelled.id}/cancel")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "cancelled"
        assert cancel_response.json()["return_code"] == 130
        assert client.post(f"/api/jobs/{cancelled.id}/cancel").status_code == 409

        report_source = (JCL_DIRECTORY / "REPORT.jcl").read_text(encoding="utf-8")
        report_submission = client.post("/api/jobs", json={"content": report_source})
        report_job = _wait_for_job(client, report_submission.json()["id"])
        assert report_job["status"] == "completed"
        assert "COBOL BATCH REPORT" in report_job["stdout"]
        spool = client.get(f"/api/jobs/{report_job['id']}/spool")
        assert spool.status_code == 200
        assert "REPORT RECORDS: 0001" in spool.json()["stdout"]
        assert client.get("/api/reports/jobs").json()[0]["id"] == report_job["id"]

        bad_jcl = "//BADJOB JOB (ACCT),'BAD'\n//BADSTEP EXEC PGM=MISSING"
        failed_response = client.post("/api/jobs", json={"content": bad_jcl})
        failed = _wait_for_job(client, failed_response.json()["id"])
        retry_response = client.post(f"/api/jobs/{failed['id']}/retry")
        assert retry_response.status_code == 202
        retried = _wait_for_job(client, retry_response.json()["id"])
        assert retried["id"] != failed["id"]
        assert retried["status"] == "failed"
        assert client.post(f"/api/jobs/{report_job['id']}/retry").status_code == 409

        metrics = client.get("/api/metrics")
        assert metrics.status_code == 200
        assert metrics.json()["total_jobs"] == 4
        assert metrics.json()["cancelled_jobs"] == 1
        assert metrics.json()["database_bytes"] > 0

        if app.state.cobol_executor.compiler is None:
            assert client.get("/api/vsam/customers").status_code == 503
        else:
            customer = {"customer_id": "C0000001", "name": "Sample Customer"}
            assert client.post("/api/vsam/customers", json=customer).status_code == 201
            assert client.get("/api/vsam/customers/C0000001").json()["name"] == customer["name"]
            assert client.put(
                "/api/vsam/customers/C0000001", json={"name": "Updated Customer"}
            ).json()["name"] == "Updated Customer"
            assert client.delete("/api/vsam/customers/C0000001").status_code == 204
            assert client.get("/api/vsam/customers/C0000001").status_code == 404


def test_additional_bundled_cobol_workflows(tmp_path: Path) -> None:
    app = create_app(
        database_path=tmp_path / "jobs.sqlite3",
        programs_directory=PROGRAMS,
    )
    expected_output = {
        "PAYROLL": "GROSS PAY: 0001000",
        "TRANSACT": "NEW BALANCE: 00001250",
        "CUSTOMER": "CUSTOMER RECORD PROCESSED",
    }

    with TestClient(app) as client:
        for sample, expected in expected_output.items():
            content = (JCL_DIRECTORY / f"{sample}.jcl").read_text(encoding="utf-8")
            submitted = client.post("/api/jobs", json={"content": content})
            assert submitted.status_code == 202
            job = _wait_for_job(client, submitted.json()["id"])
            assert job["status"] == "completed"
            assert expected in job["stdout"]


def test_running_job_cancellation_reaches_executor(tmp_path: Path) -> None:
    class WaitingExecutor:
        timeout_seconds = 2

        def __init__(self) -> None:
            import threading

            self.started = threading.Event()

        def execute(
            self,
            program: str,
            stdin: str = "",
            cancel_event=None,
            working_directory=None,
        ) -> ExecutionResult:
            self.started.set()
            assert cancel_event is not None
            cancel_event.wait(timeout=2)
            return ExecutionResult(0, "finished", "", "test-executor")

    app = create_app(
        database_path=tmp_path / "jobs.sqlite3",
        programs_directory=PROGRAMS,
    )
    executor = WaitingExecutor()
    app.state.job_scheduler.executor = executor
    app.state.job_scheduler.simulator.executor = executor

    with TestClient(app) as client:
        submitted = client.post("/api/jobs", json={"content": GREET_JCL})
        assert submitted.status_code == 202
        job_id = submitted.json()["id"]
        assert executor.started.wait(timeout=2)
        cancelled = client.post(f"/api/jobs/{job_id}/cancel")
        assert cancelled.status_code == 200
        final_job = _wait_for_job(client, job_id)
        assert final_job["status"] == "cancelled"
        assert final_job["return_code"] == 130
        assert final_job["steps"][0]["status"] == "blocked"


def test_existing_sqlite_database_migrates_cancelled_status(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed')),
                jcl TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                return_code INTEGER,
                stdout TEXT NOT NULL DEFAULT '',
                stderr TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE job_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                program TEXT NOT NULL,
                position INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (
                    status IN ('queued', 'running', 'completed', 'failed', 'blocked')
                ),
                return_code INTEGER,
                stdout TEXT NOT NULL DEFAULT '',
                stderr TEXT NOT NULL DEFAULT '',
                executor TEXT,
                started_at TEXT,
                finished_at TEXT,
                UNIQUE (job_id, name),
                UNIQUE (job_id, position)
            );
            INSERT INTO jobs (id, name, status, jcl, created_at)
            VALUES ('legacy-job', 'LEGACY', 'queued', '//LEGACY JOB', '2026-01-01');
            INSERT INTO job_steps (job_id, name, program, position, status)
            VALUES ('legacy-job', 'STEP1', 'GREET', 0, 'queued');
            """
        )

    database = Database(database_path)
    database.initialize()
    assert database.get_job("legacy-job") is not None
    assert database.cancel_queued_job("legacy-job")
    assert database.get_job("legacy-job").status == "cancelled"
