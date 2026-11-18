import os
from pathlib import Path


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = BACKEND_DIRECTORY / "data" / "control_tower.db"
DEFAULT_COBOL_DIRECTORY = BACKEND_DIRECTORY / "cobol"
DEFAULT_VSAM_DIRECTORY = BACKEND_DIRECTORY / "data" / "vsam"


def database_path() -> Path:
    return Path(os.environ.get("CONTROL_TOWER_DATABASE_PATH", str(DEFAULT_DATABASE_PATH)))


def cors_origins() -> list[str]:
    return [
        origin.strip()
        for origin in os.environ.get(
            "CONTROL_TOWER_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]
