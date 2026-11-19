import asyncio
import logging
from typing import Any

from telegram import BotCommand, Update
from telegram.ext import Application, ApplicationBuilder, CallbackQueryHandler, CommandHandler

from ..config import (
    telegram_admin_ids,
    telegram_bot_token,
    telegram_mode,
    telegram_webhook_secret,
    telegram_webhook_url,
)
from ..core.cobol_executor import CobolExecutor
from ..core.job_scheduler import JobScheduler
from ..database.connection import Database
from ..database.models import Job
from ..services.dataset_service import DatasetService
from ..services.job_service import JobService
from .handlers import BotHandlers
from .notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class TelegramBotService:
    def __init__(
        self,
        database: Database,
        scheduler: JobScheduler,
        executor: CobolExecutor,
        dataset_service: DatasetService,
        job_service: JobService,
        token: str | None = None,
    ) -> None:
        self.database = database
        self.scheduler = scheduler
        self.executor = executor
        self.dataset_service = dataset_service
        self.job_service = job_service
        self.token = token or telegram_bot_token()
        self.application: Application | None = None
        self.notifier: TelegramNotifier | None = None
        self.handlers: BotHandlers | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._is_running: bool = False

        if self.token:
            self._setup_application()

    def _setup_application(self) -> None:
        if not self.token:
            return

        self.application = ApplicationBuilder().token(self.token).build()
        self.notifier = TelegramNotifier(self.application.bot)
        self.handlers = BotHandlers(
            database=self.database,
            scheduler=self.scheduler,
            executor=self.executor,
            dataset_service=self.dataset_service,
            notifier=self.notifier,
        )

        # Register commands
        self.application.add_handler(CommandHandler("start", self.handlers.start))
        self.application.add_handler(CommandHandler("help", self.handlers.help_command))
        self.application.add_handler(CommandHandler("status", self.handlers.status_command))
        self.application.add_handler(CommandHandler("jobs", self.handlers.jobs_command))
        self.application.add_handler(CommandHandler("running", self.handlers.running_command))
        self.application.add_handler(CommandHandler("failed", self.handlers.failed_command))
        self.application.add_handler(CommandHandler("job", self.handlers.job_command))
        self.application.add_handler(CommandHandler("logs", self.handlers.logs_command))
        self.application.add_handler(CommandHandler("datasets", self.handlers.datasets_command))
        self.application.add_handler(CommandHandler("metrics", self.handlers.metrics_command))
        self.application.add_handler(CommandHandler("rc", self.handlers.rc_command))

        # Register inline keyboard callback query handler
        self.application.add_handler(CallbackQueryHandler(self.handlers.callback_query))

        # Register global error handler
        self.application.add_error_handler(self.handlers.error_handler)

        # Connect completion listener to JobScheduler
        self.scheduler.add_completion_listener(self._on_job_completed)

    def _on_job_completed(self, job: Job) -> None:
        if not self.notifier or not self._loop or not self._loop.is_running():
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.notifier.notify_job_completed(job, admin_ids=telegram_admin_ids()),
                self._loop,
            )
        except Exception as exc:
            logger.warning("Could not dispatch job %s completion notification to Telegram: %s", job.id, exc)

    async def start(self) -> None:
        if not self.application:
            logger.warning("TelegramBotService: No TELEGRAM_BOT_TOKEN provided; bot not started.")
            return

        self._loop = asyncio.get_running_loop()
        mode = telegram_mode()

        try:
            await self.application.initialize()
            await self.application.start()

            # Set bot commands menu in Telegram UI
            try:
                commands = [
                    BotCommand("start", "Welcome message & dashboard"),
                    BotCommand("help", "Help & command reference"),
                    BotCommand("status", "System & engine status"),
                    BotCommand("jobs", "List recent batch jobs"),
                    BotCommand("running", "List running / queued jobs"),
                    BotCommand("failed", "List failed batch jobs"),
                    BotCommand("job", "Inspect a specific job"),
                    BotCommand("logs", "View spool & execution logs"),
                    BotCommand("datasets", "List cataloged datasets"),
                    BotCommand("metrics", "Job execution metrics"),
                    BotCommand("rc", "Return code classifications"),
                ]
                await self.application.bot.set_my_commands(commands)
            except Exception as exc:
                logger.debug("Could not set bot commands menu: %s", exc)

            if mode == "webhook":
                webhook_url = telegram_webhook_url()
                if webhook_url:
                    secret = telegram_webhook_secret()
                    await self.application.bot.set_webhook(
                        url=webhook_url,
                        secret_token=secret,
                        drop_pending_updates=True,
                    )
                    logger.info("Telegram Bot started in webhook mode with URL: %s", webhook_url)
                else:
                    logger.warning("TELEGRAM_MODE=webhook configured but TELEGRAM_WEBHOOK_URL is not set.")
            else:
                if self.application.updater:
                    await self.application.updater.start_polling(drop_pending_updates=True)
                    logger.info("Telegram Bot started in long-polling mode.")

            self._is_running = True
        except Exception as exc:
            logger.exception("Failed to start Telegram Bot service: %s", exc)

    async def stop(self) -> None:
        if not self.application or not self._is_running:
            return

        logger.info("Stopping Telegram Bot service...")
        self._is_running = False
        try:
            if self.application.updater and self.application.updater.running:
                await self.application.updater.stop()
            if self.application.running:
                await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram Bot service stopped cleanly.")
        except Exception as exc:
            logger.exception("Error while stopping Telegram Bot service: %s", exc)

    async def process_update(self, update_dict: dict[str, Any]) -> None:
        if not self.application:
            return
        update = Update.de_json(update_dict, self.application.bot)
        await self.application.process_update(update)
