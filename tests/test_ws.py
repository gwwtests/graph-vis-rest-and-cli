"""WebSocket broadcast tests."""

import json


def test_ws_connect(client):
    with client.websocket_connect("/ws") as ws:
        # Connection established — just verify no error
        pass


def test_ws_broadcast_on_add_node(client):
    with client.websocket_connect("/ws") as ws:
        client.post("/api/add-node", json={"id": "A", "label": "A"})
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "add-node"
        assert msg["data"]["id"] == "A"


def test_ws_broadcast_on_remove_node(client):
    client.post("/api/add-triplet", json={
        "subject": "A", "predicate": "x", "object": "B",
    })
    with client.websocket_connect("/ws") as ws:
        client.post("/api/remove-node", json={"id": "A"})
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "remove-node"
        assert msg["data"]["id"] == "A"
        assert "A-x-B" in msg["data"]["connected_edges"]


def test_ws_broadcast_on_add_edge(client):
    client.post("/api/add-node", json={"id": "A", "label": "A"})
    client.post("/api/add-node", json={"id": "B", "label": "B"})
    with client.websocket_connect("/ws") as ws:
        client.post("/api/add-edge", json={
            "from": "A", "to": "B", "label": "links",
        })
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "add-edge"
        assert msg["data"]["id"] == "A-links-B"


def test_ws_broadcast_on_remove_edge(client):
    client.post("/api/add-triplet", json={
        "subject": "A", "predicate": "r", "object": "B",
    })
    with client.websocket_connect("/ws") as ws:
        client.post("/api/remove-edge", json={"id": "A-r-B"})
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "remove-edge"
        assert msg["data"]["id"] == "A-r-B"


def test_ws_broadcast_on_add_triplet(client):
    with client.websocket_connect("/ws") as ws:
        client.post("/api/add-triplet", json={
            "subject": "X", "predicate": "knows", "object": "Y",
        })
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "add-triplet"
        assert msg["data"]["subject"] == "X"
        assert msg["data"]["predicate"] == "knows"
        assert msg["data"]["object"] == "Y"


def test_ws_broadcast_on_clear(client):
    client.post("/api/add-triplet", json={
        "subject": "A", "predicate": "x", "object": "B",
    })
    with client.websocket_connect("/ws") as ws:
        client.post("/api/clear")
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "clear"
        assert msg["data"] == {}


def test_ws_multi_client_broadcast(client):
    with client.websocket_connect("/ws") as ws1:
        with client.websocket_connect("/ws") as ws2:
            client.post("/api/add-node", json={"id": "M", "label": "M"})
            msg1 = json.loads(ws1.receive_text())
            msg2 = json.loads(ws2.receive_text())
            assert msg1["event"] == "add-node"
            assert msg2["event"] == "add-node"
            assert msg1["data"]["id"] == "M"
            assert msg2["data"]["id"] == "M"


def test_ws_broadcast_on_highlight_mode(client):
    with client.websocket_connect("/ws") as ws:
        client.post("/api/highlight-mode", json={"mode": "pulse"})
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "highlight-mode"
        assert msg["data"]["mode"] == "pulse"
        assert msg["data"]["fadeDuration"] == 3000


def test_ws_broadcast_on_input_mode(client):
    with client.websocket_connect("/ws") as ws:
        client.post("/api/input-mode", json={"mode": "minimal"})
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "input-mode"
        assert msg["data"]["mode"] == "minimal"


def test_ws_disconnect_handling(client):
    with client.websocket_connect("/ws"):
        pass  # disconnects on exit

    # Server should still work after client disconnect
    r = client.post("/api/add-node", json={"id": "Z", "label": "Z"})
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# Read-only mode over the WebSocket path
# ---------------------------------------------------------------------------

import pytest
from fastapi import WebSocketDisconnect

from graph_vis_server import server_flags


def test_read_only_ws_action_mutation_dropped(client):
    """Regression: a WS mutating action in read-only mode must NOT reach the
    store — it should not appear in GET /api/graph."""
    server_flags["read_only"] = True
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({
            "event": "action",
            "data": {"action": "add_node", "id": "Ghost", "label": "Ghost"},
        }))
        # The server replies with an error; use it as a sync barrier so the
        # subsequent GET is guaranteed to observe post-processing state.
        reply = json.loads(ws.receive_text())
        assert reply == {"error": "read-only"}

    graph = client.get("/api/graph").json()
    assert graph["nodes"] == []
    assert graph["edges"] == []


def test_read_only_ws_restyle_dropped(client):
    """restyle is a mutating action and must be dropped in read-only mode."""
    server_flags["read_only"] = False
    client.post("/api/add-node", json={"id": "A", "label": "A"})
    server_flags["read_only"] = True
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({
            "event": "action",
            "data": {"action": "restyle", "id": "A", "color": "#ff0000"},
        }))
        reply = json.loads(ws.receive_text())
        assert reply == {"error": "read-only"}

    node = client.get("/api/graph").json()["nodes"][0]
    assert node.get("color") != "#ff0000"


def test_read_only_ws_toggle_node_allowed(client):
    """View-state toggles still apply + relay in read-only mode."""
    server_flags["read_only"] = False
    client.post("/api/add-triplet", json={
        "subject": "A", "predicate": "x", "object": "B",
    })
    server_flags["read_only"] = True
    # Second listener receives the relayed toggle.
    with client.websocket_connect("/ws") as ws1, \
            client.websocket_connect("/ws") as ws2:
        ws1.send_text(json.dumps({
            "event": "action",
            "data": {"action": "toggle_node", "id": "A"},
        }))
        relayed = json.loads(ws2.receive_text())
        assert relayed["event"] == "action"
        assert relayed["data"]["action"] == "toggle_node"

    node = next(n for n in client.get("/api/graph").json()["nodes"]
                if n["id"] == "A")
    assert node.get("hidden") is True


# ---------------------------------------------------------------------------
# Optional auth token on the WS connect
# ---------------------------------------------------------------------------

def test_ws_token_required_missing_rejected(client):
    server_flags["token"] = "s3cret"
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws"):
            pass


def test_ws_token_required_wrong_rejected(client):
    server_flags["token"] = "s3cret"
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws?token=nope"):
            pass


def test_ws_token_required_correct_accepted(client):
    server_flags["token"] = "s3cret"
    with client.websocket_connect("/ws?token=s3cret") as ws:
        client.post(
            "/api/add-node",
            json={"id": "A", "label": "A"},
            headers={"Authorization": "Bearer s3cret"},
        )
        msg = json.loads(ws.receive_text())
        assert msg["event"] == "add-node"


def test_ws_no_token_configured_accepts_plain(client):
    """Backward compatible: no token configured -> plain connect works."""
    with client.websocket_connect("/ws") as ws:
        pass


# ---------------------------------------------------------------------------
# WS Origin check (cross-site protection)
# ---------------------------------------------------------------------------

def test_ws_cross_site_origin_rejected(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
                "/ws", headers={"origin": "http://evil.example.com"}):
            pass


def test_ws_same_host_origin_allowed(client):
    # TestClient's Host header is "testserver".
    with client.websocket_connect(
            "/ws", headers={"origin": "http://testserver"}) as ws:
        pass


def test_ws_allowed_origin_additive(client):
    server_flags["allowed_origins"] = ["http://trusted.example.com"]
    with client.websocket_connect(
            "/ws", headers={"origin": "http://trusted.example.com"}) as ws:
        pass
