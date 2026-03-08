"""Tests for graph2ttl converter."""

import io
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "..", "scripts", "converters", "graph2ttl"))

from graph2ttl import convert, _sanitize_local_name

FIXTURE_DIR = os.path.join(os.path.dirname(__file__),
                           "..", "scripts", "converters", "graph2ttl", "input")


# ---------------------------------------------------------------------------
# TestConvert -- basic library API tests
# ---------------------------------------------------------------------------


class TestConvert:
    """Basic conversion tests using the library API."""

    def test_simple_graph(self):
        data = {
            "nodes": [{"id": "Alice"}, {"id": "Bob"}],
            "edges": [{"from": "Alice", "to": "Bob", "label": "knows"}],
        }
        ttl = convert(data)
        assert "ex:Alice" in ttl
        assert "ex:knows" in ttl
        assert "ex:Bob" in ttl
        assert "@prefix ex:" in ttl

    def test_multiple_edges(self):
        data = {
            "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
            "edges": [
                {"from": "A", "to": "B", "label": "x"},
                {"from": "B", "to": "C", "label": "y"},
            ],
        }
        ttl = convert(data)
        assert "ex:A ex:x ex:B" in ttl
        assert "ex:B ex:y ex:C" in ttl

    def test_default_predicate_for_unlabeled_edge(self):
        data = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [{"from": "A", "to": "B"}],
        }
        ttl = convert(data)
        assert "ex:relatedTo" in ttl

    def test_empty_label_uses_default_predicate(self):
        data = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [{"from": "A", "to": "B", "label": ""}],
        }
        ttl = convert(data)
        assert "ex:relatedTo" in ttl

    def test_styling_extras_dropped(self):
        with open(os.path.join(FIXTURE_DIR, "styled.json")) as f:
            data = json.load(f)
        ttl = convert(data)
        # Styling properties should not appear in output
        assert "#4CAF50" not in ttl
        assert "database" not in ttl
        assert "dashes" not in ttl
        # But edge triples should be present
        assert "ex:queries" in ttl
        assert "ex:reads" in ttl

    def test_deterministic_output(self):
        """Multiple calls with the same input produce identical output."""
        data = {
            "nodes": [{"id": "Z"}, {"id": "A"}, {"id": "M"}],
            "edges": [
                {"from": "Z", "to": "A", "label": "p"},
                {"from": "A", "to": "M", "label": "q"},
                {"from": "M", "to": "Z", "label": "r"},
            ],
        }
        results = [convert(data) for _ in range(5)]
        assert all(r == results[0] for r in results)


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases: empty graph, unicode, spaces, single edge."""

    def test_empty_graph(self):
        ttl = convert({"nodes": [], "edges": []})
        assert "@prefix ex: <http://example.org/>" in ttl
        # Should be basically just the prefix, no triples
        lines = [l.strip() for l in ttl.strip().splitlines() if l.strip()]
        assert len(lines) == 1  # only the prefix line

    def test_unicode_node_ids(self):
        with open(os.path.join(FIXTURE_DIR, "unicode.json")) as f:
            data = json.load(f)
        ttl = convert(data)
        assert "München" in ttl
        assert "Tokyo" in ttl
        assert "São_Paulo" in ttl

    def test_spaces_in_node_ids(self):
        data = {
            "nodes": [{"id": "New York"}, {"id": "Los Angeles"}],
            "edges": [{"from": "New York", "to": "Los Angeles", "label": "route"}],
        }
        ttl = convert(data)
        assert "New_York" in ttl
        assert "Los_Angeles" in ttl
        # No raw spaces in URI local names
        assert "ex:New York" not in ttl

    def test_single_edge(self):
        data = {
            "nodes": [{"id": "X"}, {"id": "Y"}],
            "edges": [{"from": "X", "to": "Y", "label": "connects"}],
        }
        ttl = convert(data)
        assert "ex:X ex:connects ex:Y" in ttl

    def test_isolated_nodes_excluded(self):
        """Nodes without edges should not appear in the output."""
        data = {
            "nodes": [{"id": "A"}, {"id": "B"}, {"id": "Lonely"}],
            "edges": [{"from": "A", "to": "B", "label": "link"}],
        }
        ttl = convert(data)
        assert "Lonely" not in ttl

    def test_edge_missing_from_or_to_skipped(self):
        data = {
            "nodes": [],
            "edges": [
                {"from": "", "to": "B", "label": "bad"},
                {"from": "A", "to": "", "label": "bad"},
                {"from": "A", "to": "B", "label": "good"},
            ],
        }
        ttl = convert(data)
        assert "ex:A ex:good ex:B" in ttl
        # Only one triple line expected (excluding the prefix line)
        triple_lines = [l for l in ttl.strip().splitlines()
                        if l.strip().endswith(" .") and not l.startswith("@")]
        assert len(triple_lines) == 1

    def test_duplicate_edges_deduplicated(self):
        """RDF graphs are sets; duplicate triples should appear once."""
        data = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [
                {"from": "A", "to": "B", "label": "knows"},
                {"from": "A", "to": "B", "label": "knows"},
            ],
        }
        ttl = convert(data)
        # Should only have one triple
        assert ttl.count("ex:A ex:knows ex:B") == 1


# ---------------------------------------------------------------------------
# TestCrossValidation -- round-trip with ttl2graph
# ---------------------------------------------------------------------------


class TestCrossValidation:
    """Round-trip: graph2ttl output -> ttl2graph.convert() -> verify edges."""

    @staticmethod
    def _round_trip(graph_data):
        from scripts.converters.ttl2graph.ttl2graph import convert as ttl2graph_convert
        ttl = convert(graph_data)
        vertices, edges = ttl2graph_convert(io.StringIO(ttl))
        return vertices, edges

    def test_simple_round_trip(self):
        data = {
            "nodes": [{"id": "Alice"}, {"id": "Bob"}, {"id": "Charlie"}],
            "edges": [
                {"from": "Alice", "to": "Bob", "label": "knows"},
                {"from": "Bob", "to": "Charlie", "label": "likes"},
            ],
        }
        vertices, edges = self._round_trip(data)
        assert sorted(edges) == [
            ("Alice", "Bob", "knows"),
            ("Bob", "Charlie", "likes"),
        ]
        assert vertices == {"Alice", "Bob", "Charlie"}

    def test_round_trip_with_spaces(self):
        data = {
            "nodes": [{"id": "New York"}, {"id": "Boston"}],
            "edges": [{"from": "New York", "to": "Boston", "label": "train"}],
        }
        vertices, edges = self._round_trip(data)
        # Spaces become underscores in the URI local name
        assert ("New_York", "Boston", "train") in edges

    def test_round_trip_empty(self):
        data = {"nodes": [], "edges": []}
        vertices, edges = self._round_trip(data)
        assert len(edges) == 0
        assert len(vertices) == 0

    def test_round_trip_styled(self):
        """Styled graph loses extras but keeps edge structure."""
        with open(os.path.join(FIXTURE_DIR, "styled.json")) as f:
            data = json.load(f)
        vertices, edges = self._round_trip(data)
        edge_tuples = {(e[0], e[1], e[2]) for e in edges}
        assert ("Server", "DB", "queries") in edge_tuples
        assert ("Server", "Cache", "reads") in edge_tuples

    def test_round_trip_fixture_simple(self):
        with open(os.path.join(FIXTURE_DIR, "simple.json")) as f:
            data = json.load(f)
        vertices, edges = self._round_trip(data)
        assert sorted(edges) == [
            ("Alice", "Bob", "knows"),
            ("Bob", "Charlie", "likes"),
        ]


# ---------------------------------------------------------------------------
# TestNativeValidation -- parse output with rdflib to verify valid TTL
# ---------------------------------------------------------------------------


class TestNativeValidation:
    """Verify that the output is valid Turtle parseable by rdflib."""

    def _parse_ttl(self, graph_data):
        from rdflib import Graph as RDFGraph
        ttl = convert(graph_data)
        g = RDFGraph()
        g.parse(data=ttl, format="turtle")
        return g

    def test_simple_valid_ttl(self):
        data = {
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [{"from": "A", "to": "B", "label": "rel"}],
        }
        g = self._parse_ttl(data)
        assert len(g) == 1

    def test_empty_valid_ttl(self):
        g = self._parse_ttl({"nodes": [], "edges": []})
        assert len(g) == 0

    def test_unicode_valid_ttl(self):
        with open(os.path.join(FIXTURE_DIR, "unicode.json")) as f:
            data = json.load(f)
        g = self._parse_ttl(data)
        assert len(g) == 3  # 3 edges in unicode fixture

    def test_all_fixtures_valid(self):
        """Every fixture file should produce valid TTL."""
        from rdflib import Graph as RDFGraph
        for fname in os.listdir(FIXTURE_DIR):
            if not fname.endswith(".json"):
                continue
            with open(os.path.join(FIXTURE_DIR, fname)) as f:
                data = json.load(f)
            ttl = convert(data)
            g = RDFGraph()
            g.parse(data=ttl, format="turtle")  # should not raise


# ---------------------------------------------------------------------------
# TestCLI -- subprocess invocation
# ---------------------------------------------------------------------------


class TestCLI:
    """Test the CLI entry point via subprocess."""

    SCRIPT = os.path.join(os.path.dirname(__file__),
                          "..", "scripts", "converters", "graph2ttl",
                          "graph2ttl.py")

    def test_file_argument(self):
        fixture = os.path.join(FIXTURE_DIR, "simple.json")
        result = subprocess.run(
            [sys.executable, self.SCRIPT, fixture],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "ex:Alice" in result.stdout
        assert "ex:knows" in result.stdout

    def test_stdin_input(self):
        data = json.dumps({
            "nodes": [{"id": "P"}, {"id": "Q"}],
            "edges": [{"from": "P", "to": "Q", "label": "test"}],
        })
        result = subprocess.run(
            [sys.executable, self.SCRIPT],
            input=data, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "ex:P ex:test ex:Q" in result.stdout

    def test_empty_graph_cli(self):
        data = json.dumps({"nodes": [], "edges": []})
        result = subprocess.run(
            [sys.executable, self.SCRIPT],
            input=data, capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        assert "@prefix ex:" in result.stdout
