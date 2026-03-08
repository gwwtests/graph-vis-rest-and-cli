# Extension Transport Protocol Design

## Overview

Extensions communicate with external subscribers (CLI tools, scripts, other services) through the existing WebSocket channel using namespaced event conventions. No new server code is needed for the relay — the server already broadcasts all WebSocket messages.

## Protocol Conventions

### Extension → External (events)

Extensions emit events by sending JSON messages through the WebSocket. Events are namespaced with `ext:<extension-name>:<event-name>`:

```json
{"event": "ext:color-spawner:node-created", "data": {"id": "child-1", "color": "#FF5733"}}
{"event": "ext:shortest-path:path-computed", "data": {"path": ["A", "B", "D"], "cost": 7}}
{"event": "ext:sum-propagation:sum-updated", "data": {"id": "root", "sum": 42}}
```

The server broadcasts these to all WebSocket clients. External subscribers filter by event prefix.

### External → Extension (commands)

External callers send commands using the existing `ws_command` request/response pattern:

```json
{"command": "ext:shortest-path:set-source", "request_id": "uuid", "params": {"node": "A"}}
```

The browser's `handleWsCommand` dispatches to the extension's registered handler. The extension responds:

```json
{"response_to": "uuid", "data": {"status": "ok", "path_count": 5}}
```

### Implementation in Core

The browser's `handleWsCommand` function gains a plugin dispatch mechanism:

```javascript
const extCommandHandlers = {};

window.graphVis.onCommand = function(commandName, handler) {
    extCommandHandlers[commandName] = handler;
};

async function handleWsCommand(msg) {
    const {command, request_id, params} = msg;
    let result = {};

    // Check extension handlers first
    if (extCommandHandlers[command]) {
        try {
            result = await extCommandHandlers[command](params);
        } catch (e) {
            result = {error: e.message};
        }
    } else {
        // Existing core command handling
        switch (command) {
            case 'capture-screenshot': ...
            case 'get-dom': ...
            case 'set-ui': ...
            default: result = {error: 'Unknown command: ' + command};
        }
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({response_to: request_id, data: result}));
    }
}
```

### Event Sending Helper

```javascript
window.graphVis.sendEvent = function(eventName, data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({event: eventName, data: data}));
    }
};
```

The server receives this on the WebSocket and broadcasts it to all other connected clients (the existing `broadcast` method). The server does not need to understand or parse extension events — it just relays.

## Server-Side Filtering (Future)

For now, the server blindly relays all WebSocket messages. In the future, subscribers could register interest in specific event prefixes via a REST endpoint:

```
POST /api/subscribe {"prefix": "ext:shortest-path:"}
```

This is out of scope for the initial implementation but the namespacing convention makes it easy to add later.

## External Subscriber Example

A Python script that subscribes to shortest-path updates:

```python
import asyncio, json, websockets

async def watch_shortest_path():
    async with websockets.connect("ws://localhost:7849/ws") as ws:
        async for msg in ws:
            data = json.loads(msg)
            if data.get("event", "").startswith("ext:shortest-path:"):
                print(f"Path update: {data['data']}")

asyncio.run(watch_shortest_path())
```

## Naming Conventions

| Pattern | Example | Purpose |
|---------|---------|---------|
| `ext:<name>:<noun>` | `ext:color-spawner:node-created` | Event emitted by extension |
| `ext:<name>:<verb>` | `ext:shortest-path:set-source` | Command sent to extension |
| Core events | `add-node`, `remove-edge`, `clear` | Unchanged, no prefix |
| Core commands | `capture-screenshot`, `get-dom` | Unchanged, no prefix |

Extension names should be lowercase kebab-case matching the JS filename without extension.
