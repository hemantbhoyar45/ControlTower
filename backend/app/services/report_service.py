from datetime import datetime, timedelta, timezone
from typing import Any

from ..database.connection import Database


class ReportService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def summary(self) -> dict[str, Any]:
        start_date = (datetime.now(timezone.utc).date() - timedelta(days=6)).isoformat()
        return self.database.job_report(start_date)
