"""Tests for graph2dot converter."""

import json
import os
import shutil
import subprocess
import sys

import pytest

from scripts.converters.graph2dot.graph2dot import convert, _escape_dot
from scripts.converters.dot2graph.dot2graph import convert as dot2graph_convert

FIXTURES = os.path.join(
    os.path.dirname(__file__),
    os.pardir,
    "scripts",
    "converters",
    "graph2dot",
    "input",
)


def _load(name: str) -> dict:
    with open(os.path.join(FIXTURES, name)) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# TestConvert -- basic library API
# ---------------------------------------------------------------------------

class TestConvert:
    """Basic library API tests."""

    def test_simple(self):
        data = _load("simple.json")
        dot = convert(data)
        assert '"Alice"' in dot
        assert '"Bob"' in dot
        assert '"Alice" -> "Bob"' in dot
        assert 'label="knows"' in dot

    def test_empty(self):
        data = _load("empty.json")
        dot = convert(data)
        assert "digraph G {" in dot
        assert dot.strip().endswith("}")

    def test_styled_extras_ignored(self):
        data = _load("styled.json")
        dot = convert(data)
        # Styling properties must NOT appear in DOT output
        assert "#ff0000" not in dot
        assert "borderWidth" not in dot
        assert "shadow" not in dot
        assert "dashes" not in dot
        # But labels must be present
        assert 'label="Node A"' in dot
        assert 'label="styled edge"' in dot

    def test_compact_mode(self):
        data = _load("simple.json")
        dot = convert(data, compact=True)
        # Compact: no indentation, single-line-ish
        assert "    " not in dot

    def test_edge_without_label(self):
        data = {
            "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
            "edges": [{"id": "e1", "from": "A", "to": "B"}],
        }
        dot = convert(data)
        assert '"A" -> "B";' in dot
        assert "label" not in dot.split("->")[1].split(";")[0]

    def test_edge_with_empty_label(self):
        data = {
            "nodes": [{"id": "X", "label": "X"}, {"id": "Y", "label": "Y"}],
            "edges": [{"id": "e1", "from": "X", "to": "Y", "label": ""}],
        }
        dot = convert(data)
        # Empty label should not produce [label=""]
        line = [l for l in dot.splitlines() if "->" in l][0]
        assert "label" not in line


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases: empty graph, single node, unicode, spaces, special chars."""

    def test_single_node_no_edges(self):
        data = {"nodes": [{"id": "Lonely", "label": "Lonely"}], "edges": []}
        dot = convert(data)
        assert '"Lonely"' in dot
        assert "->" not in dot

    def test_spaces_in_ids(self):
        data = _load("spaces.json")
        dot = convert(data)
        assert '"New York"' in dot
        assert '"San Francisco"' in dot
        assert '"New York" -> "San Francisco"' in dot

    def test_special_chars_quotes(self):
        data = _load("special_chars.json")
        dot = convert(data)
        # Quotes in IDs must be escaped
        assert r'say \"hello\"' in dot

    def test_special_chars_backslash(self):
        data = _load("special_chars.json")
        dot = convert(data)
        # Backslashes in IDs must be escaped
        assert r"path\\to\\file" in dot

    def test_unicode_node(self):
        data = {
            "nodes": [
                {"id": "Tokyo", "label": "\u6771\u4eac"},
                {"id": "Osaka", "label": "\u5927\u962a"},
            ],
            "edges": [{"id": "e1", "from": "Tokyo", "to": "Osaka", "label": "\u65b0\u5e79\u7dda"}],
        }
        dot = convert(data)
        assert "\u6771\u4eac" in dot  # Tokyo in kanji
        assert "\u65b0\u5e79\u7dda" in dot  # Shinkansen in kanji

    def test_node_label_differs_from_id(self):
        data = {
            "nodes": [{"id": "n1", "label": "First Node"}],
            "edges": [],
        }
        dot = convert(data)
        assert '"n1" [label="First Node"]' in dot

    def test_node_without_label_uses_id(self):
        data = {"nodes": [{"id": "auto"}], "edges": []}
        dot = convert(data)
        assert '"auto" [label="auto"]' in dot


# ---------------------------------------------------------------------------
# TestDOTSyntax -- structural validation
# ---------------------------------------------------------------------------

class TestDOTSyntax:
    """Verify DOT structural correctness."""

    def test_starts_with_digraph(self):
        dot = convert(_load("simple.json"))
        assert dot.lstrip().startswith("digraph G {")

    def test_ends_with_closing_brace(self):
        dot = convert(_load("simple.json"))
        assert dot.strip().endswith("}")

    def test_semicolons_on_statements(self):
        dot = convert(_load("simple.json"))
        body_lines = [
            l.strip()
            for l in dot.splitlines()
            if l.strip() and not l.strip().startswith("digraph") and l.strip() != "}"
        ]
        for line in body_lines:
            assert line.endswith(";"), f"Missing semicolon: {line}"

    def test_all_identifiers_quoted(self):
        dot = convert(_load("spaces.json"))
        # Every node reference should be quoted
        for name in ["New York", "San Francisco", "Los Angeles"]:
            assert f'"{name}"' in dot


# ---------------------------------------------------------------------------
# TestCrossValidation -- round-trip via dot2graph
# ---------------------------------------------------------------------------

class TestCrossValidation:
    """Round-trip: graph2dot output -> dot2graph.convert() -> edges match."""

    def test_simple_roundtrip(self):
        data = _load("simple.json")
        dot = convert(data)
        vertices, edges = dot2graph_convert(dot)
        assert ("Alice", "Bob", "knows") in edges

    def test_spaces_roundtrip(self):
        data = _load("spaces.json")
        dot = convert(data)
        vertices, edges = dot2graph_convert(dot)
        assert ("New York", "San Francisco", "flight") in edges
        assert ("San Francisco", "Los Angeles", "drive") in edges

    def test_styled_roundtrip(self):
        data = _load("styled.json")
        dot = convert(data)
        vertices, edges = dot2graph_convert(dot)
        assert ("A", "B", "styled edge") in edges

    def test_edge_count_preserved(self):
        data = _load("simple.json")
        dot = convert(data)
        _, edges = dot2graph_convert(dot)
        assert len(edges) == len(data["edges"])

    def test_unlabeled_edge_roundtrip(self):
        """Edges without labels get '->' as label from dot2graph."""
        data = {
            "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
            "edges": [{"id": "e1", "from": "A", "to": "B"}],
        }
        dot = convert(data)
        _, edges = dot2graph_convert(dot)
        assert len(edges) == 1
        assert edges[0][0] == "A"
        assert edges[0][1] == "B"


# ---------------------------------------------------------------------------
# TestNativeValidation -- graphviz dot binary
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    shutil.which("dot") is None, reason="graphviz not installed"
)
class TestNativeValidation:
    """Validate DOT output with the real graphviz `dot` binary."""

    def _validate_dot(self, dot_text: str):
        result = subprocess.run(
            ["dot", "-Tsvg"],
            input=dot_text,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"dot failed: {result.stderr}"
        assert "<svg" in result.stdout

    def test_simple_valid(self):
        self._validate_dot(convert(_load("simple.json")))

    def test_empty_valid(self):
        self._validate_dot(convert(_load("empty.json")))

    def test_spaces_valid(self):
        self._validate_dot(convert(_load("spaces.json")))

    def test_styled_valid(self):
        self._validate_dot(convert(_load("styled.json")))

    def test_special_chars_valid(self):
        self._validate_dot(convert(_load("special_chars.json")))


# ---------------------------------------------------------------------------
# TestCLI -- subprocess invocation
# ---------------------------------------------------------------------------

class TestCLI:
    """Test CLI invocation via subprocess."""

    SCRIPT = os.path.join(
        os.path.dirname(__file__),
        os.pardir,
        "scripts",
        "converters",
        "graph2dot",
        "graph2dot.py",
    )

    def test_file_arg(self):
        infile = os.path.join(FIXTURES, "simple.json")
        result = subprocess.run(
            [sys.executable, self.SCRIPT, infile],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "digraph G {" in result.stdout
        assert '"Alice" -> "Bob"' in result.stdout

    def test_stdin(self):
        data = json.dumps(_load("simple.json"))
        result = subprocess.run(
            [sys.executable, self.SCRIPT],
            input=data,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "digraph G {" in result.stdout

    def test_compact_flag(self):
        infile = os.path.join(FIXTURES, "simple.json")
        result = subprocess.run(
            [sys.executable, self.SCRIPT, "--compact", infile],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "    " not in result.stdout

    def test_empty_graph_cli(self):
        infile = os.path.join(FIXTURES, "empty.json")
        result = subprocess.run(
            [sys.executable, self.SCRIPT, infile],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "digraph G {" in result.stdout
