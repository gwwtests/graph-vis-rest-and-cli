# Extension Examples Design

## Overview

Five extension demos that showcase the extension mechanism's capabilities, from simple (backward-compat delete) to complex (interactive Dijkstra). Each has a launcher script in `examples/demos/`.

---

## 1. delete-on-doubleclick

**Purpose:** Backward compatibility — restores the original double-click-to-delete behavior as a loadable extension.

**Files:** `static/extensions/delete-on-doubleclick.js`

**Behavior:**
- Registers `network.on('doubleClick', ...)` handler
- Shows confirmation modal: "Delete node {label}?"
- On confirm: calls `api.removeNode()` and broadcasts via REST
- Creates its own modal DOM elements on load (or reuses existing if present)

**Interaction with core hooks:** If a node has `on_doubleClick` hooks defined, those take priority — the extension only fires for nodes without hooks. This means hooks and the delete extension coexist.

**Launch:**
```bash
./examples/demos/delete-demo.sh
```

---

## 2. color-spawner

**Purpose:** Demonstrate HTML overlays on nodes with interactive elements (textbox + button) and dynamic graph mutation.

**Files:** `static/extensions/color-spawner.js`, `static/extensions/color-spawner.css`

**Behavior:**
- On load: creates a root node "Spawner" with an HTML overlay containing:
  - A text input showing a random hex color (e.g., `#FF5733`)
  - A "New" button
- Clicking "New" creates a child node colored with the textbox value
  - The child also gets its own overlay with a random hex color and "New" button
  - An edge connects parent → child
- Users can edit the hex color in any textbox before clicking "New"
- Each spawned child is independently functional (recursive spawning)

**HTML Overlay Implementation:**
- Uses `canvasToDOM()` for positioning overlays over nodes
- Overlays follow nodes on drag/zoom via `afterDrawing` event
- Each overlay is a positioned `<div>` with `pointer-events: auto`

**Events emitted:**
- `ext:color-spawner:node-created` — `{id, color, parent}`

**Launch:**
```bash
./examples/demos/color-spawner-demo.sh
```

---

## 3. sum-propagation

**Purpose:** Demonstrate bidirectional data flow — child values propagate sums upward through the tree.

**Files:** `static/extensions/sum-propagation.js`, `static/extensions/sum-propagation.css`

**Behavior:**
- On load: creates a root node "Root" with value `0` displayed in a textbox overlay
- Root has a "+" button to add child nodes
- Each child has:
  - A number input (textbox) initialized to `0`
  - A "+" button to add its own children
- When any number is changed in a textbox:
  - The node's displayed value updates
  - All ancestor nodes recompute their displayed value as the **sum of their children's values**
  - Propagation goes all the way up to the root
- Node labels show: `{name}: {value}` where value = own input value (for leaves) or sum of children (for non-leaves)

**Propagation Algorithm:**
```
function propagateUp(nodeId):
    children = getChildNodes(nodeId)
    if children.length == 0:
        return getInputValue(nodeId)
    sum = Σ propagateUp(child) for child in children
    updateDisplay(nodeId, sum)
    return sum
```

**Events emitted:**
- `ext:sum-propagation:value-changed` — `{id, value, sum}`
- `ext:sum-propagation:sum-updated` — `{id, sum}` (for non-leaf nodes)

**Launch:**
```bash
./examples/demos/sum-propagation-demo.sh
```

---

## 4. shortest-path

**Purpose:** Interactive Dijkstra's algorithm visualization with editable edge weights and real-time path recomputation.

**Files:** `static/extensions/shortest-path.js`, `static/extensions/shortest-path.css`

**Behavior:**

### Initial State
- Loads a sample weighted graph (6-8 nodes, 10-12 edges)
- Edge labels show weights (integers 1-10)
- A designated source node (e.g., "S") with `borderWidth: 4`
- All nodes display their shortest-path distance from S in their label

### Edge Weight Editing
- Clicking an edge opens a popup/modal to edit the weight
  - Small input field with current weight, "OK" and "Cancel" buttons
  - Positioned near the click location
- On confirm: edge weight updates, Dijkstra recomputes, all node labels and edge styles update

### Shortest Path Visualization
- Edges on the shortest path tree: bold (width 4), colored highlight
- Other edges: normal width (1-2), muted color
- Node labels: `{name}\n(d={distance})` where distance is shortest path from source
- Unreachable nodes: label shows `(d=∞)`

### Controls
- **"Randomize Weights"** button: assigns random weights 1-10 to all edges, recomputes
- **"New Random Graph"** button: generates a new random connected graph with n nodes and m edges
  - Default: 6 nodes, 10 edges
  - Node names: A, B, C, D, E, F...
  - Ensures connectivity (spanning tree + random extra edges)
  - Source node is always the first node

### Dijkstra Implementation
Standard priority-queue Dijkstra, runs entirely in the browser:

```javascript
function dijkstra(sourceId) {
    const dist = {};
    const prev = {};
    const visited = new Set();
    // Initialize
    nodes.forEach(n => { dist[n.id] = Infinity; prev[n.id] = null; });
    dist[sourceId] = 0;
    // Process
    while (visited.size < nodes.length) {
        const u = unvisited node with minimum dist;
        visited.add(u);
        for (const edge of edges connecting u) {
            const v = other endpoint;
            const alt = dist[u] + edge.weight;
            if (alt < dist[v]) {
                dist[v] = alt;
                prev[v] = u;
            }
        }
    }
    return { dist, prev };
}
```

### Events Emitted
- `ext:shortest-path:path-computed` — `{source, distances: {nodeId: dist}, tree_edges: [edgeId]}`
- `ext:shortest-path:weight-changed` — `{edgeId, oldWeight, newWeight}`
- `ext:shortest-path:graph-randomized` — `{nodeCount, edgeCount}`

### Commands Accepted
- `ext:shortest-path:set-source` — `{node: "A"}` — change source node
- `ext:shortest-path:randomize-weights` — `{}` — randomize all weights
- `ext:shortest-path:new-graph` — `{nodes: 6, edges: 10}` — generate new random graph

**Launch:**
```bash
./examples/demos/shortest-path-demo.sh
```

---

## 5. random-graph (utility extension)

**Purpose:** Adds a "Random Graph" button to generate random graphs on demand. Useful standalone and as a building block for other extensions.

**Files:** `static/extensions/random-graph.js`

**Behavior:**
- Adds a floating button "Random Graph" to the UI
- Clicking it generates a random connected graph:
  - Configurable node count (default 6) and edge density
  - Random node names (A-Z or generated)
  - Ensures connectivity via random spanning tree
  - Random edge labels (optional)
- Clears existing graph before generating

**Commands Accepted:**
- `ext:random-graph:generate` — `{nodes: 8, edges: 12, clear: true}`

**Events Emitted:**
- `ext:random-graph:generated` — `{nodeCount, edgeCount}`

**Launch:** Can be combined with any other extension:
```bash
./graph-vis-server.py --ext random-graph.js --ext shortest-path.js --ext shortest-path.css
```

---

## Example JSONL Files

### examples/mindmap.jsonl

A pre-built expandable mind map using core hooks (no extensions needed):

```
Machine Learning → Supervised → {SVM, Random Forest, Neural Networks}
                 → Unsupervised → {K-Means, PCA, DBSCAN}
                 → Reinforcement → {Q-Learning, Policy Gradient}
```

All children start hidden. Clicking a parent reveals/hides its children.

### examples/styled-hooks.jsonl

Demonstrates `restyle` and `toggle_style` actions — clicking nodes changes their color/shape.

### examples/shortest-path-graph.jsonl

A weighted graph for use with the shortest-path extension. Edge extras include `weight` field.

---

## Demo Script Convention

All demo scripts follow the pattern:

```bash
#!/bin/bash
# examples/demos/{name}-demo.sh
# Description of what the demo shows
cd "$(dirname "$0")/../.."
exec ./graph-vis-server.py \
    --ext {extension1}.js \
    --ext {extension1}.css \
    "$@"
```

The `"$@"` pass-through allows adding extra flags (e.g., `--port 9999`).

Each demo script is executable (`chmod +x`) and self-documenting with a header comment.
