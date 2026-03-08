"""Tests for graph2csv converter."""

import csv
import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "scripts", "converters", "graph2csv"))

from graph2csv import convert

# Also import csv2graph for cross-validation
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "scripts", "converters", "csv2graph"))

from csv2graph import convert as csv2graph_convert

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONVERTER = os.path.join(REPO_ROOT, "scripts", "converters",
                         "graph2csv", "graph2csv.py")
INPUT_DIR = os.path.join(REPO_ROOT, "scripts", "converters",
                         "graph2csv", "input")


# ---------------------------------------------------------------------------
# TestConvert -- basic library API tests
# ---------------------------------------------------------------------------

class TestConvert:
    """Basic convert() function tests with inline dicts."""

    def test_single_edge(self):
        graph = {
            "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
            "edges": [{"from": "A", "to": "B", "label": "knows"}],
        }
        result = convert(graph)
        lines = result.split("\n")
        assert lines[0] == "from,to,label"
        assert lines[1] == "A,B,knows"
        assert len(lines) == 2

    def test_multiple_edges(self):
        graph = {
            "nodes": [
                {"id": "A", "label": "A"},
                {"id": "B", "label": "B"},
                {"id": "C", "label": "C"},
            ],
            "edges": [
                {"from": "A", "to": "B", "label": "knows"},
                {"from": "B", "to": "C", "label": "likes"},
            ],
        }
        result = convert(graph)
        lines = result.split("\n")
        assert len(lines) == 3
        assert lines[1] == "A,B,knows"
        assert lines[2] == "B,C,likes"

    def test_edge_order_preserved(self):
        graph = {
            "nodes": [],
            "edges": [
                {"from": "Z", "to": "Y", "label": "third"},
                {"from": "A", "to": "B", "label": "first"},
                {"from": "M", "to": "N", "label": "second"},
            ],
        }
        result = convert(graph)
        lines = result.split("\n")
        assert lines[1] == "Z,Y,third"
        assert lines[2] == "A,B,first"
        assert lines[3] == "M,N,second"


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: empty, unicode, commas, isolated nodes."""

    def test_empty_graph(self):
        result = convert({"nodes": [], "edges": []})
        assert result == "from,to,label"

    def test_unicode(self):
        graph = {
            "nodes": [{"id": "M\u00fcnchen", "label": "M\u00fcnchen"},
                       {"id": "\u6771\u4eac", "label": "Tokyo"}],
            "edges": [{"from": "M\u00fcnchen", "to": "\u6771\u4eac",
                        "label": "Flug nach"}],
        }
        result = convert(graph)
        lines = result.split("\n")
        assert "M\u00fcnchen" in lines[1]
        assert "\u6771\u4eac" in lines[1]
        assert "Flug nach" in lines[1]

    def test_field_with_comma(self):
        graph = {
            "nodes": [],
            "edges": [{"from": "A, Inc.", "to": "B", "label": "owns"}],
        }
        result = convert(graph)
        # csv.writer should quote the field
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert rows[1][0] == "A, Inc."

    def test_field_with_quotes(self):
        graph = {
            "nodes": [],
            "edges": [{"from": 'Say "hello"', "to": "B", "label": "greets"}],
        }
        result = convert(graph)
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert rows[1][0] == 'Say "hello"'

    def test_nodes_without_edges_not_in_output(self):
        graph = {
            "nodes": [{"id": "Lonely", "label": "Lonely"},
                       {"id": "A", "label": "A"},
                       {"id": "B", "label": "B"}],
            "edges": [{"from": "A", "to": "B", "label": "edge"}],
        }
        result = convert(graph)
        assert "Lonely" not in result

    def test_missing_label_defaults_empty(self):
        graph = {
            "nodes": [],
            "edges": [{"from": "A", "to": "B"}],
        }
        result = convert(graph)
        lines = result.split("\n")
        assert lines[1] == "A,B,"


# ---------------------------------------------------------------------------
# TestExtrasDropped
# ---------------------------------------------------------------------------

class TestExtrasDropped:
    """Verify that vis-network styling extras do NOT appear in CSV output."""

    def test_node_extras_not_in_output(self):
        graph = {
            "nodes": [
                {"id": "A", "label": "A", "color": "#ff0000", "shape": "diamond",
                 "borderWidth": 3, "font": {"size": 20}},
                {"id": "B", "label": "B", "color": "#0000ff"},
            ],
            "edges": [{"from": "A", "to": "B", "label": "e"}],
        }
        result = convert(graph)
        assert "#ff0000" not in result
        assert "diamond" not in result
        assert "borderWidth" not in result
        assert "#0000ff" not in result

    def test_edge_extras_not_in_output(self):
        graph = {
            "nodes": [],
            "edges": [{"from": "A", "to": "B", "label": "e",
                        "color": "#00cc00", "width": 4, "dashes": True,
                        "smooth": {"type": "curvedCW"}}],
        }
        result = convert(graph)
        assert "#00cc00" not in result
        assert "width" not in result
        assert "dashes" not in result
        assert "smooth" not in result

    def test_styled_fixture(self):
        with open(os.path.join(INPUT_DIR, "styled.json")) as f:
            graph = json.load(f)
        result = convert(graph)
        # Only header + 2 edge rows
        lines = result.split("\n")
        assert len(lines) == 3
        # No styling keywords
        for keyword in ["color", "shape", "borderWidth", "font", "dashes",
                         "arrows", "smooth", "width", "#ff6600", "#0066ff",
                         "#00cc00", "diamond", "box", "curvedCW"]:
            assert keyword not in result


# ---------------------------------------------------------------------------
# TestCrossValidation -- round-trip with csv2graph
# ---------------------------------------------------------------------------

class TestCrossValidation:
    """graph2csv output fed back into csv2graph should produce matching edges."""

    def test_round_trip_simple(self):
        with open(os.path.join(INPUT_DIR, "simple.json")) as f:
            graph = json.load(f)
        csv_text = convert(graph)
        vertices, edges = csv2graph_convert(io.StringIO(csv_text))
        # Same number of edges
        assert len(edges) == len(graph["edges"])
        # Same edge data (order preserved)
        for orig, (frm, to, label) in zip(graph["edges"], edges):
            assert orig["from"] == frm
            assert orig["to"] == to
            assert orig["label"] == label

    def test_round_trip_unicode(self):
        with open(os.path.join(INPUT_DIR, "unicode.json")) as f:
            graph = json.load(f)
        csv_text = convert(graph)
        vertices, edges = csv2graph_convert(io.StringIO(csv_text))
        assert len(edges) == len(graph["edges"])
        for orig, (frm, to, label) in zip(graph["edges"], edges):
            assert orig["from"] == frm
            assert orig["to"] == to
            assert orig["label"] == label

    def test_round_trip_empty(self):
        csv_text = convert({"nodes": [], "edges": []})
        vertices, edges = csv2graph_convert(io.StringIO(csv_text))
        assert len(edges) == 0
        assert len(vertices) == 0


# ---------------------------------------------------------------------------
# TestNativeValidation -- verify output is valid CSV via stdlib
# ---------------------------------------------------------------------------

class TestNativeValidation:
    """Parse graph2csv output with Python's csv.reader to verify validity."""

    def test_valid_csv_simple(self):
        with open(os.path.join(INPUT_DIR, "simple.json")) as f:
            graph = json.load(f)
        csv_text = convert(graph)
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        assert rows[0] == ["from", "to", "label"]
        assert len(rows) == 3  # header + 2 edges
        for row in rows[1:]:
            assert len(row) == 3

    def test_valid_csv_unicode(self):
        with open(os.path.join(INPUT_DIR, "unicode.json")) as f:
            graph = json.load(f)
        csv_text = convert(graph)
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        assert rows[0] == ["from", "to", "label"]
        assert len(rows) == 4  # header + 3 edges

    def test_valid_csv_empty(self):
        csv_text = convert({"nodes": [], "edges": []})
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0] == ["from", "to", "label"]


# ---------------------------------------------------------------------------
# TestCLI -- subprocess invocation
# ---------------------------------------------------------------------------

class TestCLI:
    """Test the CLI entry point via subprocess."""

    def test_file_argument(self):
        result = subprocess.run(
            [sys.executable, CONVERTER,
             os.path.join(INPUT_DIR, "simple.json")],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0] == "from,to,label"
        assert len(lines) == 3

    def test_stdin(self):
        graph = json.dumps({
            "nodes": [],
            "edges": [{"from": "X", "to": "Y", "label": "z"}],
        })
        result = subprocess.run(
            [sys.executable, CONVERTER],
            input=graph, capture_output=True, text=True,
        )
        assert result.returncode == 0
        lines = result.stdout.strip().split("\n")
        assert lines[0] == "from,to,label"
        assert lines[1] == "X,Y,z"

    def test_help(self):
        result = subprocess.run(
            [sys.executable, CONVERTER, "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "CSV" in result.stdout or "csv" in result.stdout.lower()

    def test_empty_graph_file(self):
        result = subprocess.run(
            [sys.executable, CONVERTER,
             os.path.join(INPUT_DIR, "empty.json")],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "from,to,label"
