"""Tests for the fleetjsonl2graph adapter.

Assert the three fleet->graph-vis mappings:
  * edge ``rel`` -> non-empty ``label``
  * node ``kind`` -> vis styling extras (color + shape)
  * ``drift`` skipped by default / rendered as annotation with ``--drift``
"""

import io
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
CONV_DIR = os.path.join(ROOT, "scripts", "converters", "fleetjsonl2graph")
SCRIPT = os.path.join(CONV_DIR, "fleetjsonl2graph.py")
SAMPLE = os.path.join(ROOT, "examples", "fleet-topology-sample.jsonl")

sys.path.insert(0, CONV_DIR)
import fleetjsonl2graph as adapter  # noqa: E402


def _run(source, drift=False):
    return adapter.convert(io.StringIO(source), drift=drift)


def _by_type(lines, typ):
    return [o for o in lines if o["type"] == typ]


# --- rel -> label ---------------------------------------------------------

def test_rel_becomes_label():
    lines = _run('{"type":"edge","rel":"oversees","from":"A","to":"B"}\n')
    edges = _by_type(lines, "edge")
    assert len(edges) == 1
    assert edges[0]["label"] == "oversees"
    assert "rel" not in edges[0]


def test_all_edges_carry_nonempty_labels():
    with open(SAMPLE) as fh:
        lines = adapter.convert(fh)
    edges = _by_type(lines, "edge")
    assert edges, "sample must contain edges"
    for e in edges:
        assert e.get("label"), f"edge {e.get('id')} has empty label"


def test_coordinates_edge_present():
    # acceptance greps for "coordinates" in the rendered graph
    with open(SAMPLE) as fh:
        lines = adapter.convert(fh)
    labels = {e["label"] for e in _by_type(lines, "edge")}
    assert "coordinates" in labels


# --- kind -> styling ------------------------------------------------------

def test_kind_adds_color_and_shape():
    lines = _run('{"type":"node","id":"L","kind":"lead"}\n')
    node = _by_type(lines, "node")[0]
    assert "color" in node and isinstance(node["color"], dict)
    assert "background" in node["color"]
    assert "shape" in node


def test_all_sample_nodes_have_color_and_shape():
    with open(SAMPLE) as fh:
        lines = adapter.convert(fh)
    nodes = _by_type(lines, "node")
    assert nodes
    for n in nodes:
        assert "color" in n and "shape" in n, f"node {n.get('id')} missing styling"


def test_kinds_get_distinct_shapes():
    src = (
        '{"type":"node","id":"L","kind":"lead"}\n'
        '{"type":"node","id":"C","kind":"coord"}\n'
        '{"type":"node","id":"S","kind":"session"}\n'
    )
    nodes = {n["id"]: n for n in _by_type(_run(src), "node")}
    assert nodes["L"]["shape"] == "box"
    assert nodes["C"]["shape"] == "ellipse"
    assert nodes["S"]["shape"] == "dot"


def test_stale_node_gets_dashed_border():
    node = _by_type(_run('{"type":"node","id":"X","kind":"session","stale":true}\n'), "node")[0]
    assert node["shapeProperties"]["borderDashes"]


def test_not_alive_node_gets_dashed_border():
    node = _by_type(_run('{"type":"node","id":"X","kind":"coord","alive":false}\n'), "node")[0]
    assert node["shapeProperties"]["borderDashes"]


def test_terminated_node_marked_and_red():
    node = _by_type(_run('{"type":"node","id":"T","kind":"terminated","alive":false}\n'), "node")[0]
    assert "✕" in node["label"]
    assert node["color"]["background"] == "#E53935"


def test_input_styling_not_clobbered():
    src = '{"type":"node","id":"L","kind":"lead","color":{"background":"#000000"},"shape":"star"}\n'
    node = _by_type(_run(src), "node")[0]
    assert node["color"]["background"] == "#000000"
    assert node["shape"] == "star"


def test_stale_edge_dashed():
    edge = _by_type(_run('{"type":"edge","rel":"coordinates","from":"A","to":"B","stale":true}\n'), "edge")[0]
    assert edge["dashes"] is True


# --- drift ---------------------------------------------------------------

def test_drift_skipped_by_default():
    src = '{"type":"drift","kind":"uncovered","count":1,"detail":["x"],"subject":"S"}\n'
    lines = _run(src, drift=False)
    assert lines == []


def test_drift_rendered_with_flag():
    src = (
        '{"type":"node","id":"S","kind":"session"}\n'
        '{"type":"drift","kind":"uncovered","count":2,"detail":["a","b"],"subject":"S"}\n'
    )
    lines = _run(src, drift=True)
    drift_nodes = [n for n in _by_type(lines, "node") if n.get("kind") == "drift"]
    assert len(drift_nodes) == 1
    dn = drift_nodes[0]
    assert dn["color"]["border"] == "#C62828"
    # annotation attached to its subject
    drift_edges = [e for e in _by_type(lines, "edge") if e["to"] == dn["id"]]
    assert drift_edges and drift_edges[0]["from"] == "S"


def test_unknown_type_dropped():
    lines = _run('{"type":"wormhole","id":"Z"}\n')
    assert lines == []


# --- CLI / stdin round-trip ----------------------------------------------

def test_cli_stdin_produces_valid_jsonl():
    with open(SAMPLE) as fh:
        data = fh.read()
    proc = subprocess.run(
        [sys.executable, SCRIPT],
        input=data, capture_output=True, text=True, check=True,
    )
    out_lines = [json.loads(ln) for ln in proc.stdout.strip().splitlines()]
    assert all("type" in o for o in out_lines)
    assert any(o["type"] == "edge" and o.get("label") == "coordinates" for o in out_lines)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
