# Graph Visualization Server with REST API + WebSocket

## Overview

A collaborative graph visualization web app with a Python FastAPI backend. Multiple browsers, CLI clients, and API consumers can view and edit the same graph in real time. The frontend is adapted from tripleter v5 (vis-network triplet graph builder), connecting via REST + WebSocket APIs for graph mutation and multi-client sync.

## Architecture

```
Browser A ──WS──┐
Browser B ──WS──┤── FastAPI server (graph-vis-server.py) ──── graph-vis-cli.py
Browser C ──WS──┘        │                                      ├── REPL commands
  ├── REST API: mutations │                                      ├── Load from files
  ├── WebSocket: sync     ├── GraphStore (in-memory)             └── Format converters
  └── Hook action relay   ├── ConnectionManager
                          └── Static mount (/static)

Mutation flow: Any source → REST API → store update → WS broadcast to ALL browsers
Action flow:   Browser X executes → WS relay → server updates store → other browsers execute
```

## Quick Start

```bash
# Run server (auto-installs deps via uv)
./graph-vis-server.py
# or: python graph-vis-server.py
# or: GRAPH_VIS_PORT=9999 ./graph-vis-server.py

# Open browser
xdg-open http://localhost:7849

# CLI: pipe commands (non-interactive default)
echo "Alice knows Bob" | ./graph-vis-cli.py

# CLI: positional commands
./graph-vis-cli.py "Alice knows Bob" "g"

# CLI: load a file and show graph
./graph-vis-cli.py -l examples/social-network.csv "g"

# CLI: interactive REPL
./graph-vis-cli.py --repl

# CLI: env vars for connection
GRAPH_VIS_HOST=10.0.0.5 ./graph-vis-cli.py -l data.csv "g"

# Read-only mode (viewers can explore but not modify)
./graph-vis-server.py --read-only
# or: GRAPH_VIS_READ_ONLY=true ./graph-vis-server.py

# Collaboration: share the URL — all browsers sync in real time
# Open http://<your-ip>:7849 on multiple devices
```

## API Reference

### REST Endpoints

| Method | Path | Body | Description |
|--------|------|------|-------------|
| GET | `/api/graph` | — | Full graph `{nodes: [...], edges: [...]}` |
| POST | `/api/add-node` | `{id, label, ...extras}` | Add a node (extras: vis-network styling) |
| POST | `/api/remove-node` | `{id}` | Remove node + connected edges |
| POST | `/api/add-edge` | `{from, to, label?, id?, ...extras}` | Add an edge (label optional, extras: styling) |
| POST | `/api/remove-edge` | `{id}` | Remove an edge |
| POST | `/api/add-triplet` | `{subject, predicate, object}` | Add subject→predicate→object |
| POST | `/api/clear` | — | Clear graph to empty state |
| GET | `/api/input-mode` | — | Get current input mode `{mode}` |
| POST | `/api/input-mode` | `{mode}` | Set input mode (multiline/single/minimal/none) |
| GET | `/api/extensions` | — | List active extensions `{extensions: [...]}` |
| GET | `/api/events` | — | Server-Sent-Events stream of all broadcast events (see below) |
| GET | `/api/highlight-mode` | — | Get current highlight settings |
| POST | `/api/highlight-mode` | `{mode?, fadeDuration?, ...}` | Set highlight mode (fade/pulse/glow) |
| GET | `/api/screenshot` | query params | Capture graph as PNG/JPEG (via browser) |
| GET | `/api/dom` | — | Graph layout introspection (via browser) |
| POST | `/api/ui` | `{input_visible}` | Toggle browser UI elements |
| GET | `/api/read-only` | — | Check read-only status `{read_only: bool}` |

### WebSocket

Connect to `/ws`. Receives JSON broadcast events for all mutations:

```json
{"event": "add-node", "data": {"id": "Alice", "label": "Alice"}}
{"event": "remove-node", "data": {"id": "Alice", "connected_edges": ["Alice-knows-Bob"]}}
{"event": "add-edge", "data": {"id": "A-knows-B", "from": "A", "to": "B", "label": "knows"}}
{"event": "remove-edge", "data": {"id": "A-knows-B"}}
{"event": "add-triplet", "data": {"subject": "A", "predicate": "knows", "object": "B", "nodes": [...], "edges": [...]}}
{"event": "clear", "data": {}}
{"event": "input-mode", "data": {"mode": "minimal"}}
{"event": "highlight-mode", "data": {"mode": "fade", ...}}
{"event": "action", "data": {"action": "toggle_node", "id": "Alice"}}
```

Server can also send commands to the browser and receive responses:

```json
{"command": "capture-screenshot", "request_id": "...", "params": {...}}
```

Browser responds:

```json
{"response_to": "...", "data": {...}}
```

### Server-Sent Events (`GET /api/events`)

A one-way, stdlib-friendly event stream for **non-browser** subscribers (the CLI
`--subscribe` loop, scripts, `curl`). Every event the server broadcasts to
WebSocket clients — plus browser-driven `action` and `ext:` relays — is also
written here as an SSE frame:

```
: connected

data: {"event":"add-node","data":{"id":"Alice","label":"Alice"}}

data: {"event":"add-triplet","data":{"subject":"A","predicate":"knows","object":"B", ...}}

: ping
```

* `data:` lines carry the same JSON event objects as `/ws` (a `rev` field is
  included when present).
* `: ping` comments are sent every ~15s as a heartbeat.
* Each subscriber has a **bounded** queue; a slow/stuck consumer is dropped so
  it cannot leak server memory.
* Unlike `/ws`, this endpoint never receives browser-command traffic, so a
  plain streaming HTTP client can consume it safely. `/ws` is unchanged.

```bash
# Observe with curl
curl -N http://localhost:7849/api/events

# Observe with the CLI (see CLI section)
./graph-vis-cli.py --subscribe
```

## Node Hooks (Declarative Interactivity)

Nodes can define `on_click` and `on_doubleClick` arrays of actions in JSONL:

```jsonl
{"type":"node","id":"Root","label":"Root","on_click":[
  {"action":"toggle_node","id":"Child1"},
  {"action":"toggle_style","id":"Root","style":{"borderWidth":4}}
]}
{"type":"node","id":"Child1","label":"Child","hidden":true,"physics":false}
{"type":"edge","from":"Root","to":"Child1","hidden":true,"physics":false}
```

### Action Types

| Action | Fields | Behavior |
|--------|--------|----------|
| `toggle_node` | `id` | Toggle `hidden`/`physics` (show/hide with edges) |
| `toggle_edge` | `id` | Toggle edge `hidden`/`physics` |
| `restyle` | `id`, + props | Permanently update node/edge styling |
| `toggle_style` | `id`, `style` | Alternate between original and given style |
| `add_node` | `id`, `label?`, extras | Create new node (no-op if exists) |
| `remove_node` | `id` | Remove node + connected edges |
| `add_edge` | `from`, `to`, extras | Create new edge |
| `remove_edge` | `id` | Remove edge |

### Examples

* `examples/mindmap.jsonl` — expandable mind map (click to reveal/hide subtrees)
* `examples/styled-hooks.jsonl` — restyle vs toggle_style demonstrations

## JS/CSS Extensions

Load additional JavaScript and CSS from `static/extensions/` via `--ext` flag:

```bash
./graph-vis-server.py --ext color-spawner.js --ext color-spawner.css
# or: GRAPH_VIS_EXTENSIONS=color-spawner.js,color-spawner.css ./graph-vis-server.py
```

Extensions access the graph via `window.graphVis`:

```javascript
(function(gv) {
    gv.nodes;              // vis.DataSet
    gv.edges;              // vis.DataSet
    gv.network;            // vis.Network
    gv.container;          // #graph DOM element
    gv.api;                // REST API helper
    gv.executeAction(act); // execute a hook action
    gv.sendEvent(name, data);     // emit WS event (ext:<name>:<event>)
    gv.onCommand(name, handler);  // register WS command handler
})(window.graphVis);
```

### Bundled Extensions

| Extension | Description | Demo |
|-----------|-------------|------|
| `delete-on-doubleclick.js` | Backward-compat double-click delete modal | `examples/demos/delete-demo.sh` |
| `color-spawner.js/css` | HTML overlay textboxes, spawn colored children | `examples/demos/color-spawner-demo.sh` |
| `sum-propagation.js/css` | Tree with number inputs, sum propagates up | `examples/demos/sum-propagation-demo.sh` |
| `shortest-path.js/css` | Interactive Dijkstra with edge weight editing | `examples/demos/shortest-path-demo.sh` |
| `random-graph.js` | Generate random connected graphs | Combinable with others |

### Extension Transport Protocol

Extensions communicate with external subscribers via namespaced WebSocket events:

* Extension → outside: `{"event":"ext:<name>:<event>","data":{...}}`
* Outside → extension: `{"command":"ext:<name>:<cmd>","request_id":"...","params":{...}}`

## Multi-Client Collaboration

Multiple browsers, CLI clients, and API consumers collaborate in real time on the same graph.

### How it works

* **REST mutations** (add/remove node/edge, triplet, clear) → server updates store → broadcasts to ALL connected browsers via WebSocket
* **Hook actions** (toggle_node, restyle, add/remove via click) → browser executes locally → sends via WS → server updates store + relays to all other browsers
* **New clients** joining get the full graph state (including colors, hidden flags) via `GET /api/graph`

### Collaboration example

```bash
# Terminal 1: start server
./graph-vis-server.py

# Terminal 2: open on laptop
xdg-open http://localhost:7849

# Terminal 3: share with phone (e.g. via Tailscale)
echo "Open http://$(tailscale ip -4):7849 on your phone"

# Terminal 4: add nodes from CLI — appears on all browsers
echo "Alice knows Bob" | ./graph-vis-cli.py
echo "Bob likes Charlie" | ./graph-vis-cli.py

# All browsers update in real time, regardless of source
```

### Browser slash commands

Type in the browser text input:

* `/clear` — Clear the entire graph (blocked in read-only mode)
* `/help` — Show available commands

### Read-only mode

Block all mutations while allowing viewing, dragging, zoom/pan:

```bash
./graph-vis-server.py --read-only
# Mutation endpoints return 403, browser /clear shows alert
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_VIS_PORT` | `7849` | Server port |
| `GRAPH_VIS_HOST` | `0.0.0.0` (server) / `127.0.0.1` (CLI) | Bind address (server) / connect address (CLI) |
| `GRAPH_VIS_INPUT_MODE` | `minimal` | Initial input mode (multiline/single/minimal/none) |
| `GRAPH_VIS_EXTENSIONS` | — | Comma-separated extension filenames |
| `GRAPH_VIS_READ_ONLY` | — | Set to `1`/`true`/`yes` for read-only mode |

## CLI

Non-interactive by default (reads stdin). Use `--repl` for interactive mode.

```bash
# Pipe-friendly (default)
echo "Alice knows Bob" | ./graph-vis-cli.py

# Positional commands
./graph-vis-cli.py "Alice knows Bob" "g"

# Load files + commands
./graph-vis-cli.py -l examples/social-network.csv -l extra.ttl "g"

# Interactive REPL
./graph-vis-cli.py --repl

# Subscribe: stream graph events live (Ctrl-C to stop)
./graph-vis-cli.py --subscribe                 # human-readable lines
./graph-vis-cli.py --subscribe --format jsonl  # raw JSON per line (pipe to jq)
```

```bash
# Store graph to file
./graph-vis-cli.py "Alice knows Bob" "store graph.jsonl"

# Load, modify, store
./graph-vis-cli.py -l data.csv "Alice likes Eve" -s out.jsonl

# Format detected from extension
./graph-vis-cli.py -l data.csv -s graph.dot
./graph-vis-cli.py -l data.csv -s graph.csv
```

**Execution order:** connect → `--load` files → commands (positional/stdin/file) → `--store` → `--subscribe` → `--repl`

`--subscribe [--format jsonl|human]` opens a long-running SSE stream over `GET /api/events`, printing one line per graph event (from any source) until Ctrl-C (exits 0). Stdlib-only; implies no REPL.

Commands: `add/a/+`, `del/d/rm/-`, `list/ls/l`, `graph/g`, `clear`, `screenshot/ss`, `dom`, `ui hide/show`, `Load/L`, `store/Store/S`, `help/?/h`, `quit/q`

2 bare words = labelless edge, 3 bare words = add triplet.

Multiline blocks: `+++` (plain), `+++csv`, `+++jsonl`, `+++ttl`, `+++dot`, `+++mermaid`.

See `graph-vis-cli.README.md` for full reference.

## Format Converters

### Ingest (Load): format → graph

| Extension | Converter | Dependencies |
|-----------|-----------|-------------|
| `.csv` | `scripts/converters/csv2graph/csv2graph.py` | stdlib |
| `.ttl`, `.n3` | `scripts/converters/ttl2graph/ttl2graph.py` | rdflib (via uv) |
| `.dot`, `.gv` | `scripts/converters/dot2graph/dot2graph.py` | stdlib |
| `.mermaid`, `.mmd` | `scripts/converters/mermaid2graph/mermaid2graph.py` | stdlib |
| `.jsonl` | `scripts/converters/jsonl2graph/jsonl2graph.py` | stdlib |

### Export (Store): graph → format

| Extension | Converter | Lossless | Dependencies |
|-----------|-----------|----------|-------------|
| `.jsonl` | `scripts/converters/graph2jsonl/graph2jsonl.py` | Yes | stdlib |
| `.csv` | `scripts/converters/graph2csv/graph2csv.py` | No | stdlib |
| `.dot`, `.gv` | `scripts/converters/graph2dot/graph2dot.py` | No | stdlib |
| `.ttl`, `.n3` | `scripts/converters/graph2ttl/graph2ttl.py` | No | rdflib (via uv) |
| `.mermaid`, `.mmd` | `scripts/converters/graph2mermaid/graph2mermaid.py` | No | stdlib |

All converters work as both CLI tools and importable libraries. Only JSONL is lossless (preserves styling, hooks, extras). Other formats export triplets only.

## Testing

```bash
# Server unit tests (API + WebSocket + SSE + Extensions)
PYTHONPATH=. pytest tests/test_api.py tests/test_ws.py tests/test_sse.py tests/test_extensions.py -v -p no:playwright

# CLI unit tests (includes store command tests)
PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest

# Ingest converter tests
PYTHONPATH=. pytest tests/test_csv2graph.py tests/test_dot2graph.py tests/test_mermaid2graph.py tests/test_jsonl2graph.py -v -p no:playwright --noconftest

# Export converter tests (graph2X)
PYTHONPATH=. pytest tests/test_graph2jsonl.py tests/test_graph2csv.py tests/test_graph2dot.py tests/test_graph2mermaid.py -v -p no:playwright --noconftest

# TTL converter tests (require rdflib)
uv run --with rdflib pytest tests/test_ttl2graph.py tests/test_graph2ttl.py -v -p no:playwright --noconftest

# E2E tests (Docker)
./manage test
```

## Project Structure

```
graph-vis-server.py          # FastAPI server (uv run shebang)
graph-vis-cli.py             # REPL CLI client (stdlib-only)
static/index.html            # Frontend UI (hooks + extension loader)
static/deps/                 # vis-network local fallback
static/extensions/           # JS/CSS extensions (loaded via --ext)
tests/                       # Unit tests (pytest)
e2e/                         # E2E tests (Docker + Selenium)
manage                       # Docker orchestration script
examples/                    # Example graph files (.csv, .dot, .ttl, .mermaid, .jsonl)
examples/demos/              # Demo launcher scripts for extensions
docs/design/                 # Design documents
docs/plans/                  # Planning and feature roadmap documents
docs/tutorial/               # Illustrated tutorial with screenshots
qa/                          # QA procedures, CDP tools, screenshots
scripts/converters/          # Format converter scripts
├── csv2graph/               #   CSV → graph (ingest)
├── ttl2graph/               #   Turtle/N3 → graph (ingest)
├── dot2graph/               #   Graphviz DOT → graph (ingest)
├── mermaid2graph/           #   Mermaid → graph (ingest)
├── jsonl2graph/             #   JSONL → graph (ingest, with styling)
├── graph2jsonl/             #   graph → JSONL (export, lossless)
├── graph2csv/               #   graph → CSV (export)
├── graph2dot/               #   graph → Graphviz DOT (export)
├── graph2ttl/               #   graph → Turtle RDF (export)
└── graph2mermaid/           #   graph → Mermaid (export)
```
