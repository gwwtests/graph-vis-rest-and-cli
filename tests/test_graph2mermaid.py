"""Tests for graph2mermaid converter."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.converters.graph2mermaid.graph2mermaid import convert
from scripts.converters.mermaid2graph.mermaid2graph import convert as mermaid2graph_convert

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "scripts" / "converters" / "graph2mermaid" / "input"
CONVERTER = Path(__file__).resolve().parent.parent / "scripts" / "converters" / "graph2mermaid" / "graph2mermaid.py"


# ---------------------------------------------------------------------------
# TestConvert -- basic library API tests
# ---------------------------------------------------------------------------

class TestConvert:
    """Basic library API tests for the convert() function."""

    def test_simple_graph(self):
        graph = {
            "nodes": [
                {"id": "Alice", "label": "Alice"},
                {"id": "Bob", "label": "Bob"},
                {"id": "Charlie", "label": "Charlie"},
            ],
            "edges": [
                {"id": "e1", "from": "Alice", "to": "Bob", "label": "knows"},
                {"id": "e2", "from": "Bob", "to": "Charlie", "label": "likes"},
            ],
        }
        result = convert(graph)
        assert "graph LR" in result
        assert "    Alice -->|knows| Bob" in result
        assert "    Bob -->|likes| Charlie" in result

    def test_returns_string(self):
        result = convert({"nodes": [], "edges": []})
        assert isinstance(result, str)

    def test_edges_sorted(self):
        graph = {
            "nodes": [{"id": "C"}, {"id": "A"}, {"id": "B"}],
            "edges": [
                {"id": "e1", "from": "C", "to": "A", "label": "z"},
                {"id": "e2", "from": "A", "to": "B", "label": "x"},
            ],
        }
        result = convert(graph)
        lines = result.strip().split("\n")
        # After header, edges should be sorted: A->B before C->A
        edge_lines = [l for l in lines[1:] if "-->" in l]
        assert edge_lines[0].strip().startswith("A")
        assert edge_lines[1].strip().startswith("C")

    def test_fixture_simple(self):
        with open(FIXTURE_DIR / "simple.json") as f:
            graph = json.load(f)
        result = convert(graph)
        assert "Alice -->|knows| Bob" in result
        assert "Bob -->|likes| Charlie" in result


# ---------------------------------------------------------------------------
# TestEdgeCases -- empty graph, single node, no labels, unicode
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: empty graph, single node, missing labels, unicode."""

    def test_empty_graph(self):
        result = convert({"nodes": [], "edges": []})
        assert result.strip() == "graph LR"

    def test_single_node_no_edges(self):
        graph = {"nodes": [{"id": "Lonely"}], "edges": []}
        result = convert(graph)
        lines = result.strip().split("\n")
        assert lines[0] == "graph LR"
        assert "    Lonely" in lines

    def test_edges_without_labels(self):
        graph = {
            "nodes": [{"id": "X"}, {"id": "Y"}],
            "edges": [{"id": "e1", "from": "X", "to": "Y", "label": ""}],
        }
        result = convert(graph)
        assert "    X --> Y" in result
        # Should NOT have pipe-delimited label
        assert "-->|" not in result

    def test_edges_missing_label_key(self):
        graph = {
            "nodes": [{"id": "X"}, {"id": "Y"}],
            "edges": [{"id": "e1", "from": "X", "to": "Y"}],
        }
        result = convert(graph)
        assert "    X --> Y" in result
        assert "-->|" not in result

    def test_unicode_ids(self):
        graph = {
            "nodes": [{"id": "Алиса"}, {"id": "Боб"}],
            "edges": [{"id": "e1", "from": "Алиса", "to": "Боб", "label": "знает"}],
        }
        result = convert(graph)
        assert "Алиса -->|знает| Боб" in result

    def test_standalone_nodes_sorted(self):
        graph = {
            "nodes": [{"id": "Zeta"}, {"id": "Alpha"}, {"id": "Mid"}],
            "edges": [],
        }
        result = convert(graph)
        lines = result.strip().split("\n")
        node_lines = [l.strip() for l in lines[1:]]
        assert node_lines == ["Alpha", "Mid", "Zeta"]

    def test_mixed_connected_and_standalone(self):
        graph = {
            "nodes": [{"id": "A"}, {"id": "B"}, {"id": "Orphan"}],
            "edges": [{"id": "e1", "from": "A", "to": "B", "label": "rel"}],
        }
        result = convert(graph)
        assert "    A -->|rel| B" in result
        assert "    Orphan" in result

    def test_fixture_no_labels(self):
        with open(FIXTURE_DIR / "no_labels.json") as f:
            graph = json.load(f)
        result = convert(graph)
        assert "-->|" not in result
        assert "X --> Y" in result
        assert "Y --> Z" in result


# ---------------------------------------------------------------------------
# TestMermaidSyntax -- verify output format correctness
# ---------------------------------------------------------------------------

class TestMermaidSyntax:
    """Verify output starts with 'graph LR', uses correct arrow syntax."""

    def test_starts_with_header(self):
        result = convert({"nodes": [{"id": "A"}], "edges": []})
        assert result.startswith("graph LR")

    def test_labelled_edge_format(self):
        graph = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [{"id": "e1", "from": "A", "to": "B", "label": "test"}],
        }
        result = convert(graph)
        lines = result.strip().split("\n")
        edge_line = [l for l in lines if "test" in l][0]
        assert edge_line == "    A -->|test| B"

    def test_bare_edge_format(self):
        graph = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [{"id": "e1", "from": "A", "to": "B"}],
        }
        result = convert(graph)
        lines = result.strip().split("\n")
        edge_line = [l for l in lines if "-->" in l][0]
        assert edge_line == "    A --> B"

    def test_four_space_indent(self):
        graph = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [{"id": "e1", "from": "A", "to": "B", "label": "x"}],
        }
        result = convert(graph)
        for line in result.strip().split("\n")[1:]:
            assert line.startswith("    "), f"Line not 4-space indented: {line!r}"

    def test_styling_extras_dropped(self):
        with open(FIXTURE_DIR / "styled.json") as f:
            graph = json.load(f)
        result = convert(graph)
        # Should not contain any styling keywords
        assert "color" not in result
        assert "background" not in result
        assert "border" not in result
        assert "dashes" not in result
        assert "smooth" not in result
        # But edges should be present
        assert "Alpha -->|connects| Beta" in result
        assert "Beta -->|links| Gamma" in result


# ---------------------------------------------------------------------------
# TestCrossValidation -- round-trip: graph2mermaid → mermaid2graph
# ---------------------------------------------------------------------------

class TestCrossValidation:
    """Round-trip: graph2mermaid output fed into mermaid2graph should match."""

    def test_roundtrip_labelled(self):
        graph = {
            "nodes": [{"id": "Alice"}, {"id": "Bob"}, {"id": "Charlie"}],
            "edges": [
                {"id": "e1", "from": "Alice", "to": "Bob", "label": "knows"},
                {"id": "e2", "from": "Bob", "to": "Charlie", "label": "likes"},
            ],
        }
        mermaid_text = convert(graph)
        vertices, edges = mermaid2graph_convert(mermaid_text)

        # Check vertices
        assert "Alice" in vertices
        assert "Bob" in vertices
        assert "Charlie" in vertices

        # Check edges match
        edge_set = {(src, dst, label) for src, dst, label in edges}
        assert ("Alice", "Bob", "knows") in edge_set
        assert ("Bob", "Charlie", "likes") in edge_set

    def test_roundtrip_unlabelled(self):
        """Unlabelled edges use bare arrows; mermaid2graph returns '->' label."""
        graph = {
            "nodes": [{"id": "X"}, {"id": "Y"}],
            "edges": [{"id": "e1", "from": "X", "to": "Y"}],
        }
        mermaid_text = convert(graph)
        vertices, edges = mermaid2graph_convert(mermaid_text)

        assert "X" in vertices
        assert "Y" in vertices
        assert len(edges) == 1
        src, dst, label = edges[0]
        assert src == "X"
        assert dst == "Y"
        # mermaid2graph returns "->" for bare arrows
        assert label == "->"

    def test_roundtrip_fixture_simple(self):
        with open(FIXTURE_DIR / "simple.json") as f:
            graph = json.load(f)
        mermaid_text = convert(graph)
        vertices, edges = mermaid2graph_convert(mermaid_text)

        original_edges = {(e["from"], e["to"], e["label"]) for e in graph["edges"]}
        roundtrip_edges = {(src, dst, label) for src, dst, label in edges}
        assert original_edges == roundtrip_edges

    def test_roundtrip_styled_drops_extras(self):
        """Styled graph round-trips correctly (extras dropped, edges preserved)."""
        with open(FIXTURE_DIR / "styled.json") as f:
            graph = json.load(f)
        mermaid_text = convert(graph)
        vertices, edges = mermaid2graph_convert(mermaid_text)

        original_edges = {(e["from"], e["to"], e["label"]) for e in graph["edges"]}
        roundtrip_edges = {(src, dst, label) for src, dst, label in edges}
        assert original_edges == roundtrip_edges


# ---------------------------------------------------------------------------
# TestCLI -- subprocess invocation
# ---------------------------------------------------------------------------

class TestCLI:
    """Test CLI invocation via subprocess."""

    def test_cli_file_arg(self):
        result = subprocess.run(
            [sys.executable, str(CONVERTER), str(FIXTURE_DIR / "simple.json")],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "graph LR" in result.stdout
        assert "Alice -->|knows| Bob" in result.stdout

    def test_cli_stdin(self):
        input_data = json.dumps({
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [{"id": "e1", "from": "A", "to": "B", "label": "rel"}],
        })
        result = subprocess.run(
            [sys.executable, str(CONVERTER)],
            input=input_data,
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "A -->|rel| B" in result.stdout

    def test_cli_empty_graph(self):
        result = subprocess.run(
            [sys.executable, str(CONVERTER), str(FIXTURE_DIR / "empty.json")],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "graph LR"

    def test_cli_no_labels(self):
        result = subprocess.run(
            [sys.executable, str(CONVERTER), str(FIXTURE_DIR / "no_labels.json")],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "-->|" not in result.stdout
        assert "X --> Y" in result.stdout
