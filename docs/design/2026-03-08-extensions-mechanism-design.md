# JS/CSS Extensions Mechanism Design

## Overview

The server can load additional JavaScript and CSS files from `static/extensions/` to extend browser-side functionality. This keeps the core `index.html` minimal while allowing rich interactive features via composable extension modules.

## Loading Mechanism

### Server-Side

Extensions are specified via CLI flags and/or environment variable:

```bash
# CLI flags (repeatable)
./graph-vis-server.py --ext color-spawner.js --ext color-spawner.css

# Environment variable (comma-separated)
GRAPH_VIS_EXTENSIONS=color-spawner.js,color-spawner.css ./graph-vis-server.py

# Both combined (merged, deduplicated)
GRAPH_VIS_EXTENSIONS=shortest-path.js ./graph-vis-server.py --ext color-spawner.js
```

Extension filenames are relative to `static/extensions/`. The server validates that each file exists at startup and exits with an error if not found.

### Server Implementation

Add a new endpoint that returns the list of active extensions:

```python
@app.get("/api/extensions")
async def get_extensions():
    return {"extensions": active_extensions}
```

Where `active_extensions` is a list of `{"type": "js"|"css", "path": "/static/extensions/filename"}` objects built at startup from the CLI flags and env var.

### Browser-Side

On page load, the browser fetches `/api/extensions` and dynamically injects `<script>` and `<link>` tags:

```javascript
async function loadExtensions() {
    const resp = await fetch('/api/extensions');
    const { extensions } = await resp.json();
    for (const ext of extensions) {
        if (ext.type === 'css') {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = ext.path;
            document.head.appendChild(link);
        } else if (ext.type === 'js') {
            await new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = ext.path;
                script.onload = resolve;
                script.onerror = reject;
                document.body.appendChild(script);
            });
        }
    }
}
```

JS extensions are loaded sequentially (in specified order) to allow dependencies. CSS is loaded in order too (later files override earlier).

## Extension API Contract

Extensions receive access to the graph via a global `graphVis` object exposed by the core:

```javascript
// Exposed by index.html before extensions load
window.graphVis = {
    // Data access
    nodes,          // vis.DataSet
    edges,          // vis.DataSet
    network,        // vis.Network instance

    // WebSocket
    ws,             // WebSocket connection
    sendEvent(name, data),   // send ext:<name> event
    onCommand(name, handler), // register handler for ext:<name> commands

    // Core hook system
    executeAction(action),   // execute a hook action programmatically

    // Utilities
    container,      // DOM element for the graph
    api,            // REST API helper object
};
```

### Extension Registration Pattern

Extensions self-register via a conventional pattern:

```javascript
// static/extensions/my-extension.js
(function(gv) {
    'use strict';

    const EXTENSION_NAME = 'my-extension';

    // Register event handlers
    gv.network.on('click', function(params) {
        // custom click handling
    });

    // Register for WS commands from external callers
    gv.onCommand(`ext:${EXTENSION_NAME}:do-something`, function(params) {
        // handle command, return result
        return { status: 'ok' };
    });

    // Emit events to external subscribers
    function notifyExternalSubscribers(data) {
        gv.sendEvent(`ext:${EXTENSION_NAME}:something-happened`, data);
    }

    console.log(`[${EXTENSION_NAME}] loaded`);

})(window.graphVis);
```

## Directory Structure

```
static/extensions/
├── delete-on-doubleclick.js     # Backward-compat delete modal
├── color-spawner.js             # Color spawner demo
├── color-spawner.css            # Color spawner styles
├── sum-propagation.js           # Sum propagation demo
├── sum-propagation.css          # Sum propagation styles
├── shortest-path.js             # Dijkstra visualization
├── shortest-path.css            # Shortest path styles
└── random-graph.js              # Random graph generator
```

## Demo Launch Scripts

Each extension demo has a launcher script in `examples/demos/`:

```bash
#!/bin/bash
# examples/demos/color-spawner-demo.sh
exec ./graph-vis-server.py \
    --ext color-spawner.js \
    --ext color-spawner.css \
    "$@"
```

```bash
#!/bin/bash
# examples/demos/shortest-path-demo.sh
exec ./graph-vis-server.py \
    --ext shortest-path.js \
    --ext shortest-path.css \
    "$@"
```

```bash
#!/bin/bash
# examples/demos/mindmap-demo.sh
# Core hooks only — no extensions needed
exec ./graph-vis-server.py "$@"
# Then load: examples/mindmap.jsonl via CLI
```

## HTML Overlays for Extensions

Since vis-network is Canvas-based and doesn't support HTML inside nodes, extensions that need HTML elements (textboxes, buttons) use DOM overlay positioning:

```javascript
// Create an overlay div positioned over a node
function createNodeOverlay(nodeId, htmlContent) {
    const overlay = document.createElement('div');
    overlay.className = 'ext-node-overlay';
    overlay.innerHTML = htmlContent;
    overlay.dataset.nodeId = nodeId;
    document.getElementById('graph-container').appendChild(overlay);
    updateOverlayPosition(overlay, nodeId);
    return overlay;
}

function updateOverlayPosition(overlay, nodeId) {
    const pos = gv.network.getPosition(nodeId);
    const domPos = gv.network.canvasToDOM(pos);
    overlay.style.left = domPos.x + 'px';
    overlay.style.top = domPos.y + 'px';
}

// Update positions on network events
gv.network.on('afterDrawing', () => {
    document.querySelectorAll('.ext-node-overlay').forEach(overlay => {
        updateOverlayPosition(overlay, overlay.dataset.nodeId);
    });
});
```

Extensions must handle cleanup when nodes are removed and repositioning on zoom/pan/drag.

## Bundled vs. User Extensions

All extensions in `static/extensions/` ship with the project. Users can add their own extensions to the same directory. The `--ext` flag doesn't distinguish between bundled and user extensions — they're all files in the extensions directory.

Future consideration: allow `--ext-dir` to specify additional directories, but this is not in scope for the initial implementation.
