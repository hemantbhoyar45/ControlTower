import re

from fastapi import APIRouter, HTTPException, Request, Response, status

from ..schemas.vsam import CustomerSchema, CustomerWrite
from ..services.vsam_service import VsamOperationError, VsamUnavailable


router = APIRouter(prefix="/api/vsam/customers", tags=["vsam"])


def _run(
    action: str, customer_id: str, name: str, request: Request
) -> dict[str, str] | None:
    if not re.fullmatch(r"[A-Za-z0-9]{1,8}", customer_id):
        raise HTTPException(status_code=422, detail="Customer IDs must be 1-8 letters or digits.")
    try:
        return request.app.state.vsam_service.execute(action, customer_id.upper(), name)
    except VsamUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VsamOperationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("", response_model=CustomerSchema, status_code=status.HTTP_201_CREATED)
def add_customer(payload: CustomerSchema, request: Request) -> CustomerSchema:
    customer = _run("ADD", payload.customer_id, payload.name, request)
    if customer is None:
        raise HTTPException(status_code=422, detail="The VSAM program did not return the inserted record.")
    return CustomerSchema(**customer)


@router.get("", response_model=list[CustomerSchema])
def list_customers(request: Request) -> list[CustomerSchema]:
    try:
        customers = request.app.state.vsam_service.list_customers()
    except VsamUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except VsamOperationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [CustomerSchema(**customer) for customer in customers]


@router.get("/{customer_id}", response_model=CustomerSchema)
def read_customer(customer_id: str, request: Request) -> CustomerSchema:
    customer = _run("GET", customer_id, "", request)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return CustomerSchema(**customer)


@router.put("/{customer_id}", response_model=CustomerSchema)
def update_customer(
    customer_id: str, payload: CustomerWrite, request: Request
) -> CustomerSchema:
    customer = _run("UPDATE", customer_id, payload.name, request)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return CustomerSchema(**customer)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(customer_id: str, request: Request) -> Response:
    customer = _run("DELETE", customer_id, "", request)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
