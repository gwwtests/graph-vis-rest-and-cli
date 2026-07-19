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

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import base64

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Read-only mode — blocks all mutation endpoints
# ---------------------------------------------------------------------------

server_flags = {"read_only": False}


def require_writable():
    """Raise 403 if server is in read-only mode."""
    if server_flags["read_only"]:
        raise HTTPException(status_code=403, detail="Server is in read-only mode")


# ---------------------------------------------------------------------------
# Highlight settings (in-memory, broadcast via WS)
# ---------------------------------------------------------------------------

VALID_HIGHLIGHT_MODES = ("none", "fade", "pulse", "glow")

highlight_settings: dict = {
    "mode": "fade",
    "fadeDuration": 3000,
    "highlightColor": "#FFD700",
    "highlightEdgeColor": "#FF6B35",
}


# ---------------------------------------------------------------------------
# Input mode settings (in-memory, broadcast via WS)
# ---------------------------------------------------------------------------

VALID_INPUT_MODES = ("multiline", "single", "minimal", "none")

input_mode_settings: dict = {
    "mode": os.environ.get("GRAPH_VIS_INPUT_MODE", "minimal"),
}


# ---------------------------------------------------------------------------
# Extension loading
# ---------------------------------------------------------------------------

active_extensions: list[dict] = []


# ---------------------------------------------------------------------------
# Graph store (in-memory)
# ---------------------------------------------------------------------------

class GraphStore:
    def __init__(self):
        self.nodes: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}
        # Monotonic revision counter, incremented on every graph mutation.
        # Broadcast in every mutation event and in GET /api/graph so clients
        # can detect gaps / stale state and resync (see bump()).
        self.rev: int = 0

    def bump(self) -> int:
        """Increment and return the revision counter (one bump per mutation)."""
        self.rev += 1
        return self.rev

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
            "rev": self.rev,
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
        text = json.dumps(message)
        for conn in list(self.active_connections):
            try:
                await conn.send_text(text)
            except Exception:
                self.disconnect(conn)


manager = ConnectionManager()


async def broadcast_mutation(event: str, data: dict) -> int:
    """Bump the store revision and broadcast a graph-mutation event.

    Every mutation event carries the new ``rev`` so clients can detect gaps
    (missed events) and resync from GET /api/graph.
    """
    rev = store.bump()
    await manager.broadcast({"event": event, "data": data, "rev": rev})
    return rev


# ---------------------------------------------------------------------------
# WS command-response (server → browser → server)
# ---------------------------------------------------------------------------

_pending_requests: dict[str, asyncio.Future] = {}


async def ws_command(command: str, params: dict = None, timeout: float = 10.0) -> dict | None:
    """Send a command to the first connected browser and await response."""
    if not manager.active_connections:
        return None
    request_id = str(uuid.uuid4())
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    _pending_requests[request_id] = future
    try:
        conn = manager.active_connections[0]
        await conn.send_json({
            "command": command,
            "request_id": request_id,
            "params": params or {},
        })
        return await asyncio.wait_for(future, timeout=timeout)
    except (asyncio.TimeoutError, Exception):
        return None
    finally:
        _pending_requests.pop(request_id, None)


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


class UIRequest(BaseModel):
    input_visible: bool | None = None


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


class InputModeRequest(BaseModel):
    mode: str

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v):
        if v not in VALID_INPUT_MODES:
            raise ValueError(f"mode must be one of {VALID_INPUT_MODES}")
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
    require_writable()
    extras = req.model_extra or {}
    node = store.add_node(req.id, req.label, **extras)
    await broadcast_mutation("add-node", node)
    return {"ok": True, "node": node}


@app.post("/api/remove-node")
async def remove_node(req: RemoveNodeRequest):
    require_writable()
    removed_edges = store.remove_node(req.id)
    await broadcast_mutation(
        "remove-node",
        {"id": req.id, "connected_edges": removed_edges},
    )
    return {"ok": True, "removed_edges": removed_edges}


@app.post("/api/add-edge")
async def add_edge(req: AddEdgeRequest):
    require_writable()
    extras = req.model_extra or {}
    edge = store.add_edge(req.edge_from, req.edge_to, req.label, req.id, **extras)
    await broadcast_mutation("add-edge", edge)
    return {"ok": True, "edge": edge}


@app.post("/api/remove-edge")
async def remove_edge(req: RemoveEdgeRequest):
    require_writable()
    removed = store.remove_edge(req.id)
    await broadcast_mutation("remove-edge", {"id": req.id})
    return {"ok": True, "removed": removed}


@app.post("/api/clear")
async def clear_graph():
    require_writable()
    store.nodes.clear()
    store.edges.clear()
    await broadcast_mutation("clear", {})
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


@app.get("/api/input-mode")
async def get_input_mode():
    return input_mode_settings


@app.post("/api/input-mode")
async def set_input_mode(req: InputModeRequest):
    input_mode_settings["mode"] = req.mode
    await manager.broadcast({"event": "input-mode", "data": {"mode": req.mode}})
    return {"ok": True, "mode": req.mode}


@app.get("/api/read-only")
async def get_read_only():
    return {"read_only": server_flags["read_only"]}


@app.get("/api/extensions")
async def get_extensions():
    return {"extensions": active_extensions}


@app.post("/api/add-triplet")
async def add_triplet(req: AddTripletRequest):
    require_writable()
    result = store.add_triplet(req.subject, req.predicate, req.object)
    await broadcast_mutation("add-triplet", {
        "subject": req.subject,
        "predicate": req.predicate,
        "object": req.object,
        "nodes": result["nodes"],
        "edge": result["edge"],
    })
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# Introspection endpoints (screenshot, DOM, UI control)
# ---------------------------------------------------------------------------

@app.get("/api/screenshot")
async def screenshot(
    padding: float = Query(0.1, description="Extra space around graph (fraction)"),
    fit: bool = Query(True, description="Auto-fit to content before capture"),
    format: str = Query("png", description="Image format: png or jpeg"),
    quality: float = Query(0.92, description="JPEG quality (0-1)"),
    width: int = Query(None, description="Override canvas width"),
    height: int = Query(None, description="Override canvas height"),
    hide_ui: bool = Query(True, description="Hide input box/buttons"),
    background: str = Query("white", description="Background color"),
):
    """Capture the graph visualization as an image via browser."""
    params = {
        "padding": padding, "fit": fit, "format": format,
        "quality": quality, "hide_ui": hide_ui, "background": background,
    }
    if width is not None:
        params["width"] = width
    if height is not None:
        params["height"] = height

    result = await ws_command("capture-screenshot", params, timeout=15.0)
    if result is None:
        return Response(status_code=503, content="No browser connected")

    image_data = result.get("image", "")
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]

    media_type = "image/png" if format == "png" else "image/jpeg"
    return Response(
        content=base64.b64decode(image_data),
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename=graph.{format}"},
    )


@app.get("/api/dom")
async def get_dom():
    """Get graph layout introspection data from the browser."""
    result = await ws_command("get-dom", timeout=5.0)
    if result is None:
        return Response(status_code=503, content="No browser connected")
    return result


@app.post("/api/ui")
async def set_ui(req: UIRequest):
    """Toggle browser UI elements."""
    params = {}
    if req.input_visible is not None:
        params["input_visible"] = req.input_visible
    result = await ws_command("set-ui", params, timeout=5.0)
    if result is None:
        return Response(status_code=503, content="No browser connected")
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# Store updates for hook actions relayed via WebSocket
# ---------------------------------------------------------------------------

def _apply_action_to_store(action: dict):
    """Update the server-side store when a browser sends a hook action.

    Mutation actions (add/remove node/edge) update the store so new clients
    get correct state.  Visual actions (toggle, restyle) update stored
    properties so the full graph snapshot stays consistent.
    """
    act = action.get("action")
    if act == "add_node":
        node_id = action.get("id")
        if node_id and node_id not in store.nodes:
            label = action.get("label", node_id)
            extras = {k: v for k, v in action.items()
                      if k not in ("action", "id", "label")}
            store.add_node(node_id, label, **extras)
    elif act == "remove_node":
        store.remove_node(action.get("id", ""))
    elif act == "add_edge":
        edge_from = action.get("from")
        edge_to = action.get("to")
        if edge_from and edge_to:
            label = action.get("label", "")
            edge_id = action.get("id")
            extras = {k: v for k, v in action.items()
                      if k not in ("action", "from", "to", "label", "id")}
            store.add_edge(edge_from, edge_to, label, edge_id, **extras)
    elif act == "remove_edge":
        store.remove_edge(action.get("id", ""))
    elif act == "toggle_node":
        node = store.nodes.get(action.get("id"))
        if node:
            show = node.get("hidden", False)
            node["hidden"] = not show
            node["physics"] = show
            # Toggle connected edges
            for edge in store.edges.values():
                if edge["from"] == node["id"] or edge["to"] == node["id"]:
                    if not show:
                        edge["hidden"] = True
                        edge["physics"] = False
                    else:
                        other_id = edge["to"] if edge["from"] == node["id"] else edge["from"]
                        other = store.nodes.get(other_id)
                        if other and not other.get("hidden", False):
                            edge["hidden"] = False
                            edge["physics"] = True
    elif act == "toggle_edge":
        edge = store.edges.get(action.get("id"))
        if edge:
            show = edge.get("hidden", False)
            edge["hidden"] = not show
            edge["physics"] = show
    elif act == "restyle":
        item_id = action.get("id")
        props = {k: v for k, v in action.items() if k not in ("action",)}
        target = store.nodes if item_id in store.nodes else store.edges
        item = target.get(item_id)
        if item:
            item.update(props)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            try:
                msg = json.loads(text)
                # Command response from browser
                if "response_to" in msg:
                    req_id = msg["response_to"]
                    if req_id in _pending_requests and not _pending_requests[req_id].done():
                        _pending_requests[req_id].set_result(msg.get("data", {}))
                    continue
                # Hook action relay: update store + broadcast to other clients
                if msg.get("event") == "action":
                    action = msg.get("data", {})
                    _apply_action_to_store(action)
                    # A relayed action mutates the store — bump the revision
                    # and carry it in the relayed payload so other clients keep
                    # their rev in sync and can detect gaps.
                    msg["rev"] = store.bump()
                    relay_text = json.dumps(msg)
                    for conn in list(manager.active_connections):
                        if conn is not websocket:
                            try:
                                await conn.send_text(relay_text)
                            except Exception:
                                manager.disconnect(conn)
                    continue
                # Extension events: relay to all other clients
                if "event" in msg and str(msg["event"]).startswith("ext:"):
                    for conn in list(manager.active_connections):
                        if conn is not websocket:
                            try:
                                await conn.send_text(text)
                            except Exception:
                                manager.disconnect(conn)
                    continue
            except (json.JSONDecodeError, KeyError):
                pass
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
  %(prog)s --ext color-spawner.js --ext color-spawner.css  Load extensions

Environment variables:
  GRAPH_VIS_PORT           Server port (default: 7849)
  GRAPH_VIS_INPUT_MODE     Initial input mode (default: multiline)
  GRAPH_VIS_EXTENSIONS     Comma-separated extension filenames""",
    )
    parser.add_argument("--host",
                        default=os.environ.get("GRAPH_VIS_HOST", "0.0.0.0"),
                        help="Bind address (env: GRAPH_VIS_HOST, default: 0.0.0.0)")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("GRAPH_VIS_PORT", "7849")),
                        help="Server port (env: GRAPH_VIS_PORT, default: 7849)")
    parser.add_argument("--input-mode",
                        default=os.environ.get("GRAPH_VIS_INPUT_MODE", "minimal"),
                        choices=VALID_INPUT_MODES,
                        help="Initial input mode (env: GRAPH_VIS_INPUT_MODE, default: minimal)")
    parser.add_argument("--read-only", action="store_true",
                        default=os.environ.get("GRAPH_VIS_READ_ONLY", "").lower() in ("1", "true", "yes"),
                        help="Read-only mode: block all mutation endpoints (env: GRAPH_VIS_READ_ONLY)")
    parser.add_argument("--ext", action="append", default=[],
                        help="Load JS/CSS extension from static/extensions/ (repeatable)")
    # Support bare "help" as positional
    parser.add_argument("command", nargs="?", default=None,
                        help=argparse.SUPPRESS)

    args = parser.parse_args()
    if args.command == "help":
        parser.parse_args(["--help"])
    elif args.command is not None:
        parser.error(f"unknown command: {args.command}")

    input_mode_settings["mode"] = args.input_mode

    server_flags["read_only"] = args.read_only
    if server_flags["read_only"]:
        print("Read-only mode: mutation endpoints are disabled")

    # Collect extensions from --ext flags and GRAPH_VIS_EXTENSIONS env var
    ext_names = list(args.ext)
    env_exts = os.environ.get("GRAPH_VIS_EXTENSIONS", "")
    if env_exts:
        ext_names.extend(e.strip() for e in env_exts.split(",") if e.strip())
    # Deduplicate while preserving order
    seen = set()
    for name in ext_names:
        if name not in seen:
            seen.add(name)
            ext_path = os.path.join(STATIC_DIR, "extensions", name)
            if not os.path.isfile(ext_path):
                parser.error(f"Extension not found: {ext_path}")
            ext_type = "css" if name.endswith(".css") else "js"
            active_extensions.append({
                "type": ext_type,
                "path": f"/static/extensions/{name}",
            })
    if active_extensions:
        print(f"Loaded extensions: {', '.join(e['path'] for e in active_extensions)}")

    uvicorn.run(app, host=args.host, port=args.port)
