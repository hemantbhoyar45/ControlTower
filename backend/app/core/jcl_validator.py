from dataclasses import dataclass, field
import re
from typing import Any

from .cobol_executor import CobolExecutor
from .jcl_parser import JCLDD, JCLStep, ParsedJCL
from ..database.connection import Database


_NAME_RE = re.compile(r"^[A-Z0-9@$#-]{1,8}$", re.IGNORECASE)
_STMT_RE = re.compile(
    r"^//(?P<name>[A-Z0-9@$#-]{1,8})\s+(?P<operation>JOB|EXEC|DD)\b(?P<operands>.*)$",
    re.IGNORECASE,
)
_PGM_RE = re.compile(r"(?:^|,)\s*PGM\s*=\s*['\"]?([A-Z0-9@$#-]{1,8})", re.IGNORECASE)
_DSN_RE = re.compile(
    r"(?:^|,)\s*DSN\s*=\s*(?:'([^']+)'|\"([^\"]+)\"|([^,\s]+))",
    re.IGNORECASE,
)
_INLINE_RE = re.compile(r"^\s*(?:\*|DATA)\s*(?:,|$)", re.IGNORECASE)


@dataclass(slots=True)
class ValidationDiagnostic:
    severity: str  # "error" | "warning" | "info"
    rule: str
    message: str
    statement: str | None = None
    line_number: int | None = None


@dataclass(slots=True)
class ValidationResult:
    is_valid: bool
    job_name: str | None = None
    steps: list[JCLStep] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    diagnostics: list[ValidationDiagnostic] = field(default_factory=list)
    structure_summary: str = ""

    @property
    def parsed(self) -> ParsedJCL | None:
        if self.is_valid and self.job_name:
            return ParsedJCL(job_name=self.job_name, steps=self.steps)
        return None


def validate_jcl_content(
    content: str,
    executor: CobolExecutor | None = None,
    database: Database | None = None,
) -> ValidationResult:
    diagnostics: list[ValidationDiagnostic] = []
    errors: list[str] = []
    warnings: list[str] = []

    if not content or not content.strip():
        msg = "JCL content is empty."
        errors.append(msg)
        diagnostics.append(ValidationDiagnostic("error", "STRUCTURE", msg))
        return ValidationResult(
            is_valid=False,
            errors=errors,
            warnings=warnings,
            diagnostics=diagnostics,
            structure_summary="Empty JCL submission.",
        )

    lines = content.splitlines()
    job_name: str | None = None
    steps: list[JCLStep] = []
    current_step: JCLStep | None = None
    step_names: set[str] = set()
    has_sysout: bool = False
    index = 0

    while index < len(lines):
        line_num = index + 1
        raw_line = lines[index]
        line = raw_line.rstrip()
        index += 1

        if not line.strip():
            continue

        if line.startswith("//*"):
            # Comment line
            continue

        if not line.startswith("//"):
            msg = f"Line {line_num}: Unexpected non-JCL line outside inline DD stream: {line[:60]}"
            errors.append(msg)
            diagnostics.append(
                ValidationDiagnostic("error", "SYNTAX_PREFIX", msg, statement=line, line_number=line_num)
            )
            continue

        match = _STMT_RE.match(line)
        if match is None:
            if line.strip() == "//":
                # End of JCL stream delimiter
                continue
            msg = f"Line {line_num}: Malformed or unsupported JCL statement: {line[:60]}"
            errors.append(msg)
            diagnostics.append(
                ValidationDiagnostic("error", "SYNTAX_MALFORMED", msg, statement=line, line_number=line_num)
            )
            continue

        name = match.group("name").upper()
        operation = match.group("operation").upper()
        operands = match.group("operands").strip()

        if not _NAME_RE.match(name):
            msg = f"Line {line_num}: Statement name '{name}' is invalid (must be 1-8 alphanumeric/@#$ characters)."
            errors.append(msg)
            diagnostics.append(
                ValidationDiagnostic("error", "NAME_SYNTAX", msg, statement=line, line_number=line_num)
            )

        if operation == "JOB":
            if job_name is not None:
                msg = f"Line {line_num}: Multiple JOB statements detected. Only one JOB statement permitted per submission."
                errors.append(msg)
                diagnostics.append(
                    ValidationDiagnostic("error", "SINGLE_JOB", msg, statement=line, line_number=line_num)
                )
            else:
                job_name = name
                if not operands:
                    msg = f"Line {line_num}: JOB statement '{name}' must include accounting parameters."
                    errors.append(msg)
                    diagnostics.append(
                        ValidationDiagnostic("error", "JOB_OPERANDS", msg, statement=line, line_number=line_num)
                    )
                else:
                    diagnostics.append(
                        ValidationDiagnostic(
                            "info",
                            "JOB_DECLARED",
                            f"Valid JOB statement '{name}' declared with parameters: {operands[:40]}",
                            statement=line,
                            line_number=line_num,
                        )
                    )

        elif operation == "EXEC":
            if job_name is None:
                msg = f"Line {line_num}: EXEC statement '{name}' appears before a JOB statement."
                errors.append(msg)
                diagnostics.append(
                    ValidationDiagnostic("error", "ORDER_JOB_FIRST", msg, statement=line, line_number=line_num)
                )

            pgm_match = _PGM_RE.search(operands)
            if pgm_match is None:
                msg = f"Line {line_num}: EXEC step '{name}' must specify program via PGM=program_name."
                errors.append(msg)
                diagnostics.append(
                    ValidationDiagnostic("error", "EXEC_PGM", msg, statement=line, line_number=line_num)
                )
            else:
                program = pgm_match.group(1).upper()
                if not _NAME_RE.match(program):
                    msg = f"Line {line_num}: Program name '{program}' in step '{name}' is invalid."
                    errors.append(msg)
                    diagnostics.append(
                        ValidationDiagnostic("error", "PGM_NAME", msg, statement=line, line_number=line_num)
                    )

                if name in step_names:
                    msg = f"Line {line_num}: Duplicate step name '{name}' detected."
                    errors.append(msg)
                    diagnostics.append(
                        ValidationDiagnostic("error", "DUPLICATE_STEP", msg, statement=line, line_number=line_num)
                    )
                step_names.add(name)

                current_step = JCLStep(name=name, program=program)
                steps.append(current_step)
                diagnostics.append(
                    ValidationDiagnostic(
                        "info",
                        "STEP_DECLARED",
                        f"Step '{name}' configured to execute PGM={program}",
                        statement=line,
                        line_number=line_num,
                    )
                )

                # Check program availability if executor provided
                if executor is not None:
                    available_programs = set(executor.list_programs())
                    if program not in available_programs:
                        msg = f"Line {line_num}: COBOL program '{program}' is not in the approved library."
                        errors.append(msg)
                        diagnostics.append(
                            ValidationDiagnostic("error", "PROGRAM_NOT_FOUND", msg, statement=line, line_number=line_num)
                        )

        elif operation == "DD":
            if current_step is None:
                msg = f"Line {line_num}: DD statement '{name}' must follow an EXEC statement."
                errors.append(msg)
                diagnostics.append(
                    ValidationDiagnostic("error", "DD_WITHOUT_EXEC", msg, statement=line, line_number=line_num)
                )
                continue

            if name.upper() in {"SYSOUT", "SYSPRINT"}:
                has_sysout = True

            dsn_match = _DSN_RE.search(operands)
            dataset = (
                next(val for val in dsn_match.groups() if val is not None).upper()
                if dsn_match
                else None
            )

            dd = JCLDD(name=name, dataset=dataset)
            current_step.datasets.append(dd)

            if _INLINE_RE.match(operands):
                # Consume inline data until /*
                start_line = index
                inline_found = False
                while index < len(lines):
                    if lines[index].strip() == "/*":
                        inline_found = True
                        index += 1
                        break
                    dd.inline_data.append(lines[index])
                    index += 1

                if not inline_found:
                    msg = f"Line {line_num}: Inline stream for DD '{name}' is missing closing '/*' delimiter."
                    errors.append(msg)
                    diagnostics.append(
                        ValidationDiagnostic("error", "MISSING_DELIMITER", msg, statement=line, line_number=line_num)
                    )
                else:
                    diagnostics.append(
                        ValidationDiagnostic(
                            "info",
                            "INLINE_DD",
                            f"DD '{name}' captured {len(dd.inline_data)} inline record(s).",
                            statement=line,
                            line_number=line_num,
                        )
                    )

            # Check dataset reference in SQLite if SYSIN DD DSN=...
            if name.upper() == "SYSIN" and dataset and database is not None:
                if database.get_dataset(dataset) is None:
                    msg = f"Line {line_num}: Referenced SYSIN dataset '{dataset}' does not exist in SQLite catalog."
                    errors.append(msg)
                    diagnostics.append(
                        ValidationDiagnostic("error", "DATASET_NOT_FOUND", msg, statement=line, line_number=line_num)
                    )

    if job_name is None:
        msg = "Missing required JOB statement."
        errors.append(msg)
        diagnostics.append(ValidationDiagnostic("error", "MISSING_JOB", msg))

    if not steps:
        msg = "At least one EXEC PGM step is required."
        errors.append(msg)
        diagnostics.append(ValidationDiagnostic("error", "MISSING_EXEC", msg))

    if steps and not has_sysout:
        msg = "No SYSOUT/SYSPRINT DD statement detected; step stdout may not be routed to standard spool."
        warnings.append(msg)
        diagnostics.append(ValidationDiagnostic("warning", "SPOOL_ROUTING", msg))

    is_valid = len(errors) == 0
    total_dd = sum(len(step.datasets) for step in steps)
    if is_valid:
        structure_summary = (
            f"Valid JCL syntax: 1 JOB ({job_name}), {len(steps)} EXEC step(s), {total_dd} DD statement(s)."
        )
    else:
        structure_summary = f"Validation failed with {len(errors)} error(s) and {len(warnings)} warning(s)."

    return ValidationResult(
        is_valid=is_valid,
        job_name=job_name,
        steps=steps,
        errors=errors,
        warnings=warnings,
        diagnostics=diagnostics,
        structure_summary=structure_summary,
    )
