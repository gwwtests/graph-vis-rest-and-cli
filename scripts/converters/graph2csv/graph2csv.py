#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""graph2csv -- Convert graph JSON to CSV format.

Problem Statement
-----------------
We are given a JSON object representing a directed, labeled graph as returned
by the ``/api/graph`` REST endpoint.  The structure contains two arrays:

    {"nodes": [...], "edges": [...]}

Each edge object has at least ``from``, ``to``, and ``label`` fields, and may
carry additional styling properties (color, width, font, etc.) that are
specific to the vis-network rendering engine.

Our task is to export the edge data as a CSV file with three columns:
``from``, ``to``, ``label``.  This is intentionally a **lossy** export --
styling extras are dropped, and isolated nodes (nodes with no edges) are not
represented, because CSV is an edge-centric format.

Approach
--------
We iterate over the ``edges`` array in order, extracting only the three
canonical fields.  Python's built-in ``csv.writer`` handles proper quoting
of fields that contain commas, quotes, or newlines.

Output Format
-------------
A header row ``from,to,label`` followed by one data row per edge.  An empty
graph produces a header-only output.

Usage
-----
    ./graph2csv.py graph.json          # read from file, CSV to stdout
    cat graph.json | ./graph2csv.py    # read from stdin
    ./graph2csv.py --help              # show usage

Library usage::

    from graph2csv import convert

    csv_text = convert({"nodes": [...], "edges": [...]})
"""

import argparse
import csv
import io
import json
import sys


def convert(graph_data: dict) -> str:
    """Convert {"nodes": [...], "edges": [...]} to CSV string.

    Output: header row "from,to,label" followed by one row per edge.
    Uses Python csv.writer for proper quoting of fields with commas/spaces.
    Nodes without edges are NOT included (CSV is edge-centric).

    Parameters
    ----------
    graph_data : dict
        A dictionary with "nodes" and "edges" keys, as returned by /api/graph.

    Returns
    -------
    str
        CSV-formatted string (with trailing newline stripped).
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["from", "to", "label"])
    for edge in graph_data.get("edges", []):
        writer.writerow([edge["from"], edge["to"], edge.get("label", "")])
    return buf.getvalue().rstrip("\n")


def main():
    """CLI: reads JSON from file arg or stdin, writes CSV to stdout."""
    parser = argparse.ArgumentParser(
        description="Convert graph JSON to CSV format.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default=None,
        help="JSON input file (default: stdin)",
    )
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        parser.parse_args(["--help"])
    args = parser.parse_args()

    if args.file:
        with open(args.file) as fh:
            graph_data = json.load(fh)
    else:
        graph_data = json.load(sys.stdin)

    print(convert(graph_data))


if __name__ == "__main__":
    main()
