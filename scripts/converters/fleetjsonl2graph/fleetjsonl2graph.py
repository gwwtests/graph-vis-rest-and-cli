#!/usr/bin/env python3
"""fleetjsonl2graph -- Adapt fleet-topology JSONL into graph-vis JSONL.

Problem Statement
-----------------
The external fleet renderer ``fleet_topology_tree.py -F jsonl`` emits one JSON
object per line describing a coordinator/session fleet topology.  That JSONL is
*almost* loadable by ``graph-vis-cli.py -l file.jsonl`` (which understands
``{"type":"node"|"edge"|"triplet"}`` lines and passes unknown fields through as
vis-network styling extras).  Three small gaps remain:

1. Fleet **edges** carry ``rel`` (e.g. ``"rel":"oversees"``) instead of the
   ``label`` graph-vis expects, so they would load with empty labels.
2. Fleet **nodes** carry ``kind`` (lead/coord/session/manager/subteam/worker/
   terminated/workstream) plus status flags (``alive``/``stale``/``uncovered``/
   ``live``).  graph-vis passes these through but does not style on them.
3. Fleet ``drift`` records have no graph-vis equivalent and would be dropped.

This adapter closes those gaps.  It reads fleet JSONL (stdin or a path) and
emits graph-vis JSONL (stdout), mapping:

* ``rel`` -> ``label`` on edges (and a muted dashed style for stale edges).
* ``kind`` -> vis-network ``color``/``shape`` styling on nodes.  ``stale:true``
  or ``alive:false`` -> dashed muted border.  ``terminated`` -> red + ``✕``.
* ``drift`` lines are **skipped by default**; with ``--drift`` each becomes a
  red annotation node attached (by edge) to its ``subject``.

The output is loadable via ``graph-vis-cli.py -l out.jsonl`` or pasted into a
``+++jsonl`` block.

Usage
-----
    ./fleetjsonl2graph.py fleet.jsonl              # -> graph-vis JSONL on stdout
    cat fleet.jsonl | ./fleetjsonl2graph.py        # read from stdin
    ./fleetjsonl2graph.py --drift fleet.jsonl      # also render drift findings

Library usage::

    from fleetjsonl2graph import convert, format_jsonl

    lines = convert("fleet.jsonl", drift=True)
    print(format_jsonl(lines))

Design note
-----------
Deliberately thin: unknown ``type`` values and unknown node/edge fields are
preserved as pass-through extras, so future fleet fields keep flowing to
vis-network without adapter changes.
"""

import argparse
import json
import sys


# --- styling map: fleet ``kind`` -> vis-network node styling --------------
# Colours are chosen to be distinguishable in both light and dark graph
# backgrounds.  Each entry is merged into the node dict (caller-supplied
# fields win, so an explicit ``color`` in the input is never clobbered).
KIND_STYLE = {
    "lead":       {"shape": "box",     "color": {"background": "#FFD700", "border": "#B8860B"},
                   "font": {"color": "#3a2f00"}},
    "coord":      {"shape": "ellipse", "color": {"background": "#2196F3", "border": "#1565C0"},
                   "font": {"color": "white"}},
    "session":    {"shape": "dot",     "color": {"background": "#4CAF50", "border": "#2E7D32"}},
    "manager":    {"shape": "box",     "color": {"background": "#9C27B0", "border": "#6A1B9A"},
                   "font": {"color": "white"}},
    "subteam":    {"shape": "box",     "color": {"background": "#9E9E9E", "border": "#616161"}},
    "workstream": {"shape": "box",     "color": {"background": "#BDBDBD", "border": "#757575"}},
    "worker":     {"shape": "dot",     "color": {"background": "#009688", "border": "#00695C"},
                   "font": {"color": "white"}},
    "terminated": {"shape": "box",     "color": {"background": "#E53935", "border": "#B71C1C"},
                   "font": {"color": "white"},
                   "shapeProperties": {"borderDashes": [5, 5]}},
}

# Fallback style for unknown kinds -- still gives shape+color so downstream
# consumers can rely on their presence.
DEFAULT_STYLE = {"shape": "dot", "color": {"background": "#90A4AE", "border": "#546E7A"}}

# Muted border used to flag stale / not-alive nodes.
MUTED_BORDER = "#9E9E9E"


def _style_node(node):
    """Return a graph-vis node dict for one fleet node dict.

    Applies ``kind`` styling, then overlays status flags (stale / not-alive).
    Original fields are preserved as pass-through extras.
    """
    out = dict(node)
    out.pop("type", None)
    node_id = out.get("id")
    kind = out.get("kind")

    style = KIND_STYLE.get(kind, DEFAULT_STYLE)
    # Merge styling *under* the node's own fields (input wins).
    for key, val in style.items():
        out.setdefault(key, val)

    out.setdefault("label", node_id)

    # Status overlays: stale or explicitly dead -> dashed muted border.
    stale = out.get("stale") is True or out.get("alive") is False
    if stale and kind != "terminated":
        out.setdefault("shapeProperties", {})
        # do not clobber an explicit borderDashes
        if isinstance(out["shapeProperties"], dict):
            out["shapeProperties"].setdefault("borderDashes", [5, 5])
        # mute the border colour without destroying the background
        col = out.get("color")
        if isinstance(col, dict):
            col.setdefault("border", MUTED_BORDER)

    # terminated nodes get a visible mark on the label
    if kind == "terminated" and "✕" not in str(out.get("label", "")):
        out["label"] = f"✕ {out.get('label', node_id)}"

    return out


def _style_edge(edge):
    """Return a graph-vis edge dict for one fleet edge dict.

    Maps ``rel`` -> ``label`` and styles stale edges as dashed + muted.
    """
    out = dict(edge)
    out.pop("type", None)

    # rel -> label (do not clobber an explicit label)
    rel = out.pop("rel", None)
    if rel is not None:
        out.setdefault("label", rel)
    out.setdefault("label", "")

    frm = out.get("from")
    to = out.get("to")
    out.setdefault("id", f"{frm}-{out['label']}-{to}")

    if out.get("stale") is True:
        out.setdefault("dashes", True)
        out.setdefault("color", {"color": MUTED_BORDER})

    return out


def _drift_nodes_edges(drift, index):
    """Render one fleet drift record as an annotation node (+ optional edge).

    ``drift`` is a fleet ``{"type":"drift", "kind":..., "count":..., ...}``
    record.  A stable id is built from ``kind`` + *index*.  If the record
    carries a ``subject`` referencing a node id, an edge attaches the
    annotation to that subject.
    """
    kind = drift.get("kind", "drift")
    count = drift.get("count")
    detail = drift.get("detail")
    node_id = f"drift::{kind}::{index}"

    label = f"⚠ {kind}"
    if count is not None:
        label += f" ({count})"
    if isinstance(detail, list) and detail:
        label += "\n" + ", ".join(str(d) for d in detail)
    elif isinstance(detail, str):
        label += "\n" + detail

    node = {
        "type": "node",
        "id": node_id,
        "label": label,
        "kind": "drift",
        "shape": "box",
        "color": {"background": "#FFCDD2", "border": "#C62828"},
        "font": {"color": "#7f0000"},
        "shapeProperties": {"borderDashes": [3, 3]},
    }
    lines = [node]

    subject = drift.get("subject")
    if subject:
        lines.append({
            "type": "edge",
            "from": subject,
            "to": node_id,
            "label": "drift",
            "id": f"{subject}-drift-{node_id}",
            "dashes": True,
            "color": {"color": "#C62828"},
        })
    return lines


def convert(source, drift=False):
    """Adapt fleet JSONL into a list of graph-vis JSONL objects.

    Parameters
    ----------
    source : str or file-like
        A filesystem path (str) or an open file/StringIO with fleet JSONL.
    drift : bool
        If True, render ``drift`` records as red annotation nodes.  Default
        False (drift lines are skipped).

    Returns
    -------
    list of dict
        graph-vis JSONL objects, each with a ``type`` field.  Nodes come
        first (in first-seen order), then edges, then drift annotations.
    """
    if isinstance(source, str):
        with open(source) as fh:
            return _adapt(fh, drift)
    return _adapt(source, drift)


def _adapt(fh, drift):
    nodes = []
    edges = []
    drift_lines = []
    drift_index = 0

    for line in fh:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        obj = json.loads(stripped)
        typ = obj.get("type")

        if typ == "node":
            node = _style_node(obj)
            node_out = {"type": "node"}
            node_out.update(node)
            nodes.append(node_out)
        elif typ == "edge":
            edge = _style_edge(obj)
            edge_out = {"type": "edge"}
            edge_out.update(edge)
            edges.append(edge_out)
        elif typ == "drift":
            if drift:
                drift_lines.extend(_drift_nodes_edges(obj, drift_index))
            drift_index += 1
        # unknown types are dropped (mirrors graph-vis loader behaviour)

    return nodes + edges + drift_lines


def format_jsonl(lines):
    """Serialize a list of graph-vis objects to JSONL text (no trailing NL)."""
    return "\n".join(json.dumps(o) for o in lines)


def main():
    parser = argparse.ArgumentParser(
        description="Adapt fleet-topology JSONL into graph-vis JSONL.",
    )
    parser.add_argument("file", nargs="?", default=None,
                        help="fleet JSONL input file (default: stdin)")
    parser.add_argument("--drift", action="store_true",
                        help="render drift findings as red annotation nodes")
    if len(sys.argv) > 1 and sys.argv[1] == "help":
        parser.parse_args(["--help"])
    args = parser.parse_args()

    if args.file:
        lines = convert(args.file, drift=args.drift)
    else:
        lines = convert(sys.stdin, drift=args.drift)

    print(format_jsonl(lines))


if __name__ == "__main__":
    main()
