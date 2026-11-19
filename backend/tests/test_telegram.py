import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram import CallbackQuery, Message, Update, User

from app.database.connection import Database
from app.database.models import Dataset, DatasetDetail, Job, JobStep
from app.core.cobol_executor import CobolExecutor
from app.core.job_scheduler import JobScheduler
from app.services.dataset_service import DatasetService
from app.telegram.formatters import (
    escape,
    format_access_denied,
    format_datasets,
    format_help,
    format_job_completion_notification,
    format_job_detail,
    format_job_spool,
    format_jobs_list,
    format_metrics,
    format_rc_explanation,
    format_status,
    format_welcome,
)
from app.telegram.handlers import BotHandlers
from app.telegram.notifier import TelegramNotifier
from app.telegram.rc import classify_return_code


def make_mock_user(user_id: int = 12345, first_name: str = "TestUser") -> User:
    user = MagicMock(spec=User)
    user.id = user_id
    user.first_name = first_name
    return user


def make_mock_update(user_id: int = 12345, text: str = "/start") -> Update:
    update = MagicMock(spec=Update)
    update.effective_user = make_mock_user(user_id)
    message = MagicMock(spec=Message)
    message.reply_text = AsyncMock()
    message.text = text
    update.message = message
    update.callback_query = None
    return update


def make_mock_callback_update(user_id: int = 12345, data: str = "cb:status") -> Update:
    update = MagicMock(spec=Update)
    update.effective_user = make_mock_user(user_id)
    query = MagicMock(spec=CallbackQuery)
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    update.message = None
    return update


# 1. Return Code Classifications
def test_rc_classifications() -> None:
    rc0 = classify_return_code(0)
    assert rc0.code_str == "RC 0000"
    assert rc0.classification == "SUCCESS"
    assert "🟢" in rc0.emoji

    rc4 = classify_return_code(4)
    assert rc4.code_str == "RC 0004"
    assert rc4.classification == "WARNING"
    assert "🟡" in rc4.emoji

    rc8 = classify_return_code(8)
    assert rc8.code_str == "RC 0008"
    assert rc8.classification == "CRITICAL ERROR"
    assert "🔴" in rc8.emoji

    rc12 = classify_return_code(12)
    assert rc12.code_str == "RC 0012"
    assert rc12.classification == "ADVANCED CRITICAL ERROR"
    assert "🚨" in rc12.emoji

    rc130 = classify_return_code(130)
    assert rc130.code_str == "RC 0130"
    assert rc130.classification == "CANCELLED"

    rc_none = classify_return_code(None)
    assert rc_none.code_str == "RC ----"
    assert "UNKNOWN" in rc_none.classification


# 2. Text Formatters
def test_formatters() -> None:
    welcome = format_welcome("Alex")
    assert "Alex" in welcome
    assert "Mainframe Control Tower" in welcome

    help_text = format_help()
    assert "/status" in help_text
    assert "/jobs" in help_text
    assert "/logs" in help_text

    rc_guide = format_rc_explanation()
    assert "RC 0000" in rc_guide
    assert "RC 0004" in rc_guide
    assert "RC 0008" in rc_guide
    assert "RC 0012" in rc_guide

    denied = format_access_denied(99999)
    assert "99999" in denied
    assert "Access Denied" in denied


def test_job_and_spool_formatters() -> None:
    step = JobStep(
        id=1,
        job_id="test-job-id",
        name="STEP01",
        program="INCR",
        position=0,
        status="completed",
        return_code=0,
        stdout="NEXT COUNT: 0042\n",
        stderr="",
        executor="gnucobol",
        started_at="2026-11-19T05:00:00+00:00",
        finished_at="2026-11-19T05:00:02+00:00",
    )
    job = Job(
        id="test-job-id",
        name="INCRJOB",
        status="completed",
        jcl="//INCRJOB JOB\n//STEP01 EXEC PGM=INCR\n",
        created_at="2026-11-19T04:59:59+00:00",
        started_at="2026-11-19T05:00:00+00:00",
        finished_at="2026-11-19T05:00:02+00:00",
        return_code=0,
        stdout="== STEP01 (INCR) ==\nNEXT COUNT: 0042\n",
        stderr="",
        steps=[step],
    )

    detail = format_job_detail(job)
    assert "INCRJOB" in detail
    assert "test-job-id" in detail
    assert "RC 0000" in detail
    assert "SUCCESS" in detail

    spool = format_job_spool(job)
    assert "NEXT COUNT: 0042" in spool
    assert "--- SYSOUT ---" in spool


def test_long_log_truncation() -> None:
    huge_stdout = "X" * 5000
    job = Job(
        id="huge-job",
        name="HUGE",
        status="completed",
        jcl="",
        created_at="2026-11-19T05:00:00+00:00",
        started_at="2026-11-19T05:00:00+00:00",
        finished_at="2026-11-19T05:00:01+00:00",
        return_code=0,
        stdout=huge_stdout,
        stderr="",
        steps=[],
    )
    spool = format_job_spool(job)
    assert "Truncated" in spool
    assert len(spool) < 4096


# 3. Security and Access Control
def test_security_access_control(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        # Only allow user 11111
        monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "11111,22222")

        mock_db = MagicMock(spec=Database)
        mock_sched = MagicMock(spec=JobScheduler)
        mock_exec = MagicMock(spec=CobolExecutor)
        mock_ds = MagicMock(spec=DatasetService)
        mock_notif = MagicMock(spec=TelegramNotifier)

        handlers = BotHandlers(mock_db, mock_sched, mock_exec, mock_ds, mock_notif)

        # Unauthorized user 99999
        update_unauth = make_mock_update(user_id=99999, text="/jobs")
        await handlers.jobs_command(update_unauth, MagicMock())

        update_unauth.message.reply_text.assert_called_once()
        reply_args = update_unauth.message.reply_text.call_args[1]
        assert "Access Denied" in reply_args["text"]
        assert "99999" in reply_args["text"]
        mock_db.list_jobs.assert_not_called()

        # Authorized user 11111
        mock_db.list_jobs.return_value = ([], 0)
        update_auth = make_mock_update(user_id=11111, text="/jobs")
        await handlers.jobs_command(update_auth, MagicMock())
        mock_db.list_jobs.assert_called_once()

    asyncio.run(_run())


# 4. Command Handlers
def test_command_handlers(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "*")

        mock_db = MagicMock(spec=Database)
        mock_sched = MagicMock(spec=JobScheduler)
        mock_sched.queue_depth = 0
        mock_exec = MagicMock(spec=CobolExecutor)
        mock_exec.engine_name = "gnucobol"
        mock_exec.compiler = "/usr/bin/cobc"
        mock_ds = MagicMock(spec=DatasetService)
        mock_notif = MagicMock(spec=TelegramNotifier)

        handlers = BotHandlers(mock_db, mock_sched, mock_exec, mock_ds, mock_notif)

        # /start
        update = make_mock_update(12345, "/start")
        await handlers.start(update, MagicMock())
        update.message.reply_text.assert_called_once()
        assert "Mainframe Control Tower" in update.message.reply_text.call_args[1]["text"]

        # /help
        update = make_mock_update(12345, "/help")
        await handlers.help_command(update, MagicMock())
        assert "/status" in update.message.reply_text.call_args[1]["text"]

        # /status
        mock_db.system_metrics.return_value = {
            "total_jobs": 10,
            "running_jobs": 1,
            "queued_jobs": 0,
            "completed_jobs": 8,
            "failed_jobs": 1,
        }
        update = make_mock_update(12345, "/status")
        await handlers.status_command(update, MagicMock())
        assert "Operational" in update.message.reply_text.call_args[1]["text"]

        # /rc
        update = make_mock_update(12345, "/rc")
        await handlers.rc_command(update, MagicMock())
        assert "RC 0000 — SUCCESS" in update.message.reply_text.call_args[1]["text"]

        # /failed
        job_failed = Job(
            id="failed-id-1",
            name="BADJOB",
            status="failed",
            jcl="",
            created_at="2026-11-19T05:00:00+00:00",
            started_at="2026-11-19T05:00:00+00:00",
            finished_at="2026-11-19T05:00:01+00:00",
            return_code=8,
            stdout="",
            stderr="Step failed with RC 8",
            steps=[],
        )
        mock_db.list_jobs.return_value = ([job_failed], 1)
        update = make_mock_update(12345, "/failed")
        await handlers.failed_command(update, MagicMock())
        assert "BADJOB" in update.message.reply_text.call_args[1]["text"]
        assert "RC 0008" in update.message.reply_text.call_args[1]["text"]

    asyncio.run(_run())


# 5. Interactive Callback Queries
def test_callback_query_navigation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "*")

        mock_db = MagicMock(spec=Database)
        mock_sched = MagicMock(spec=JobScheduler)
        mock_sched.queue_depth = 2
        mock_exec = MagicMock(spec=CobolExecutor)
        mock_exec.engine_name = "gnucobol"
        mock_exec.compiler = "/usr/bin/cobc"
        mock_ds = MagicMock(spec=DatasetService)
        mock_notif = MagicMock(spec=TelegramNotifier)

        handlers = BotHandlers(mock_db, mock_sched, mock_exec, mock_ds, mock_notif)

        # Click 'cb:status'
        mock_db.system_metrics.return_value = {
            "total_jobs": 5,
            "running_jobs": 0,
            "queued_jobs": 0,
            "completed_jobs": 5,
            "failed_jobs": 0,
        }
        update = make_mock_callback_update(12345, "cb:status")
        await handlers.callback_query(update, MagicMock())
        update.callback_query.edit_message_text.assert_called_once()
        assert "Operational" in update.callback_query.edit_message_text.call_args[1]["text"]

        # Click 'cb:job:<id>'
        sample_job = Job(
            id="job-abc",
            name="PAYROLL",
            status="completed",
            jcl="",
            created_at="2026-11-19T05:00:00+00:00",
            started_at="2026-11-19T05:00:00+00:00",
            finished_at="2026-11-19T05:00:01+00:00",
            return_code=0,
            stdout="PAYROLL RUN OK\n",
            stderr="",
            steps=[],
        )
        mock_db.get_job.return_value = sample_job
        update = make_mock_callback_update(12345, "cb:job:job-abc")
        await handlers.callback_query(update, MagicMock())
        assert "PAYROLL" in update.callback_query.edit_message_text.call_args[1]["text"]

    asyncio.run(_run())


# 6. Notification System and Deduplication
def test_notification_deduplication() -> None:
    async def _run() -> None:
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()

        notifier = TelegramNotifier(mock_bot)
        notifier.register_chat_id(123456)

        job = Job(
            id="notify-job-1",
            name="NIGHTLY",
            status="completed",
            jcl="",
            created_at="2026-11-19T05:00:00+00:00",
            started_at="2026-11-19T05:00:00+00:00",
            finished_at="2026-11-19T05:00:05+00:00",
            return_code=0,
            stdout="DONE",
            stderr="",
            steps=[],
        )

        # First trigger: message should be sent
        await notifier.notify_job_completed(job, admin_ids={123456})
        assert mock_bot.send_message.call_count == 1
        call_args = mock_bot.send_message.call_args[1]
        assert "RC 0000 – SUCCESS" in call_args["text"]
        assert "NIGHTLY" in call_args["text"]

        # Second trigger with same event: duplicate should be prevented
        await notifier.notify_job_completed(job, admin_ids={123456})
        assert mock_bot.send_message.call_count == 1

    asyncio.run(_run())


# 7. Notification for Warning / Error / Critical
def test_notification_return_codes() -> None:
    async def _run() -> None:
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        notifier = TelegramNotifier(mock_bot)

        # RC 0004 Warning
        job_warn = Job(
            id="job-warn",
            name="WARN01",
            status="completed",
            jcl="",
            created_at="2026-11-19T05:00:00+00:00",
            started_at="2026-11-19T05:00:00+00:00",
            finished_at="2026-11-19T05:00:02+00:00",
            return_code=4,
            stdout="",
            stderr="",
            steps=[],
        )
        await notifier.notify_job_completed(job_warn, admin_ids={111})
        assert "RC 0004 – WARNING" in mock_bot.send_message.call_args[1]["text"]

        # RC 0008 Error
        job_err = Job(
            id="job-err",
            name="ERR01",
            status="failed",
            jcl="",
            created_at="2026-11-19T05:00:00+00:00",
            started_at="2026-11-19T05:00:00+00:00",
            finished_at="2026-11-19T05:00:02+00:00",
            return_code=8,
            stdout="",
            stderr="File not found",
            steps=[],
        )
        await notifier.notify_job_completed(job_err, admin_ids={111})
        assert "RC 0008 – CRITICAL ERROR" in mock_bot.send_message.call_args[1]["text"]

        # RC 0012 Critical
        job_crit = Job(
            id="job-crit",
            name="CRIT01",
            status="failed",
            jcl="",
            created_at="2026-11-19T05:00:00+00:00",
            started_at="2026-11-19T05:00:00+00:00",
            finished_at="2026-11-19T05:00:02+00:00",
            return_code=12,
            stdout="",
            stderr="Severe system abend",
            steps=[],
        )
        await notifier.notify_job_completed(job_crit, admin_ids={111})
        assert "RC 0012 – ADVANCED CRITICAL ERROR" in mock_bot.send_message.call_args[1]["text"]

    asyncio.run(_run())


# 8. Backend / Database Error Resilience
def test_database_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _run() -> None:
        monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "*")

        mock_db = MagicMock(spec=Database)
        mock_db.list_jobs.side_effect = RuntimeError("Database locked or connection failed")
        mock_sched = MagicMock(spec=JobScheduler)
        mock_exec = MagicMock(spec=CobolExecutor)
        mock_ds = MagicMock(spec=DatasetService)
        mock_notif = MagicMock(spec=TelegramNotifier)

        handlers = BotHandlers(mock_db, mock_sched, mock_exec, mock_ds, mock_notif)

        update = make_mock_update(12345, "/jobs")
        # Should not throw unhandled exception
        await handlers.jobs_command(update, MagicMock())
        reply_text = update.message.reply_text.call_args[1]["text"]
        assert "Unable to query batch jobs from database" in reply_text

    asyncio.run(_run())
