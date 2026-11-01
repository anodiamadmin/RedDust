from fastapi import APIRouter
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])

@router.get("/healthz", response_model=HealthResponse, status_code=200)
def healthz() -> HealthResponse:
    return HealthResponse()