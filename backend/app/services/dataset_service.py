import re

from ..database.connection import Database, DatasetAlreadyExists
from ..database.models import Dataset, DatasetDetail


_DATASET_NAME = re.compile(r"^[A-Z0-9@$#][A-Z0-9.@$#-]{0,43}$")


class InvalidDatasetName(ValueError):
    pass


class DatasetService:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def normalize_name(name: str) -> str:
        normalized = name.strip().upper()
        if not _DATASET_NAME.fullmatch(normalized):
            raise InvalidDatasetName(
                "Dataset names must be 1-44 characters using letters, digits, "
                "periods, @, #, $, or hyphens."
            )
        return normalized

    def list(self) -> list[Dataset]:
        return self.database.list_datasets()

    def get(self, name: str) -> DatasetDetail | None:
        return self.database.get_dataset(self.normalize_name(name))

    def create(self, name: str, organization: str, records: list[str]) -> DatasetDetail:
        normalized = self.normalize_name(name)
        org = organization.strip().upper()
        if not org:
            raise ValueError("Dataset organization must not be empty.")
        return self.database.create_dataset(normalized, org, records)

    def replace_records(self, name: str, records: list[str]) -> DatasetDetail | None:
        return self.database.replace_dataset_records(self.normalize_name(name), records)


__all__ = ["DatasetAlreadyExists", "DatasetService", "InvalidDatasetName"]
