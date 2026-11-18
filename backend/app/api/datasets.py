from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request, status

from ..database.connection import DatasetAlreadyExists
from ..database.models import DatasetDetail
from ..schemas.dataset import (
    DatasetCreate,
    DatasetDetailSchema,
    DatasetListSchema,
    DatasetRecordsUpdate,
)
from ..services.dataset_service import InvalidDatasetName


router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _dataset_response(dataset: DatasetDetail) -> DatasetDetailSchema:
    return DatasetDetailSchema(**asdict(dataset.dataset), records=dataset.records)


@router.get("", response_model=DatasetListSchema)
def list_datasets(request: Request) -> DatasetListSchema:
    datasets = request.app.state.dataset_service.list()
    return DatasetListSchema(items=datasets, total=len(datasets))


@router.post("", response_model=DatasetDetailSchema, status_code=status.HTTP_201_CREATED)
def create_dataset(payload: DatasetCreate, request: Request) -> DatasetDetailSchema:
    try:
        dataset = request.app.state.dataset_service.create(
            payload.name, payload.organization, payload.records
        )
    except InvalidDatasetName as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatasetAlreadyExists as exc:
        raise HTTPException(status_code=409, detail="Dataset already exists.") from exc
    return _dataset_response(dataset)


@router.get("/{dataset_name}/records", response_model=list[str])
def get_dataset_records(dataset_name: str, request: Request) -> list[str]:
    dataset = _get_dataset(dataset_name, request)
    return dataset.records


@router.put("/{dataset_name}/records", response_model=DatasetDetailSchema)
def replace_dataset_records(
    dataset_name: str, payload: DatasetRecordsUpdate, request: Request
) -> DatasetDetailSchema:
    try:
        dataset = request.app.state.dataset_service.replace_records(
            dataset_name, payload.records
        )
    except InvalidDatasetName as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return _dataset_response(dataset)


@router.get("/{dataset_name}", response_model=DatasetDetailSchema)
def get_dataset(dataset_name: str, request: Request) -> DatasetDetailSchema:
    return _dataset_response(_get_dataset(dataset_name, request))


def _get_dataset(dataset_name: str, request: Request) -> DatasetDetail:
    try:
        dataset = request.app.state.dataset_service.get(dataset_name)
    except InvalidDatasetName as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return dataset
