# ttl2graph.py — Developer Notes

## Purpose

Converts Turtle/N3 RDF format to the intermediate graph format using `rdflib`.

## Dual-Use Pattern

* **CLI** — `./ttl2graph.py input.ttl`
* **Library** — `from ttl2graph import convert; edges = convert(text)`.

## Key Design Decisions

* **rdflib dependency** — Unlike other converters, this one requires `rdflib`. Declared in PEP 723 inline metadata for `uv run`.
* **URI shortening** — Extracts local name from URIs (after `#` or last `/`). Falls back to full URI if no fragment.
* **Literal handling** — RDF object literals are converted to string representation.

## Testing

```bash
pytest tests/test_ttl2graph.py -v
```

37 tests. Note: requires `rdflib` installed (`pip install rdflib` or run via `uv`).

## Gotchas

* `uv run` shebang auto-installs rdflib on first run — may be slow initially.
* N3 format (`.n3`) is also supported — rdflib handles both.
* Blank nodes get auto-generated IDs that aren't human-readable.
