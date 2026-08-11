"""FastAPI service.

Run with: uvicorn app.services.api:api --reload
"""

from fastapi import FastAPI

from app import __version__
from app.core.logging import setup_logging
from app.schemas import HealthResponse

setup_logging()

api = FastAPI(title="Invoice Pilot API", version=__version__)


@api.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)
