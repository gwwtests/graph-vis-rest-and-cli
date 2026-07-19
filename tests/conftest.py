import pytest
from fastapi.testclient import TestClient

from graph_vis_server import (
    app,
    store,
    manager,
    highlight_settings,
    input_mode_settings,
    server_flags,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset graph store, connection manager, and highlight settings before each test."""
    store.nodes.clear()
    store.edges.clear()
    manager.active_connections.clear()
    server_flags.update({
        "read_only": False,
        "token": None,
        "allowed_origins": None,
    })
    highlight_settings.update({
        "mode": "none",
        "fadeDuration": 3000,
        "highlightColor": "#FFD700",
        "highlightEdgeColor": "#FF6B35",
    })
    input_mode_settings.update({
        "mode": "multiline",
    })
    yield


@pytest.fixture
def client():
    return TestClient(app)
