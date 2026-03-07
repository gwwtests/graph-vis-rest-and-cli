# csv2graph

## Problem Statement

Given a CSV file where the first three columns represent source, target, and
edge label (header row names are ignored), convert it to the graph intermediate
format.

## Input Format

A CSV file with a header row and data rows. Only the first three columns are
used (remaining columns are ignored). The first row is always treated as a
header and skipped.

### Example Input (`sample.csv`)

    source,target,relationship
    Alice,Bob,knows
    Bob,Charlie,likes
    Charlie,Alice,helps

## Output Format

### Plain text (default)

First line: `Vn En` (vertex count, edge count).
Subsequent lines: `from to label` (one edge per line).

    3 3
    Alice Bob knows
    Bob Charlie likes
    Charlie Alice helps

### CSV (`--csv`)

    from,to,label
    Alice,Bob,knows
    Bob,Charlie,likes
    Charlie,Alice,helps

### JSONL (`--jsonl`)

    {"from": "Alice", "to": "Bob", "label": "knows"}
    {"from": "Bob", "to": "Charlie", "label": "likes"}
    {"from": "Charlie", "to": "Alice", "label": "helps"}
