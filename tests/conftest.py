"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_project_input():
    """Sample project description for testing."""
    return {
        "description": (
            "An e-commerce platform for a small business that sells handmade "
            "crafts online. Needs user authentication, product catalog, shopping "
            "cart, payment processing, and order management. Expected ~1000 "
            "concurrent users. Team of 3 developers, 6-month timeline."
        ),
        "documents": [],
    }
