# graph-vis-server.py — Developer Notes

## Architecture

Single-file FastAPI server with three core components:

* **GraphStore** — In-memory dict-based graph storage. Node ID = label. Edge ID = `{from}-{label}-{to}`. Cascade delete on node removal.
* **ConnectionManager** — WebSocket broadcast to all connected clients. Tolerates disconnects gracefully.
* **REST endpoints** — Action-based (not RESTful CRUD). Each mutation broadcasts via WS.

## Key Design Decisions

* **PEP 723 inline metadata** — Dependencies declared in script header for `uv run` shebang. No separate requirements.txt needed for server execution.
* **Static mount at `/static`** — vis-network JS/CSS served locally with CDN fallback in HTML.
* **Root `/` serves `index.html`** — FileResponse, not redirect, so bookmarks work.
* **Edge ID convention** — `{from}-{label}-{to}` means duplicate edges with same subject/predicate/object overwrite silently. This is intentional (idempotent adds).

## Import Symlink

`graph_vis_server.py` → `graph-vis-server.py` symlink exists for Python imports (dashes aren't valid in module names). Listed in `.gitignore`.

## Testing

```bash
PYTHONPATH=. pytest tests/test_api.py tests/test_ws.py -v -p no:playwright
```

Tests use `fastapi.testclient.TestClient` (sync). `conftest.py` resets `store` and `manager` between tests.

## Gotchas

* `-p no:playwright` flag needed if pytest-playwright is installed globally without playwright browsers.
* `PYTHONPATH=.` required so pytest finds the symlink for imports.
* The `Field(alias="from")` trick in `AddEdgeRequest` handles `from` being a Python keyword.

## Planned Additions

* `/api/screenshot` — WS command-response to capture browser canvas (see design doc).
* `/api/dom` — WS command-response to get graph layout introspection.
* `/api/ui` — WS command to toggle UI visibility.
