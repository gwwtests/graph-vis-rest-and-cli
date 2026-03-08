# Screenshot, DOM Introspection & UI Control — Design

## Context

Add screenshot capture, graph layout introspection, and UI toggle capabilities. The browser serves as the renderer; server and CLI control it via a WebSocket command-response protocol.

## Design Summary

```
                 GET /api/screenshot?padding=0.1
                 GET /api/dom
                 POST /api/ui
CLI ──REST──→ Server ──WS command──→ Browser
                 ↑                      │
                 └──WS response─────────┘
                 ↓
              HTTP response (image/json)
```

### WS Command-Response Protocol

Browser receives commands on the existing `/ws` connection:

```json
{"command": "capture-screenshot", "request_id": "abc123", "params": {"padding": 0.1, "format": "png"}}
{"command": "get-dom", "request_id": "def456", "params": {}}
{"command": "set-ui", "request_id": "ghi789", "params": {"input_visible": false}}
```

Browser responds:

```json
{"response_to": "abc123", "data": {"image": "data:image/png;base64,..."}}
{"response_to": "def456", "data": {"viewport": {...}, "nodes": [...], "scale": 1.2}}
{"response_to": "ghi789", "data": {"ok": true}}
```

### Screenshot Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `padding` | `0.1` | Extra space around graph (fraction) |
| `fit` | `true` | Auto-fit to content before capture |
| `format` | `png` | `png` or `jpeg` |
| `quality` | `0.92` | JPEG quality (ignored for PNG) |
| `width` | *current* | Override canvas width |
| `height` | *current* | Override canvas height |
| `hide_ui` | `true` | Hide input box/buttons |
| `background` | `white` | Background color |

### DOM Response

```json
{
  "viewport": {"x": -200, "y": -150, "width": 800, "height": 600},
  "nodes": [{"id": "Alice", "x": 50, "y": 120, "shape": "circle", "label": "Alice"}],
  "edges": [{"id": "Alice-knows-Bob", "from": "Alice", "to": "Bob", "label": "knows"}],
  "canvas": {"width": 1200, "height": 800},
  "scale": 1.2
}
```

### CLI Commands

```
screenshot [filename]    Save graph screenshot (shortcut: ss)
dom                      Show graph DOM/layout info
ui hide                  Hide input controls (shortcut: ui off)
ui show                  Show input controls (shortcut: ui on)
```
