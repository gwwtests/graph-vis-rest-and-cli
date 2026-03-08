#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""mermaid2graph -- Convert Mermaid graph definitions to graph intermediate format.

Problem Statement
-----------------
We are given a text file containing a Mermaid graph or flowchart definition.
The first line is a header of the form ``graph LR``, ``flowchart TD``, or
similar -- it declares the diagram type and layout direction but carries no
edge data, so we skip it.

Every subsequent non-empty line may contain an edge between two nodes,
optionally annotated with a label.  Three notations are recognised:

    A -->|label| B          pipe-delimited label on a directed arrow
    A -- label --> B        label placed between double-dash and arrow
    A --> B                 bare directed arrow (label defaults to "->")

Node identifiers are stripped of leading/trailing whitespace.  Semicolons
and trailing comments are tolerated but not required.

The output is the *graph intermediate format* shared across all converters
in this project.  In its default (plain-text) form, the first line holds
two integers -- the number of unique vertices and the number of edges --
followed by one ``from to label`` triple per line.  Two alternative
serialisations are available: CSV (``--csv``) and JSON Lines (``--jsonl``).

Usage
-----
    ./mermaid2graph.py input.mermaid
    ./mermaid2graph.py input.mermaid --csv
    ./mermaid2graph.py input.mermaid --jsonl
    cat input.mermaid | ./mermaid2graph.py

Library API
-----------
    >>> from mermaid2graph import convert, format_output
    >>> vertices, edges = convert(open("input.mermaid").read())
    >>> print(format_output(vertices, edges))
"""

import argparse
import json
import re
import sys


# ---------------------------------------------------------------------------
# Regex patterns for edge forms.  Each pattern captures three groups: the
# source node, the label (if present), and the target node.
#
# Supported arrow styles:
#   -->   normal directed arrow
#   ==>   thick directed arrow
#   -.->  dotted directed arrow
#
# Label forms:
#   A -->|label| B          pipe-delimited label
#   A -- label --> B        label between double-dash and arrow
#   A --> B                 bare arrow (label defaults to "->")
# ---------------------------------------------------------------------------

# Arrow stem alternatives: --> | ==> | -.->
_ARROW = r"(?:-->|==>|-\.->)"

_PAT_PIPE_LABEL = re.compile(
    rf"^\s*(\S+)\s+{_ARROW}\|([^|]+)\|\s+(\S+)"
)
_PAT_DASH_LABEL = re.compile(
    rf"^\s*(\S+)\s+--\s+(.+?)\s+{_ARROW}\s+(\S+)"
)
_PAT_NO_LABEL = re.compile(
    rf"^\s*(\S+)\s+{_ARROW}\s+(\S+)"
)

_HEADER_RE = re.compile(r"^\s*(graph|flowchart)\s", re.IGNORECASE)


def convert(source: str) -> tuple[set, list[tuple]]:
    """Parse a Mermaid graph definition and return vertices and edges.

    Parameters
    ----------
    source : str
        The full text of a Mermaid graph definition.

    Returns
    -------
    vertices : set of str
        Unique node identifiers found in the graph.
    edges : list of (str, str, str)
        Each element is a ``(from, to, label)`` triple.
    """
    vertices: set[str] = set()
    edges: list[tuple[str, str, str]] = []

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip the header line (graph LR, flowchart TD, etc.)
        if _HEADER_RE.match(stripped):
            continue

        # Try each pattern in order of specificity.
        m = _PAT_PIPE_LABEL.match(stripped)
        if m:
            src, label, tgt = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            vertices.update([src, tgt])
            edges.append((src, tgt, label))
            continue

        m = _PAT_DASH_LABEL.match(stripped)
        if m:
            src, label, tgt = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
            vertices.update([src, tgt])
            edges.append((src, tgt, label))
            continue

        m = _PAT_NO_LABEL.match(stripped)
        if m:
            src, tgt = m.group(1).strip(), m.group(2).strip()
            vertices.update([src, tgt])
            edges.append((src, tgt, "->"))
            continue

    return vertices, edges


def format_output(vertices: set, edges: list[tuple], fmt: str = "plain") -> str:
    """Serialise the parsed graph into the requested output format.

    Parameters
    ----------
    vertices : set of str
        Unique vertex identifiers.
    edges : list of (str, str, str)
        ``(from, to, label)`` triples.
    fmt : str
        One of ``"plain"`` (default), ``"csv"``, or ``"jsonl"``.

    Returns
    -------
    str
        The formatted output, without a trailing newline.
    """
    if fmt == "csv":
        lines = ["from,to,label"]
        for frm, to, label in edges:
            lines.append(f"{frm},{to},{label}")
        return "\n".join(lines)

    if fmt == "jsonl":
        lines = []
        for frm, to, label in edges:
            lines.append(json.dumps({"from": frm, "to": to, "label": label}))
        return "\n".join(lines)

    # Default: plain text
    lines = [f"{len(vertices)} {len(edges)}"]
    for frm, to, label in edges:
        lines.append(f"{frm} {to} {label}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert Mermaid graph definitions to graph intermediate format.",
    )
    parser.add_argument(
        "file", nargs="?", default=None,
        help="Input Mermaid file (reads stdin if omitted)",
    )
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument("--csv", action="store_true", help="Output as CSV")
    fmt.add_argument("--jsonl", action="store_true", help="Output as JSON Lines")
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        parser.parse_args(["--help"])
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            source = f.read()
    else:
        source = sys.stdin.read()

    vertices, edges = convert(source)

    out_fmt = "csv" if args.csv else "jsonl" if args.jsonl else "plain"
    print(format_output(vertices, edges, out_fmt))


if __name__ == "__main__":
    main()
