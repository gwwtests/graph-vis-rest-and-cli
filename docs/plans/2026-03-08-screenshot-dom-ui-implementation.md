# Screenshot, DOM & UI Control — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add screenshot capture, DOM introspection, and UI toggle via WS command-response protocol between server and browser, with CLI commands.

**Architecture:** Server sends commands to browser via WebSocket, browser responds with data. New REST endpoints (`/api/screenshot`, `/api/dom`, `/api/ui`) act as bridges. CLI wraps these endpoints.

**Tech Stack:** FastAPI (server), vis-network JS API (browser), stdlib urllib (CLI)

---

### Task 1: WS Command-Response Infrastructure (Server)

Add async request/response dispatch to the server. When an HTTP endpoint needs browser data, it sends a WS command and awaits the response.

**Files:**

* Modify: `graph-vis-server.py`

**Step 1: Add pending requests dict and command dispatch**

Add to server after `ConnectionManager`:

```python
import asyncio
import uuid

# Pending WS command-response requests
_pending_requests: dict[str, asyncio.Future] = {}

async def ws_command(command: str, params: dict = None, timeout: float = 10.0) -> dict:
    """Send a command to the first connected browser and await response."""
    if not manager.active_connections:
        return None
    request_id = str(uuid.uuid4())
    future = asyncio.get_event_loop().create_future()
    _pending_requests[request_id] = future
    try:
        conn = manager.active_connections[0]
        await conn.send_json({
            "command": command,
            "request_id": request_id,
            "params": params or {},
        })
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        return None
    finally:
        _pending_requests.pop(request_id, None)
```

**Step 2: Handle responses in WebSocket endpoint**

Update `websocket_endpoint` to detect response messages:

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            text = await websocket.receive_text()
            # Check if this is a command response
            import json
            try:
                msg = json.loads(text)
                if "response_to" in msg:
                    req_id = msg["response_to"]
                    if req_id in _pending_requests:
                        _pending_requests[req_id].set_result(msg.get("data", {}))
                    continue
            except (json.JSONDecodeError, KeyError):
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

**Step 3: Run tests**

```bash
PYTHONPATH=. pytest tests/test_api.py tests/test_ws.py -v -p no:playwright
```

Expected: All 20 existing tests still pass.

**Step 4: Commit**

```bash
git add graph-vis-server.py
git commit -m "feat: Add WS command-response infrastructure to server"
```

---

### Task 2: Screenshot Endpoint (Server)

**Files:**

* Modify: `graph-vis-server.py`

**Step 1: Add screenshot endpoint**

```python
from fastapi import Query
from fastapi.responses import Response
import base64

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
    params = {
        "padding": padding, "fit": fit, "format": format,
        "quality": quality, "width": width, "height": height,
        "hide_ui": hide_ui, "background": background,
    }
    result = await ws_command("capture-screenshot", params, timeout=15.0)
    if result is None:
        return Response(status_code=503, content="No browser connected")

    image_data = result.get("image", "")
    # Strip data URI prefix
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]

    media_type = "image/png" if format == "png" else "image/jpeg"
    return Response(
        content=base64.b64decode(image_data),
        media_type=media_type,
        headers={"Content-Disposition": f"inline; filename=graph.{format}"},
    )
```

**Step 2: Commit**

```bash
git add graph-vis-server.py
git commit -m "feat: Add /api/screenshot endpoint"
```

---

### Task 3: DOM and UI Endpoints (Server)

**Files:**

* Modify: `graph-vis-server.py`

**Step 1: Add DOM endpoint**

```python
@app.get("/api/dom")
async def get_dom():
    result = await ws_command("get-dom", timeout=5.0)
    if result is None:
        return Response(status_code=503, content="No browser connected")
    return result
```

**Step 2: Add UI endpoint**

```python
class UIRequest(BaseModel):
    input_visible: bool = None

@app.post("/api/ui")
async def set_ui(req: UIRequest):
    params = {}
    if req.input_visible is not None:
        params["input_visible"] = req.input_visible
    result = await ws_command("set-ui", params, timeout=5.0)
    if result is None:
        return Response(status_code=503, content="No browser connected")
    return {"ok": True, **result}
```

**Step 3: Commit**

```bash
git add graph-vis-server.py
git commit -m "feat: Add /api/dom and /api/ui endpoints"
```

---

### Task 4: Browser Command Handler (Frontend)

**Files:**

* Modify: `static/index.html`

**Step 1: Add WS command handler in `ws.onmessage`**

Update the existing `ws.onmessage` to detect commands:

```javascript
ws.onmessage = (evt) => {
    const msg = JSON.parse(evt.data);
    if (msg.command) {
        handleWsCommand(msg);
    } else {
        handleWsEvent(msg);
    }
};
```

**Step 2: Implement `handleWsCommand` dispatcher**

```javascript
async function handleWsCommand(msg) {
    const {command, request_id, params} = msg;
    let result = {};
    try {
        switch (command) {
            case 'capture-screenshot':
                result = await captureScreenshot(params);
                break;
            case 'get-dom':
                result = getDomInfo();
                break;
            case 'set-ui':
                result = setUiState(params);
                break;
            default:
                result = {error: 'Unknown command: ' + command};
        }
    } catch (e) {
        result = {error: e.message};
    }
    ws.send(JSON.stringify({response_to: request_id, data: result}));
}
```

**Step 3: Implement `captureScreenshot`**

```javascript
async function captureScreenshot(params) {
    const {padding = 0.1, fit = true, format = 'png', quality = 0.92,
           width, height, hide_ui = true, background = 'white'} = params;

    const inputContainer = document.getElementById('input-container');
    const modeToggle = document.getElementById('mode-toggle');
    const wsStatusEl = document.getElementById('ws-status');

    // Save and hide UI
    const savedDisplay = {};
    if (hide_ui) {
        for (const el of [inputContainer, modeToggle, wsStatusEl]) {
            savedDisplay[el.id] = el.style.display;
            el.style.display = 'none';
        }
    }

    // Save original canvas size
    const graphEl = document.getElementById('graph');
    const savedWidth = graphEl.style.width;
    const savedHeight = graphEl.style.height;

    // Resize if requested
    if (width) graphEl.style.width = width + 'px';
    if (height) graphEl.style.height = height + 'px';
    if (width || height) network.redraw();

    // Fit to content
    if (fit) {
        const allNodeIds = nodes.getIds();
        if (allNodeIds.length > 0) {
            network.fit({nodes: allNodeIds, animation: false,
                        minZoomLevel: 0.1, maxZoomLevel: 5});
        }
    }

    // Wait for render
    await new Promise(r => setTimeout(r, 100));

    // Set background and capture
    const canvas = document.querySelector('#graph canvas');
    const ctx = canvas.getContext('2d');

    // Create a copy with background
    const tempCanvas = document.createElement('canvas');
    tempCanvas.width = canvas.width;
    tempCanvas.height = canvas.height;
    const tempCtx = tempCanvas.getContext('2d');
    tempCtx.fillStyle = background;
    tempCtx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
    tempCtx.drawImage(canvas, 0, 0);

    const mimeType = format === 'jpeg' ? 'image/jpeg' : 'image/png';
    const image = tempCanvas.toDataURL(mimeType, quality);

    // Restore
    if (width || height) {
        graphEl.style.width = savedWidth;
        graphEl.style.height = savedHeight;
        network.redraw();
    }
    if (hide_ui) {
        for (const el of [inputContainer, modeToggle, wsStatusEl]) {
            el.style.display = savedDisplay[el.id];
        }
    }

    return {image};
}
```

**Step 4: Implement `getDomInfo`**

```javascript
function getDomInfo() {
    const positions = network.getPositions();
    const scale = network.getScale();
    const viewPosition = network.getViewPosition();
    const canvas = document.querySelector('#graph canvas');

    const nodeList = nodes.get().map(n => ({
        ...n,
        x: positions[n.id] ? positions[n.id].x : null,
        y: positions[n.id] ? positions[n.id].y : null,
    }));

    const edgeList = edges.get();

    return {
        viewport: {
            x: viewPosition.x,
            y: viewPosition.y,
        },
        nodes: nodeList,
        edges: edgeList,
        canvas: {
            width: canvas.width,
            height: canvas.height,
        },
        scale: scale,
    };
}
```

**Step 5: Implement `setUiState`**

```javascript
function setUiState(params) {
    const inputContainer = document.getElementById('input-container');
    const modeToggle = document.getElementById('mode-toggle');

    if (params.input_visible !== undefined) {
        const display = params.input_visible ? '' : 'none';
        inputContainer.style.display = params.input_visible ? 'flex' : 'none';
        modeToggle.style.display = params.input_visible ? '' : 'none';
    }
    return {ok: true};
}
```

**Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat: Add WS command handler for screenshot, DOM, and UI control"
```

---

### Task 5: CLI Commands

**Files:**

* Modify: `graph-vis-cli.py`

**Step 1: Add screenshot method to GraphClient**

```python
def screenshot(self, filename=None, **params):
    """Download screenshot. Returns raw image bytes."""
    query = '&'.join(f'{k}={v}' for k, v in params.items() if v is not None)
    url = f"{self.base_url}/api/screenshot"
    if query:
        url += '?' + query
    req = urllib.request.Request(url)
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        data = resp.read()
        if filename:
            with open(filename, 'wb') as f:
                f.write(data)
        return data
    except urllib.error.HTTPError as e:
        if e.code == 503:
            return None
        raise

def get_dom(self):
    return self._request("GET", "/api/dom")

def set_ui(self, input_visible):
    return self._request("POST", "/api/ui", {"input_visible": input_visible})
```

**Step 2: Add REPL commands**

```python
def do_screenshot(self, arg):
    """screenshot [filename] — Save graph screenshot (shortcut: ss)"""
    filename = arg.strip() or "graph.png"
    data = self.client.screenshot(filename=filename)
    if data is None:
        print("Error: No browser connected (503)")
        return
    print(f"Saved: {filename} ({len(data)} bytes)")

do_ss = do_screenshot

def do_dom(self, arg):
    """dom — Show graph DOM/layout info"""
    result = self.client.get_dom()
    if result is None:
        print("Error: No browser connected (503)")
        return
    import json
    print(json.dumps(result, indent=2))

def do_ui(self, arg):
    """ui hide|show — Toggle input controls (shortcuts: ui off/on)"""
    arg = arg.strip().lower()
    if arg in ('hide', 'off'):
        self.client.set_ui(False)
        print("UI hidden.")
    elif arg in ('show', 'on'):
        self.client.set_ui(True)
        print("UI shown.")
    else:
        print("Usage: ui hide|show")
```

**Step 3: Update help text**

Add to the help output:

```
  screenshot / ss  [filename]            Save graph screenshot
  dom                                    Show graph layout info
  ui               hide|show             Toggle input controls
```

**Step 4: Run CLI tests**

```bash
PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest
```

**Step 5: Commit**

```bash
git add graph-vis-cli.py
git commit -m "feat: Add screenshot, dom, ui commands to CLI"
```

---

### Task 6: Unit Tests for New Endpoints

**Files:**

* Modify: `tests/test_api.py`

**Step 1: Add tests for 503 when no browser connected**

```python
def test_screenshot_no_browser(client):
    resp = client.get("/api/screenshot")
    assert resp.status_code == 503

def test_dom_no_browser(client):
    resp = client.get("/api/dom")
    assert resp.status_code == 503

def test_ui_no_browser(client):
    resp = client.post("/api/ui", json={"input_visible": False})
    assert resp.status_code == 503
```

**Step 2: Run tests**

```bash
PYTHONPATH=. pytest tests/test_api.py -v -p no:playwright
```

**Step 3: Commit**

```bash
git add tests/test_api.py
git commit -m "test: Add unit tests for screenshot/dom/ui 503 responses"
```

---

### Task 7: Update Documentation

**Files:**

* Modify: `AGENTS.md`
* Modify: `graph-vis-server.README.md`
* Modify: `graph-vis-cli.README.md`
* Modify: `graph-vis-server.DEV_NOTES.md`
* Modify: `graph-vis-cli.DEV_NOTES.md`

**Step 1: Add new endpoints to AGENTS.md API table**

Add to REST Endpoints table:

```
| GET | `/api/screenshot` | query params | Capture graph as PNG/JPEG |
| GET | `/api/dom` | — | Graph layout introspection |
| POST | `/api/ui` | `{input_visible}` | Toggle browser UI |
```

Add to CLI commands:

```
Commands: ..., `screenshot/ss`, `dom`, `ui hide/show`
```

**Step 2: Update server README with new endpoints**

**Step 3: Update CLI README with new commands**

**Step 4: Update DEV_NOTES for both scripts**

**Step 5: Commit**

```bash
git add AGENTS.md graph-vis-server.README.md graph-vis-cli.README.md \
        graph-vis-server.DEV_NOTES.md graph-vis-cli.DEV_NOTES.md
git commit -m "docs: Document screenshot, DOM, and UI control endpoints"
```

---

## Verification

1. Start server: `./graph-vis-server.py`
2. Open browser: `http://localhost:7849`
3. Add some nodes: `echo "Alice knows Bob" | ./graph-vis-cli.py`
4. Take screenshot: `./graph-vis-cli.py "ss graph.png"` — saves PNG
5. `curl http://localhost:7849/api/screenshot > test.png` — binary PNG
6. `curl http://localhost:7849/api/screenshot?format=jpeg&quality=0.5` — low-quality JPEG
7. `curl http://localhost:7849/api/dom | jq .` — JSON with positions
8. CLI: `dom` — prints layout JSON
9. CLI: `ui hide` — input box disappears in browser
10. CLI: `ui show` — input box reappears
11. With no browser: all three return 503
