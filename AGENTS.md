# Graph Visualization Server with REST API + WebSocket

## Overview

A graph visualization web app with a Python FastAPI backend. The frontend is adapted from tripleter v5 (vis-network triplet graph builder), connecting via REST + WebSocket APIs for graph mutation and multi-client sync.

## Architecture

```
Browser (vis-network)  ←→  FastAPI server (server.py)
   ├── REST API: mutation requests     ├── GraphStore (in-memory)
   ├── WebSocket: real-time sync       ├── ConnectionManager (broadcast)
   └── Static files served from /      └── Static mount (/static)
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run server
./server.py
# or: python server.py
# or: GRAPH_VIS_PORT=9999 ./server.py

# Open browser
xdg-open http://localhost:7849
```

## API Reference

### REST Endpoints

| Method | Path | Body | Description |
|--------|------|------|-------------|
| GET | `/api/graph` | — | Full graph `{nodes: [...], edges: [...]}` |
| POST | `/api/add-node` | `{id, label}` | Add a node |
| POST | `/api/remove-node` | `{id}` | Remove node + connected edges |
| POST | `/api/add-edge` | `{from, to, label, id?}` | Add an edge |
| POST | `/api/remove-edge` | `{id}` | Remove an edge |
| POST | `/api/add-triplet` | `{subject, predicate, object}` | Add subject→predicate→object |

### WebSocket

Connect to `/ws`. Receives JSON broadcast events for all mutations:

```json
{"event": "add-node", "data": {"id": "Alice", "label": "Alice"}}
{"event": "remove-node", "data": {"id": "Alice", "connected_edges": ["Alice-knows-Bob"]}}
{"event": "add-edge", "data": {"id": "A-knows-B", "from": "A", "to": "B", "label": "knows"}}
{"event": "remove-edge", "data": {"id": "A-knows-B"}}
{"event": "add-triplet", "data": {"subject": "A", "predicate": "knows", "object": "B", "nodes": [...], "edges": [...]}}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_VIS_PORT` | `7849` | Server port |

## Testing

```bash
# Unit tests
pytest tests/

# E2E tests (Docker)
./manage test
```

## Project Structure

```
server.py           # FastAPI server (executable)
static/index.html   # Frontend UI
static/deps/        # vis-network local fallback
tests/              # Unit tests (pytest)
e2e/                # E2E tests (Docker + Selenium)
manage              # Docker orchestration script
```
