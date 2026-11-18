import threading
from pathlib import Path

from ..core.cobol_executor import CobolExecutor, CobolExecutionError


class VsamUnavailable(RuntimeError):
    pass


class VsamOperationError(ValueError):
    pass


class VsamService:
    def __init__(self, executor: CobolExecutor, directory: Path) -> None:
        self.executor = executor
        self.directory = directory.resolve()
        self._lock = threading.Lock()

    def execute(self, action: str, customer_id: str, name: str = "") -> dict[str, str] | None:
        if self.executor.compiler is None:
            raise VsamUnavailable("VSAM KSDS operations require GnuCOBOL (cobc).")
        command = f"{action}|{customer_id}|{name}\n"
        with self._lock:
            try:
                result = self.executor.execute(
                    "VSAMCUS",
                    stdin=command,
                    working_directory=self.directory,
                )
            except CobolExecutionError as exc:
                raise VsamOperationError(str(exc)) from exc
        if result.return_code != 0:
            raise VsamOperationError(result.stderr or "The VSAM COBOL program failed.")
        response = result.stdout.strip()
        if response.startswith("ERROR|"):
            message = response.split("|", maxsplit=1)[1]
            if message == "NOTFOUND":
                return None
            raise VsamOperationError(message)
        if action in {"GET", "ADD", "UPDATE", "DELETE"}:
            parts = response.split("|", maxsplit=2)
            if len(parts) != 3 or parts[0] != "OK":
                raise VsamOperationError("The VSAM program returned an invalid customer record.")
            return {"customer_id": parts[1].strip(), "name": parts[2].strip()}
        return None

    def list_customers(self) -> list[dict[str, str]]:
        if self.executor.compiler is None:
            raise VsamUnavailable("VSAM KSDS operations require GnuCOBOL (cobc).")
        with self._lock:
            try:
                result = self.executor.execute(
                    "VSAMCUS",
                    stdin="LIST||\n",
                    working_directory=self.directory,
                )
            except CobolExecutionError as exc:
                raise VsamOperationError(str(exc)) from exc
        if result.return_code != 0:
            raise VsamOperationError(result.stderr or "The VSAM COBOL program failed.")
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if lines == ["EMPTY"]:
            return []
        customers: list[dict[str, str]] = []
        for line in lines:
            parts = line.split("|", maxsplit=2)
            if len(parts) != 3 or parts[0] != "OK":
                raise VsamOperationError("The VSAM program returned an invalid customer list.")
            customers.append({"customer_id": parts[1].strip(), "name": parts[2].strip()})
        return customers
