import asyncio
import logging
import signal
import sys
from pathlib import Path

from ..config import (
    DEFAULT_COBOL_DIRECTORY,
    DEFAULT_VSAM_DIRECTORY,
    database_path,
    telegram_bot_token,
)
from ..core.cobol_executor import CobolExecutor
from ..core.job_scheduler import JobScheduler
from ..database.connection import Database
from ..services.dataset_service import DatasetService
from ..services.job_service import JobService
from .bot import TelegramBotService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("telegram-runner")


async def main() -> None:
    token = telegram_bot_token()
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable is not set. Exiting.")
        sys.exit(1)

    db_path = database_path()
    logger.info("Connecting to database at: %s", db_path)
    database = Database(db_path)
    database.initialize()

    executor = CobolExecutor(DEFAULT_COBOL_DIRECTORY)
    scheduler = JobScheduler(database, executor)
    dataset_service = DatasetService(database)
    job_service = JobService(database, scheduler)

    scheduler.start()
    bot_service = TelegramBotService(
        database=database,
        scheduler=scheduler,
        executor=executor,
        dataset_service=dataset_service,
        job_service=job_service,
        token=token,
    )

    await bot_service.start()
    logger.info("Telegram Bot is running! Press Ctrl+C to stop.")

    stop_event = asyncio.Event()

    def handle_signal(*_: object) -> None:
        logger.info("Shutdown signal received.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_signal)
        except (NotImplementedError, RuntimeError):
            pass

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("Shutting down bot and scheduler...")
        await bot_service.stop()
        scheduler.stop()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
