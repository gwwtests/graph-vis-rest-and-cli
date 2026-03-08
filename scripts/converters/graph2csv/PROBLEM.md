# Graph to CSV Export

## Problem

You are given a JSON object representing a directed, labeled graph.  The JSON
has the structure:

```json
{
  "nodes": [{"id": "A", "label": "A", ...}, ...],
  "edges": [{"id": "e1", "from": "A", "to": "B", "label": "knows", ...}, ...]
}
```

Nodes and edges may carry additional styling properties (color, shape, width,
font settings, etc.) used by the vis-network rendering engine.

Write a program that reads this JSON and outputs a CSV file with exactly three
columns: `from`, `to`, `label`.  One row per edge, in the order they appear in
the input.

## Constraints

* The output must begin with the header row `from,to,label`.
* Styling properties on nodes and edges must be **dropped** -- only the three
  canonical edge fields appear in the output.
* Nodes that have no edges are **not** represented in the output (CSV is an
  edge-centric format).
* An empty graph (no edges) produces a single header line and nothing else.
* Fields containing commas, double quotes, or newlines must be properly quoted
  per RFC 4180.
* Unicode characters must be preserved.

## Input

A single JSON object read from a file argument or standard input.

## Output

CSV text written to standard output.

## Examples

### Input

```json
{
  "nodes": [
    {"id": "Alice", "label": "Alice"},
    {"id": "Bob", "label": "Bob"}
  ],
  "edges": [
    {"id": "e1", "from": "Alice", "to": "Bob", "label": "knows"}
  ]
}
```

### Output

```
from,to,label
Alice,Bob,knows
```

### Input (empty)

```json
{"nodes": [], "edges": []}
```

### Output (empty)

```
from,to,label
```
