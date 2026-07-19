"""Shared action-contract tests for the WS hook-action relay path.

Hook actions (toggle_node, toggle_edge, toggle_style, restyle, add_node,
remove_node, add_edge, remove_edge) are interpreted twice:

* server-side by ``_apply_action_to_store`` in ``graph-vis-server.py`` (so
  late-joining clients get correct state from ``GET /api/graph``), and
* client-side by ``executeAction`` in ``static/index.html`` (the live
  vis-network DataSet).

These two interpreters must stay in lock-step.  This module pins the
**server-side** semantics table-driven, one row per documented action type,
by driving each action through the real WebSocket relay (``{"event":"action",
...}``) and asserting the resulting ``GET /api/graph`` snapshot.  The
index.html implementation mirrors the same semantics JS-side; full JS
automation lives in the e2e suite.
"""

import json

import pytest


def _relay(client, action, setup=None):
    """Drive one hook action through the WS relay and return the graph state.

    Uses two websockets: the action is sent on ``sender`` and, because the
    relay applies the action to the store *before* forwarding it to the other
    clients, blocking on ``observer.receive_text()`` guarantees the store
    mutation has completed before we snapshot ``GET /api/graph``.
    """
    if setup:
        setup(client)
    with client.websocket_connect("/ws") as sender, \
            client.websocket_connect("/ws") as observer:
        sender.send_text(json.dumps({"event": "action", "data": action}))
        relayed = json.loads(observer.receive_text())
        assert relayed["event"] == "action"
    return client.get("/api/graph").json()


def _node(graph, node_id):
    return next((n for n in graph["nodes"] if n["id"] == node_id), None)


def _edge(graph, edge_id):
    return next((e for e in graph["edges"] if e["id"] == edge_id), None)


# --- setups -----------------------------------------------------------------

def _seed_triplet(client):
    client.post("/api/add-triplet", json={
        "subject": "A", "predicate": "knows", "object": "B",
    })


def _seed_styled_node(client):
    client.post("/api/add-node", json={
        "id": "A", "label": "A", "color": "#111111", "borderWidth": 1,
    })


# --- table-driven cases -----------------------------------------------------
#
# Each row: (id, setup, action, assertion(graph)).

def _assert_toggle_node(graph):
    node = _node(graph, "A")
    assert node["hidden"] is True
    assert node["physics"] is False
    # connected edge is hidden along with the node
    assert _edge(graph, "A-knows-B")["hidden"] is True


def _assert_toggle_edge(graph):
    edge = _edge(graph, "A-knows-B")
    assert edge["hidden"] is True
    assert edge["physics"] is False


def _assert_toggle_style(graph):
    node = _node(graph, "A")
    assert node["color"] == "#FF0000"
    assert node["borderWidth"] == 5
    # original stashed for the reverse toggle
    assert node["_original_style"] == {"color": "#111111", "borderWidth": 1}


def _assert_restyle(graph):
    node = _node(graph, "A")
    assert node["color"] == "#00FF00"


def _assert_add_node(graph):
    node = _node(graph, "N")
    assert node is not None
    assert node["label"] == "New"
    assert node["shape"] == "box"


def _assert_remove_node(graph):
    assert _node(graph, "A") is None
    # cascade-removes the connected edge
    assert _edge(graph, "A-knows-B") is None


def _assert_add_edge(graph):
    edge = _edge(graph, "P-r-Q")
    assert edge is not None
    # endpoints auto-created by GraphStore.add_edge
    assert _node(graph, "P") is not None
    assert _node(graph, "Q") is not None


def _assert_remove_edge(graph):
    assert _edge(graph, "A-knows-B") is None
    # nodes stay put; only the edge goes
    assert _node(graph, "A") is not None


CASES = [
    ("toggle_node", _seed_triplet,
     {"action": "toggle_node", "id": "A"}, _assert_toggle_node),
    ("toggle_edge", _seed_triplet,
     {"action": "toggle_edge", "id": "A-knows-B"}, _assert_toggle_edge),
    ("toggle_style", _seed_styled_node,
     {"action": "toggle_style", "id": "A",
      "style": {"color": "#FF0000", "borderWidth": 5}}, _assert_toggle_style),
    ("restyle", _seed_styled_node,
     {"action": "restyle", "id": "A", "color": "#00FF00"}, _assert_restyle),
    ("add_node", None,
     {"action": "add_node", "id": "N", "label": "New", "shape": "box"},
     _assert_add_node),
    ("remove_node", _seed_triplet,
     {"action": "remove_node", "id": "A"}, _assert_remove_node),
    ("add_edge", None,
     {"action": "add_edge", "from": "P", "to": "Q", "label": "r"},
     _assert_add_edge),
    ("remove_edge", _seed_triplet,
     {"action": "remove_edge", "id": "A-knows-B"}, _assert_remove_edge),
]


@pytest.mark.parametrize("name,setup,action,assertion",
                         CASES, ids=[c[0] for c in CASES])
def test_action_applied_to_store(client, name, setup, action, assertion):
    graph = _relay(client, action, setup)
    assertion(graph)


def test_toggle_style_round_trip(client):
    """A second toggle_style restores the original style (mirrors index.html)."""
    _seed_styled_node(client)
    action = {"action": "toggle_style", "id": "A",
              "style": {"color": "#FF0000", "borderWidth": 5}}
    graph = _relay(client, action)
    assert _node(graph, "A")["color"] == "#FF0000"
    # toggle back
    graph = _relay(client, action)
    node = _node(graph, "A")
    assert node["color"] == "#111111"
    assert node["borderWidth"] == 1
    assert "_original_style" not in node or node["_original_style"] in (None, {})


def test_add_edge_endpoint_autocreate_via_rest(client):
    """POST /api/add-edge auto-creates missing endpoints and reports them."""
    r = client.post("/api/add-edge", json={"from": "X", "to": "Y"})
    assert r.status_code == 200
    body = r.json()
    created_ids = {n["id"] for n in body["nodes"]}
    assert created_ids == {"X", "Y"}

    graph = client.get("/api/graph").json()
    assert _node(graph, "X") is not None
    assert _node(graph, "Y") is not None
    assert _edge(graph, "X--Y") is not None


def test_add_edge_existing_endpoints_not_recreated(client):
    """Pre-existing endpoints are not reported as created."""
    client.post("/api/add-node", json={"id": "X", "label": "X"})
    r = client.post("/api/add-edge", json={"from": "X", "to": "Y", "label": "l"})
    body = r.json()
    created_ids = {n["id"] for n in body["nodes"]}
    assert created_ids == {"Y"}
