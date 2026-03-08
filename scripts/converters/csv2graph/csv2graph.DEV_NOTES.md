# csv2graph.py — Developer Notes

## Purpose

Converts CSV files to the intermediate graph format. Expects 3-column CSV: `subject, predicate, object`.

## Dual-Use Pattern

* **CLI** — `./csv2graph.py input.csv` or pipe via stdin.
* **Library** — `from csv2graph import convert; edges = convert(text)`.

## Key Design Decisions

* **Stdlib only** — Uses `csv` module. No pandas or external deps.
* **Flexible header detection** — If first row looks like a header (common names like "subject", "from", "source"), it's skipped.
* **Output modes** — Plain (intermediate format), `--csv`, `--jsonl`. Controlled by `format_output()`.
* **uv run shebang** — PEP 723 metadata even though no deps, for consistency across converters.

## Intermediate Format

```
V <node_count> E <edge_count>
<from> <to> <label>
...
```

## Testing

```bash
pytest tests/test_csv2graph.py -v
```

45 tests covering: basic parsing, headers, quoting, edge cases, output formats.

## Gotchas

* Bare `help` command handled before argparse: `if sys.argv[1] == "help": parser.parse_args(["--help"])`.
* Empty lines and whitespace-only lines are silently skipped.
