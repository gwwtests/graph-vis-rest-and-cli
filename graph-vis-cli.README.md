# graph-vis-cli.py

CLI for the graph visualization server. Non-interactive by default (reads stdin for easy piping). Use `--repl` for interactive mode.

## Usage

```bash
# Pipe commands (default when no args)
echo "Alice knows Bob" | ./graph-vis-cli.py

# Positional commands
./graph-vis-cli.py "Alice knows Bob" "Charlie likes Alice" "g"

# Load graph files, then run commands
./graph-vis-cli.py -l examples/social-network.csv "g"
./graph-vis-cli.py -l data.csv -l extra.ttl "l nodes"

# Load file, then enter REPL
./graph-vis-cli.py -l examples/family-tree.dot --repl

# Read commands from file
./graph-vis-cli.py -i commands.txt

# Interactive REPL
./graph-vis-cli.py --repl

# Help
./graph-vis-cli.py help
./graph-vis-cli.py -h
./graph-vis-cli.py --help
```

## Environment Variables

Connection settings via env vars (flags override):

```bash
export GRAPH_VIS_HOST=10.0.0.5
export GRAPH_VIS_PORT=9999
echo "g" | ./graph-vis-cli.py
```

| Variable | Default | Description |
|----------|---------|-------------|
| `GRAPH_VIS_HOST` | `127.0.0.1` | Server IP |
| `GRAPH_VIS_PORT` | `7849` | Server port |

## CLI Flags

| Flag | Description |
|------|-------------|
| `--host HOST` | Server IP (env: `GRAPH_VIS_HOST`) |
| `--port PORT` | Server port (env: `GRAPH_VIS_PORT`) |
| `-v / -vv / -vvv` | Verbosity: requests / +headers+timing / +payloads |
| `-l, --load FILE` | Load graph file before commands (repeatable) |
| `--stdin` | Read commands from stdin (also default when no args) |
| `-i, --input FILE` | Read commands from file |
| `--repl` | Enter interactive REPL mode |
| `-h, --help` | Show help |

## Execution Order

1. Connect to server
2. Load all `--load` files (in order)
3. Execute commands (positional / stdin / input file)
4. Enter REPL if `--repl` specified

## Commands

| Command | Shortcuts | Args | Description |
|---------|-----------|------|-------------|
| `add` | `a`, `+` | `<subj> <pred> <obj>` | Add triplet |
| `add-node` | `an` | `<id>` | Add single node |
| `add-edge` | `ae` | `<from> <pred> <to>` | Add edge |
| `del` / `delete` | `d`, `rm`, `-` | `<id>` | Delete node (cascade) |
| `del-edge` | `de` | `<edge-id>` | Delete edge |
| `list` / `ls` | `l` | `[nodes\|edges]` | List graph contents |
| `graph` | `g` | — | Full graph summary |
| `Load` | `L` | `<filepath>` | Load graph from file |
| `help` | `?`, `h` | — | Show command reference |
| `quit` / `exit` | `q`, `Ctrl+D` | — | Exit REPL |

**Shorthand:** 3 bare words are treated as `add` — `Alice knows Bob` = `add Alice knows Bob`.

**Comments:** Lines starting with `#` are skipped (useful in command files).

## Load Format Support

| Extension | Converter | Dependencies |
|-----------|-----------|-------------|
| `.csv` | csv2graph | stdlib |
| `.ttl`, `.n3` | ttl2graph | rdflib (via uv) |
| `.dot`, `.gv` | dot2graph | stdlib |
| `.mermaid`, `.mmd` | mermaid2graph | stdlib |

## Examples

Ready-to-use example graphs in `examples/`:

```bash
./graph-vis-cli.py -l examples/social-network.csv "g"
./graph-vis-cli.py -l examples/family-tree.dot "l"
./graph-vis-cli.py -l examples/web-of-knowledge.ttl "g"
./graph-vis-cli.py -l examples/software-arch.mermaid "g"
```

## Testing

```bash
PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest
```
