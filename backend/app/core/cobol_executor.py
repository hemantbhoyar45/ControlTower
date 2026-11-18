import ast
import operator
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path


class CobolExecutionError(Exception):
    pass


@dataclass(slots=True)
class ExecutionResult:
    return_code: int
    stdout: str
    stderr: str
    executor: str


@dataclass(slots=True)
class _Field:
    kind: str
    width: int
    value: str | int


_FIELD = re.compile(
    r"^\d{2}\s+([A-Z0-9-]+)\s+PIC\s+([X9])(?:\((\d+)\))?"
    r"(?:\s+VALUE\s+(.+?))?\.$",
    re.IGNORECASE,
)
_TOKEN = re.compile(r'"(?:[^"]|"")*"|\'(?:[^\']|\'\')*\'|[A-Z0-9-]+', re.IGNORECASE)
_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.floordiv,
}
_COMPARISONS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
}


class CobolExecutor:
    def __init__(self, programs_directory: Path, timeout_seconds: int = 10) -> None:
        self.programs_directory = programs_directory.resolve()
        self.timeout_seconds = timeout_seconds
        self.compiler = shutil.which("cobc")

    @property
    def engine_name(self) -> str:
        return "gnucobol" if self.compiler else "cobol-subset-interpreter"

    def list_programs(self) -> list[str]:
        if not self.programs_directory.is_dir():
            return []
        return sorted(
            path.stem.upper()
            for path in self.programs_directory.iterdir()
            if path.is_file() and path.suffix.lower() in {".cob", ".cbl"}
        )

    def get_program_source(self, program: str) -> str | None:
        path = self._find_program(program)
        return path.read_text(encoding="utf-8") if path else None

    def execute(
        self,
        program: str,
        stdin: str = "",
        cancel_event: threading.Event | None = None,
        working_directory: Path | None = None,
    ) -> ExecutionResult:
        path = self._find_program(program)
        if path is None:
            raise CobolExecutionError(f"COBOL program {program} is not available.")
        if self.compiler:
            return self._execute_compiled(path, stdin, cancel_event, working_directory)
        return _interpret(path.read_text(encoding="utf-8"), stdin)

    def _find_program(self, program: str) -> Path | None:
        name = program.upper()
        if not re.fullmatch(r"[A-Z0-9@$#-]{1,8}", name):
            return None
        for suffix in (".cob", ".cbl"):
            path = (self.programs_directory / f"{name}{suffix}").resolve()
            if path.parent == self.programs_directory and path.is_file():
                return path
        return None

    def _execute_compiled(
        self,
        source: Path,
        stdin: str,
        cancel_event: threading.Event | None,
        working_directory: Path | None,
    ) -> ExecutionResult:
        assert self.compiler is not None
        execution_directory = (
            working_directory.resolve() if working_directory else None
        )
        if execution_directory is not None:
            execution_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="mainframe-cobol-") as directory:
            executable = Path(directory) / "program.exe"
            compile_result = _run_process(
                [self.compiler, "-x", str(source), "-o", str(executable)],
                cwd=directory,
                timeout_seconds=self.timeout_seconds,
                cancel_event=cancel_event,
            )
            if compile_result.return_code != 0:
                return compile_result
            return _run_process(
                [str(executable)],
                cwd=str(execution_directory or Path(directory)),
                stdin=stdin,
                timeout_seconds=self.timeout_seconds,
                cancel_event=cancel_event,
            )


def _run_process(
    command: list[str],
    cwd: str,
    timeout_seconds: int,
    cancel_event: threading.Event | None,
    stdin: str = "",
) -> ExecutionResult:
    with subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        deadline = time.monotonic() + timeout_seconds
        pending_input: str | None = stdin
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                stdout, stderr = process.communicate()
                raise CobolExecutionError(
                    f"GnuCOBOL compilation or execution exceeded {timeout_seconds} seconds: "
                    f"{stderr.strip() or stdout.strip()}"
                )
            try:
                stdout, stderr = process.communicate(
                    input=pending_input,
                    timeout=min(remaining, 0.1),
                )
                break
            except subprocess.TimeoutExpired:
                pending_input = None
                if cancel_event is not None and cancel_event.is_set():
                    process.terminate()
                    try:
                        stdout, stderr = process.communicate(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        stdout, stderr = process.communicate()
                    return ExecutionResult(
                        130, stdout or "", stderr or "Job cancelled.", "gnucobol"
                    )
        if cancel_event is not None and cancel_event.is_set():
            return ExecutionResult(130, stdout, stderr, "gnucobol")
        return ExecutionResult(process.returncode, stdout, stderr, "gnucobol")


def _interpret(source: str, stdin: str) -> ExecutionResult:
    fields: dict[str, _Field] = {}
    statements: list[str] = []
    in_procedure = False

    for raw_line in source.splitlines():
        line = _code_from_source_line(raw_line)
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("PROCEDURE DIVISION"):
            in_procedure = True
            continue
        if not in_procedure:
            declaration = _FIELD.match(line)
            if declaration:
                name, kind, width_text, initial = declaration.groups()
                width = int(width_text or "1")
                if width > 4096:
                    raise CobolExecutionError(f"Field {name} exceeds the supported field width.")
                fields[name.upper()] = _Field(
                    kind.upper(), width, _initial_value(kind, initial)
                )
            continue
        statements.append(line.strip())

    if not in_procedure:
        raise CobolExecutionError("The COBOL program has no PROCEDURE DIVISION.")

    input_lines = iter(stdin.splitlines())
    output: list[str] = []
    for statement in statements:
        command = statement.rstrip(".").strip()
        if not command:
            continue
        if re.fullmatch(r"(?:STOP\s+RUN|GOBACK)", command, re.IGNORECASE):
            break
        if command.upper().startswith("DISPLAY "):
            output.append(_display(command[8:].strip(), fields))
        elif command.upper().startswith("MOVE "):
            match = re.fullmatch(r"MOVE\s+(.+?)\s+TO\s+([A-Z0-9-]+)", command, re.IGNORECASE)
            if not match:
                raise CobolExecutionError(f"Unsupported MOVE statement: {command}")
            target = _get_field(fields, match.group(2))
            target.value = _resolve_value(match.group(1), fields)
        elif command.upper().startswith("ADD "):
            match = re.fullmatch(r"ADD\s+(.+?)\s+TO\s+([A-Z0-9-]+)", command, re.IGNORECASE)
            if not match:
                raise CobolExecutionError(f"Unsupported ADD statement: {command}")
            target = _get_field(fields, match.group(2))
            target.value = _numeric_value(target.value) + _numeric_value(
                _resolve_value(match.group(1), fields)
            )
        elif command.upper().startswith("SUBTRACT "):
            match = re.fullmatch(
                r"SUBTRACT\s+(.+?)\s+FROM\s+([A-Z0-9-]+)", command, re.IGNORECASE
            )
            if not match:
                raise CobolExecutionError(f"Unsupported SUBTRACT statement: {command}")
            target = _get_field(fields, match.group(2))
            target.value = _numeric_value(target.value) - _numeric_value(
                _resolve_value(match.group(1), fields)
            )
        elif command.upper().startswith("COMPUTE "):
            match = re.fullmatch(r"COMPUTE\s+([A-Z0-9-]+)\s*=\s*(.+)", command, re.IGNORECASE)
            if not match:
                raise CobolExecutionError(f"Unsupported COMPUTE statement: {command}")
            target = _get_field(fields, match.group(1))
            target.value = _compute(match.group(2), fields)
        elif command.upper().startswith("ACCEPT "):
            name = command[7:].strip().upper()
            target = _get_field(fields, name)
            try:
                value = next(input_lines)
            except StopIteration:
                value = ""
            target.value = _coerce(value, target.kind)
        else:
            raise CobolExecutionError(f"Unsupported COBOL statement: {command}")

    return ExecutionResult(0, "".join(f"{line}\n" for line in output), "", "cobol-subset-interpreter")


def _code_from_source_line(raw_line: str) -> str:
    if len(raw_line) >= 7 and raw_line[:6].isspace():
        indicator = raw_line[6]
        if indicator in {"*", "/", "D", "d"}:
            return ""
        if indicator.isspace() or indicator == "-":
            return raw_line[7:72].strip()
    stripped = raw_line.strip()
    if stripped.startswith("*"):
        return ""
    return stripped


def _initial_value(kind: str, value: str | None) -> str | int:
    if value is None:
        return 0 if kind.upper() == "9" else ""
    return _coerce(value.strip(), kind.upper())


def _coerce(value: str, kind: str) -> str | int:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1].replace('""', '"')
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1].replace("''", "'")
    if kind.upper() == "9":
        try:
            return int(value)
        except ValueError as exc:
            raise CobolExecutionError(f"Expected a numeric value, received {value!r}.") from exc
    return value


def _get_field(fields: dict[str, _Field], name: str) -> _Field:
    field = fields.get(name.upper())
    if field is None:
        raise CobolExecutionError(f"COBOL field {name} is not declared.")
    return field


def _numeric_value(value: str | int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise CobolExecutionError(f"Expected a numeric value, received {value!r}.") from exc


def _resolve_value(value: str, fields: dict[str, _Field]) -> str | int:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return _coerce(value, "X")
    if re.fullmatch(r"[+-]?\d+", value):
        return int(value)
    return _get_field(fields, value).value


def _format_field(field: _Field) -> str:
    if field.kind == "9":
        return str(_numeric_value(field.value)).zfill(field.width)
    return str(field.value).ljust(field.width)


def _display(operands: str, fields: dict[str, _Field]) -> str:
    tokens = _TOKEN.findall(operands)
    if not tokens:
        return ""
    result: list[str] = []
    for token in tokens:
        if token.startswith('"') or token.startswith("'"):
            result.append(str(_coerce(token, "X")))
        elif re.fullmatch(r"\d+", token):
            result.append(token)
        else:
            result.append(_format_field(_get_field(fields, token)))
    return "".join(result).rstrip()


def _compute(expression: str, fields: dict[str, _Field]) -> int:
    normalized = expression.upper().replace("**", "^")
    for name in sorted(fields, key=len, reverse=True):
        normalized = re.sub(rf"\b{re.escape(name)}\b", str(fields[name].value), normalized)
    normalized = normalized.replace("^", "**")
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise CobolExecutionError(f"Invalid COMPUTE expression: {expression}") from exc
    return _eval_expression(tree.body)


def _eval_expression(node: ast.expr) -> int:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.BinOp):
        operation = _BINARY_OPERATORS.get(type(node.op))
        if operation is None:
            raise CobolExecutionError("Unsupported operator in COMPUTE expression.")
        try:
            return int(operation(_eval_expression(node.left), _eval_expression(node.right)))
        except ZeroDivisionError as exc:
            raise CobolExecutionError("Division by zero in COMPUTE expression.") from exc
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _eval_expression(node.operand)
        return operand if isinstance(node.op, ast.UAdd) else -operand
    raise CobolExecutionError("Unsupported value in COMPUTE expression.")
