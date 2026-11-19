from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from ..database.models import Job


def main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📊 Dashboard", callback_data="cb:status"),
            InlineKeyboardButton("📋 All Jobs", callback_data="cb:jobs"),
        ],
        [
            InlineKeyboardButton("⚡ Running Jobs", callback_data="cb:running"),
            InlineKeyboardButton("❌ Failed Jobs", callback_data="cb:failed"),
        ],
        [
            InlineKeyboardButton("📜 Execution Logs", callback_data="cb:logs_menu"),
            InlineKeyboardButton("📈 System Metrics", callback_data="cb:metrics"),
        ],
        [
            InlineKeyboardButton("🏷️ Datasets", callback_data="cb:datasets"),
            InlineKeyboardButton("ℹ️ Return Codes", callback_data="cb:rc"),
        ],
        [
            InlineKeyboardButton("❓ Help", callback_data="cb:help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def job_detail_keyboard(job_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📜 View Spool Logs", callback_data=f"cb:logs:{job_id}"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"cb:job:{job_id}"),
        ],
        [
            InlineKeyboardButton("⬅️ Back to Jobs", callback_data="cb:jobs"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="cb:menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def job_notification_keyboard(job_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🔍 View Job Details", callback_data=f"cb:job:{job_id}"),
            InlineKeyboardButton("📜 View Spool Logs", callback_data=f"cb:logs:{job_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def jobs_list_keyboard(jobs: list[Job], action: str = "job") -> InlineKeyboardMarkup:
    buttons = []
    # Up to 6 quick buttons for the jobs
    for job in jobs[:6]:
        rc_str = f"RC {job.return_code:04d}" if job.return_code is not None else "RUNNING"
        status_icon = "🟢" if job.status == "completed" else "🔴" if job.status == "failed" else "🟡"
        buttons.append([
            InlineKeyboardButton(
                f"{status_icon} {job.name} ({rc_str})",
                callback_data=f"cb:{action}:{job.id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton("🔄 Refresh", callback_data=f"cb:{action}s" if action == "job" else "cb:jobs"),
        InlineKeyboardButton("🏠 Main Menu", callback_data="cb:menu"),
    ])
    return InlineKeyboardMarkup(buttons)


def logs_selection_keyboard(jobs: list[Job]) -> InlineKeyboardMarkup:
    buttons = []
    for job in jobs[:6]:
        rc_str = f"RC {job.return_code:04d}" if job.return_code is not None else job.status.upper()
        buttons.append([
            InlineKeyboardButton(
                f"📜 {job.name} ({rc_str})",
                callback_data=f"cb:logs:{job.id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton("🏠 Main Menu", callback_data="cb:menu"),
    ])
    return InlineKeyboardMarkup(buttons)


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Main Menu", callback_data="cb:menu")]
    ])
