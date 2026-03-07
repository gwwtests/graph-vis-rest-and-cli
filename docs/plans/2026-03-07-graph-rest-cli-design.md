# Design: graph-rest-cli.py — REPL CLI for Graph Visualization Server

## Overview

A standalone stdlib-only Python CLI that connects to the graph-vis server via REST API and provides a REPL for interactive graph operations. Supports loading graphs from multiple file formats via converter scripts.

## CLI Interface

```bash
./graph-rest-cli.py [--host HOST] [--port PORT] [-v|-vv|-vvv] [-h|--help]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Server IP |
| `--port` | `7849` | Server port |
| `-v` | — | Verbose: show HTTP requests/responses |
| `-vv` | — | Debug: show headers + timing |
| `-vvv` | — | Trace: show full payloads |
| `-h, --help` | — | Show usage and exit |

## REPL

### Prompt

```
graph@127.0.0.1:7849>
```

Shows connection info. On startup, pings `GET /api/graph`, prints summary:

```
Connected to 127.0.0.1:7849 (3 nodes, 2 edges)
Type 'help' or '?' for commands.
graph@127.0.0.1:7849>
```

### Commands

| Command | Shortcuts | Args | Description |
|---------|-----------|------|-------------|
| `add` | `a` | `<subj> <pred> <obj>` | Add triplet |
| `add-node` | `an` | `<id>` | Add single node |
| `add-edge` | `ae` | `<from> <pred> <to>` | Add edge |
| `del` / `delete` | `d`, `rm` | `<id>` | Delete node (cascade) |
| `del-edge` | `de` | `<edge-id>` | Delete edge |
| `list` / `ls` | `l` | `[nodes\|edges]` | List all, or filter |
| `graph` | `g` | — | Full graph summary |
| `Load` | `L` | `<filepath>` | Load graph from file |
| `help` | `?`, `h` | — | Show command reference |
| `quit` / `exit` | `q`, `Ctrl+D` | — | Exit REPL |

**Default command**: 3 bare words treated as `add` — `Alice knows Bob` = `add Alice knows Bob`.

### Verbosity Levels

| Level | Shows |
|-------|-------|
| `-v` | HTTP method + URL + status code |
| `-vv` | Above + headers + timing |
| `-vvv` | Above + full request/response payloads |

## Load Command (`L`)

Detects format by file extension, shells out to the appropriate converter script, parses intermediate output, sends triplets to server.

```
graph@127.0.0.1:7849> L data.csv
Loaded 15 edges, 8 nodes from data.csv (csv)
graph@127.0.0.1:7849> L ontology.ttl
Loaded 42 edges, 23 nodes from ontology.ttl (ttl)
```

### Supported Formats

| Extension | Converter | Dependencies |
|-----------|-----------|-------------|
| `.csv` | `csv2graph.py` | stdlib (csv) |
| `.ttl`, `.n3` | `ttl2graph.py` | rdflib |
| `.dot`, `.gv` | `dot2graph.py` | stdlib (regex) |
| `.mermaid`, `.mmd` | `mermaid2graph.py` | stdlib (regex) |

## Converter Architecture

### Intermediate Format (Contract)

Plain text (default):

```
Vn En
x y w
x y w
...
```

First line: two integers (vertex count, edge count). Next En lines: `from to label`.

CSV output (`--csv`):

```csv
from,to,label
x,y,w
```

JSONL output (`--jsonl`):

```json
{"from": "x", "to": "y", "label": "w"}
```

### Directory Structure

```
scripts/converters/
├── csv2graph/
│   ├── PROBLEM.md
│   ├── csv2graph.py
│   ├── input/
│   └── output/
├── ttl2graph/
│   ├── PROBLEM.md
│   ├── ttl2graph.py
│   ├── input/
│   └── output/
├── dot2graph/
│   ├── PROBLEM.md
│   ├── dot2graph.py
│   ├── input/
│   └── output/
└── mermaid2graph/
    ├── PROBLEM.md
    ├── mermaid2graph.py
    ├── input/
    └── output/
```

### Converter Script Contract

Each converter:

* `#!/usr/bin/env -S uv run` shebang with PEP 723 inline metadata
* Dual-use: executable standalone AND importable as library
* Python docstrings in Knuth literate programming style
* `convert(source) -> (vertices: set, edges: list[tuple])` — library API
* `format_output(vertices, edges, fmt) -> str` — shared serialization
* `main()` — CLI entry point with argparse
* Supports: stdin or file arg, `--csv`, `--jsonl`, plain text default
* PROBLEM.md mirrors docstring with ACM ICPC style I/O examples

### Example Converter Template

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""csv2graph — Convert CSV triplet files to graph intermediate format.

Problem Statement
-----------------
Given a CSV file where the first three columns represent subject, predicate,
and object (header names ignored), produce the intermediate graph format.

Usage
-----
    ./csv2graph.py input.csv
    ./csv2graph.py input.csv --jsonl
    cat input.csv | ./csv2graph.py
"""

def convert(source):
    """Return (vertices: set, edges: list[tuple])."""
    ...

def format_output(vertices, edges, fmt="plain"):
    """Serialize to plain/csv/jsonl."""
    ...

def main():
    ...

if __name__ == "__main__":
    main()
```

## Implementation Plan

1. `graph-rest-cli.py` — main REPL tool (stdlib-only)
2. Converter team (parallel, one agent per converter):
   * `csv2graph.py` — stdlib
   * `ttl2graph.py` — rdflib
   * `dot2graph.py` — stdlib regex
   * `mermaid2graph.py` — stdlib regex
3. Integration — CLI `L` command calls converters, parses output, sends to server
