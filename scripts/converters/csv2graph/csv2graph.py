#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""csv2graph -- Convert CSV triplet files to graph intermediate format.

Problem Statement
-----------------
We are given a CSV file whose rows describe edges in a directed, labeled graph.
The file has a header row (which we skip) followed by data rows.  Each row
contains at least three columns; the first three are interpreted as:

    source, target, relationship

Any additional columns are silently ignored.  Our task is to extract the set of
unique vertices and the ordered list of edges, then serialize them in one of
three output formats.

Approach
--------
We lean on Python's built-in ``csv`` module for robust parsing (handling quoted
fields, varying delimiters if we ever extend, etc.).  The ``convert`` function
accepts either a file-system path (str) or an already-opened file-like object,
making the code equally convenient as a library import and as a CLI tool that
reads from a positional argument or stdin.

Output Formats
--------------
* **plain** (default) -- First line is ``Vn En`` (vertex count, edge count).
  Subsequent lines are ``from to label``, one per edge.
* **csv** (``--csv``) -- Header ``from,to,label`` followed by CSV data rows.
* **jsonl** (``--jsonl``) -- One JSON object per line:
  ``{"from": "...", "to": "...", "label": "..."}``.

Usage
-----
    ./csv2graph.py input.csv              # plain text to stdout
    ./csv2graph.py input.csv --csv        # CSV to stdout
    ./csv2graph.py input.csv --jsonl      # JSONL to stdout
    cat input.csv | ./csv2graph.py        # read from stdin
    cat input.csv | ./csv2graph.py --csv  # stdin + CSV output

Library usage::

    from csv2graph import convert, format_output

    vertices, edges = convert("data.csv")
    print(format_output(vertices, edges, fmt="jsonl"))
"""

import argparse
import csv
import io
import json
import sys


def convert(source):
    """Parse a CSV triplet file and return the graph.

    Parameters
    ----------
    source : str or file-like
        A filesystem path (str) or an open file/StringIO with CSV content.

    Returns
    -------
    tuple[set, list[tuple]]
        ``(vertices, edges)`` where *vertices* is a set of unique vertex names
        and *edges* is a list of ``(from, to, label)`` tuples in file order.
    """
    if isinstance(source, str):
        with open(source, newline="") as fh:
            return _parse(fh)
    return _parse(source)


def _parse(fh):
    """Internal CSV reader -- consumes an open file handle."""
    reader = csv.reader(fh)
    next(reader)  # skip header
    vertices = set()
    edges = []
    for row in reader:
        if len(row) < 3:
            continue
        frm, to, label = row[0], row[1], row[2]
        vertices.update((frm, to))
        edges.append((frm, to, label))
    return vertices, edges


def format_output(vertices, edges, fmt="plain"):
    """Serialize *vertices* and *edges* into the requested format.

    Parameters
    ----------
    vertices : set
        Unique vertex names.
    edges : list[tuple]
        List of ``(from, to, label)`` tuples.
    fmt : str
        One of ``"plain"``, ``"csv"``, or ``"jsonl"``.

    Returns
    -------
    str
        The formatted output, without a trailing newline.
    """
    if fmt == "plain":
        lines = [f"{len(vertices)} {len(edges)}"]
        for frm, to, label in edges:
            lines.append(f"{frm} {to} {label}")
        return "\n".join(lines)

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["from", "to", "label"])
        for frm, to, label in edges:
            writer.writerow([frm, to, label])
        return buf.getvalue().rstrip("\n")

    if fmt == "jsonl":
        lines = []
        for frm, to, label in edges:
            lines.append(json.dumps({"from": frm, "to": to, "label": label}))
        return "\n".join(lines)

    raise ValueError(f"Unknown format: {fmt!r}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert CSV triplet files to graph intermediate format.",
    )
    parser.add_argument("file", nargs="?", default=None,
                        help="CSV input file (default: stdin)")
    parser.add_argument("--csv", action="store_true",
                        help="Output in CSV format")
    parser.add_argument("--jsonl", action="store_true",
                        help="Output in JSONL format")
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        parser.parse_args(["--help"])
    args = parser.parse_args()

    fmt = "plain"
    if args.csv:
        fmt = "csv"
    elif args.jsonl:
        fmt = "jsonl"

    if args.file:
        vertices, edges = convert(args.file)
    else:
        vertices, edges = convert(sys.stdin)

    print(format_output(vertices, edges, fmt))


if __name__ == "__main__":
    main()
