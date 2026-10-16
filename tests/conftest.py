import pytest

from app.database import connect


@pytest.fixture
def conn():
    """A fresh in-memory database for every test."""
    c = connect(":memory:")
    yield c
    c.close()