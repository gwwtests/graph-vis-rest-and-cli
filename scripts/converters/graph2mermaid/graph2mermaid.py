#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""graph2mermaid -- Convert graph JSON to Mermaid diagram format.

Problem Statement
-----------------
We are given a JSON object representing a graph, as returned by the
``/api/graph`` REST endpoint.  The object has two arrays:

* ``nodes`` -- each element is ``{"id": "...", "label": "...", ...extras}``
* ``edges`` -- each element is ``{"id": "...", "from": "...", "to": "...",
  "label": "...", ...extras}``

Mermaid is a **lossy** export format: only the directed edge relationships
(and their labels) are preserved.  All styling extras on nodes and edges are
silently dropped.

The output is a valid Mermaid ``graph LR`` definition.

Output Rules
~~~~~~~~~~~~
* Header line: ``graph LR``
* Labelled edges: ``    SRC -->|LABEL| DST`` (4-space indent, pipe-delimited)
* Unlabelled edges (missing or empty label): ``    SRC --> DST``
* Nodes that have no edges get a standalone declaration: ``    NodeId``
* Edges are sorted lexicographically by ``(from, to, label)`` for
  deterministic output.
* Standalone nodes are sorted lexicographically and listed after edges.

Usage
-----
    ./graph2mermaid.py input.json
    cat input.json | ./graph2mermaid.py
    curl -s http://localhost:7849/api/graph | ./graph2mermaid.py

Library API
-----------
    >>> from graph2mermaid import convert
    >>> mermaid_text = convert({"nodes": [...], "edges": [...]})
"""

import argparse
import json
import sys


def convert(graph_data: dict) -> str:
    """Convert {"nodes": [...], "edges": [...]} to Mermaid string.

    Output starts with 'graph LR' header, followed by edge declarations
    and standalone node declarations for nodes without any edges.

    Parameters
    ----------
    graph_data : dict
        Graph JSON with ``nodes`` and ``edges`` arrays.

    Returns
    -------
    str
        A valid Mermaid graph definition.
    """
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    lines = ["graph LR"]

    # Collect node IDs that participate in edges
    connected_node_ids: set[str] = set()

    # Build sorted edge lines
    edge_tuples = []
    for e in edges:
        src = str(e["from"])
        dst = str(e["to"])
        label = e.get("label", "") or ""
        label = label.strip()
        edge_tuples.append((src, dst, label))

    edge_tuples.sort()

    for src, dst, label in edge_tuples:
        connected_node_ids.add(src)
        connected_node_ids.add(dst)
        if label:
            lines.append(f"    {src} -->|{label}| {dst}")
        else:
            lines.append(f"    {src} --> {dst}")

    # Standalone nodes (no edges)
    all_node_ids = {str(n["id"]) for n in nodes}
    standalone = sorted(all_node_ids - connected_node_ids)
    for node_id in standalone:
        lines.append(f"    {node_id}")

    return "\n".join(lines)


def main():
    """CLI: reads JSON from file arg or stdin, writes Mermaid to stdout."""
    parser = argparse.ArgumentParser(
        description="Convert graph JSON to Mermaid diagram format.",
    )
    parser.add_argument(
        "file", nargs="?", default=None,
        help="Input JSON file (reads stdin if omitted)",
    )
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        parser.parse_args(["--help"])
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            source = f.read()
    else:
        source = sys.stdin.read()

    graph_data = json.loads(source)
    print(convert(graph_data))


if __name__ == "__main__":
    main()
