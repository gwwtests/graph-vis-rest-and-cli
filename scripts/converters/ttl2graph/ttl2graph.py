#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["rdflib>=7.0"]
# ///
"""ttl2graph -- Convert RDF Turtle/N3 files to graph intermediate format.

We are given an RDF file in Turtle (.ttl) or Notation3 (.n3) syntax.  Each
triple in the file describes a directed edge in a graph: the subject is the
source vertex, the object is the target vertex, and the predicate is the edge
label.  Our task is to extract the *local name* from every URI -- that is, the
fragment identifier after ``#`` if one exists, or else the last path segment --
and to emit the graph in a simple intermediate format that downstream tools can
consume without needing an RDF library of their own.

The intermediate format comes in three flavours.  The default *plain text*
format prints a header line with the vertex and edge counts, followed by one
line per edge (``from to label``).  The ``--csv`` flag produces a CSV with a
header row, and ``--jsonl`` produces one JSON object per line.

Problem Statement (ACM ICPC style)
-----------------------------------
**Input:**  An RDF file in Turtle or N3 format on stdin or as a positional
argument.

**Output:** The graph intermediate format on stdout.

    >>> # Given input sample.ttl:
    >>> # @prefix ex: <http://example.org/> .
    >>> # ex:Alice ex:knows ex:Bob .
    >>> # ex:Bob ex:likes ex:Charlie .
    >>>
    >>> # Plain output:
    >>> # 3 2
    >>> # Alice Bob knows
    >>> # Bob Charlie likes

Usage
-----
    ./ttl2graph.py input.ttl
    ./ttl2graph.py input.ttl --csv
    ./ttl2graph.py input.ttl --jsonl
    cat input.n3 | ./ttl2graph.py
"""

import argparse
import json
import sys

from rdflib import Graph


def _local_name(uri):
    """Extract the local name from an RDF URI.

    If the URI contains a fragment (``#``), return everything after it.
    Otherwise return the last path segment (everything after the final ``/``).
    For literals or blank nodes, return the string representation as-is.
    """
    s = str(uri)
    if "#" in s:
        return s.rsplit("#", 1)[1]
    if "/" in s:
        return s.rsplit("/", 1)[1]
    return s


def convert(source):
    """Parse RDF triples and return ``(vertices, edges)``.

    *source* is a file path (str) or a file-like object.  Returns a tuple
    ``(vertices: set[str], edges: list[tuple[str, str, str]])`` where each
    edge tuple is ``(from, to, label)`` with local names extracted from URIs.
    Edges are sorted by ``(from, to, label)`` for deterministic output,
    since rdflib does not guarantee triple iteration order.
    """
    g = Graph()
    if isinstance(source, str):
        g.parse(source)
    else:
        g.parse(source, format="turtle")

    vertices = set()
    edges = []
    for subj, pred, obj in g:
        s, p, o = _local_name(subj), _local_name(pred), _local_name(obj)
        vertices.add(s)
        vertices.add(o)
        edges.append((s, o, p))

    edges.sort()
    return vertices, edges


def format_output(vertices, edges, fmt="plain"):
    """Serialize vertices and edges to the requested format.

    *fmt* is one of ``"plain"`` (default), ``"csv"``, or ``"jsonl"``.
    """
    lines = []
    if fmt == "plain":
        lines.append(f"{len(vertices)} {len(edges)}")
        for frm, to, label in edges:
            lines.append(f"{frm} {to} {label}")
    elif fmt == "csv":
        lines.append("from,to,label")
        for frm, to, label in edges:
            lines.append(f"{frm},{to},{label}")
    elif fmt == "jsonl":
        for frm, to, label in edges:
            lines.append(json.dumps({"from": frm, "to": to, "label": label}))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="Convert RDF Turtle/N3 to graph intermediate format.",
    )
    parser.add_argument("file", nargs="?", help="Input .ttl or .n3 file (default: stdin)")
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument("--csv", action="store_true", help="Output CSV format")
    fmt.add_argument("--jsonl", action="store_true", help="Output JSONL format")
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        parser.parse_args(["--help"])
    args = parser.parse_args()

    if args.csv:
        out_fmt = "csv"
    elif args.jsonl:
        out_fmt = "jsonl"
    else:
        out_fmt = "plain"

    source = args.file if args.file else sys.stdin
    vertices, edges = convert(source)
    sys.stdout.write(format_output(vertices, edges, out_fmt))


if __name__ == "__main__":
    main()
