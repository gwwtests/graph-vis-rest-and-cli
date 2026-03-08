# Graph Visualization Server with REST API + WebSocket

## Overview

A graph visualization web app with a Python FastAPI backend. The frontend is adapted from tripleter v5 (vis-network triplet graph builder), connecting via REST + WebSocket APIs for graph mutation and multi-client sync.

## Architecture

```
Browser (vis-network)  ←→  FastAPI server (graph-vis-server.py)  ←→  graph-vis-cli.py
   ├── REST API: mutation requests     ├── GraphStore (in-memory)     ├── REPL commands
   ├── WebSocket: real-time sync       ├── ConnectionManager          ├── Load from files
   └── Static files served from /      └── Static mount (/static)    └── Format converters
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
| GET | `/api/highlight-mode` | — | Get current highlight settings |
| POST | `/api/highlight-mode` | `{mode?, fadeDuration?, ...}` | Set highlight mode (fade/pulse/glow) |
| GET | `/api/screenshot` | query params | Capture graph as PNG/JPEG (via browser) |
| GET | `/api/dom` | — | Graph layout introspection (via browser) |
| POST | `/api/ui` | `{input_visible}` | Toggle browser UI elements |

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
```

Server can also send commands to the browser and receive responses:

```json
{"command": "capture-screenshot", "request_id": "...", "params": {...}}
```

Browser responds:

```json
{"response_to": "...", "data": {...}}
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

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_VIS_PORT` | `7849` | Server port |
| `GRAPH_VIS_HOST` | `0.0.0.0` (server) / `127.0.0.1` (CLI) | Bind address (server) / connect address (CLI) |
| `GRAPH_VIS_INPUT_MODE` | `multiline` | Initial input mode (multiline/single/minimal/none) |
| `GRAPH_VIS_EXTENSIONS` | — | Comma-separated extension filenames |

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
```

**Execution order:** connect → `--load` files → commands (positional/stdin/file) → `--repl`

Commands: `add/a/+`, `del/d/rm/-`, `list/ls/l`, `graph/g`, `clear`, `screenshot/ss`, `dom`, `ui hide/show`, `Load/L`, `help/?/h`, `quit/q`

2 bare words = labelless edge, 3 bare words = add triplet.

Multiline blocks: `+++` (plain), `+++csv`, `+++jsonl`, `+++ttl`, `+++dot`, `+++mermaid`.

See `graph-vis-cli.README.md` for full reference.

## Format Converters

Load graphs from files via the `L` command or use converters standalone:

| Extension | Converter | Dependencies |
|-----------|-----------|-------------|
| `.csv` | `scripts/converters/csv2graph/csv2graph.py` | stdlib |
| `.ttl`, `.n3` | `scripts/converters/ttl2graph/ttl2graph.py` | rdflib (via uv) |
| `.dot`, `.gv` | `scripts/converters/dot2graph/dot2graph.py` | stdlib |
| `.mermaid`, `.mmd` | `scripts/converters/mermaid2graph/mermaid2graph.py` | stdlib |
| `.jsonl` | `scripts/converters/jsonl2graph/jsonl2graph.py` | stdlib |

Each converter outputs an intermediate format (plain/`--csv`/`--jsonl`) and works as both a CLI tool and an importable library.

## Testing

```bash
# Server unit tests (API + WebSocket + Extensions)
PYTHONPATH=. pytest tests/test_api.py tests/test_ws.py tests/test_extensions.py -v -p no:playwright

# CLI unit tests
PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest

# JSONL converter tests
PYTHONPATH=. pytest tests/test_jsonl2graph.py -v -p no:playwright

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
scripts/converters/          # Format converter scripts
├── csv2graph/               #   CSV → graph
├── ttl2graph/               #   Turtle/N3 → graph
├── dot2graph/               #   Graphviz DOT → graph
├── mermaid2graph/           #   Mermaid → graph
└── jsonl2graph/             #   JSONL → graph (with styling)
```
