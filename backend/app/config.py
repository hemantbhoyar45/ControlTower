import os
from pathlib import Path
from dotenv import load_dotenv


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = BACKEND_DIRECTORY / "data" / "control_tower.db"
DEFAULT_COBOL_DIRECTORY = BACKEND_DIRECTORY / "cobol"
DEFAULT_VSAM_DIRECTORY = BACKEND_DIRECTORY / "data" / "vsam"

# Load local environment file if present
load_dotenv(BACKEND_DIRECTORY / ".env")
load_dotenv(BACKEND_DIRECTORY.parent / ".env")


def database_path() -> Path:
    return Path(os.environ.get("CONTROL_TOWER_DATABASE_PATH", str(DEFAULT_DATABASE_PATH)))


def cors_origins() -> list[str]:
    return [
        origin.strip()
        for origin in os.environ.get(
            "CONTROL_TOWER_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8081,http://127.0.0.1:8081",
        ).split(",")
        if origin.strip()
    ]


def telegram_bot_token() -> str | None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    return token if token else None


def telegram_admin_ids() -> set[int] | None:
    """
    Returns None if all users are permitted (wildcard '*'),
    or a set of integer Telegram user IDs.
    """
    raw = os.environ.get("ADMIN_TELEGRAM_IDS", "").strip()
    if not raw:
        return set()
    if raw == "*":
        return None
    ids: set[int] = set()
    for item in raw.split(","):
        item = item.strip()
        if item.isdigit():
            ids.add(int(item))
    return ids


def is_telegram_user_authorized(user_id: int) -> bool:
    admin_ids = telegram_admin_ids()
    if admin_ids is None:
        return True
    return user_id in admin_ids


def telegram_mode() -> str:
    return os.environ.get("TELEGRAM_MODE", "polling").strip().lower()


def telegram_webhook_url() -> str | None:
    url = os.environ.get("TELEGRAM_WEBHOOK_URL", "").strip()
    return url if url else None


def telegram_webhook_secret() -> str | None:
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
    return secret if secret else None
