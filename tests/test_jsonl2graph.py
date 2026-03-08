"""Tests for jsonl2graph converter."""

import io
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "scripts", "converters", "jsonl2graph"))

from jsonl2graph import convert, format_output


def test_convert_triplets():
    data = '\n'.join([
        json.dumps({"type": "triplet", "subject": "A", "predicate": "knows", "object": "B"}),
        json.dumps({"type": "triplet", "subject": "B", "predicate": "likes", "object": "C"}),
    ])
    result = convert(io.StringIO(data))
    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2
    assert result["edges"][0]["from"] == "A"
    assert result["edges"][0]["label"] == "knows"


def test_convert_nodes_with_extras():
    data = json.dumps({
        "type": "node", "id": "X", "label": "X-Label",
        "color": "#ff0000", "shape": "diamond",
    })
    result = convert(io.StringIO(data))
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["color"] == "#ff0000"
    assert result["nodes"][0]["shape"] == "diamond"


def test_convert_edges_with_extras():
    data = '\n'.join([
        json.dumps({"type": "node", "id": "A", "label": "A"}),
        json.dumps({"type": "node", "id": "B", "label": "B"}),
        json.dumps({
            "type": "edge", "from": "A", "to": "B", "label": "connects",
            "color": "#00ff00", "width": 3,
        }),
    ])
    result = convert(io.StringIO(data))
    assert result["edges"][0]["color"] == "#00ff00"
    assert result["edges"][0]["width"] == 3


def test_convert_edge_optional_label():
    data = '\n'.join([
        json.dumps({"type": "node", "id": "A", "label": "A"}),
        json.dumps({"type": "node", "id": "B", "label": "B"}),
        json.dumps({"type": "edge", "from": "A", "to": "B"}),
    ])
    result = convert(io.StringIO(data))
    assert result["edges"][0]["label"] == ""


def test_convert_mixed():
    """Nodes, edges, and triplets together."""
    data = '\n'.join([
        json.dumps({"type": "node", "id": "A", "label": "Alpha", "color": "red"}),
        json.dumps({"type": "triplet", "subject": "A", "predicate": "knows", "object": "B"}),
        json.dumps({"type": "edge", "from": "B", "to": "A", "label": "trusts", "width": 2}),
    ])
    result = convert(io.StringIO(data))
    assert len(result["nodes"]) == 2
    assert len(result["edges"]) == 2
    a_node = [n for n in result["nodes"] if n["id"] == "A"][0]
    assert a_node["color"] == "red"
    assert a_node["label"] == "Alpha"


def test_convert_skips_comments_and_blanks():
    data = '\n'.join([
        "# this is a comment",
        "",
        json.dumps({"type": "node", "id": "A", "label": "A"}),
        "   ",
    ])
    result = convert(io.StringIO(data))
    assert len(result["nodes"]) == 1


def test_format_output_plain():
    result = {
        "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
        "edges": [{"id": "A-knows-B", "from": "A", "to": "B", "label": "knows"}],
    }
    out = format_output(result, fmt="plain")
    lines = out.strip().split("\n")
    assert lines[0] == "2 1"
    assert "A B knows" in lines[1]


def test_format_output_jsonl():
    result = {
        "nodes": [{"id": "A", "label": "A", "color": "red"}],
        "edges": [],
    }
    out = format_output(result, fmt="jsonl")
    obj = json.loads(out.strip())
    assert obj["type"] == "node"
    assert obj["color"] == "red"


def test_convert_from_file(tmp_path):
    f = tmp_path / "test.jsonl"
    f.write_text('\n'.join([
        json.dumps({"type": "triplet", "subject": "X", "predicate": "y", "object": "Z"}),
    ]))
    result = convert(str(f))
    assert len(result["edges"]) == 1
