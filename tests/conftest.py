import pytest
from fastapi.testclient import TestClient

from server import app, store, manager


@pytest.fixture(autouse=True)
def reset_state():
    """Reset graph store and connection manager before each test."""
    store.nodes.clear()
    store.edges.clear()
    manager.active_connections.clear()
    yield


@pytest.fixture
def client():
    return TestClient(app)
