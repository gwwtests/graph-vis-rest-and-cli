#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""dot2graph -- Convert Graphviz DOT files to graph intermediate format.

Problem Statement
-----------------
We are given a text file in DOT format -- the lingua franca of Graphviz --
describing a graph as a collection of nodes connected by edges.  Our task is
to extract every edge together with its label and emit a compact intermediate
representation suitable for downstream graph tools.

The DOT language admits two flavours of edge operator:

    A -> B          (directed, used inside ``digraph``)
    A -- B          (undirected, used inside ``graph``)

Nodes may appear as bare identifiers (``Alice``) or as quoted strings
(``"San Francisco"``).  Each edge may carry attributes in square brackets;
we care only about the ``label`` attribute:

    Alice -> Bob [label="knows"];

If no label is given we fall back to the edge operator itself (``"->"`` or
``"--"``), so that every edge always carries *some* label in the output.

Lines that contain only DOT structural keywords -- ``digraph``, ``graph``,
``subgraph``, ``node``, ``edge``, ``strict``, or closing braces -- are
silently skipped.

Output Formats
--------------
The converter supports three output formats selected by CLI flags:

*Plain text* (default) -- first line is ``Vn En`` (vertex count, edge count),
followed by one ``from to label`` triple per line:

    3 2
    Alice Bob knows
    Bob Charlie likes

*CSV* (``--csv``) -- RFC 4180 with a header row:

    from,to,label
    Alice,Bob,knows
    Bob,Charlie,likes

*JSONL* (``--jsonl``) -- one JSON object per line:

    {"from": "Alice", "to": "Bob", "label": "knows"}
    {"from": "Bob", "to": "Charlie", "label": "likes"}

Usage
-----
    ./dot2graph.py graph.dot              # plain text to stdout
    ./dot2graph.py graph.dot --csv        # CSV to stdout
    cat graph.dot | ./dot2graph.py --jsonl  # JSONL from stdin

Library API
-----------
    >>> vertices, edges = convert(open("graph.dot").read())
    >>> print(format_output(vertices, edges, fmt="plain"))
"""

import argparse
import csv
import io
import json
import re
import sys


# Regex: captures edges like  A -> B [label="knows"];
# Supports quoted or unquoted node names, -> and -- operators.
_EDGE_RE = re.compile(
    r"""
    (?P<src>"[^"]*"|[A-Za-z_]\w*)    # source node: quoted or bare id
    \s*
    (?P<op>->|--)                     # edge operator
    \s*
    (?P<dst>"[^"]*"|[A-Za-z_]\w*)    # destination node
    \s*
    (?:\[([^\]]*)\])?                 # optional attributes in [ ]
    \s*;?\s*$                         # optional semicolon, end of line
    """,
    re.VERBOSE,
)

# Regex to extract label="value" from attribute string.
_LABEL_RE = re.compile(r'label\s*=\s*"([^"]*)"', re.IGNORECASE)

# DOT keywords that begin structural lines we should skip.
_DOT_KEYWORDS = frozenset(
    {"digraph", "graph", "subgraph", "node", "edge", "strict"}
)


def _unquote(name: str) -> str:
    """Strip surrounding double-quotes from a DOT identifier, if present."""
    if name.startswith('"') and name.endswith('"'):
        return name[1:-1]
    return name


def convert(source: str) -> tuple[set, list[tuple]]:
    """Parse DOT source text and return (vertices, edges).

    Parameters
    ----------
    source : str
        Complete DOT file content.

    Returns
    -------
    vertices : set of str
        All node names that appear in at least one edge.
    edges : list of (str, str, str)
        Each tuple is (from_node, to_node, label).
    """
    vertices: set[str] = set()
    edges: list[tuple[str, str, str]] = []

    for raw_line in source.splitlines():
        line = raw_line.strip()
        if not line or line == "{" or line == "}":
            continue

        # Skip lines that start with a DOT keyword followed by optional
        # identifier and opening brace -- these are structural, not edges.
        first_token = line.split()[0].rstrip("{").lower()
        if first_token in _DOT_KEYWORDS:
            continue

        m = _EDGE_RE.match(line)
        if not m:
            continue

        src = _unquote(m.group("src"))
        dst = _unquote(m.group("dst"))
        op = m.group("op")

        # Extract label from attributes, or fall back to the operator.
        attrs = m.group(4) or ""
        lm = _LABEL_RE.search(attrs)
        label = lm.group(1) if lm else op

        vertices.add(src)
        vertices.add(dst)
        edges.append((src, dst, label))

    return vertices, edges


def format_output(vertices: set, edges: list[tuple], fmt: str = "plain") -> str:
    """Serialize graph to the requested output format.

    Parameters
    ----------
    vertices : set of str
        Node names.
    edges : list of (str, str, str)
        Edge triples (from, to, label).
    fmt : str
        One of ``"plain"`` (default), ``"csv"``, or ``"jsonl"``.

    Returns
    -------
    str
        Formatted output string (no trailing newline).
    """
    if fmt == "plain":
        lines = [f"{len(vertices)} {len(edges)}"]
        for src, dst, label in edges:
            lines.append(f"{src} {dst} {label}")
        return "\n".join(lines)

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["from", "to", "label"])
        for src, dst, label in edges:
            writer.writerow([src, dst, label])
        return buf.getvalue().rstrip("\n")

    if fmt == "jsonl":
        lines = []
        for src, dst, label in edges:
            lines.append(json.dumps({"from": src, "to": dst, "label": label}))
        return "\n".join(lines)

    raise ValueError(f"Unknown format: {fmt!r}")


def main():
    """CLI entry point -- parse args, read input, convert, print."""
    parser = argparse.ArgumentParser(
        description="Convert Graphviz DOT files to graph intermediate format.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="DOT file to convert (reads stdin if omitted)",
    )
    fmt_group = parser.add_mutually_exclusive_group()
    fmt_group.add_argument(
        "--csv", action="store_const", const="csv", dest="fmt",
        help="Output as CSV",
    )
    fmt_group.add_argument(
        "--jsonl", action="store_const", const="jsonl", dest="fmt",
        help="Output as JSON Lines",
    )
    parser.set_defaults(fmt="plain")

    args = parser.parse_args()

    if args.file:
        with open(args.file) as fh:
            source = fh.read()
    else:
        source = sys.stdin.read()

    vertices, edges = convert(source)
    print(format_output(vertices, edges, args.fmt))


if __name__ == "__main__":
    main()
