#!/usr/bin/env python3
"""Graph Visualization Server with REST API + WebSocket for multi-client sync."""

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Graph store (in-memory)
# ---------------------------------------------------------------------------

class GraphStore:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}

    def add_node(self, node_id: str, label: str) -> dict:
        node = {"id": node_id, "label": label}
        self.nodes[node_id] = node
        return node

    def remove_node(self, node_id: str) -> list[str]:
        """Remove node and return list of cascade-removed edge IDs."""
        self.nodes.pop(node_id, None)
        removed_edges = [
            eid for eid, e in list(self.edges.items())
            if e["from"] == node_id or e["to"] == node_id
        ]
        for eid in removed_edges:
            self.edges.pop(eid, None)
        return removed_edges

    def add_edge(self, edge_from: str, edge_to: str, label: str,
                 edge_id: Optional[str] = None) -> dict:
        if edge_id is None:
            edge_id = f"{edge_from}-{label}-{edge_to}"
        edge = {"id": edge_id, "from": edge_from, "to": edge_to, "label": label}
        self.edges[edge_id] = edge
        return edge

    def remove_edge(self, edge_id: str) -> bool:
        return self.edges.pop(edge_id, None) is not None

    def add_triplet(self, subject: str, predicate: str, obj: str) -> dict:
        """Add subject -predicate-> object. Returns created nodes and edge."""
        created_nodes = []
        if subject not in self.nodes:
            created_nodes.append(self.add_node(subject, subject))
        if obj not in self.nodes:
            created_nodes.append(self.add_node(obj, obj))
        edge = self.add_edge(subject, obj, predicate)
        return {"nodes": created_nodes, "edge": edge}

    def get_full_graph(self) -> dict:
        return {
            "nodes": list(self.nodes.values()),
            "edges": list(self.edges.values()),
        }


store = GraphStore()


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        import json
        text = json.dumps(message)
        for conn in list(self.active_connections):
            try:
                await conn.send_text(text)
            except Exception:
                self.disconnect(conn)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class AddNodeRequest(BaseModel):
    id: str
    label: str


class RemoveNodeRequest(BaseModel):
    id: str


class AddEdgeRequest(BaseModel):
    edge_from: str = Field(alias="from")
    edge_to: str = Field(alias="to")
    label: str
    id: Optional[str] = None

    model_config = {"populate_by_name": True}


class RemoveEdgeRequest(BaseModel):
    id: str


class AddTripletRequest(BaseModel):
    subject: str
    predicate: str
    object: str


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield

app = FastAPI(title="Graph Visualization Server", lifespan=lifespan)

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/api/graph")
async def get_graph():
    return store.get_full_graph()


@app.post("/api/add-node")
async def add_node(req: AddNodeRequest):
    node = store.add_node(req.id, req.label)
    await manager.broadcast({"event": "add-node", "data": node})
    return {"ok": True, "node": node}


@app.post("/api/remove-node")
async def remove_node(req: RemoveNodeRequest):
    removed_edges = store.remove_node(req.id)
    await manager.broadcast({
        "event": "remove-node",
        "data": {"id": req.id, "connected_edges": removed_edges},
    })
    return {"ok": True, "removed_edges": removed_edges}


@app.post("/api/add-edge")
async def add_edge(req: AddEdgeRequest):
    edge = store.add_edge(req.edge_from, req.edge_to, req.label, req.id)
    await manager.broadcast({"event": "add-edge", "data": edge})
    return {"ok": True, "edge": edge}


@app.post("/api/remove-edge")
async def remove_edge(req: RemoveEdgeRequest):
    removed = store.remove_edge(req.id)
    await manager.broadcast({"event": "remove-edge", "data": {"id": req.id}})
    return {"ok": True, "removed": removed}


@app.post("/api/add-triplet")
async def add_triplet(req: AddTripletRequest):
    result = store.add_triplet(req.subject, req.predicate, req.object)
    await manager.broadcast({
        "event": "add-triplet",
        "data": {
            "subject": req.subject,
            "predicate": req.predicate,
            "object": req.object,
            "nodes": result["nodes"],
            "edge": result["edge"],
        },
    })
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive read loop
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Static files + root
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("GRAPH_VIS_PORT", "7849"))
    uvicorn.run(app, host="0.0.0.0", port=port)
