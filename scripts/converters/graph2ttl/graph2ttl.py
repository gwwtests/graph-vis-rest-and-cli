#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = ["rdflib>=7.0"]
# ///
"""graph2ttl -- Convert graph JSON to RDF Turtle format.

Given a graph in the ``/api/graph`` JSON format (a dict with ``nodes`` and
``edges`` arrays), produce an RDF Turtle serialization where each edge becomes
an RDF triple.

Turtle is a **triple-centric** format: only edges are represented.  Node
styling properties, isolated nodes (those without edges), and edge extras
(color, width, etc.) are silently dropped -- this is a lossy export by design.

Problem Statement (ACM ICPC style)
-----------------------------------
**Input:**  A JSON object on stdin or as a file argument, with the structure::

    {
      "nodes": [{"id": "Alice", "label": "Alice", ...}, ...],
      "edges": [{"from": "Alice", "to": "Bob", "label": "knows", ...}, ...]
    }

**Output:** An RDF Turtle document on stdout, using ``ex:`` as the default
namespace prefix (``http://example.org/``).

    >>> # Given the input above, output:
    >>> # @prefix ex: <http://example.org/> .
    >>> #
    >>> # ex:Alice ex:knows ex:Bob .

**Rules:**

* Each edge ``(from, to, label)`` becomes a triple
  ``ex:<from> ex:<label> ex:<to> .``
* Node IDs and edge labels are sanitized for use as URI local names:
  spaces become underscores, other special characters are percent-encoded.
* Edges without a label use ``ex:relatedTo`` as the default predicate.
* Triples are sorted lexicographically for deterministic output.
* Nodes that have no edges are **not** included.
* An empty graph (no edges) produces only the prefix declaration.

Usage
-----
    ./graph2ttl.py input.json
    cat input.json | ./graph2ttl.py
    curl -s http://localhost:7849/api/graph | ./graph2ttl.py
"""

import argparse
import json
import re
import sys

from rdflib import Graph, Namespace, URIRef


EX = Namespace("http://example.org/")

# Characters that are unsafe in IRI local names and need escaping
_UNSAFE_RE = re.compile(r'[<>"{}|\\^`\s]')


def _sanitize_local_name(name: str) -> str:
    """Sanitize a string for use as a Turtle URI local name.

    Spaces become underscores.  Unicode letters and digits are kept as-is
    (they are valid in IRIs).  Only characters truly unsafe in IRIs are
    percent-encoded.
    """
    name = name.replace(" ", "_")
    return _UNSAFE_RE.sub(lambda m: "%" + m.group().encode("utf-8").hex("%").upper(), name)


def convert(graph_data: dict) -> str:
    """Convert {"nodes": [...], "edges": [...]} to Turtle string.

    Uses rdflib to build a proper RDF graph, ensuring valid TTL output.
    Only edges are exported; isolated nodes and styling extras are dropped.
    """
    g = Graph()
    g.bind("ex", EX)

    edges = graph_data.get("edges", [])

    for edge in edges:
        subj_id = edge.get("from", "")
        obj_id = edge.get("to", "")
        label = edge.get("label", "")

        if not subj_id or not obj_id:
            continue

        subj = URIRef(str(EX) + _sanitize_local_name(subj_id))
        obj = URIRef(str(EX) + _sanitize_local_name(obj_id))

        if label:
            pred = URIRef(str(EX) + _sanitize_local_name(label))
        else:
            pred = URIRef(str(EX) + "relatedTo")

        g.add((subj, pred, obj))

    result = g.serialize(format="turtle")
    # rdflib omits the prefix declaration when the graph is empty;
    # emit it ourselves for consistency.
    if not edges or result.strip() == "":
        return "@prefix ex: <http://example.org/> .\n\n"
    return result


def main():
    """CLI: reads JSON from file arg or stdin, writes TTL to stdout."""
    parser = argparse.ArgumentParser(
        description="Convert graph JSON to RDF Turtle format.",
    )
    parser.add_argument(
        "file", nargs="?",
        help="Input JSON file (default: stdin)",
    )
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        parser.parse_args(["--help"])
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            graph_data = json.load(f)
    else:
        graph_data = json.load(sys.stdin)

    sys.stdout.write(convert(graph_data))


if __name__ == "__main__":
    main()
