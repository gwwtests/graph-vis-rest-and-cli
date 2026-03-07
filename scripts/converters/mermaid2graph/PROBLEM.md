# mermaid2graph

## Problem Statement

Given a Mermaid graph or flowchart definition, extract all edges (with labels)
and produce the graph intermediate format. The converter parses the textual
Mermaid syntax using regular expressions — no external dependencies required.

Mermaid graphs begin with a header line such as `graph LR`, `graph TD`,
`flowchart LR`, etc. Each subsequent non-empty line defines one or more edges
between nodes, optionally with labels.

## Supported Edge Syntax

Three forms are recognized:

* `A -->|label| B` — labeled arrow (pipe-delimited label)
* `A -- label --> B` — labeled link (label between dashes and arrow)
* `A --> B` — unlabeled arrow (default label: `->`)

Node names are stripped of surrounding whitespace. The header line is skipped.

## Input Format

A Mermaid graph definition, either from a file or standard input.

### Example Input (`sample.mermaid`)

    graph LR
        Alice -->|knows| Bob
        Bob -->|likes| Charlie

## Output Format

### Plain text (default)

First line: `Vn En` (vertex count, edge count).
Subsequent lines: `from to label` (one edge per line).

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
