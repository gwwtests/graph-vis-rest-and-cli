"""Comprehensive tests for dot2graph converter.

Tests the convert() and format_output() library API, CLI invocation via
subprocess, and (optionally) validation against native graphviz tools.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

# Add converter to path so we can import it directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "converters", "dot2graph"))
from dot2graph import convert, format_output, _unquote


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONVERTER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "converters", "dot2graph", "dot2graph.py"
)

HAS_GRAPHVIZ = shutil.which("dot") is not None


def run_cli(*args, stdin_data=None):
    """Run dot2graph.py as a subprocess and return (stdout, stderr, returncode)."""
    cmd = [sys.executable, CONVERTER_PATH] + list(args)
    result = subprocess.run(
        cmd, input=stdin_data, capture_output=True, text=True, timeout=10
    )
    return result.stdout, result.stderr, result.returncode


# ===========================================================================
# Library API: convert()
# ===========================================================================


class TestConvertBasic:
    """Basic edge parsing via convert()."""

    def test_simple_digraph(self):
        src = 'digraph G { A -> B [label="knows"]; }'
        verts, edges = convert(src)
        assert verts == {"A", "B"}
        assert edges == [("A", "B", "knows")]

    def test_simple_undirected(self):
        src = 'graph G { A -- B [label="friends"]; }'
        verts, edges = convert(src)
        assert verts == {"A", "B"}
        assert edges == [("A", "B", "friends")]

    def test_multiple_edges(self):
        src = """digraph G {
            A -> B [label="x"];
            B -> C [label="y"];
            A -> C [label="z"];
        }"""
        verts, edges = convert(src)
        assert verts == {"A", "B", "C"}
        assert len(edges) == 3
        assert ("A", "B", "x") in edges
        assert ("B", "C", "y") in edges
        assert ("A", "C", "z") in edges

    def test_self_loop(self):
        src = 'digraph G { A -> A [label="self"]; }'
        verts, edges = convert(src)
        assert verts == {"A"}
        assert edges == [("A", "A", "self")]


class TestConvertMissingLabel:
    """When label attribute is absent, default to the edge operator."""

    def test_directed_no_label(self):
        src = "digraph G { A -> B; }"
        verts, edges = convert(src)
        assert edges == [("A", "B", "->")]

    def test_undirected_no_label(self):
        src = "graph G { X -- Y; }"
        verts, edges = convert(src)
        assert edges == [("X", "Y", "--")]

    def test_no_attributes_no_semicolon(self):
        src = "digraph G {\n  A -> B\n}"
        verts, edges = convert(src)
        assert edges == [("A", "B", "->")]


class TestConvertAttributes:
    """Attribute parsing edge cases."""

    def test_multiple_attributes_label_present(self):
        src = 'digraph G { A -> B [label="x", color="red"]; }'
        verts, edges = convert(src)
        assert edges == [("A", "B", "x")]

    def test_label_with_spaces(self):
        src = 'digraph G { A -> B [label="has a relationship with"]; }'
        _, edges = convert(src)
        assert edges[0][2] == "has a relationship with"

    def test_attributes_without_label(self):
        src = 'digraph G { A -> B [color="blue", style="dashed"]; }'
        _, edges = convert(src)
        assert edges == [("A", "B", "->")]


class TestConvertQuotedNames:
    """Quoted node names."""

    def test_quoted_node_names(self):
        src = 'digraph G { "Node A" -> "Node B" [label="connects"]; }'
        verts, edges = convert(src)
        assert verts == {"Node A", "Node B"}
        assert edges == [("Node A", "Node B", "connects")]

    def test_mixed_quoted_unquoted(self):
        src = 'digraph G { Alice -> "Bob Smith" [label="knows"]; }'
        verts, edges = convert(src)
        assert "Alice" in verts
        assert "Bob Smith" in verts
        assert edges == [("Alice", "Bob Smith", "knows")]


class TestConvertEmptyAndTrivial:
    """Empty and trivial graphs."""

    def test_empty_digraph(self):
        src = "digraph G {}"
        verts, edges = convert(src)
        assert verts == set()
        assert edges == []

    def test_empty_graph(self):
        src = "graph G {}"
        verts, edges = convert(src)
        assert verts == set()
        assert edges == []

    def test_empty_string(self):
        verts, edges = convert("")
        assert verts == set()
        assert edges == []

    def test_only_whitespace(self):
        verts, edges = convert("   \n\n  \n  ")
        assert verts == set()
        assert edges == []


class TestConvertNodeDeclarations:
    """Node-only declarations (no edges) are ignored by convert()."""

    def test_node_declaration_ignored(self):
        src = """digraph G {
            A [shape=box];
            B [shape=circle];
        }"""
        verts, edges = convert(src)
        # Node declarations without edges are not captured
        assert verts == set()
        assert edges == []

    def test_nodes_plus_edges(self):
        src = """digraph G {
            A [shape=box];
            B [shape=circle];
            A -> B [label="link"];
        }"""
        verts, edges = convert(src)
        assert verts == {"A", "B"}
        assert edges == [("A", "B", "link")]


class TestConvertComments:
    """DOT comments should be skipped."""

    def test_line_comment(self):
        src = """digraph G {
            // This is a comment
            A -> B [label="x"];
        }"""
        _, edges = convert(src)
        assert edges == [("A", "B", "x")]

    def test_block_comment_single_line(self):
        src = """digraph G {
            /* block comment */
            A -> B [label="x"];
        }"""
        _, edges = convert(src)
        assert edges == [("A", "B", "x")]


class TestConvertStructural:
    """Structural DOT keywords are skipped."""

    def test_strict_keyword(self):
        src = """strict digraph G {
            A -> B [label="x"];
        }"""
        _, edges = convert(src)
        assert edges == [("A", "B", "x")]

    def test_subgraph(self):
        src = """digraph G {
            subgraph cluster_0 {
                A -> B [label="inner"];
            }
            C -> D [label="outer"];
        }"""
        verts, edges = convert(src)
        assert ("A", "B", "inner") in edges
        assert ("C", "D", "outer") in edges
        assert len(edges) == 2

    def test_node_and_edge_keywords(self):
        src = """digraph G {
            node [shape=box];
            edge [color=red];
            A -> B [label="x"];
        }"""
        _, edges = convert(src)
        assert edges == [("A", "B", "x")]


class TestConvertUnicode:
    """Unicode in node names and labels."""

    def test_unicode_label(self):
        src = 'digraph G { A -> B [label="日本語"]; }'
        _, edges = convert(src)
        assert edges == [("A", "B", "日本語")]

    def test_unicode_quoted_nodes(self):
        src = 'digraph G { "Ünîcödé" -> "Ñodé" [label="connects"]; }'
        verts, edges = convert(src)
        assert "Ünîcödé" in verts
        assert "Ñodé" in verts


class TestConvertExampleFile:
    """Test with the actual example file shipped in examples/."""

    def test_family_tree_dot(self):
        example = os.path.join(
            os.path.dirname(__file__), "..", "examples", "family-tree.dot"
        )
        if not os.path.exists(example):
            pytest.skip("Example file not found")
        with open(example) as f:
            src = f.read()
        verts, edges = convert(src)
        assert "George" in verts
        assert "Mary" in verts
        assert len(edges) == 9
        # Spot-check a specific edge
        assert ("George", "Mary", "married_to") in edges


# ===========================================================================
# Internal helper: _unquote
# ===========================================================================


class TestUnquote:
    def test_quoted(self):
        assert _unquote('"hello"') == "hello"

    def test_unquoted(self):
        assert _unquote("hello") == "hello"

    def test_empty_quoted(self):
        assert _unquote('""') == ""

    def test_single_quote_not_stripped(self):
        assert _unquote("'hello'") == "'hello'"


# ===========================================================================
# Library API: format_output()
# ===========================================================================


class TestFormatPlain:
    def test_basic(self):
        verts = {"A", "B"}
        edges = [("A", "B", "knows")]
        out = format_output(verts, edges, "plain")
        lines = out.split("\n")
        assert lines[0] == "2 1"
        assert lines[1] == "A B knows"

    def test_empty(self):
        out = format_output(set(), [], "plain")
        assert out == "0 0"

    def test_multiple_edges(self):
        verts = {"A", "B", "C"}
        edges = [("A", "B", "x"), ("B", "C", "y")]
        out = format_output(verts, edges, "plain")
        lines = out.split("\n")
        assert lines[0] == "3 2"
        assert len(lines) == 3


class TestFormatCSV:
    def test_basic(self):
        verts = {"A", "B"}
        edges = [("A", "B", "knows")]
        out = format_output(verts, edges, "csv")
        lines = out.split("\n")
        assert lines[0] == "from,to,label"
        assert lines[1] == "A,B,knows"

    def test_empty(self):
        out = format_output(set(), [], "csv")
        assert out == "from,to,label"

    def test_values_with_commas(self):
        verts = {"A, B", "C"}
        edges = [("A, B", "C", "label,with,commas")]
        out = format_output(verts, edges, "csv")
        lines = out.split("\n")
        assert lines[0] == "from,to,label"
        # CSV should properly quote fields containing commas
        import csv
        import io
        reader = csv.reader(io.StringIO(out))
        rows = list(reader)
        assert rows[1] == ["A, B", "C", "label,with,commas"]


class TestFormatJSONL:
    def test_basic(self):
        verts = {"A", "B"}
        edges = [("A", "B", "knows")]
        out = format_output(verts, edges, "jsonl")
        obj = json.loads(out)
        assert obj == {"from": "A", "to": "B", "label": "knows"}

    def test_empty(self):
        out = format_output(set(), [], "jsonl")
        assert out == ""

    def test_multiple(self):
        edges = [("A", "B", "x"), ("B", "C", "y")]
        out = format_output({"A", "B", "C"}, edges, "jsonl")
        lines = out.strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert set(obj.keys()) == {"from", "to", "label"}


class TestFormatUnknown:
    def test_raises_on_unknown_format(self):
        with pytest.raises(ValueError, match="Unknown format"):
            format_output(set(), [], "xml")


# ===========================================================================
# CLI invocation via subprocess
# ===========================================================================


class TestCLI:
    """Test the CLI entry point via subprocess."""

    def test_stdin_plain(self):
        dot = 'digraph G { A -> B [label="x"]; }'
        stdout, stderr, rc = run_cli(stdin_data=dot)
        assert rc == 0
        lines = stdout.strip().split("\n")
        assert lines[0] == "2 1"
        assert lines[1] == "A B x"

    def test_stdin_csv(self):
        dot = 'digraph G { A -> B [label="x"]; }'
        stdout, _, rc = run_cli("--csv", stdin_data=dot)
        assert rc == 0
        lines = stdout.strip().split("\n")
        assert lines[0] == "from,to,label"
        assert lines[1] == "A,B,x"

    def test_stdin_jsonl(self):
        dot = 'digraph G { A -> B [label="x"]; }'
        stdout, _, rc = run_cli("--jsonl", stdin_data=dot)
        assert rc == 0
        obj = json.loads(stdout.strip())
        assert obj == {"from": "A", "to": "B", "label": "x"}

    def test_file_argument(self):
        dot = 'digraph G { X -> Y [label="link"]; }'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dot", delete=False) as f:
            f.write(dot)
            f.flush()
            try:
                stdout, _, rc = run_cli(f.name)
                assert rc == 0
                assert "X Y link" in stdout
            finally:
                os.unlink(f.name)

    def test_empty_graph_cli(self):
        dot = "digraph G {}"
        stdout, _, rc = run_cli(stdin_data=dot)
        assert rc == 0
        assert stdout.strip() == "0 0"

    def test_example_file(self):
        example = os.path.join(
            os.path.dirname(__file__), "..", "examples", "family-tree.dot"
        )
        if not os.path.exists(example):
            pytest.skip("Example file not found")
        stdout, _, rc = run_cli(example)
        assert rc == 0
        lines = stdout.strip().split("\n")
        # First line: vertex_count edge_count
        parts = lines[0].split()
        assert int(parts[1]) == 9  # 9 edges in family-tree.dot


# ===========================================================================
# Validation against native graphviz (if available)
# ===========================================================================


@pytest.mark.skipif(not HAS_GRAPHVIZ, reason="graphviz 'dot' not installed")
class TestGraphvizNativeComparison:
    """Compare converter output against graphviz native JSON output."""

    def _extract_edges_from_dot_json(self, dot_source):
        """Use `dot -Tjson` to parse DOT and extract edges."""
        result = subprocess.run(
            ["dot", "-Tjson"],
            input=dot_source,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"dot -Tjson failed: {result.stderr}"
        data = json.loads(result.stdout)
        edges = []
        for edge in data.get("edges", []):
            tail = data["objects"][edge["tail"]]["name"]
            head = data["objects"][edge["head"]]["name"]
            label = edge.get("label", "")
            edges.append((tail, head, label))
        return edges

    def test_simple_digraph_matches(self):
        dot = """digraph G {
            A -> B [label="knows"];
            B -> C [label="likes"];
        }"""
        native_edges = self._extract_edges_from_dot_json(dot)
        _, our_edges = convert(dot)
        # Both should find the same edges (same set of tuples)
        assert set(our_edges) == set(native_edges)

    def test_family_tree_matches(self):
        example = os.path.join(
            os.path.dirname(__file__), "..", "examples", "family-tree.dot"
        )
        if not os.path.exists(example):
            pytest.skip("Example file not found")
        with open(example) as f:
            dot = f.read()
        native_edges = self._extract_edges_from_dot_json(dot)
        _, our_edges = convert(dot)
        assert set(our_edges) == set(native_edges)

    def test_unlabeled_edges(self):
        dot = "digraph G { A -> B; C -> D; }"
        native_edges = self._extract_edges_from_dot_json(dot)
        _, our_edges = convert(dot)
        # Native gives empty label, ours gives "->"
        # Just verify same edge pairs exist
        native_pairs = {(e[0], e[1]) for e in native_edges}
        our_pairs = {(e[0], e[1]) for e in our_edges}
        assert our_pairs == native_pairs


# ===========================================================================
# End-to-end: convert() + format_output() round-trip
# ===========================================================================


class TestRoundTrip:
    """Test convert → format_output pipeline."""

    def test_plain_round_trip(self):
        dot = """digraph G {
            Alice -> Bob [label="knows"];
            Bob -> Charlie [label="likes"];
        }"""
        verts, edges = convert(dot)
        out = format_output(verts, edges, "plain")
        lines = out.split("\n")
        assert lines[0] == "3 2"

    def test_csv_round_trip_parseable(self):
        dot = 'digraph G { A -> B [label="test"]; }'
        verts, edges = convert(dot)
        out = format_output(verts, edges, "csv")
        import csv
        import io
        reader = csv.DictReader(io.StringIO(out))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["from"] == "A"
        assert rows[0]["to"] == "B"
        assert rows[0]["label"] == "test"

    def test_jsonl_round_trip_parseable(self):
        dot = """digraph G {
            X -> Y [label="a"];
            Y -> Z [label="b"];
        }"""
        verts, edges = convert(dot)
        out = format_output(verts, edges, "jsonl")
        objs = [json.loads(line) for line in out.strip().split("\n")]
        assert len(objs) == 2
        labels = {o["label"] for o in objs}
        assert labels == {"a", "b"}
