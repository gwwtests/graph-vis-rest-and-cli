"""REST API endpoint tests."""


def test_empty_graph(client):
    r = client.get("/api/graph")
    assert r.status_code == 200
    data = r.json()
    assert data == {"nodes": [], "edges": []}


def test_add_node(client):
    r = client.post("/api/add-node", json={"id": "Alice", "label": "Alice"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["node"]["id"] == "Alice"

    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["id"] == "Alice"


def test_add_duplicate_node(client):
    client.post("/api/add-node", json={"id": "A", "label": "A"})
    client.post("/api/add-node", json={"id": "A", "label": "A-updated"})
    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 1
    assert graph["nodes"][0]["label"] == "A-updated"


def test_remove_node(client):
    client.post("/api/add-node", json={"id": "X", "label": "X"})
    r = client.post("/api/remove-node", json={"id": "X"})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 0


def test_remove_node_cascades_edges(client):
    client.post("/api/add-triplet", json={
        "subject": "A", "predicate": "knows", "object": "B",
    })
    client.post("/api/add-triplet", json={
        "subject": "B", "predicate": "likes", "object": "C",
    })
    # B has two edges: A-knows-B and B-likes-C
    r = client.post("/api/remove-node", json={"id": "B"})
    removed = r.json()["removed_edges"]
    assert "A-knows-B" in removed
    assert "B-likes-C" in removed

    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 2  # A and C remain
    assert len(graph["edges"]) == 0


def test_add_edge(client):
    client.post("/api/add-node", json={"id": "A", "label": "A"})
    client.post("/api/add-node", json={"id": "B", "label": "B"})
    r = client.post("/api/add-edge", json={
        "from": "A", "to": "B", "label": "connects",
    })
    assert r.status_code == 200
    edge = r.json()["edge"]
    assert edge["id"] == "A-connects-B"


def test_add_edge_custom_id(client):
    client.post("/api/add-node", json={"id": "A", "label": "A"})
    client.post("/api/add-node", json={"id": "B", "label": "B"})
    r = client.post("/api/add-edge", json={
        "from": "A", "to": "B", "label": "x", "id": "custom-id",
    })
    assert r.json()["edge"]["id"] == "custom-id"


def test_remove_edge(client):
    client.post("/api/add-triplet", json={
        "subject": "A", "predicate": "knows", "object": "B",
    })
    r = client.post("/api/remove-edge", json={"id": "A-knows-B"})
    assert r.json()["ok"] is True
    assert r.json()["removed"] is True

    graph = client.get("/api/graph").json()
    assert len(graph["edges"]) == 0
    assert len(graph["nodes"]) == 2  # nodes remain


def test_remove_nonexistent_edge(client):
    r = client.post("/api/remove-edge", json={"id": "nope"})
    assert r.json()["removed"] is False


def test_add_triplet(client):
    r = client.post("/api/add-triplet", json={
        "subject": "Alice", "predicate": "knows", "object": "Bob",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert len(data["nodes"]) == 2
    assert data["edge"]["id"] == "Alice-knows-Bob"

    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1


def test_add_triplet_existing_nodes(client):
    client.post("/api/add-node", json={"id": "A", "label": "A"})
    r = client.post("/api/add-triplet", json={
        "subject": "A", "predicate": "sees", "object": "B",
    })
    # Only B should be newly created
    assert len(r.json()["nodes"]) == 1
    assert r.json()["nodes"][0]["id"] == "B"


def test_full_lifecycle(client):
    # Build a small graph
    client.post("/api/add-triplet", json={
        "subject": "X", "predicate": "a", "object": "Y",
    })
    client.post("/api/add-triplet", json={
        "subject": "Y", "predicate": "b", "object": "Z",
    })
    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 3
    assert len(graph["edges"]) == 2

    # Remove middle node — cascades
    client.post("/api/remove-node", json={"id": "Y"})
    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 0

    # Add it back
    client.post("/api/add-triplet", json={
        "subject": "X", "predicate": "c", "object": "Z",
    })
    graph = client.get("/api/graph").json()
    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1
