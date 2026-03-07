# dot2graph

## Problem Statement

Given a DOT graph description file (Graphviz format), extract all edges with
their labels and convert them to the graph intermediate format.

The parser must handle both directed (`->`) and undirected (`--`) edge
operators, quoted and unquoted node names, and optional `label` attributes
on edges. DOT structural keywords (`digraph`, `graph`, `subgraph`, `node`,
`edge`, `strict`) and attribute-only lines are ignored.

## Input Format

A DOT file containing a graph definition. Edges follow the pattern:

    NodeA -> NodeB [label="relationship"];

or:

    NodeA -- NodeB [label="relationship"];

Node names may be quoted (`"Node Name"`) or bare identifiers. The `label`
attribute in square brackets is optional; if omitted, the edge label defaults
to `"->"` for directed graphs or `"--"` for undirected graphs.

### Example Input (`sample.dot`)

    digraph G {
        Alice -> Bob [label="knows"];
        Bob -> Charlie [label="likes"];
    }

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
