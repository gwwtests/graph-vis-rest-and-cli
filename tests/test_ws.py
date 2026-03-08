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
