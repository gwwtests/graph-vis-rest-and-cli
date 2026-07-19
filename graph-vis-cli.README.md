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

# Store graph to file after commands
./graph-vis-cli.py -l data.csv -s output.jsonl
./graph-vis-cli.py -l data.csv -s graph.dot

# Load file, then enter REPL
./graph-vis-cli.py -l examples/family-tree.dot --repl

# Read commands from file
./graph-vis-cli.py -i commands.txt

# Interactive REPL
./graph-vis-cli.py --repl

# Subscribe: stream live graph events until Ctrl-C
./graph-vis-cli.py --subscribe                 # human-readable
./graph-vis-cli.py --subscribe --format jsonl  # raw JSON per line

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
| `-s, --store FILE` | Save graph to file after commands (.jsonl .csv .dot .ttl .mermaid) |
| `--stdin` | Read commands from stdin (also default when no args) |
| `-i, --input FILE` | Read commands from file |
| `--repl` | Enter interactive REPL mode |
| `--subscribe` | Stream graph events from `/api/events` (SSE) until Ctrl-C; implies no REPL |
| `--format jsonl\|human` | Output format for `--subscribe` (default: `human`) |
| `-h, --help` | Show help |

## Execution Order

1. Connect to server
2. Load all `--load` files (in order)
3. Execute commands (positional / stdin / input file)
4. Store graph if `--store` specified
5. Subscribe stream if `--subscribe` specified (long-running; implies no REPL)
6. Enter REPL if `--repl` specified

## Subscribe Mode

`--subscribe` opens a live [Server-Sent-Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
stream over `GET /api/events` and prints one line per graph event as it happens
— from any source (other CLIs, REST calls, browser clicks). Uses only stdlib
(`urllib` streaming); no WebSocket client required. Ctrl-C exits cleanly (0).

```bash
# Terminal 1: watch
./graph-vis-cli.py --subscribe

# Terminal 2: mutate — appears live in terminal 1
echo "Alice knows Bob" | ./graph-vis-cli.py
```

`--format human` (default) prints terse lines:

```
+ triplet Alice knows Bob
+ node Carol
- edge Alice-knows-Bob
clear
```

`--format jsonl` prints the raw event JSON per line (pipe to `jq`):

```bash
./graph-vis-cli.py --subscribe --format jsonl | jq '.event'
```


## Commands

| Command | Shortcuts | Args | Description |
|---------|-----------|------|-------------|
| `add` | `a`, `+` | `<from> <to>` | Add labelless edge |
| `add` | `a`, `+` | `<subj> <pred> <obj>` | Add triplet |
| `add-node` | `an` | `<id>` | Add single node |
| `add-edge` | `ae` | `<from> <pred> <to>` | Add edge |
| `del` / `delete` | `d`, `rm`, `-` | `<id>` | Delete node (cascade) |
| `del-edge` | `de` | `<edge-id>` | Delete edge |
| `list` / `ls` | `l` | `[nodes\|edges]` | List graph contents |
| `graph` | `g` | — | Full graph summary |
| `Load` | `L` | `<filepath>` | Load graph from file |
| `store` | `Store`, `S` | `<filepath>` | Save graph to file |
| `help` | `?`, `h` | — | Show command reference |
| `screenshot` | `ss` | `[filename] [k=v ...]` | Save graph screenshot |
| `dom` | — | — | Show graph layout info |
| `ui` | — | `hide\|show` | Toggle browser input controls |
| `quit` / `exit` | `q`, `Ctrl+D` | — | Exit REPL |

**Shorthand:** 2 bare words = labelless edge (`Alice Bob` = `add Alice Bob`). 3 bare words = triplet (`Alice knows Bob` = `add Alice knows Bob`).

**Comments:** Lines starting with `#` are skipped (useful in command files).

## Load Format Support

| Extension | Converter | Dependencies |
|-----------|-----------|-------------|
| `.csv` | csv2graph | stdlib |
| `.ttl`, `.n3` | ttl2graph | rdflib (via uv) |
| `.dot`, `.gv` | dot2graph | stdlib |
| `.mermaid`, `.mmd` | mermaid2graph | stdlib |
| `.jsonl` | jsonl2graph | stdlib |

## Store Format Support

Save the current graph to a file. Format detected from extension (defaults to JSONL).

| Extension | Converter | Lossless | Dependencies |
|-----------|-----------|----------|-------------|
| `.jsonl` | graph2jsonl | Yes | stdlib |
| `.csv` | graph2csv | No | stdlib |
| `.dot`, `.gv` | graph2dot | No | stdlib |
| `.ttl`, `.n3` | graph2ttl | No | rdflib (via uv) |
| `.mermaid`, `.mmd` | graph2mermaid | No | stdlib |

Only JSONL preserves all node/edge properties (styling, hooks, extras). Other formats export triplets only.

```bash
# REPL usage
store graph.jsonl          # lossless save
store graph.csv            # CSV triplets
store graph.dot            # Graphviz DOT

# CLI flag
./graph-vis-cli.py -l data.csv -s converted.dot
```

## Multiline Blocks

Use `+++` markers to input multiple lines as a block:

### Plain block (each line is a command)

```
+++
Alice knows Bob
Bob likes Charlie
Charlie trusts Alice
+++
```

### Format blocks (content parsed as that format)

```
+++csv
source,target,relationship
Alice,Bob,knows
Bob,Charlie,likes
+++
```

```
+++jsonl
{"type":"node","id":"HQ","label":"HQ","color":"red","shape":"star"}
{"type":"edge","from":"HQ","to":"Server","label":"manages","width":3}
+++
```

```
+++ttl
@prefix : <http://example.org/> .
:Alice :knows :Bob .
+++
```

Supported formats: `csv`, `ttl`/`n3`, `dot`/`gv`, `mermaid`/`mmd`, `jsonl`

In REPL mode, the prompt changes to show you're inside a block.

## JSONL Format

The JSONL format supports vis-network styling properties. Each line is a JSON object:

```jsonl
{"type":"node","id":"A","label":"A","color":"#ff0000","shape":"diamond","font":{"size":18}}
{"type":"edge","from":"A","to":"B","label":"knows","color":"#00ff00","width":3,"dashes":true}
{"type":"triplet","subject":"A","predicate":"knows","object":"B"}
```

* `node`: required `id`. Optional `label` (defaults to id). All other fields pass through to vis-network.
* `edge`: required `from`, `to`. Optional `label` (default ""), `id`. All other fields pass through.
* `triplet`: required `subject`, `predicate`, `object`. Simple — no styling support.

## Examples

Ready-to-use example graphs in `examples/`:

```bash
./graph-vis-cli.py -l examples/social-network.csv "g"
./graph-vis-cli.py -l examples/family-tree.dot "l"
./graph-vis-cli.py -l examples/web-of-knowledge.ttl "g"
./graph-vis-cli.py -l examples/software-arch.mermaid "g"
./graph-vis-cli.py -l examples/styled-graph.jsonl "g"
./graph-vis-cli.py -i examples/multiline-demo.txt
```

## Testing

```bash
PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest
```
