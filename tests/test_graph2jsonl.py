"""Tests for graph2jsonl converter."""

import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "scripts", "converters", "graph2jsonl"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "scripts", "converters", "jsonl2graph"))

from graph2jsonl import convert
from jsonl2graph import convert as jsonl2graph_convert

CONVERTER = os.path.join(os.path.dirname(__file__),
                         "..", "scripts", "converters", "graph2jsonl",
                         "graph2jsonl.py")
INPUT_DIR = os.path.join(os.path.dirname(__file__),
                         "..", "scripts", "converters", "graph2jsonl", "input")


# ---------------------------------------------------------------------------
# TestConvert -- basic library API tests
# ---------------------------------------------------------------------------

class TestConvert:
    def test_simple_nodes_and_edges(self):
        graph = {
            "nodes": [
                {"id": "A", "label": "A"},
                {"id": "B", "label": "B"},
            ],
            "edges": [
                {"id": "A-knows-B", "from": "A", "to": "B", "label": "knows"},
            ],
        }
        result = convert(graph)
        lines = result.strip().split("\n")
        assert len(lines) == 3

        n1 = json.loads(lines[0])
        assert n1["type"] == "node"
        assert n1["id"] == "A"

        n2 = json.loads(lines[1])
        assert n2["type"] == "node"
        assert n2["id"] == "B"

        e1 = json.loads(lines[2])
        assert e1["type"] == "edge"
        assert e1["from"] == "A"
        assert e1["to"] == "B"
        assert e1["label"] == "knows"

    def test_nodes_before_edges(self):
        graph = {
            "nodes": [{"id": "X", "label": "X"}],
            "edges": [{"from": "X", "to": "Y", "label": "e"}],
        }
        result = convert(graph)
        lines = result.strip().split("\n")
        assert json.loads(lines[0])["type"] == "node"
        assert json.loads(lines[1])["type"] == "edge"

    def test_multiple_edges(self):
        graph = {
            "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
            "edges": [
                {"from": "A", "to": "B", "label": "e1"},
                {"from": "B", "to": "A", "label": "e2"},
            ],
        }
        result = convert(graph)
        lines = result.strip().split("\n")
        assert len(lines) == 4  # 2 nodes + 2 edges

    def test_edge_without_label(self):
        graph = {
            "nodes": [{"id": "A", "label": "A"}],
            "edges": [{"from": "A", "to": "B"}],
        }
        result = convert(graph)
        lines = result.strip().split("\n")
        edge = json.loads(lines[1])
        assert "label" not in edge or edge["label"] == ""


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_graph(self):
        result = convert({"nodes": [], "edges": []})
        assert result == ""

    def test_single_node_no_edges(self):
        result = convert({"nodes": [{"id": "Solo", "label": "Solo"}], "edges": []})
        lines = result.strip().split("\n")
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["type"] == "node"
        assert obj["id"] == "Solo"

    def test_unicode_labels(self):
        graph = {
            "nodes": [{"id": "n1", "label": "Geburtstag"}],
            "edges": [],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["label"] == "Geburtstag"

    def test_unicode_emoji(self):
        graph = {
            "nodes": [{"id": "smile", "label": "\U0001f600 Happy"}],
            "edges": [],
        }
        result = convert(graph)
        assert "\U0001f600" in result

    def test_special_chars_in_ids(self):
        graph = {
            "nodes": [{"id": "node with spaces", "label": "Node With Spaces"}],
            "edges": [],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["id"] == "node with spaces"

    def test_nodes_with_hooks(self):
        graph = {
            "nodes": [{
                "id": "R",
                "label": "Root",
                "on_click": [{"action": "toggle_node", "id": "C"}],
                "on_doubleClick": [{"action": "remove_node", "id": "C"}],
            }],
            "edges": [],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["on_click"] == [{"action": "toggle_node", "id": "C"}]
        assert obj["on_doubleClick"] == [{"action": "remove_node", "id": "C"}]

    def test_missing_nodes_key(self):
        """Gracefully handle missing keys."""
        result = convert({"edges": [{"from": "A", "to": "B"}]})
        lines = result.strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["type"] == "edge"

    def test_missing_edges_key(self):
        result = convert({"nodes": [{"id": "A", "label": "A"}]})
        lines = result.strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["type"] == "node"


# ---------------------------------------------------------------------------
# TestLossless -- verify ALL extras are preserved
# ---------------------------------------------------------------------------

class TestLossless:
    def test_node_color_and_shape(self):
        graph = {
            "nodes": [{
                "id": "S",
                "label": "Server",
                "color": {"background": "#4CAF50", "border": "#388E3C"},
                "shape": "box",
            }],
            "edges": [],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["color"] == {"background": "#4CAF50", "border": "#388E3C"}
        assert obj["shape"] == "box"

    def test_node_font(self):
        graph = {
            "nodes": [{"id": "N", "label": "N", "font": {"color": "white", "size": 16}}],
            "edges": [],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["font"] == {"color": "white", "size": 16}

    def test_node_border_width(self):
        graph = {
            "nodes": [{"id": "N", "label": "N", "borderWidth": 3}],
            "edges": [],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["borderWidth"] == 3

    def test_node_hidden_and_physics(self):
        graph = {
            "nodes": [{"id": "H", "label": "Hidden", "hidden": True, "physics": False}],
            "edges": [],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["hidden"] is True
        assert obj["physics"] is False

    def test_node_hooks_preserved(self):
        on_click = [
            {"action": "toggle_node", "id": "C1"},
            {"action": "toggle_style", "id": "Root", "style": {"borderWidth": 4}},
        ]
        graph = {
            "nodes": [{"id": "Root", "label": "Root", "on_click": on_click}],
            "edges": [],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["on_click"] == on_click

    def test_edge_color_and_width(self):
        graph = {
            "nodes": [],
            "edges": [{"from": "A", "to": "B", "color": {"color": "#00ff00"}, "width": 3}],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["color"] == {"color": "#00ff00"}
        assert obj["width"] == 3

    def test_edge_dashes(self):
        graph = {
            "nodes": [],
            "edges": [{"from": "A", "to": "B", "dashes": [5, 5]}],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["dashes"] == [5, 5]

    def test_edge_dashes_boolean(self):
        graph = {
            "nodes": [],
            "edges": [{"from": "A", "to": "B", "dashes": True}],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["dashes"] is True

    def test_edge_hidden_physics(self):
        graph = {
            "nodes": [],
            "edges": [{"from": "A", "to": "B", "hidden": True, "physics": False}],
        }
        result = convert(graph)
        obj = json.loads(result.strip())
        assert obj["hidden"] is True
        assert obj["physics"] is False

    def test_all_fixture_files_lossless(self):
        """Load each fixture, convert, and verify every field is present."""
        for fname in ["simple.json", "styled.json", "hooks.json"]:
            path = os.path.join(INPUT_DIR, fname)
            with open(path) as fh:
                graph = json.load(fh)
            result = convert(graph)
            lines = result.strip().split("\n")
            # Reconstruct and compare
            node_idx = 0
            edge_idx = 0
            for line in lines:
                obj = json.loads(line)
                if obj["type"] == "node":
                    orig = graph["nodes"][node_idx]
                    for k, v in orig.items():
                        assert obj[k] == v, f"{fname}: node field {k} mismatch"
                    node_idx += 1
                elif obj["type"] == "edge":
                    orig = graph["edges"][edge_idx]
                    for k, v in orig.items():
                        assert obj[k] == v, f"{fname}: edge field {k} mismatch"
                    edge_idx += 1


# ---------------------------------------------------------------------------
# TestCrossValidation -- round-trip with jsonl2graph
# ---------------------------------------------------------------------------

class TestCrossValidation:
    def _round_trip(self, graph):
        """graph -> JSONL string -> jsonl2graph -> graph dict."""
        jsonl_str = convert(graph)
        return jsonl2graph_convert(io.StringIO(jsonl_str))

    def test_simple_round_trip(self):
        graph = {
            "nodes": [
                {"id": "Alice", "label": "Alice"},
                {"id": "Bob", "label": "Bob"},
            ],
            "edges": [
                {"id": "Alice-knows-Bob", "from": "Alice", "to": "Bob", "label": "knows"},
            ],
        }
        result = self._round_trip(graph)
        assert len(result["nodes"]) == len(graph["nodes"])
        assert len(result["edges"]) == len(graph["edges"])
        # Check node IDs match
        orig_ids = {n["id"] for n in graph["nodes"]}
        result_ids = {n["id"] for n in result["nodes"]}
        assert orig_ids == result_ids

    def test_styled_round_trip(self):
        graph = {
            "nodes": [{
                "id": "S",
                "label": "Server",
                "color": {"background": "#4CAF50"},
                "shape": "box",
                "borderWidth": 2,
            }],
            "edges": [{
                "id": "S-q-D",
                "from": "S",
                "to": "D",
                "label": "q",
                "width": 3,
                "dashes": True,
            }],
        }
        result = self._round_trip(graph)
        node = result["nodes"][0]
        assert node["color"] == {"background": "#4CAF50"}
        assert node["shape"] == "box"
        assert node["borderWidth"] == 2
        edge = result["edges"][0]
        assert edge["width"] == 3
        assert edge["dashes"] is True

    def test_hooks_round_trip(self):
        on_click = [{"action": "toggle_node", "id": "C"}]
        graph = {
            "nodes": [{
                "id": "R",
                "label": "Root",
                "on_click": on_click,
            }],
            "edges": [],
        }
        result = self._round_trip(graph)
        assert result["nodes"][0]["on_click"] == on_click

    def test_empty_round_trip(self):
        graph = {"nodes": [], "edges": []}
        result = self._round_trip(graph)
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_fixture_file_round_trip(self):
        """Load styled.json fixture, convert via graph2jsonl, then back."""
        path = os.path.join(INPUT_DIR, "styled.json")
        with open(path) as fh:
            graph = json.load(fh)
        result = self._round_trip(graph)
        assert len(result["nodes"]) == len(graph["nodes"])
        assert len(result["edges"]) == len(graph["edges"])
        # Verify styling survived
        for orig, conv in zip(graph["nodes"], result["nodes"]):
            for k, v in orig.items():
                assert conv[k] == v, f"Node field {k} lost in round-trip"
        for orig, conv in zip(graph["edges"], result["edges"]):
            for k, v in orig.items():
                assert conv[k] == v, f"Edge field {k} lost in round-trip"


# ---------------------------------------------------------------------------
# TestCLI -- subprocess invocation
# ---------------------------------------------------------------------------

class TestCLI:
    def test_file_arg(self):
        path = os.path.join(INPUT_DIR, "simple.json")
        proc = subprocess.run(
            [sys.executable, CONVERTER, path],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0
        lines = proc.stdout.strip().split("\n")
        assert len(lines) == 3
        assert json.loads(lines[0])["type"] == "node"

    def test_stdin(self):
        graph = json.dumps({
            "nodes": [{"id": "X", "label": "X"}],
            "edges": [],
        })
        proc = subprocess.run(
            [sys.executable, CONVERTER],
            input=graph, capture_output=True, text=True,
        )
        assert proc.returncode == 0
        obj = json.loads(proc.stdout.strip())
        assert obj["type"] == "node"
        assert obj["id"] == "X"

    def test_help(self):
        proc = subprocess.run(
            [sys.executable, CONVERTER, "--help"],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0
        assert "JSONL" in proc.stdout or "jsonl" in proc.stdout.lower()

    def test_help_subcommand(self):
        proc = subprocess.run(
            [sys.executable, CONVERTER, "help"],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0

    def test_output_file(self, tmp_path):
        input_path = os.path.join(INPUT_DIR, "simple.json")
        output_path = str(tmp_path / "out.jsonl")
        proc = subprocess.run(
            [sys.executable, CONVERTER, input_path, "-o", output_path],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0
        with open(output_path) as fh:
            lines = fh.read().strip().split("\n")
        assert len(lines) == 3

    def test_empty_graph_cli(self):
        path = os.path.join(INPUT_DIR, "empty.json")
        proc = subprocess.run(
            [sys.executable, CONVERTER, path],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == ""
