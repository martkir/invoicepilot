import pytest
from fastapi.testclient import TestClient

from app.services.api import api


@pytest.fixture
def client() -> TestClient:
    return TestClient(api)
