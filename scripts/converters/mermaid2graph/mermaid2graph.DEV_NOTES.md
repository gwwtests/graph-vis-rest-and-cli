# mermaid2graph.py — Developer Notes

## Purpose

Converts Mermaid flowchart/graph syntax to the intermediate graph format.

## Dual-Use Pattern

* **CLI** — `./mermaid2graph.py input.mermaid`
* **Library** — `from mermaid2graph import convert; edges = convert(text)`.

## Key Design Decisions

* **Stdlib only** — Regex-based parser.
* **Arrow type support** — Handles `-->` (normal), `==>` (thick), `-.->` (dotted). All treated as directed edges.
* **Label extraction** — `A -->|label| B` and `A -- label --> B` both supported.
* **Node label extraction** — `A[Label Text]`, `A(Label)`, `A{Label}`, `A((Label))` all parsed.

## Bug History

* **Thick/dotted arrows** — Original implementation only matched `-->`. Fixed by generalizing the arrow regex to also match `==>` and `-.->` patterns.

## Testing

```bash
pytest tests/test_mermaid2graph.py -v
```

46 tests covering: arrow types, labels, node shapes, subgraphs, direction keywords.

## Gotchas

* Mermaid `graph` and `flowchart` keywords both supported as header.
* Direction keywords (`TD`, `LR`, `BT`, `RL`) are parsed but don't affect output (graph is position-agnostic).
* Subgraph declarations are parsed for containment but edges are what matter for the graph output.
* Node IDs in Mermaid can contain special chars — careful with regex matching.
