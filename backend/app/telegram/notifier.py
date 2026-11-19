import asyncio
import logging
from typing import TYPE_CHECKING

from telegram import Bot
from telegram.error import TelegramError

from ..database.models import Job
from .formatters import format_job_completion_notification
from .keyboards import job_notification_keyboard

if TYPE_CHECKING:
    from .bot import TelegramBotService

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._notified_events: set[str] = set()
        self._known_chat_ids: set[int] = set()

    def register_chat_id(self, chat_id: int) -> None:
        self._known_chat_ids.add(chat_id)

    async def notify_job_completed(
        self,
        job: Job,
        admin_ids: set[int] | None = None,
    ) -> None:
        # Avoid duplicate notifications for the same job terminal event
        event_key = f"{job.id}:{job.status}:{job.return_code}"
        if event_key in self._notified_events:
            logger.debug("Skipping duplicate notification for event: %s", event_key)
            return

        self._notified_events.add(event_key)

        targets: set[int] = set()
        if admin_ids is not None and len(admin_ids) > 0:
            targets.update(admin_ids)
        else:
            # If wildcard '*' is configured, broadcast to all chats that contacted the bot
            targets.update(self._known_chat_ids)

        if not targets:
            logger.info("No recipient Telegram chat IDs registered for job %s notification", job.id)
            return

        text = format_job_completion_notification(job)
        keyboard = job_notification_keyboard(job.id)

        for chat_id in targets:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                logger.info("Sent job %s notification to Telegram chat %s", job.id, chat_id)
            except TelegramError as exc:
                logger.warning(
                    "Failed to deliver job %s notification to chat %s: %s",
                    job.id,
                    chat_id,
                    exc,
                )
            except Exception as exc:
                logger.exception(
                    "Unexpected error delivering notification to chat %s: %s",
                    chat_id,
                    exc,
                )
