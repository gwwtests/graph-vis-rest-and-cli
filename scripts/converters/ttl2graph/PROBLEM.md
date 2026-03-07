# ttl2graph

## Problem Statement

Given an RDF file in Turtle (.ttl) or Notation3 (.n3) format containing triples
of the form `subject predicate object`, extract the local names from URIs and
convert the triples to the graph intermediate format.

URI local name extraction: use the fragment identifier if present
(`http://example.org/ns#Alice` -> `Alice`), otherwise use the last path segment
(`http://example.org/Alice` -> `Alice`).

## Input Format

An RDF file in Turtle or Notation3 syntax. Prefixed names and full URIs are
both supported. Literal objects are used as-is (without quotes).

### Example Input (`sample.ttl`)

    @prefix ex: <http://example.org/> .
    ex:Alice ex:knows ex:Bob .
    ex:Bob ex:likes ex:Charlie .

## Output Format

### Plain text (default)

First line: `Vn En` (vertex count, edge count).
Subsequent lines: `from to label` (one edge per line, in parse order).
Vertices are counted from all unique subjects and objects.

    3 2
    Alice Bob knows
    Bob Charlie likes

### CSV (`--csv`)

    from,to,label
    Alice,Bob,knows
    Bob,Charlie,likes

### JSONL (`--jsonl`)

    {"from": "Alice", "to": "Bob", "label": "knows"}
    {"from": "Bob", "to": "Charlie", "label": "likes"}
