# Graph2X Export Converters Design

**Date:** 2026-03-08
**Status:** In Progress

## Overview

Create 5 graph-to-format export converters, mirroring the existing format-to-graph
ingest converters. These enable the `store` CLI command to save the current graph
state to various file formats.

## Converters

| Converter | Output Format | Lossless | Cross-validation |
|-----------|--------------|----------|-----------------|
| `graph2jsonl` | JSONL | Yes (preserves all extras) | round-trip with `jsonl2graph` |
| `graph2csv` | CSV | No (triplets only) | round-trip with `csv2graph` + `csv.reader` |
| `graph2dot` | Graphviz DOT | No (triplets only) | `dot -Tsvg` + round-trip with `dot2graph` |
| `graph2ttl` | Turtle RDF | No (triplets only) | `rdflib` parsing + round-trip with `ttl2graph` |
| `graph2mermaid` | Mermaid | No (triplets only) | round-trip with `mermaid2graph` |

## Input Format

All converters accept the same input — the `/api/graph` JSON structure:

```json
{
  "nodes": [{"id": "Alice", "label": "Alice", "color": "red", ...}],
  "edges": [{"id": "A-knows-B", "from": "Alice", "to": "Bob", "label": "knows", ...}]
}
```

## Converter API Pattern

Each `graph2X.py`:

* **uv shebang** (`#!/usr/bin/env -S uv run`) with PEP 723 metadata
* **`convert(graph_data: dict) -> str`** — library API, takes `{"nodes":..., "edges":...}` dict
* **CLI**: reads JSON from file arg or stdin, writes output format to stdout
* **PROBLEM.md** — ICM/ICPC-style problem statement
* **`input/`** — test fixture JSON files
* **Located at** `scripts/converters/graph2X/graph2X.py`

## Test Structure (per converter)

Tests at `tests/test_graph2X.py`:

1. `TestConvert` — library API with inline dicts
2. `TestEdgeCases` — empty graph, single node, unicode, special chars, nodes without edges
3. `TestCrossValidation` — round-trip with matching X2graph converter
4. `TestNativeValidation` — parse output with native tools
5. `TestCLI` — subprocess invocation (file arg, stdin, help)

## Future: CLI `store` Command Integration

After converters are built and tested, integrate into `graph-vis-cli.py`:

* REPL command: `store myfile.jsonl` / `store graph.csv`
* CLI flag: `-s FILE` / `--store FILE`
* Positional: `./graph-vis-cli.py "Alice knows Bob" "store out.jsonl"`
* Format detected from file extension, JSONL default
