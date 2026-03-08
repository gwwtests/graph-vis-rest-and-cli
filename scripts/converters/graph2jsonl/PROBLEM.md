# graph2jsonl

## Problem Statement

Given a JSON object representing a graph (as returned by the `/api/graph`
endpoint), convert it to JSONL format where each line is a self-contained JSON
object describing one graph element.

This is the **reverse** of `jsonl2graph`: it exports a graph to JSONL for
archival, transfer, or re-import.  The conversion is **lossless** -- all node
and edge properties including styling extras, hooks (`on_click`,
`on_doubleClick`), visibility flags (`hidden`, `physics`), and any other
arbitrary fields are preserved.

## Input Format

A JSON object with two keys:

* `nodes` -- array of node objects, each with at least `id` and `label`
* `edges` -- array of edge objects, each with at least `from` and `to`

Both may contain arbitrary extra fields.

### Example Input

```json
{
  "nodes": [
    {"id": "Alice", "label": "Alice", "color": "red"},
    {"id": "Bob", "label": "Bob"}
  ],
  "edges": [
    {"id": "Alice-knows-Bob", "from": "Alice", "to": "Bob", "label": "knows", "width": 3}
  ]
}
```

## Output Format

JSONL (one JSON object per line). Nodes are emitted first, then edges.

Each node line has `"type": "node"` plus all original fields.
Each edge line has `"type": "edge"` plus all original fields.

### Example Output

```
{"type": "node", "id": "Alice", "label": "Alice", "color": "red"}
{"type": "node", "id": "Bob", "label": "Bob"}
{"type": "edge", "id": "Alice-knows-Bob", "from": "Alice", "to": "Bob", "label": "knows", "width": 3}
```

## Round-Trip Property

The output of `graph2jsonl` is valid input for `jsonl2graph`.  For graphs
that were originally created from JSONL (without triplet shorthand), the
round-trip `graph -> JSONL -> graph` should produce an equivalent graph.
