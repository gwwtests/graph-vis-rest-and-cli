# Core Node Hooks System Design

## Overview

Declarative hooks on graph nodes that trigger actions (add/remove/toggle/restyle nodes and edges) in response to click and doubleClick events. Hooks are defined in JSONL input and stored as node extras, executed entirely in the browser.

## JSONL Format

Hooks are defined as `on_click` and `on_doubleClick` fields on node objects. Each is an array of action objects executed in order.

```jsonl
{"type":"node","id":"Topic","label":"Topic","on_click":[
  {"action":"toggle_node","id":"Sub1"},
  {"action":"toggle_edge","id":"Topic--Sub1"}
]}
{"type":"node","id":"Sub1","label":"Subtopic 1","hidden":true,"physics":false}
{"type":"edge","id":"Topic--Sub1","from":"Topic","to":"Sub1","hidden":true,"physics":false}
```

Pre-define all nodes/edges in JSONL. Use `"hidden":true,"physics":false` for initially-invisible elements that hooks reveal.

## Action Types

| Action | Required Fields | Optional Fields | Behavior |
|--------|----------------|-----------------|----------|
| `add_node` | `id` | `label`, vis-network extras | Create new node (no-op if exists) |
| `remove_node` | `id` | — | Remove node + connected edges |
| `add_edge` | `from`, `to` | `label`, `id`, extras | Create new edge |
| `remove_edge` | `id` | — | Remove edge |
| `toggle_node` | `id` | — | Toggle `hidden`/`physics` on existing node + its edges |
| `toggle_edge` | `id` | — | Toggle `hidden`/`physics` on existing edge |
| `restyle` | `id` | any vis-network property | Permanently update node/edge styling via `DataSet.update()` |
| `toggle_style` | `id`, `style` | — | Alternate between original and given style properties |

### toggle_node behavior

When toggling a node visible (`hidden: false, physics: true`), also toggle all edges that connect to/from it — but only edges where **both** endpoints would be visible after the toggle. This prevents orphan edges appearing when only one end is shown.

When toggling hidden (`hidden: true, physics: false`), hide the node and all its connected edges unconditionally.

### toggle_style behavior

First invocation: store current values of the properties being changed, apply new values.
Second invocation: restore stored original values. Alternates on each trigger.

Storage: use a `_original_style` field on the DataSet item (prefixed with underscore to avoid vis-network interpretation).

## Browser Implementation

### Event Dispatcher (in static/index.html)

Replace the hardcoded double-click delete handler with a generic dispatcher:

```javascript
function executeHookActions(nodeId, eventName) {
    const node = nodes.get(nodeId);
    if (!node) return;
    const actions = node['on_' + eventName];
    if (!actions || !Array.isArray(actions)) return;
    for (const action of actions) {
        executeAction(action);
    }
}

network.on('click', function(params) {
    if (params.nodes.length > 0) {
        const now = Date.now();
        if (now - lastClickTime < 300) {
            executeHookActions(params.nodes[0], 'doubleClick');
        } else {
            // Delay single-click to avoid firing before doubleClick detection
            setTimeout(() => {
                if (Date.now() - lastClickTime >= 300) {
                    executeHookActions(params.nodes[0], 'click');
                }
            }, 310);
        }
        lastClickTime = now;
    }
});
```

### Action Executor

```javascript
function executeAction(action) {
    switch (action.action) {
        case 'toggle_node': {
            const node = nodes.get(action.id);
            if (!node) return;
            const show = node.hidden !== false; // treat undefined as visible
            nodes.update({ id: action.id, hidden: !show, physics: show });
            // Toggle connected edges (only show if both endpoints visible)
            const connectedEdges = network.getConnectedEdges(action.id);
            for (const eid of connectedEdges) {
                const edge = edges.get(eid);
                if (!edge) continue;
                if (show) { // we're hiding this node
                    edges.update({ id: eid, hidden: true, physics: false });
                } else { // we're showing this node
                    const otherNodeId = edge.from === action.id ? edge.to : edge.from;
                    const otherNode = nodes.get(otherNodeId);
                    if (otherNode && !otherNode.hidden) {
                        edges.update({ id: eid, hidden: false, physics: true });
                    }
                }
            }
            break;
        }
        case 'toggle_edge': {
            const edge = edges.get(action.id);
            if (!edge) return;
            const show = edge.hidden !== false;
            edges.update({ id: action.id, hidden: !show, physics: show });
            break;
        }
        case 'restyle': {
            const { action: _, ...props } = action;
            const target = nodes.get(props.id) ? nodes : edges;
            target.update(props);
            break;
        }
        case 'toggle_style': {
            const { action: _, id, style } = action;
            const target = nodes.get(id) ? nodes : edges;
            const item = target.get(id);
            if (!item) return;
            const origKey = '_original_style';
            if (item[origKey]) {
                target.update({ id, ...item[origKey], [origKey]: null });
            } else {
                const original = {};
                for (const key of Object.keys(style)) {
                    original[key] = item[key];
                }
                target.update({ id, ...style, [origKey]: original });
            }
            break;
        }
        case 'add_node': {
            const { action: _, ...nodeData } = action;
            if (!nodes.get(nodeData.id)) {
                if (!nodeData.label) nodeData.label = nodeData.id;
                nodes.add(nodeData);
            }
            break;
        }
        case 'remove_node': {
            nodes.remove(action.id);
            break;
        }
        case 'add_edge': {
            const { action: _, ...edgeData } = action;
            if (!edgeData.id) {
                edgeData.id = `${edgeData.from}-${edgeData.label || ''}-${edgeData.to}`;
            }
            if (!edges.get(edgeData.id)) {
                edges.add(edgeData);
            }
            break;
        }
        case 'remove_edge': {
            edges.remove(action.id);
            break;
        }
    }
}
```

## Server-Side Changes

No server-side logic changes needed. The hook fields (`on_click`, `on_doubleClick`) are stored and broadcast as regular node extras via the existing `model_config = {"extra": "allow"}` mechanism. The browser executes hooks locally.

## Syncing Hook Actions Across Clients

When a hook executes `toggle_node`, `restyle`, etc., these are local DataSet operations. To sync across WebSocket clients, the browser should also POST the equivalent REST API call so the server broadcasts the change. This ensures multi-client consistency.

Implementation: `executeAction()` optionally calls the REST API after local DataSet mutation. Add a `sync` parameter (default `true`) that can be set to `false` when receiving broadcast updates to avoid loops.

## JSONL Converter Changes

No changes to `jsonl2graph.py` needed — `on_click` and `on_doubleClick` are already preserved as extras in the node object when outputting `--jsonl` format. For `--plain` and `--csv` output, hook data is naturally lost (these formats don't support extras).

## Example: Expandable Mind Map

```jsonl
# Root node with expand hook
{"type":"node","id":"ML","label":"Machine Learning","color":{"background":"#4CAF50"},"on_click":[
  {"action":"toggle_node","id":"Supervised"},
  {"action":"toggle_node","id":"Unsupervised"},
  {"action":"toggle_style","id":"ML","style":{"borderWidth":4,"color":{"border":"#FFD700"}}}
]}

# Children (initially hidden)
{"type":"node","id":"Supervised","label":"Supervised","hidden":true,"physics":false,"on_click":[
  {"action":"toggle_node","id":"SVM"},
  {"action":"toggle_node","id":"RF"}
]}
{"type":"node","id":"Unsupervised","label":"Unsupervised","hidden":true,"physics":false}

# Grandchildren (initially hidden)
{"type":"node","id":"SVM","label":"SVM","hidden":true,"physics":false}
{"type":"node","id":"RF","label":"Random Forest","hidden":true,"physics":false}

# Edges (initially hidden)
{"type":"edge","from":"ML","to":"Supervised","hidden":true,"physics":false}
{"type":"edge","from":"ML","to":"Unsupervised","hidden":true,"physics":false}
{"type":"edge","from":"Supervised","to":"SVM","hidden":true,"physics":false}
{"type":"edge","from":"Supervised","to":"RF","hidden":true,"physics":false}
```

Clicking "Machine Learning" reveals/hides "Supervised" and "Unsupervised" with their edges, and highlights the root with a gold border. Clicking "Supervised" reveals/hides "SVM" and "Random Forest".
