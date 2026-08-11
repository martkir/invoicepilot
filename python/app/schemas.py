"""Pydantic request/response models for the API."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
