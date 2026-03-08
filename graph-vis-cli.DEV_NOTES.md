# graph-vis-cli.py — Developer Notes

## Architecture

Stdlib-only CLI using `cmd.Cmd` for REPL and `urllib.request` for HTTP. No external dependencies.

## Key Design Decisions

* **Non-interactive default** — Reads stdin when no positional args (for piping). `--repl` required for interactive mode. This is unusual for a REPL tool but makes it pipe-friendly.
* **Mode resolution order** — positional args > input file > stdin (default) > repl. Multiple modes can combine (e.g., `-l file.csv --repl` loads then enters REPL).
* **3 bare words = add triplet** — `Alice knows Bob` auto-expands to `add Alice knows Bob`. Handled in `default()`.
* **`+` and `-` shortcuts** — Can't be `cmd.Cmd` method names (not valid identifiers), so handled in `default()` before the 3-word check.
* **Shell-like prompt** — `graph@host:port> ` shows connection target.

## Import Symlink

`graph_vis_cli.py` → `graph-vis-cli.py` symlink for Python imports. Listed in `.gitignore`.

## Testing

```bash
PYTHONPATH=. pytest tests/test_cli.py -v -p no:playwright --noconftest
```

`--noconftest` prevents loading the server's conftest which would try to import the server module.

## Gotchas

* `parse_args(argv=None)` accepts explicit argv for testability. `None` means use `sys.argv[1:]`.
* `execute_command()` skips empty lines and `#` comments — important for command files.
* `do_Load` (capital L) is intentional — avoids collision with `list/ls/l` shortcuts.
* `help` as bare positional command handled before argparse via `sys.argv` check.

## Screenshot, DOM, UI Commands

* `screenshot [file] [k=v]` (alias `ss`) — Downloads PNG/JPEG from browser via `/api/screenshot`. Supports key=value params (padding, format, quality, etc.).
* `dom` — Fetches layout JSON from `/api/dom`. Prints with `json.dumps(indent=2)`.
* `ui hide|show` (aliases: off/on) — Toggles browser input controls via `/api/ui`.
* All three return "No browser connected (503)" if no browser WebSocket is active.
