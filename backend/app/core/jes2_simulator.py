from .cobol_executor import CobolExecutor
from .jcl_parser import parse_jcl
from ..database.connection import Database
import threading


class JES2Simulator:
    def __init__(self, database: Database, executor: CobolExecutor) -> None:
        self.database = database
        self.executor = executor

    def execute_job(self, job_id: str, cancel_event: threading.Event) -> None:
        if not self.database.mark_job_running(job_id):
            return
        job = self.database.get_job(job_id)
        if job is None:
            raise RuntimeError(f"Queued job {job_id} does not exist.")
        parsed = parse_jcl(job.jcl)
        steps_by_name = {step.name: step for step in parsed.steps}
        output: list[str] = []
        errors: list[str] = []

        for step in job.steps:
            if cancel_event.is_set():
                self.database.block_queued_steps(job_id)
                self.database.finish_job(
                    job_id, "cancelled", 130, "".join(output), "Job cancelled."
                )
                return
            if step.status == "completed":
                output.append(f"== {step.name} ({step.program}) ==\n{step.stdout}")
                if step.stderr:
                    errors.append(f"== {step.name} ({step.program}) ==\n{step.stderr}")
                continue
            if step.status != "queued":
                continue
            self.database.mark_step_running(step.id)
            jcl_step = steps_by_name.get(step.name)
            if jcl_step is None:
                raise RuntimeError(f"Persisted step {step.name} is missing from the JCL.")
            sysin_dd = next((dd for dd in jcl_step.datasets if dd.name == "SYSIN"), None)
            sysin = ""
            if sysin_dd is not None:
                if sysin_dd.dataset:
                    dataset = self.database.get_dataset(sysin_dd.dataset)
                    if dataset is None:
                        raise RuntimeError(
                            f"SYSIN dataset {sysin_dd.dataset} does not exist in SQLite."
                        )
                    records = dataset.records
                else:
                    records = sysin_dd.inline_data
                sysin = "\n".join(records) + ("\n" if records else "")
            result = self.executor.execute(
                step.program, stdin=sysin, cancel_event=cancel_event
            )
            if cancel_event.is_set():
                self.database.finish_step(
                    step.id, "blocked", 130, result.stdout, "Job cancelled.", result.executor
                )
                self.database.block_queued_steps(job_id)
                self.database.finish_job(
                    job_id, "cancelled", 130, "".join(output), "Job cancelled."
                )
                return
            step_status = "completed" if result.return_code == 0 else "failed"
            self.database.finish_step(
                step.id,
                step_status,
                result.return_code,
                result.stdout,
                result.stderr,
                result.executor,
            )
            output.append(f"== {step.name} ({step.program}) ==\n{result.stdout}")
            if result.stderr:
                errors.append(f"== {step.name} ({step.program}) ==\n{result.stderr}")
            if result.return_code != 0:
                self.database.block_queued_steps(job_id)
                self.database.finish_job(
                    job_id,
                    "failed",
                    result.return_code,
                    "".join(output),
                    "\n".join(errors),
                )
                return

        self.database.finish_job(job_id, "completed", 0, "".join(output), "\n".join(errors))
