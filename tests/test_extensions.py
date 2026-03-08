"""Tests for extension loading and hooks extras pass-through."""

import os
import tempfile


def test_extensions_endpoint_empty(client):
    """No extensions loaded by default."""
    r = client.get("/api/extensions")
    assert r.status_code == 200
    assert r.json() == {"extensions": []}


def test_node_with_hook_extras(client):
    """Hook fields (on_click, on_doubleClick) are stored as extras."""
    hooks = [{"action": "toggle_node", "id": "child1"}]
    r = client.post("/api/add-node", json={
        "id": "root", "label": "Root",
        "on_click": hooks,
    })
    assert r.status_code == 200
    node = r.json()["node"]
    assert node["on_click"] == hooks

    graph = client.get("/api/graph").json()
    root = [n for n in graph["nodes"] if n["id"] == "root"][0]
    assert root["on_click"] == hooks


def test_node_with_hidden_physics(client):
    """Nodes can be created with hidden=true and physics=false."""
    r = client.post("/api/add-node", json={
        "id": "hidden1", "label": "Hidden",
        "hidden": True, "physics": False,
    })
    assert r.status_code == 200
    node = r.json()["node"]
    assert node["hidden"] is True
    assert node["physics"] is False


def test_node_double_click_hook(client):
    """on_doubleClick hook stored correctly."""
    hooks = [
        {"action": "restyle", "id": "n1", "color": {"background": "red"}},
        {"action": "toggle_style", "id": "n2", "style": {"shape": "box"}},
    ]
    r = client.post("/api/add-node", json={
        "id": "n1", "label": "N1",
        "on_doubleClick": hooks,
    })
    assert r.status_code == 200
    assert r.json()["node"]["on_doubleClick"] == hooks


def test_edge_with_extras(client):
    """Edges preserve extra styling fields."""
    client.post("/api/add-node", json={"id": "A", "label": "A"})
    client.post("/api/add-node", json={"id": "B", "label": "B"})
    r = client.post("/api/add-edge", json={
        "from": "A", "to": "B", "label": "link",
        "hidden": True, "physics": False, "width": 3,
    })
    assert r.status_code == 200
    edge = r.json()["edge"]
    assert edge["hidden"] is True
    assert edge["physics"] is False
    assert edge["width"] == 3


def test_complex_hook_structure(client):
    """Complex nested hook actions are preserved."""
    on_click = [
        {"action": "toggle_node", "id": "child1"},
        {"action": "toggle_node", "id": "child2"},
        {"action": "toggle_edge", "id": "root--child1"},
        {"action": "toggle_style", "id": "root", "style": {
            "borderWidth": 4,
            "color": {"border": "#FFD700"},
        }},
    ]
    r = client.post("/api/add-node", json={
        "id": "root", "label": "Root",
        "on_click": on_click,
        "color": {"background": "#4CAF50"},
    })
    assert r.status_code == 200
    node = r.json()["node"]
    assert len(node["on_click"]) == 4
    assert node["on_click"][3]["style"]["color"]["border"] == "#FFD700"
    assert node["color"]["background"] == "#4CAF50"


def test_full_mindmap_scenario(client):
    """Simulate loading a mindmap with hidden children and hooks."""
    # Root node with hooks
    client.post("/api/add-node", json={
        "id": "ML", "label": "Machine Learning",
        "on_click": [
            {"action": "toggle_node", "id": "Supervised"},
            {"action": "toggle_node", "id": "Unsupervised"},
        ],
    })
    # Hidden children
    client.post("/api/add-node", json={
        "id": "Supervised", "label": "Supervised",
        "hidden": True, "physics": False,
    })
    client.post("/api/add-node", json={
        "id": "Unsupervised", "label": "Unsupervised",
        "hidden": True, "physics": False,
    })
    # Hidden edges
    client.post("/api/add-edge", json={
        "from": "ML", "to": "Supervised",
        "hidden": True, "physics": False,
    })
    client.post("/api/add-edge", json={
        "from": "ML", "to": "Unsupervised",
        "hidden": True, "physics": False,
    })

    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 3
    assert len(graph["edges"]) == 2

    # Verify hidden state
    sup = [n for n in graph["nodes"] if n["id"] == "Supervised"][0]
    assert sup["hidden"] is True
    assert sup["physics"] is False

    # Verify hooks on root
    ml = [n for n in graph["nodes"] if n["id"] == "ML"][0]
    assert len(ml["on_click"]) == 2
