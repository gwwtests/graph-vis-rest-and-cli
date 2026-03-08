#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""graph2jsonl -- Convert graph JSON to JSONL format (lossless).

Problem Statement
-----------------
We are given a JSON object representing a graph, as returned by the
``/api/graph`` REST endpoint.  The object has two keys:

* ``nodes`` -- a list of node objects, each with at least ``id`` and ``label``.
* ``edges`` -- a list of edge objects, each with at least ``from``, ``to``, and
  optionally ``label`` and ``id``.

Both nodes and edges may carry arbitrary extra fields (vis-network styling,
hook actions like ``on_click`` and ``on_doubleClick``, ``hidden``, ``physics``,
etc.).

Our task is to serialize this graph into JSONL (one JSON object per line) such
that the output is directly consumable by ``jsonl2graph``.  Every field --
including all extras -- must be preserved (lossless round-trip).

Output Format
-------------
Each line is a self-contained JSON object with a ``type`` field:

* Nodes: ``{"type": "node", "id": ..., "label": ..., ...extras}``
* Edges: ``{"type": "edge", "from": ..., "to": ..., ...extras}``

Nodes are emitted first, then edges, preserving their original order within
each category.

Usage
-----
    ./graph2jsonl.py input.json           # read file, write JSONL to stdout
    cat input.json | ./graph2jsonl.py     # read from stdin
    ./graph2jsonl.py input.json -o out.jsonl  # write to file

Library usage::

    from graph2jsonl import convert

    jsonl_str = convert({"nodes": [...], "edges": [...]})
"""

import argparse
import json
import sys


def convert(graph_data: dict) -> str:
    """Convert {"nodes": [...], "edges": [...]} to JSONL string.

    Each node becomes: {"type": "node", "id": ..., "label": ..., ...extras}
    Each edge becomes: {"type": "edge", "from": ..., "to": ..., ...extras}

    All fields are preserved losslessly.

    Parameters
    ----------
    graph_data : dict
        A graph dictionary with ``nodes`` and ``edges`` lists.

    Returns
    -------
    str
        JSONL string (one JSON object per line), without trailing newline.
    """
    lines = []

    for node in graph_data.get("nodes", []):
        obj = {"type": "node"}
        obj.update(node)
        lines.append(json.dumps(obj, ensure_ascii=False))

    for edge in graph_data.get("edges", []):
        obj = {"type": "edge"}
        obj.update(edge)
        lines.append(json.dumps(obj, ensure_ascii=False))

    return "\n".join(lines)


def main():
    """CLI: reads JSON from file arg or stdin, writes JSONL to stdout."""
    parser = argparse.ArgumentParser(
        description="Convert graph JSON (from /api/graph) to JSONL format (lossless).",
    )
    parser.add_argument("file", nargs="?", default=None,
                        help="JSON input file (default: stdin)")
    parser.add_argument("-o", "--output", default=None,
                        help="Output file (default: stdout)")
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        parser.parse_args(["--help"])
    args = parser.parse_args()

    if args.file:
        with open(args.file) as fh:
            graph_data = json.load(fh)
    else:
        graph_data = json.load(sys.stdin)

    result = convert(graph_data)

    if args.output:
        with open(args.output, "w") as fh:
            fh.write(result)
            fh.write("\n")
    else:
        print(result)


if __name__ == "__main__":
    main()
