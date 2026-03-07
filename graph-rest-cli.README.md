# graph-rest-cli.py

Interactive REPL for the graph visualization server. Connects via REST API and provides command-line graph manipulation with shortcut commands.

## Usage

```bash
./graph-rest-cli.py                        # connect to 127.0.0.1:7849
./graph-rest-cli.py --port 9999            # custom port
./graph-rest-cli.py --host 10.0.0.5 -vv   # custom host, debug verbosity
./graph-rest-cli.py -h                     # show help
```

## REPL Session Example

```
Connected to http://127.0.0.1:7849 (0 nodes, 0 edges)
Type 'help' or '?' for commands.
graph@127.0.0.1:7849> Alice knows Bob
Added: Alice —knows→ Bob
graph@127.0.0.1:7849> Charlie likes Alice
Added: Charlie —likes→ Alice
graph@127.0.0.1:7849> l
Nodes (3):
  Alice
  Bob
  Charlie
Edges (2):
  Alice-knows-Bob: Alice —knows→ Bob
  Charlie-likes-Alice: Charlie —likes→ Alice
graph@127.0.0.1:7849> d Bob
Deleted node: Bob (removed 1 edge(s))
graph@127.0.0.1:7849> L data.csv
Loaded 15 edges, 8 nodes from data.csv (csv)
graph@127.0.0.1:7849> q
Bye.
```

## Commands

| Command | Shortcuts | Args | Description |
|---------|-----------|------|-------------|
| `add` | `a` | `<subj> <pred> <obj>` | Add triplet |
| `add-node` | `an` | `<id>` | Add single node |
| `add-edge` | `ae` | `<from> <pred> <to>` | Add edge |
| `del` / `delete` | `d`, `rm` | `<id>` | Delete node (cascade) |
| `del-edge` | `de` | `<edge-id>` | Delete edge |
| `list` / `ls` | `l` | `[nodes\|edges]` | List graph contents |
| `graph` | `g` | — | Full graph summary |
| `Load` | `L` | `<filepath>` | Load graph from file |
| `help` | `?`, `h` | — | Show command reference |
| `quit` / `exit` | `q`, `Ctrl+D` | — | Exit REPL |

**Shorthand:** 3 bare words are treated as `add` — typing `Alice knows Bob` is the same as `add Alice knows Bob`.

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Server IP address |
| `--port` | `7849` | Server port |
| `-v` | — | Verbose: show HTTP method + URL + status |
| `-vv` | — | Debug: add headers + timing |
| `-vvv` | — | Trace: add full request/response payloads |
| `-h, --help` | — | Show usage and exit |

## Load Command

The `L` / `Load` command detects file format by extension and converts via scripts in `scripts/converters/`:

| Extension | Converter | Dependencies |
|-----------|-----------|-------------|
| `.csv` | csv2graph | stdlib |
| `.ttl`, `.n3` | ttl2graph | rdflib (via uv) |
| `.dot`, `.gv` | dot2graph | stdlib |
| `.mermaid`, `.mmd` | mermaid2graph | stdlib |

Each converter is a standalone script that can also be used independently:

```bash
# Standalone converter usage
./scripts/converters/csv2graph/csv2graph.py data.csv           # plain text
./scripts/converters/csv2graph/csv2graph.py data.csv --csv     # CSV output
./scripts/converters/csv2graph/csv2graph.py data.csv --jsonl   # JSONL output
cat data.csv | ./scripts/converters/csv2graph/csv2graph.py     # stdin
```

## Testing

```bash
# CLI unit tests
PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest

# All server tests
pytest tests/ -v -p no:playwright
```
