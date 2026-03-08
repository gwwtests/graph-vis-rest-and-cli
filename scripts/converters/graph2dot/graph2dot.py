#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""graph2dot -- Convert graph JSON to Graphviz DOT format.

Problem Statement
-----------------
We are given a graph represented as a JSON object with two arrays: ``nodes``
and ``edges``.  Each node has at least an ``id`` and ``label`` field; each
edge has ``from``, ``to``, and optionally ``label``.  Both nodes and edges
may carry additional styling properties (colours, widths, shapes, etc.)
that are **ignored** during conversion -- DOT is a lossy export format
that preserves only structure and labels.

Our task is to emit a valid Graphviz DOT ``digraph`` (directed graph) that
faithfully represents the topology and labels of the input.

Input Format
------------
A JSON object (from ``/api/graph`` or a file):

    {
      "nodes": [{"id": "Alice", "label": "Alice"}, ...],
      "edges": [{"id": "e1", "from": "Alice", "to": "Bob", "label": "knows"}, ...]
    }

Output Format
-------------
A DOT ``digraph`` with all identifiers double-quoted (safe for spaces and
special characters).  Edge labels appear as ``[label="..."]`` attributes
when the label is non-empty.  Node declarations are always emitted for
every node in the ``nodes`` array.

    digraph G {
        "Alice" [label="Alice"];
        "Bob" [label="Bob"];
        "Alice" -> "Bob" [label="knows"];
    }

Usage
-----
    ./graph2dot.py graph.json          # read file, DOT to stdout
    cat graph.json | ./graph2dot.py    # read stdin
    ./graph2dot.py --compact graph.json  # minimal whitespace

Library API
-----------
    >>> dot_text = convert({"nodes": [...], "edges": [...]})
    >>> print(dot_text)
"""

import argparse
import json
import sys


def _escape_dot(s: str) -> str:
    """Escape a string for DOT double-quoted context."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def convert(graph_data: dict, *, compact: bool = False) -> str:
    """Convert {"nodes": [...], "edges": [...]} to DOT string.

    Parameters
    ----------
    graph_data : dict
        Graph JSON with ``nodes`` and ``edges`` arrays.
    compact : bool
        If True, emit minimal whitespace.

    Returns
    -------
    str
        Valid Graphviz DOT source text.
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    indent = "" if compact else "    "
    sep = " " if compact else "\n"

    lines: list[str] = []
    lines.append("digraph G {")

    # Node declarations
    for node in nodes:
        node_id = _escape_dot(str(node.get("id", "")))
        label = _escape_dot(str(node.get("label", node.get("id", ""))))
        lines.append(f'{indent}"{node_id}" [label="{label}"];')

    # Edge declarations
    for edge in edges:
        src = _escape_dot(str(edge.get("from", "")))
        dst = _escape_dot(str(edge.get("to", "")))
        label = edge.get("label", "")

        if label:
            escaped_label = _escape_dot(str(label))
            lines.append(f'{indent}"{src}" -> "{dst}" [label="{escaped_label}"];')
        else:
            lines.append(f'{indent}"{src}" -> "{dst}";')

    lines.append("}")

    return sep.join(lines) + "\n"


def main():
    """CLI entry point -- parse args, read input, convert, print."""
    parser = argparse.ArgumentParser(
        description="Convert graph JSON to Graphviz DOT format.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="JSON file to convert (reads stdin if omitted)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Emit minimal whitespace",
    )

    if len(sys.argv) > 1 and sys.argv[1] == "help":
        parser.parse_args(["--help"])
    args = parser.parse_args()

    if args.file:
        with open(args.file) as fh:
            source = fh.read()
    else:
        source = sys.stdin.read()

    graph_data = json.loads(source)
    sys.stdout.write(convert(graph_data, compact=args.compact))


if __name__ == "__main__":
    main()
