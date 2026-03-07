# Graph Visualization Server with REST API + WebSocket

## Overview

A graph visualization web app with a Python FastAPI backend. The frontend is adapted from tripleter v5 (vis-network triplet graph builder), connecting via REST + WebSocket APIs for graph mutation and multi-client sync.

## Architecture

```
Browser (vis-network)  ←→  FastAPI server (server.py)  ←→  graph-rest-cli.py
   ├── REST API: mutation requests     ├── GraphStore (in-memory)     ├── REPL commands
   ├── WebSocket: real-time sync       ├── ConnectionManager          ├── Load from files
   └── Static files served from /      └── Static mount (/static)    └── Format converters
```

## Quick Start

```bash
# Run server (auto-installs deps via uv)
./server.py
# or: python server.py
# or: GRAPH_VIS_PORT=9999 ./server.py

# Open browser
xdg-open http://localhost:7849

# Or use the CLI REPL
./graph-rest-cli.py
./graph-rest-cli.py --host 10.0.0.5 --port 9999 -v
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

## CLI REPL

Interactive command-line client connecting to the server via REST API:

```
graph@127.0.0.1:7849> Alice knows Bob
Added: Alice —knows→ Bob
graph@127.0.0.1:7849> l
Nodes (2):  Alice, Bob
Edges (1):  Alice —knows→ Bob
graph@127.0.0.1:7849> L data.csv
Loaded 15 edges, 8 nodes from data.csv (csv)
```

Commands: `add/a`, `del/d/rm`, `list/ls/l`, `graph/g`, `Load/L`, `help/?/h`, `quit/q`

3 bare words default to add triplet — `Alice knows Bob` = `add Alice knows Bob`.

See `graph-rest-cli.README.md` for full reference.

## Format Converters

Load graphs from files via the `L` command or use converters standalone:

| Extension | Converter | Dependencies |
|-----------|-----------|-------------|
| `.csv` | `scripts/converters/csv2graph/csv2graph.py` | stdlib |
| `.ttl`, `.n3` | `scripts/converters/ttl2graph/ttl2graph.py` | rdflib (via uv) |
| `.dot`, `.gv` | `scripts/converters/dot2graph/dot2graph.py` | stdlib |
| `.mermaid`, `.mmd` | `scripts/converters/mermaid2graph/mermaid2graph.py` | stdlib |

Each converter outputs an intermediate format (plain/`--csv`/`--jsonl`) and works as both a CLI tool and an importable library.

## Testing

```bash
# Server unit tests (20 tests)
pytest tests/test_api.py tests/test_ws.py -v -p no:playwright

# CLI unit tests (6 tests)
PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest

# E2E tests (Docker)
./manage test
```

## Project Structure

```
server.py                  # FastAPI server (uv run shebang)
graph-rest-cli.py          # REPL CLI client (stdlib-only)
static/index.html          # Frontend UI
static/deps/               # vis-network local fallback
tests/                     # Unit tests (pytest)
e2e/                       # E2E tests (Docker + Selenium)
manage                     # Docker orchestration script
scripts/converters/        # Format converter scripts
├── csv2graph/             #   CSV → graph
├── ttl2graph/             #   Turtle/N3 → graph
├── dot2graph/             #   Graphviz DOT → graph
└── mermaid2graph/         #   Mermaid → graph
```
