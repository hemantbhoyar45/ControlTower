import logging
from typing import Any

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from ..config import is_telegram_user_authorized
from ..database.connection import Database
from ..services.dataset_service import DatasetService
from ..core.job_scheduler import JobScheduler
from ..core.cobol_executor import CobolExecutor
from .formatters import (
    escape,
    format_access_denied,
    format_datasets,
    format_help,
    format_job_detail,
    format_job_spool,
    format_jobs_list,
    format_metrics,
    format_rc_explanation,
    format_status,
    format_welcome,
)
from .keyboards import (
    back_to_menu_keyboard,
    job_detail_keyboard,
    jobs_list_keyboard,
    logs_selection_keyboard,
    main_menu_keyboard,
)
from .notifier import TelegramNotifier

logger = logging.getLogger(__name__)


def check_auth(update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False
    return is_telegram_user_authorized(user.id)


async def handle_unauthorized(update: Update) -> None:
    user = update.effective_user
    user_id = user.id if user else 0
    text = format_access_denied(user_id)
    if update.callback_query:
        await update.callback_query.answer("Access Denied", show_alert=True)
        try:
            await update.callback_query.edit_message_text(text=text, parse_mode="HTML")
        except TelegramError:
            pass
    elif update.message:
        await update.message.reply_text(text=text, parse_mode="HTML")


class BotHandlers:
    def __init__(
        self,
        database: Database,
        scheduler: JobScheduler,
        executor: CobolExecutor,
        dataset_service: DatasetService,
        notifier: TelegramNotifier,
    ) -> None:
        self.database = database
        self.scheduler = scheduler
        self.executor = executor
        self.dataset_service = dataset_service
        self.notifier = notifier

    def _register_user(self, update: Update) -> None:
        if update.effective_user:
            self.notifier.register_chat_id(update.effective_user.id)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        user_name = update.effective_user.first_name if update.effective_user else "Operator"
        text = format_welcome(user_name)
        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=main_menu_keyboard())

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        text = format_help()
        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=main_menu_keyboard())

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        try:
            metrics = self.database.system_metrics()
            text = format_status(
                executor=self.executor.engine_name,
                gnucobol=self.executor.compiler is not None,
                queue_depth=self.scheduler.queue_depth,
                metrics=metrics,
            )
        except Exception as exc:
            logger.exception("Failed to query system status: %s", exc)
            text = "⚠️ <b>Error:</b> Unable to connect to Mainframe database."

        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=main_menu_keyboard())

    async def jobs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        try:
            jobs, _ = self.database.list_jobs(limit=10, offset=0)
            text = format_jobs_list(jobs, "Recent Batch Jobs")
            keyboard = jobs_list_keyboard(jobs, action="job")
        except Exception as exc:
            logger.exception("Failed to retrieve jobs: %s", exc)
            text = "⚠️ <b>Error:</b> Unable to query batch jobs from database."
            keyboard = back_to_menu_keyboard()

        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=keyboard)

    async def running_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        try:
            all_jobs, _ = self.database.list_jobs(limit=50, offset=0)
            running_jobs = [j for j in all_jobs if j.status in ("running", "queued")]
            text = format_jobs_list(running_jobs, "Running & Queued Jobs")
            keyboard = jobs_list_keyboard(running_jobs, action="job") if running_jobs else main_menu_keyboard()
        except Exception as exc:
            logger.exception("Failed to retrieve running jobs: %s", exc)
            text = "⚠️ <b>Error:</b> Unable to query running jobs."
            keyboard = back_to_menu_keyboard()

        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=keyboard)

    async def failed_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        try:
            all_jobs, _ = self.database.list_jobs(limit=50, offset=0)
            failed_jobs = [j for j in all_jobs if j.status == "failed"]
            text = format_jobs_list(failed_jobs, "Failed Batch Jobs")
            keyboard = jobs_list_keyboard(failed_jobs, action="job") if failed_jobs else main_menu_keyboard()
        except Exception as exc:
            logger.exception("Failed to retrieve failed jobs: %s", exc)
            text = "⚠️ <b>Error:</b> Unable to query failed jobs."
            keyboard = back_to_menu_keyboard()

        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=keyboard)

    async def job_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        args = context.args if context else []
        if not args:
            try:
                jobs, _ = self.database.list_jobs(limit=6, offset=0)
                text = (
                    "ℹ️ <b>Job Detail</b>\n\n"
                    "Please specify a Job ID: <code>/job &lt;JOB_ID&gt;</code>\n"
                    "Or tap one of the recent jobs below:"
                )
                keyboard = jobs_list_keyboard(jobs, action="job")
            except Exception:
                text = "Usage: <code>/job &lt;JOB_ID&gt;</code>"
                keyboard = back_to_menu_keyboard()
            if update.message:
                await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            return

        job_id = args[0].strip()
        try:
            job = self.database.get_job(job_id)
            if job is None:
                text = f"❌ <b>Job Not Found:</b> <code>{escape(job_id)}</code>\n\nPlease check the Job ID and try again."
                keyboard = back_to_menu_keyboard()
            else:
                text = format_job_detail(job)
                keyboard = job_detail_keyboard(job.id)
        except Exception as exc:
            logger.exception("Error fetching job %s: %s", job_id, exc)
            text = f"⚠️ <b>Error:</b> Unable to fetch job details for <code>{escape(job_id)}</code>."
            keyboard = back_to_menu_keyboard()

        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=keyboard)

    async def logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        args = context.args if context else []
        if not args:
            try:
                jobs, _ = self.database.list_jobs(limit=6, offset=0)
                text = (
                    "📜 <b>Execution Logs & Spool Output</b>\n\n"
                    "Please specify a Job ID: <code>/logs &lt;JOB_ID&gt;</code>\n"
                    "Or select a job below to view its spool output:"
                )
                keyboard = logs_selection_keyboard(jobs)
            except Exception:
                text = "Usage: <code>/logs &lt;JOB_ID&gt;</code>"
                keyboard = back_to_menu_keyboard()
            if update.message:
                await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            return

        job_id = args[0].strip()
        try:
            job = self.database.get_job(job_id)
            if job is None:
                text = f"❌ <b>Job Not Found:</b> <code>{escape(job_id)}</code>"
                keyboard = back_to_menu_keyboard()
            else:
                text = format_job_spool(job)
                keyboard = job_detail_keyboard(job.id)
        except Exception as exc:
            logger.exception("Error fetching logs for %s: %s", job_id, exc)
            text = f"⚠️ <b>Error:</b> Unable to fetch execution logs for <code>{escape(job_id)}</code>."
            keyboard = back_to_menu_keyboard()

        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=keyboard)

    async def datasets_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        try:
            datasets = self.dataset_service.list()
            text = format_datasets(datasets)
        except Exception as exc:
            logger.exception("Failed to query datasets: %s", exc)
            text = "⚠️ <b>Error:</b> Unable to query cataloged datasets."

        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    async def metrics_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        try:
            metrics = self.database.system_metrics()
            text = format_metrics(metrics, self.scheduler.queue_depth)
        except Exception as exc:
            logger.exception("Failed to query metrics: %s", exc)
            text = "⚠️ <b>Error:</b> Unable to calculate batch execution metrics."

        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=main_menu_keyboard())

    async def rc_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)
        text = format_rc_explanation()
        if update.message:
            await update.message.reply_text(text=text, parse_mode="HTML", reply_markup=back_to_menu_keyboard())

    async def callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        await query.answer()

        if not check_auth(update):
            await handle_unauthorized(update)
            return
        self._register_user(update)

        data = query.data or ""
        try:
            if data == "cb:menu":
                user_name = update.effective_user.first_name if update.effective_user else "Operator"
                await query.edit_message_text(
                    text=format_welcome(user_name),
                    parse_mode="HTML",
                    reply_markup=main_menu_keyboard(),
                )
            elif data == "cb:status":
                metrics = self.database.system_metrics()
                text = format_status(
                    executor=self.executor.engine_name,
                    gnucobol=self.executor.compiler is not None,
                    queue_depth=self.scheduler.queue_depth,
                    metrics=metrics,
                )
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=main_menu_keyboard())
            elif data == "cb:jobs":
                jobs, _ = self.database.list_jobs(limit=10, offset=0)
                text = format_jobs_list(jobs, "Recent Batch Jobs")
                await query.edit_message_text(
                    text=text, parse_mode="HTML", reply_markup=jobs_list_keyboard(jobs, action="job")
                )
            elif data == "cb:running":
                all_jobs, _ = self.database.list_jobs(limit=50, offset=0)
                running_jobs = [j for j in all_jobs if j.status in ("running", "queued")]
                text = format_jobs_list(running_jobs, "Running & Queued Jobs")
                keyboard = jobs_list_keyboard(running_jobs, action="job") if running_jobs else main_menu_keyboard()
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            elif data == "cb:failed":
                all_jobs, _ = self.database.list_jobs(limit=50, offset=0)
                failed_jobs = [j for j in all_jobs if j.status == "failed"]
                text = format_jobs_list(failed_jobs, "Failed Batch Jobs")
                keyboard = jobs_list_keyboard(failed_jobs, action="job") if failed_jobs else main_menu_keyboard()
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=keyboard)
            elif data == "cb:logs_menu":
                jobs, _ = self.database.list_jobs(limit=6, offset=0)
                text = (
                    "📜 <b>Execution Logs & Spool Output</b>\n\n"
                    "Select a job below to inspect its console logs and SYSOUT output:"
                )
                await query.edit_message_text(
                    text=text, parse_mode="HTML", reply_markup=logs_selection_keyboard(jobs)
                )
            elif data == "cb:datasets":
                datasets = self.dataset_service.list()
                await query.edit_message_text(
                    text=format_datasets(datasets),
                    parse_mode="HTML",
                    reply_markup=back_to_menu_keyboard(),
                )
            elif data == "cb:metrics":
                metrics = self.database.system_metrics()
                text = format_metrics(metrics, self.scheduler.queue_depth)
                await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=main_menu_keyboard())
            elif data == "cb:rc":
                await query.edit_message_text(
                    text=format_rc_explanation(),
                    parse_mode="HTML",
                    reply_markup=back_to_menu_keyboard(),
                )
            elif data == "cb:help":
                await query.edit_message_text(
                    text=format_help(),
                    parse_mode="HTML",
                    reply_markup=main_menu_keyboard(),
                )
            elif data.startswith("cb:job:"):
                job_id = data.split(":", 2)[2]
                job = self.database.get_job(job_id)
                if job:
                    await query.edit_message_text(
                        text=format_job_detail(job),
                        parse_mode="HTML",
                        reply_markup=job_detail_keyboard(job.id),
                    )
                else:
                    await query.edit_message_text(
                        text=f"❌ Job <code>{escape(job_id)}</code> not found.",
                        parse_mode="HTML",
                        reply_markup=back_to_menu_keyboard(),
                    )
            elif data.startswith("cb:logs:"):
                job_id = data.split(":", 2)[2]
                job = self.database.get_job(job_id)
                if job:
                    await query.edit_message_text(
                        text=format_job_spool(job),
                        parse_mode="HTML",
                        reply_markup=job_detail_keyboard(job.id),
                    )
                else:
                    await query.edit_message_text(
                        text=f"❌ Job <code>{escape(job_id)}</code> not found.",
                        parse_mode="HTML",
                        reply_markup=back_to_menu_keyboard(),
                    )
        except TelegramError as exc:
            logger.warning("TelegramError handling callback %s: %s", data, exc)
        except Exception as exc:
            logger.exception("Error handling callback %s: %s", data, exc)
            await query.edit_message_text(
                text="⚠️ An error occurred while processing your request.",
                parse_mode="HTML",
                reply_markup=back_to_menu_keyboard(),
            )

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Telegram error caught: %s", context.error, exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "⚠️ An unexpected error occurred while communicating with the Mainframe Control Tower service.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
