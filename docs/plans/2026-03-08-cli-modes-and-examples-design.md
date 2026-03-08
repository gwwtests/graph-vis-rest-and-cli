# Design: CLI Non-Interactive Default, Load Flag, and Example Graphs

## Overview

Refactor `graph-rest-cli.py` from REPL-default to non-interactive-default. Add repeatable `--load` flag, example graph files, env var support for host/port, and multiple input modes.

## CLI Modes

### Input Mode Resolution

```
if positional commands   → execute them
elif --input file        → read commands from file
elif --stdin or no args  → read from stdin
# then:
if --repl                → enter interactive REPL after above
```

### Usage Examples

```bash
# Pipe commands (default when no args)
echo "Alice knows Bob" | ./graph-rest-cli.py

# Positional command args
./graph-rest-cli.py "Alice knows Bob" "g"

# Read from file
./graph-rest-cli.py -i commands.txt

# Explicit stdin
./graph-rest-cli.py --stdin

# Pre-load files, then REPL
./graph-rest-cli.py -l data.csv -l extra.ttl --repl

# Pre-load files, run command, exit
./graph-rest-cli.py -l data.csv "g"

# Env vars for connection
GRAPH_VIS_HOST=10.0.0.5 GRAPH_VIS_PORT=9999 echo "g" | ./graph-rest-cli.py
```

### Argument Spec

```
--host HOST          Server IP (env: GRAPH_VIS_HOST, default: 127.0.0.1)
--port PORT          Server port (env: GRAPH_VIS_PORT, default: 7849)
-v, --verbose        Verbosity (-v, -vv, -vvv)
--stdin              Read commands from stdin (default when no args)
-i, --input FILE     Read commands from file
--repl               Enter interactive REPL
-l, --load FILE      Load graph file before commands (repeatable)
commands...          Commands to execute (positional)
-h, --help, help     Show help
```

### Host/Port Priority

1. CLI flags (`--host`, `--port`)
2. Env vars (`GRAPH_VIS_HOST`, `GRAPH_VIS_PORT`)
3. Defaults (`127.0.0.1`, `7849`)

## Execution Order

1. Connect to server
2. Process all `--load` files (in order)
3. Execute commands (positional / stdin / input file)
4. Enter REPL if `--repl`

## Example Graph Files

```
examples/
├── social-network.csv
├── family-tree.dot
├── web-of-knowledge.ttl
└── software-arch.mermaid
```

## Changes Required

1. `graph-rest-cli.py` — refactor parse_args/main, add _execute_commands/_load_files
2. `examples/` — 4 sample graph files
3. `graph-rest-cli.README.md` — updated usage
4. `AGENTS.md` — updated CLI section
5. `tests/test_cli.py` — tests for mode resolution, env vars, load
