import logging
import queue
import threading

from ..database.connection import Database
from .cobol_executor import CobolExecutor
from .jes2_simulator import JES2Simulator


logger = logging.getLogger(__name__)


class JobScheduler:
    def __init__(self, database: Database, executor: CobolExecutor) -> None:
        self.database = database
        self.executor = executor
        self.simulator = JES2Simulator(database, executor)
        self._pending: queue.Queue[str | None] = queue.Queue(maxsize=1000)
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._active: dict[str, threading.Event] = {}
        self._active_lock = threading.Lock()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stopping.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="mainframe-job-queue",
            daemon=True,
        )
        self._thread.start()
        for job_id in self.database.queued_job_ids():
            self.enqueue(job_id)

    def stop(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            return
        self._stopping.set()
        self._pending.put(None)
        self._thread.join(timeout=self.executor.timeout_seconds + 2)

    def enqueue(self, job_id: str) -> None:
        try:
            self._pending.put_nowait(job_id)
        except queue.Full as exc:
            raise RuntimeError("The job queue is full.") from exc

    def cancel(self, job_id: str) -> bool:
        if self.database.cancel_queued_job(job_id):
            return True
        with self._active_lock:
            cancel_event = self._active.get(job_id)
            if cancel_event is None:
                return False
            cancel_event.set()
            return True

    @property
    def queue_depth(self) -> int:
        return self._pending.qsize()

    def _run(self) -> None:
        while not self._stopping.is_set():
            try:
                job_id = self._pending.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                if job_id is not None:
                    cancel_event = threading.Event()
                    with self._active_lock:
                        self._active[job_id] = cancel_event
                    try:
                        self.simulator.execute_job(job_id, cancel_event)
                    finally:
                        with self._active_lock:
                            self._active.pop(job_id, None)
            except Exception as exc:
                logger.exception("Job %s could not be executed", job_id)
                if job_id is not None:
                    try:
                        self.database.fail_job(job_id, str(exc))
                    except Exception:
                        logger.exception("Could not persist failure for job %s", job_id)
            finally:
                self._pending.task_done()
