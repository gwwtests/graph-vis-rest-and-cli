# graph-vis-server.py

Graph visualization server with REST API and WebSocket for real-time multi-client sync.

## Purpose

Serves a web-based graph builder UI (adapted from tripleter v5) backed by an in-memory graph store. Clients mutate the graph via REST endpoints; all connected WebSocket clients receive real-time broadcast updates.

## Usage

```bash
# Direct execution (requires uv)
./graph-vis-server.py

# Or with python
python graph-vis-server.py

# Or with uv run explicitly
uv run graph-vis-server.py

# Custom host/port via flags
./graph-vis-server.py --host 0.0.0.0 --port 9999

# Custom port via env var
GRAPH_VIS_PORT=9999 ./graph-vis-server.py

# Show help (all three forms work)
./graph-vis-server.py --help
./graph-vis-server.py -h
./graph-vis-server.py help
```

Then open `http://localhost:7849` (or your custom port).

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_VIS_PORT` | `7849` | HTTP server port |
| `GRAPH_VIS_HOST` | `0.0.0.0` | Server bind address |

## API Endpoints

### `GET /api/graph`

Returns the full graph state.

```bash
curl http://localhost:7849/api/graph
```

Response: `{"nodes": [...], "edges": [...]}`

### `POST /api/add-node`

```bash
curl -X POST http://localhost:7849/api/add-node \
  -H 'Content-Type: application/json' \
  -d '{"id": "Alice", "label": "Alice"}'
```

### `POST /api/remove-node`

Removes a node and all connected edges (cascade delete).

```bash
curl -X POST http://localhost:7849/api/remove-node \
  -H 'Content-Type: application/json' \
  -d '{"id": "Alice"}'
```

### `POST /api/add-edge`

```bash
curl -X POST http://localhost:7849/api/add-edge \
  -H 'Content-Type: application/json' \
  -d '{"from": "Alice", "to": "Bob", "label": "knows"}'
```

### `POST /api/remove-edge`

```bash
curl -X POST http://localhost:7849/api/remove-edge \
  -H 'Content-Type: application/json' \
  -d '{"id": "Alice-knows-Bob"}'
```

### `POST /api/add-triplet`

Compound operation: creates subject and object nodes (if missing) and the predicate edge.

```bash
curl -X POST http://localhost:7849/api/add-triplet \
  -H 'Content-Type: application/json' \
  -d '{"subject": "Alice", "predicate": "knows", "object": "Bob"}'
```

### WebSocket `/ws`

Connect to receive real-time JSON broadcast events for all graph mutations:

```json
{"event": "add-node", "data": {"id": "Alice", "label": "Alice"}}
{"event": "remove-node", "data": {"id": "Alice", "connected_edges": ["Alice-knows-Bob"]}}
{"event": "add-edge", "data": {"id": "A-knows-B", "from": "A", "to": "B", "label": "knows"}}
{"event": "remove-edge", "data": {"id": "A-knows-B"}}
{"event": "add-triplet", "data": {"subject": "A", "predicate": "knows", "object": "B", ...}}
```

## Architecture

* **GraphStore**: In-memory dict-based storage. Node ID = label. Edge ID = `{from}-{predicate}-{to}`.
* **ConnectionManager**: Tracks WebSocket connections, broadcasts JSON to all on mutation.
* **Static mount**: Serves `static/` directory, with `index.html` at root `/`.

## Testing

```bash
# Unit tests
pytest tests/ -v -p no:playwright

# E2E tests (Docker)
./manage test
```
