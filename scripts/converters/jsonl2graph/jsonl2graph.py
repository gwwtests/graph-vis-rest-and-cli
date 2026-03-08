#!/usr/bin/env python3
"""jsonl2graph -- Convert JSONL graph files to graph intermediate format.

Problem Statement
-----------------
We are given a JSONL file where each line is a JSON object describing a graph
element.  Each object has a required ``type`` field which is one of ``node``,
``edge``, or ``triplet``.

* **node**: required ``id``.  Optional ``label`` (defaults to id).  All other
  fields are vis-network styling pass-through.
* **edge**: required ``from``, ``to``.  Optional ``label`` (default ""),
  ``id`` (auto-generated as ``{from}-{label}-{to}``).  All other fields are
  styling pass-through.
* **triplet**: required ``subject``, ``predicate``, ``object``.  Creates two
  nodes and one edge with no styling extras.

Lines starting with ``#`` and blank lines are skipped.

If a node ID appears in an edge or triplet but wasn't explicitly defined, it is
auto-created with ``{"id": X, "label": X}``.  If a node is defined explicitly
and then appears in a triplet, the explicit definition (with styling) is kept.

Output Formats
--------------
* **plain** (default) -- First line is ``Vn En`` (vertex count, edge count).
  Subsequent lines are ``from to label``, one per edge.
* **csv** (``--csv``) -- Header ``from,to,label`` followed by CSV data rows.
* **jsonl** (``--jsonl``) -- One JSON object per line, re-serialized with the
  ``type`` field, preserving all extras.

Usage
-----
    ./jsonl2graph.py input.jsonl              # plain text to stdout
    ./jsonl2graph.py input.jsonl --csv        # CSV to stdout
    ./jsonl2graph.py input.jsonl --jsonl      # JSONL to stdout
    cat input.jsonl | ./jsonl2graph.py        # read from stdin
    cat input.jsonl | ./jsonl2graph.py --csv  # stdin + CSV output

Library usage::

    from jsonl2graph import convert, format_output

    result = convert("data.jsonl")
    print(format_output(result, fmt="jsonl"))
"""

import argparse
import csv
import io
import json
import sys


def convert(source):
    """Parse a JSONL graph file and return the graph.

    Parameters
    ----------
    source : str or file-like
        A filesystem path (str) or an open file/StringIO with JSONL content.

    Returns
    -------
    dict
        ``{"nodes": [...], "edges": [...]}`` where each node/edge dict
        contains all fields including styling extras.
    """
    if isinstance(source, str):
        with open(source) as fh:
            return _parse(fh)
    return _parse(source)


def _parse(fh):
    """Internal JSONL reader -- consumes an open file handle."""
    # Ordered dict of node_id -> node dict (preserves insertion order)
    nodes = {}
    edges = []

    for line in fh:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        obj = json.loads(stripped)
        typ = obj["type"]

        if typ == "node":
            node_id = obj["id"]
            node = dict(obj)
            del node["type"]
            node.setdefault("label", node_id)
            nodes[node_id] = node

        elif typ == "edge":
            edge = dict(obj)
            del edge["type"]
            edge.setdefault("label", "")
            frm = edge["from"]
            to = edge["to"]
            edge.setdefault("id", f"{frm}-{edge['label']}-{to}")
            # Auto-create nodes if not explicitly defined
            _ensure_node(nodes, frm)
            _ensure_node(nodes, to)
            edges.append(edge)

        elif typ == "triplet":
            subj = obj["subject"]
            pred = obj["predicate"]
            obj_node = obj["object"]
            # Auto-create nodes if not explicitly defined
            _ensure_node(nodes, subj)
            _ensure_node(nodes, obj_node)
            edge_id = f"{subj}-{pred}-{obj_node}"
            edges.append({
                "id": edge_id,
                "from": subj,
                "to": obj_node,
                "label": pred,
            })

    return {"nodes": list(nodes.values()), "edges": edges}


def _ensure_node(nodes, node_id):
    """Add a default node entry if *node_id* is not already present."""
    if node_id not in nodes:
        nodes[node_id] = {"id": node_id, "label": node_id}


def format_output(result, fmt="plain"):
    """Serialize the graph result into the requested format.

    Parameters
    ----------
    result : dict
        ``{"nodes": [...], "edges": [...]}``.
    fmt : str
        One of ``"plain"``, ``"csv"``, or ``"jsonl"``.

    Returns
    -------
    str
        The formatted output, without a trailing newline.
    """
    nodes = result["nodes"]
    edges = result["edges"]

    if fmt == "plain":
        lines = [f"{len(nodes)} {len(edges)}"]
        for e in edges:
            lines.append(f"{e['from']} {e['to']} {e['label']}")
        return "\n".join(lines)

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(["from", "to", "label"])
        for e in edges:
            writer.writerow([e["from"], e["to"], e["label"]])
        return buf.getvalue().rstrip("\n")

    if fmt == "jsonl":
        lines = []
        for n in nodes:
            obj = {"type": "node"}
            obj.update(n)
            lines.append(json.dumps(obj))
        for e in edges:
            obj = {"type": "edge"}
            obj.update(e)
            lines.append(json.dumps(obj))
        return "\n".join(lines)

    raise ValueError(f"Unknown format: {fmt!r}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert JSONL graph files to graph intermediate format.",
    )
    parser.add_argument("file", nargs="?", default=None,
                        help="JSONL input file (default: stdin)")
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
        result = convert(args.file)
    else:
        result = convert(sys.stdin)

    print(format_output(result, fmt))


if __name__ == "__main__":
    main()
