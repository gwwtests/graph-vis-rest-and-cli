# graph2mermaid

## Problem Statement

Given a JSON object representing a graph (as returned by the `/api/graph`
REST endpoint), produce a valid Mermaid `graph LR` definition containing all
directed edges and their labels.

Mermaid is a **lossy** export format. Only node IDs and edge relationships
(source, target, label) are preserved. All styling extras (colors, shapes,
physics, hidden state, hooks, etc.) are silently dropped.

## Input Format

A JSON object with two arrays:

```json
{
  "nodes": [{"id": "Alice", "label": "Alice", ...extras}],
  "edges": [{"id": "e1", "from": "Alice", "to": "Bob", "label": "knows", ...extras}]
}
```

* `nodes[].id` is the node identifier (required).
* `edges[].from` and `edges[].to` are node identifiers (required).
* `edges[].label` is an optional edge label string.
* All other fields are ignored.

### Example Input (`simple.json`)

```json
{"nodes": [{"id": "Alice"}, {"id": "Bob"}, {"id": "Charlie"}],
 "edges": [{"id": "e1", "from": "Alice", "to": "Bob", "label": "knows"},
           {"id": "e2", "from": "Bob", "to": "Charlie", "label": "likes"}]}
```

## Output Format

A Mermaid graph definition:

```
graph LR
    Alice -->|knows| Bob
    Bob -->|likes| Charlie
```

### Rules

* First line is always `graph LR`.
* Labelled edges: `    SRC -->|LABEL| DST` (4-space indent).
* Unlabelled edges (missing or empty label): `    SRC --> DST`.
* Nodes with no edges get a standalone line: `    NodeId`.
* Edges are sorted lexicographically by `(from, to, label)`.
* Standalone nodes are sorted lexicographically and listed after edges.

### Edge Cases

* Empty graph (`{"nodes": [], "edges": []}`) outputs only `graph LR`.
* A single node with no edges outputs:

      graph LR
          NodeId
