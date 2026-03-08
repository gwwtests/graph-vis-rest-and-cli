#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "fastapi>=0.104.0",
#     "uvicorn[standard]>=0.24.0",
#     "websockets>=12.0",
# ]
# ///
"""Graph Visualization Server with REST API + WebSocket for multi-client sync."""

import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Highlight settings (in-memory, broadcast via WS)
# ---------------------------------------------------------------------------

VALID_HIGHLIGHT_MODES = ("none", "fade", "pulse", "glow")

highlight_settings: dict = {
    "mode": "none",
    "fadeDuration": 3000,
    "highlightColor": "#FFD700",
    "highlightEdgeColor": "#FF6B35",
}


# ---------------------------------------------------------------------------
# Graph store (in-memory)
# ---------------------------------------------------------------------------

class GraphStore:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}

    def add_node(self, node_id: str, label: str, **extras) -> dict:
        node = {"id": node_id, "label": label, **extras}
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
                 edge_id: Optional[str] = None, **extras) -> dict:
        if edge_id is None:
            if label:
                edge_id = f"{edge_from}-{label}-{edge_to}"
            else:
                edge_id = f"{edge_from}--{edge_to}"
        edge = {"id": edge_id, "from": edge_from, "to": edge_to, "label": label,
                **extras}
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
    model_config = {"extra": "allow"}

    id: str
    label: str


class RemoveNodeRequest(BaseModel):
    id: str


class AddEdgeRequest(BaseModel):
    edge_from: str = Field(alias="from")
    edge_to: str = Field(alias="to")
    label: str = ""
    id: Optional[str] = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class RemoveEdgeRequest(BaseModel):
    id: str


class AddTripletRequest(BaseModel):
    subject: str
    predicate: str
    object: str


class HighlightModeRequest(BaseModel):
    mode: str | None = None
    fadeDuration: int | None = None
    highlightColor: str | None = None
    highlightEdgeColor: str | None = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v):
        if v is not None and v not in VALID_HIGHLIGHT_MODES:
            raise ValueError(f"mode must be one of {VALID_HIGHLIGHT_MODES}")
        return v


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
    extras = req.model_extra or {}
    node = store.add_node(req.id, req.label, **extras)
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
    extras = req.model_extra or {}
    edge = store.add_edge(req.edge_from, req.edge_to, req.label, req.id, **extras)
    await manager.broadcast({"event": "add-edge", "data": edge})
    return {"ok": True, "edge": edge}


@app.post("/api/remove-edge")
async def remove_edge(req: RemoveEdgeRequest):
    removed = store.remove_edge(req.id)
    await manager.broadcast({"event": "remove-edge", "data": {"id": req.id}})
    return {"ok": True, "removed": removed}


@app.post("/api/clear")
async def clear_graph():
    store.nodes.clear()
    store.edges.clear()
    await manager.broadcast({"event": "clear", "data": {}})
    return {"ok": True}


@app.get("/api/highlight-mode")
async def get_highlight_mode():
    return highlight_settings


@app.post("/api/highlight-mode")
async def set_highlight_mode(req: HighlightModeRequest):
    if req.mode is not None:
        highlight_settings["mode"] = req.mode
    if req.fadeDuration is not None:
        highlight_settings["fadeDuration"] = req.fadeDuration
    if req.highlightColor is not None:
        highlight_settings["highlightColor"] = req.highlightColor
    if req.highlightEdgeColor is not None:
        highlight_settings["highlightEdgeColor"] = req.highlightEdgeColor
    await manager.broadcast({"event": "highlight-mode", "data": dict(highlight_settings)})
    return {"ok": True, **highlight_settings}


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
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(
        description="Graph Visualization Server with REST API + WebSocket.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s                          Start on default port 7849
  %(prog)s --port 9999              Start on custom port
  %(prog)s --host 127.0.0.1        Bind to localhost only

Environment variables:
  GRAPH_VIS_PORT    Server port (default: 7849)""",
    )
    parser.add_argument("--host",
                        default=os.environ.get("GRAPH_VIS_HOST", "0.0.0.0"),
                        help="Bind address (env: GRAPH_VIS_HOST, default: 0.0.0.0)")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("GRAPH_VIS_PORT", "7849")),
                        help="Server port (env: GRAPH_VIS_PORT, default: 7849)")
    # Support bare "help" as positional
    parser.add_argument("command", nargs="?", default=None,
                        help=argparse.SUPPRESS)

    args = parser.parse_args()
    if args.command == "help":
        parser.parse_args(["--help"])
    elif args.command is not None:
        parser.error(f"unknown command: {args.command}")

    uvicorn.run(app, host=args.host, port=args.port)
