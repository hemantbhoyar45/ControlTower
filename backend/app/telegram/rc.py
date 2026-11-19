from dataclasses import dataclass


@dataclass(frozen=True)
class ReturnCodeInfo:
    code_str: str
    classification: str
    emoji: str
    description: str


def classify_return_code(rc: int | None) -> ReturnCodeInfo:
    if rc is None:
        return ReturnCodeInfo(
            code_str="RC ----",
            classification="UNKNOWN / RUNNING",
            emoji="⏳",
            description="Job is currently active or return code has not been set.",
        )
    if rc == 0:
        return ReturnCodeInfo(
            code_str="RC 0000",
            classification="SUCCESS",
            emoji="🟢",
            description="Normal completion. All steps executed successfully with zero errors.",
        )
    if rc == 4:
        return ReturnCodeInfo(
            code_str="RC 0004",
            classification="WARNING",
            emoji="🟡",
            description="Warning. Minor anomalies or acceptable conditions detected that do not prevent execution.",
        )
    if rc == 8:
        return ReturnCodeInfo(
            code_str="RC 0008",
            classification="CRITICAL ERROR",
            emoji="🔴",
            description="Critical Error. The JCL or job execution encounters a serious error that prevents successful processing.",
        )
    if rc == 12:
        return ReturnCodeInfo(
            code_str="RC 0012",
            classification="ADVANCED CRITICAL ERROR",
            emoji="🚨",
            description="Advanced Critical Error. Severe execution or system-level failure requiring special attention.",
        )
    if rc == 130:
        return ReturnCodeInfo(
            code_str="RC 0130",
            classification="CANCELLED",
            emoji="🛑",
            description="Operator or user cancelled job prior to or during execution.",
        )
    if rc < 4:
        return ReturnCodeInfo(
            code_str=f"RC {rc:04d}",
            classification="SUCCESS",
            emoji="🟢",
            description=f"Normal completion with return code {rc}.",
        )
    if rc < 8:
        return ReturnCodeInfo(
            code_str=f"RC {rc:04d}",
            classification="WARNING",
            emoji="🟡",
            description=f"Warning condition encountered with return code {rc}.",
        )
    if rc < 12:
        return ReturnCodeInfo(
            code_str=f"RC {rc:04d}",
            classification="CRITICAL ERROR",
            emoji="🔴",
            description=f"Critical error condition encountered with return code {rc}.",
        )
    return ReturnCodeInfo(
        code_str=f"RC {rc:04d}",
        classification="ADVANCED CRITICAL ERROR",
        emoji="🚨",
        description=f"Advanced critical failure encountered with return code {rc}.",
    )
