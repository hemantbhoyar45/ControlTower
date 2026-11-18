import re
from dataclasses import dataclass, field


_STATEMENT = re.compile(
    r"^//(?P<name>[A-Z0-9@$#-]{1,8})\s+(?P<operation>JOB|EXEC|DD)\b(?P<operands>.*)$",
    re.IGNORECASE,
)
_JOB_NAME = re.compile(r"^//(?P<name>[A-Z0-9@$#-]{1,8})\s+JOB\b", re.IGNORECASE)
_PROGRAM = re.compile(r"(?:^|,)\s*PGM\s*=\s*['\"]?([A-Z0-9@$#-]{1,8})", re.IGNORECASE)
_DATASET = re.compile(
    r"(?:^|,)\s*DSN\s*=\s*(?:'([^']+)'|\"([^\"]+)\"|([^,\s]+))",
    re.IGNORECASE,
)
_INLINE_DD = re.compile(r"^\s*(?:\*|DATA)\s*(?:,|$)", re.IGNORECASE)


@dataclass(slots=True)
class JCLDD:
    name: str
    dataset: str | None = None
    inline_data: list[str] = field(default_factory=list)


@dataclass(slots=True)
class JCLStep:
    name: str
    program: str
    datasets: list[JCLDD] = field(default_factory=list)


@dataclass(slots=True)
class ParsedJCL:
    job_name: str
    steps: list[JCLStep]


def parse_jcl(content: str) -> ParsedJCL:
    """Parse the named JOB, EXEC PGM, and DD subset accepted by this service."""
    if not content.strip():
        raise ValueError("JCL content must not be empty.")

    job_name: str | None = None
    steps: list[JCLStep] = []
    current_step: JCLStep | None = None
    lines = content.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip():
            continue
        if line.startswith("//*"):
            continue
        if not line.startswith("//"):
            raise ValueError(f"Unexpected non-JCL line outside inline DD data: {line[:80]}")

        statement = _STATEMENT.match(line)
        if statement is None:
            if line.strip() == "//":
                continue
            raise ValueError(f"Unsupported or malformed JCL statement: {line[:80]}")

        name = statement.group("name").upper()
        operation = statement.group("operation").upper()
        operands = statement.group("operands").strip()

        if operation == "JOB":
            if job_name is not None:
                raise ValueError("Only one JOB statement is supported per submission.")
            if not operands:
                raise ValueError("The JOB statement must include job parameters.")
            job_name = name
        elif operation == "EXEC":
            if job_name is None:
                raise ValueError("The JOB statement must appear before EXEC statements.")
            program_match = _PROGRAM.search(operands)
            if program_match is None:
                raise ValueError(f"EXEC statement {name} must specify PGM=program.")
            current_step = JCLStep(name=name, program=program_match.group(1).upper())
            if any(step.name == name for step in steps):
                raise ValueError(f"Duplicate step name: {name}")
            steps.append(current_step)
        elif operation == "DD":
            if current_step is None:
                raise ValueError("Each DD statement must follow an EXEC statement.")
            dataset_match = _DATASET.search(operands)
            dataset = (
                next(value for value in dataset_match.groups() if value is not None).upper()
                if dataset_match
                else None
            )
            dd = JCLDD(name=name, dataset=dataset)
            current_step.datasets.append(dd)
            if _INLINE_DD.match(operands):
                while index < len(lines) and lines[index].strip() != "/*":
                    dd.inline_data.append(lines[index])
                    index += 1
                if index == len(lines):
                    raise ValueError(f"Inline data for DD {name} is missing its /* terminator.")
                index += 1

    if job_name is None:
        raise ValueError("A named JOB statement is required.")
    if not steps:
        raise ValueError("At least one EXEC PGM step is required.")
    return ParsedJCL(job_name=job_name, steps=steps)
