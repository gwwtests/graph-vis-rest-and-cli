# dot2graph.py — Developer Notes

## Purpose

Converts Graphviz DOT format to the intermediate graph format. Handles `digraph` and `graph` (directed/undirected).

## Dual-Use Pattern

* **CLI** — `./dot2graph.py input.dot`
* **Library** — `from dot2graph import convert; edges = convert(text)`.

## Key Design Decisions

* **Stdlib only** — Regex-based parser, no graphviz Python bindings.
* **Preprocessing step** — Splits source on `{`, `}`, `;` and strips C-style comments before line-by-line parsing. This was a bug fix — single-line DOT like `digraph G { A -> B; }` wasn't parsed without it.
* **Edge label extraction** — Parses `[label="..."]` attributes. Falls back to empty string if no label.

## Bug History

* **Single-line DOT parsing** — Original implementation did line-by-line keyword detection. `digraph G { A -> B; }` put everything on one line, so the edge line started with `digraph` and was skipped. Fixed by preprocessing: split on delimiters first, then parse individual statements.

## Testing

```bash
pytest tests/test_dot2graph.py -v
```

52 tests covering: digraph, graph, attributes, subgraphs, comments, edge cases.

## Gotchas

* Undirected graphs (`graph`) use `--` edges, directed (`digraph`) use `->`.
* Node IDs in DOT may be quoted — parser strips quotes.
* Attribute blocks `[key=val]` on nodes are currently ignored (only edge labels extracted).
