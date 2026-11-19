from datetime import datetime
import html
from typing import Any

from ..database.models import Dataset, Job
from .rc import classify_return_code


def escape(text: Any) -> str:
    return html.escape(str(text) if text is not None else "")


def format_duration(started_at: str | None, finished_at: str | None) -> str:
    if not started_at or not finished_at:
        return "—"
    try:
        start = datetime.fromisoformat(started_at)
        finish = datetime.fromisoformat(finished_at)
        delta = (finish - start).total_seconds()
        return f"{delta:.2f}s"
    except Exception:
        return "—"


def format_welcome(first_name: str) -> str:
    return (
        f"🏢 <b>Mainframe Control Tower</b>\n"
        f"<i>Batch Workload Monitoring & Operations Console</i>\n\n"
        f"Welcome, <b>{escape(first_name)}</b>!\n\n"
        f"Connect directly to your mainframe batch processing environment. "
        f"Monitor job executions, track return codes, inspect spool logs, and view system metrics.\n\n"
        f"<b>Available Commands:</b>\n"
        f"• /status – System status & engine health\n"
        f"• /jobs – List recent batch jobs\n"
        f"• /running – Show currently running jobs\n"
        f"• /failed – Show failed batch jobs\n"
        f"• /job <code>&lt;JOB_ID&gt;</code> – Inspect job details & steps\n"
        f"• /logs <code>&lt;JOB_ID&gt;</code> – View spool output & execution logs\n"
        f"• /datasets – List cataloged datasets\n"
        f"• /metrics – Batch throughput & execution metrics\n"
        f"• /rc – Return code classification guide\n"
        f"• /help – Full reference & usage instructions\n\n"
        f"👇 <i>Use the quick navigation menu below to get started:</i>"
    )


def format_help() -> str:
    return (
        f"📖 <b>Mainframe Control Tower — Bot Reference</b>\n\n"
        f"<b>System & Batch Commands:</b>\n"
        f"• <b>/status</b> — Real-time health check, GnuCOBOL engine status, and active workers.\n"
        f"• <b>/jobs</b> — Retrieve the 10 most recent batch jobs with their return codes.\n"
        f"• <b>/running</b> — Display jobs actively executing in the JES2 simulator queue.\n"
        f"• <b>/failed</b> — Filter jobs that ended with non-zero return codes or abends.\n"
        f"• <b>/job &lt;JOB_ID&gt;</b> — Step-by-step breakdown of programs and status.\n"
        f"• <b>/logs &lt;JOB_ID&gt;</b> — Full SYSOUT / SYSERR spool output.\n"
        f"• <b>/datasets</b> — View SQLite-persisted mainframe datasets and record counts.\n"
        f"• <b>/metrics</b> — Key execution metrics, success ratios, and average runtimes.\n"
        f"• <b>/rc</b> — Mainframe return-code classifications (RC 0000 to RC 0012).\n\n"
        f"<b>Interactive Features:</b>\n"
        f"Tap any button on the interactive keyboard to navigate without typing commands. "
        f"When a batch job completes or fails, an automated notification is dispatched to authorized operators."
    )


def format_rc_explanation() -> str:
    return (
        f"📋 <b>Mainframe Return Code Classifications</b>\n\n"
        f"In IBM z/OS and Mainframe batch processing, the following return-code "
        f"standards govern workload health:\n\n"
        f"🟢 <b>RC 0000 — SUCCESS</b>\n"
        f"Job completed with zero errors. All step conditions evaluated cleanly.\n\n"
        f"🟡 <b>RC 0004 — WARNING</b>\n"
        f"Completed with minor non-fatal warnings or informational anomalies. Review spool output if downstream jobs depend on specific record counts.\n\n"
        f"🔴 <b>RC 0008 — CRITICAL ERROR</b>\n"
        f"Job execution encountered an error condition. One or more steps failed, conditional branching was triggered, or expected inputs were invalid.\n\n"
        f"🚨 <b>RC 0012 — ADVANCED CRITICAL ERROR</b>\n"
        f"Severe failure or missing critical resource. Processing was halted immediately; manual remediation or restart required.\n\n"
        f"🛑 <b>RC 0130 — CANCELLED</b>\n"
        f"Batch job was cancelled by operator or scheduler prior to or during execution."
    )


def format_status(executor: str, gnucobol: bool, queue_depth: int, metrics: dict[str, Any]) -> str:
    compiler_status = "🟢 GnuCOBOL (Native Compiler)" if gnucobol else "🟡 Cobol Subset Interpreter (Fallback)"
    active = (metrics.get("running_jobs") or 0) + (metrics.get("queued_jobs") or 0)
    
    return (
        f"🖥️ <b>Mainframe Control Tower — System Status</b>\n\n"
        f"• <b>API Status:</b> 🟢 Operational\n"
        f"• <b>COBOL Engine:</b> <code>{escape(executor)}</code>\n"
        f"• <b>Execution Mode:</b> {compiler_status}\n"
        f"• <b>Queue Depth:</b> <code>{queue_depth}</code> pending\n"
        f"• <b>Active Workloads:</b> <code>{active}</code> (Running: {metrics.get('running_jobs', 0)}, Queued: {metrics.get('queued_jobs', 0)})\n"
        f"• <b>Lifetime Jobs:</b> <code>{metrics.get('total_jobs', 0)}</code> total\n"
        f"• <b>Completed:</b> <code>{metrics.get('completed_jobs', 0)}</code> | <b>Failed:</b> <code>{metrics.get('failed_jobs', 0)}</code>"
    )


def format_jobs_list(jobs: list[Job], title: str = "Recent Batch Jobs") -> str:
    if not jobs:
        return f"📋 <b>{escape(title)}</b>\n\n<i>No batch jobs found.</i>"
    
    lines = [f"📋 <b>{escape(title)}</b> (Latest {len(jobs)})\n"]
    for idx, job in enumerate(jobs, start=1):
        rc_info = classify_return_code(job.return_code)
        status_badge = {
            "completed": "🟢 DONE",
            "failed": "🔴 FAIL",
            "running": "🟡 RUN",
            "queued": "⚪ QUEUED",
            "cancelled": "🛑 CANCEL",
        }.get(job.status, f"⚪ {job.status.upper()}")
        
        created = job.created_at[:19].replace("T", " ") if job.created_at else "—"
        dur = format_duration(job.started_at, job.finished_at)
        
        lines.append(
            f"<b>{idx}. {escape(job.name)}</b> | {status_badge} | <code>{rc_info.code_str}</code>\n"
            f"   ID: <code>{job.id}</code>\n"
            f"   Time: {created} (Dur: {dur})\n"
        )
    lines.append("<i>Tap a job button below or use <code>/job &lt;ID&gt;</code> for full details.</i>")
    return "\n".join(lines)


def format_job_detail(job: Job) -> str:
    rc_info = classify_return_code(job.return_code)
    dur = format_duration(job.started_at, job.finished_at)
    created = job.created_at.replace("T", " ") if job.created_at else "—"
    started = job.started_at.replace("T", " ") if job.started_at else "—"
    finished = job.finished_at.replace("T", " ") if job.finished_at else "—"

    # Identify primary program(s)
    programs = ", ".join({step.program for step in job.steps}) or "—"

    step_lines = []
    for step in job.steps:
        s_rc = classify_return_code(step.return_code)
        s_icon = "🟢" if step.status == "completed" else "🔴" if step.status == "failed" else "⚪"
        step_lines.append(
            f"  {s_icon} <b>{escape(step.name)}</b> (PGM: <code>{escape(step.program)}</code>) → "
            f"<code>{s_rc.code_str}</code> [{escape(step.status)}]"
        )

    steps_text = "\n".join(step_lines) if step_lines else "  <i>No steps registered</i>"

    return (
        f"⚙️ <b>Job Details: {escape(job.name)}</b>\n\n"
        f"• <b>Job ID:</b> <code>{job.id}</code>\n"
        f"• <b>Status:</b> <b>{job.status.upper()}</b>\n"
        f"• <b>Return Code:</b> {rc_info.emoji} <b>{rc_info.code_str}</b> ({rc_info.classification})\n"
        f"• <b>Program(s):</b> <code>{escape(programs)}</code>\n"
        f"• <b>Duration:</b> {dur}\n"
        f"• <b>Created:</b> {created}\n"
        f"• <b>Started:</b> {started}\n"
        f"• <b>Finished:</b> {finished}\n\n"
        f"<b>Step Execution:</b>\n{steps_text}\n"
    )


def format_job_spool(job: Job) -> str:
    header = (
        f"📜 <b>Spool Logs: {escape(job.name)}</b>\n"
        f"Job ID: <code>{job.id}</code> | Status: <b>{job.status.upper()}</b>\n\n"
    )

    combined_output = ""
    if job.stdout:
        combined_output += f"--- SYSOUT ---\n{job.stdout}\n"
    if job.stderr:
        combined_output += f"--- SYSERR ---\n{job.stderr}\n"

    for step in job.steps:
        if step.stdout:
            combined_output += f"\n[{step.name} - {step.program} STDOUT]\n{step.stdout}"
        if step.stderr:
            combined_output += f"\n[{step.name} - {step.program} STDERR]\n{step.stderr}"

    if not combined_output.strip():
        combined_output = "No spool or console output recorded for this job."

    # Max Telegram text size is 4096; allow room for header and tags
    max_log_len = 3500
    if len(combined_output) > max_log_len:
        combined_output = (
            combined_output[:max_log_len]
            + f"\n\n[... Truncated, total length {len(combined_output)} characters ...]"
        )

    return f"{header}<pre><code>{escape(combined_output)}</code></pre>"


def format_datasets(datasets: list[Dataset]) -> str:
    if not datasets:
        return "🏷️ <b>Cataloged Datasets</b>\n\n<i>No datasets currently registered.</i>"

    lines = [f"🏷️ <b>Cataloged Datasets</b> ({len(datasets)} total)\n"]
    for idx, ds in enumerate(datasets, start=1):
        updated = ds.updated_at[:19].replace("T", " ") if ds.updated_at else "—"
        lines.append(
            f"<b>{idx}. {escape(ds.name)}</b>\n"
            f"   Org: <code>{escape(ds.organization)}</code> | Records: <code>{ds.record_count}</code>\n"
            f"   Updated: {updated}\n"
        )
    return "\n".join(lines)


def format_metrics(metrics: dict[str, Any], queue_depth: int) -> str:
    total = metrics.get("total_jobs") or 0
    completed = metrics.get("completed_jobs") or 0
    failed = metrics.get("failed_jobs") or 0
    cancelled = metrics.get("cancelled_jobs") or 0
    running = metrics.get("running_jobs") or 0
    queued = metrics.get("queued_jobs") or 0
    terminal = completed + failed + cancelled
    success_rate = (completed / terminal * 100) if terminal else 0.0

    db_bytes = metrics.get("database_bytes") or 0
    db_kb = db_bytes / 1024

    return (
        f"📈 <b>Mainframe Batch Execution Metrics</b>\n\n"
        f"• <b>Total Jobs Processed:</b> <code>{total}</code>\n"
        f"• <b>Success Rate:</b> <b>{success_rate:.1f}%</b>\n"
        f"• <b>Completed Jobs:</b> 🟢 <code>{completed}</code>\n"
        f"• <b>Failed Jobs:</b> 🔴 <code>{failed}</code>\n"
        f"• <b>Cancelled Jobs:</b> 🛑 <code>{cancelled}</code>\n"
        f"• <b>Active Workers:</b> ⚡ <code>{running}</code> running, <code>{queued}</code> queued\n"
        f"• <b>Queue Depth:</b> <code>{queue_depth}</code> pending in JES2\n"
        f"• <b>Database Size:</b> <code>{db_kb:.1f} KB</code>\n"
    )


def format_job_completion_notification(job: Job) -> str:
    rc_info = classify_return_code(job.return_code)
    dur = format_duration(job.started_at, job.finished_at)
    programs = ", ".join({step.program for step in job.steps}) or "—"
    
    # Execution summary
    summary_parts = []
    if job.status == "completed":
        summary_parts.append(f"Successfully finished {len(job.steps)} step(s).")
    elif job.status == "failed":
        failed_step = next((s for s in job.steps if s.status == "failed"), None)
        if failed_step:
            err = failed_step.stderr.strip().split("\n")[0] if failed_step.stderr else "Non-zero return code"
            summary_parts.append(f"Step {failed_step.name} failed: {err}")
        else:
            err = job.stderr.strip().split("\n")[0] if job.stderr else "Job execution failed"
            summary_parts.append(err)
    elif job.status == "cancelled":
        summary_parts.append("Execution cancelled by operator.")
    else:
        summary_parts.append(f"Job status: {job.status}")

    summary = " ".join(summary_parts)

    return (
        f"{rc_info.emoji} <b>Mainframe Job Notification: {escape(job.name)}</b>\n\n"
        f"• <b>Job ID:</b> <code>{job.id}</code>\n"
        f"• <b>Job Name:</b> <b>{escape(job.name)}</b>\n"
        f"• <b>Program:</b> <code>{escape(programs)}</code>\n"
        f"• <b>Return Code:</b> <b>{rc_info.code_str} – {rc_info.classification}</b>\n"
        f"• <b>Status:</b> <b>{job.status.upper()}</b>\n"
        f"• <b>Execution Time:</b> {dur}\n"
        f"• <b>Summary:</b> <i>{escape(summary)}</i>\n"
    )


def format_access_denied(user_id: int) -> str:
    return (
        f"⛔ <b>Access Denied</b>\n\n"
        f"Your Telegram User ID is: <code>{user_id}</code>\n\n"
        f"You are not authorized to access Mainframe Control Tower. "
        f"To request access, please contact your system administrator and provide your User ID to be added to <code>ADMIN_TELEGRAM_IDS</code>."
    )
