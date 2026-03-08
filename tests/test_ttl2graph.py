"""Comprehensive tests for ttl2graph converter.

Tests the convert() and format_output() library API, covering edge cases
like empty files, blank nodes, literals, semicolons/commas shorthand,
Unicode, comments, and .n3 format. Also validates against direct rdflib
parsing.
"""

import io
import json
import sys
import textwrap
from pathlib import Path

import pytest
from rdflib import Graph as RDFGraph

# Add converter to path so we can import it
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "converters" / "ttl2graph"))

from ttl2graph import _local_name, convert, format_output


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ttl_io(text: str) -> io.StringIO:
    """Wrap a Turtle string in a StringIO for convert()."""
    return io.StringIO(textwrap.dedent(text))


# ---------------------------------------------------------------------------
# _local_name unit tests
# ---------------------------------------------------------------------------

class TestLocalName:
    def test_fragment_identifier(self):
        assert _local_name("http://example.org/people#Alice") == "Alice"

    def test_path_segment(self):
        assert _local_name("http://example.org/people/Alice") == "Alice"

    def test_fragment_preferred_over_path(self):
        """Fragment after # takes precedence even when / is also present."""
        assert _local_name("http://example.org/ns#knows") == "knows"

    def test_no_fragment_no_slash(self):
        assert _local_name("justAName") == "justAName"

    def test_long_uri_no_local_name(self):
        """URI ending in / yields empty string as local name."""
        assert _local_name("http://example.org/") == ""

    def test_unicode_in_uri(self):
        assert _local_name("http://example.org/人物#アリス") == "アリス"


# ---------------------------------------------------------------------------
# convert() — basic cases
# ---------------------------------------------------------------------------

class TestConvertBasic:
    def test_empty_file(self):
        """Empty Turtle input yields no vertices and no edges."""
        vertices, edges = convert(_ttl_io(""))
        assert vertices == set()
        assert edges == []

    def test_single_triple(self):
        ttl = """\
        @prefix ex: <http://example.org/> .
        ex:Alice ex:knows ex:Bob .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert vertices == {"Alice", "Bob"}
        assert edges == [("Alice", "Bob", "knows")]

    def test_multiple_triples(self):
        ttl = """\
        @prefix ex: <http://example.org/> .
        ex:Alice ex:knows ex:Bob .
        ex:Bob ex:likes ex:Charlie .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert vertices == {"Alice", "Bob", "Charlie"}
        assert len(edges) == 2
        assert ("Alice", "Bob", "knows") in edges
        assert ("Bob", "Charlie", "likes") in edges

    def test_multiple_triples_same_predicate(self):
        ttl = """\
        @prefix ex: <http://example.org/> .
        ex:Alice ex:knows ex:Bob .
        ex:Charlie ex:knows ex:Dave .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert len(edges) == 2
        assert ("Alice", "Bob", "knows") in edges
        assert ("Charlie", "Dave", "knows") in edges


# ---------------------------------------------------------------------------
# convert() — Turtle syntax features
# ---------------------------------------------------------------------------

class TestConvertSyntax:
    def test_multiple_prefixes(self):
        ttl = """\
        @prefix foaf: <http://xmlns.com/foaf/0.1/> .
        @prefix ex: <http://example.org/> .
        ex:Alice foaf:knows ex:Bob .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert edges == [("Alice", "Bob", "knows")]

    def test_base_uri(self):
        ttl = """\
        @base <http://example.org/> .
        <Alice> <knows> <Bob> .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert vertices == {"Alice", "Bob"}
        assert edges == [("Alice", "Bob", "knows")]

    def test_semicolon_shorthand(self):
        """Same subject, multiple predicates via `;`."""
        ttl = """\
        @prefix ex: <http://example.org/> .
        ex:A ex:knows ex:B ; ex:likes ex:C .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert {"A", "B", "C"} <= vertices
        assert len(edges) == 2
        assert ("A", "B", "knows") in edges
        assert ("A", "C", "likes") in edges

    def test_comma_shorthand(self):
        """Same subject+predicate, multiple objects via `,`."""
        ttl = """\
        @prefix ex: <http://example.org/> .
        ex:A ex:knows ex:B, ex:C .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert {"A", "B", "C"} <= vertices
        assert len(edges) == 2
        assert ("A", "B", "knows") in edges
        assert ("A", "C", "knows") in edges

    def test_comments_are_ignored(self):
        ttl = """\
        @prefix ex: <http://example.org/> .
        # This is a comment
        ex:Alice ex:knows ex:Bob .
        # Another comment
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert edges == [("Alice", "Bob", "knows")]

    def test_fragment_identifiers(self):
        ttl = """\
        <http://example.org/people#Alice> <http://example.org/rel#knows> <http://example.org/people#Bob> .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert vertices == {"Alice", "Bob"}
        assert edges == [("Alice", "Bob", "knows")]


# ---------------------------------------------------------------------------
# convert() — special node types
# ---------------------------------------------------------------------------

class TestConvertSpecialNodes:
    def test_blank_nodes(self):
        """Blank nodes should be included as vertices."""
        ttl = """\
        @prefix ex: <http://example.org/> .
        _:b1 ex:knows ex:Bob .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert "Bob" in vertices
        assert len(edges) == 1
        # blank node local name varies, just check edge structure
        frm, to, label = edges[0]
        assert to == "Bob"
        assert label == "knows"

    def test_literal_objects(self):
        """Literal objects (strings) should be included as vertices."""
        ttl = """\
        @prefix ex: <http://example.org/> .
        ex:Alice ex:name "Alice Smith" .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert "Alice" in vertices
        assert "Alice Smith" in vertices
        assert len(edges) == 1
        assert edges[0] == ("Alice", "Alice Smith", "name")

    def test_typed_literal(self):
        """Typed literals are converted to their string form."""
        ttl = """\
        @prefix ex: <http://example.org/> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        ex:Alice ex:age "30"^^xsd:integer .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert "Alice" in vertices
        assert len(edges) == 1
        # The literal "30" should appear (rdflib gives "30" as str)
        frm, to, label = edges[0]
        assert frm == "Alice"
        assert label == "age"

    def test_unicode_in_uris(self):
        ttl = """\
        @prefix ex: <http://example.org/> .
        ex:Ünïcödé ex:связь ex:日本語 .
        """
        vertices, edges = convert(_ttl_io(ttl))
        assert "Ünïcödé" in vertices
        assert "日本語" in vertices
        assert edges[0][2] == "связь"


# ---------------------------------------------------------------------------
# convert() — file path input and .n3 format
# ---------------------------------------------------------------------------

class TestConvertFileInput:
    def test_file_path_input(self, tmp_path):
        """convert() accepts a file path string."""
        ttl_file = tmp_path / "test.ttl"
        ttl_file.write_text(textwrap.dedent("""\
            @prefix ex: <http://example.org/> .
            ex:A ex:rel ex:B .
        """))
        vertices, edges = convert(str(ttl_file))
        assert vertices == {"A", "B"}
        assert edges == [("A", "B", "rel")]

    def test_n3_format(self, tmp_path):
        """N3 format (.n3) should be parsed correctly via file path."""
        n3_file = tmp_path / "test.n3"
        n3_file.write_text(textwrap.dedent("""\
            @prefix ex: <http://example.org/> .
            ex:Alice ex:knows ex:Bob .
            ex:Bob ex:likes ex:Charlie .
        """))
        vertices, edges = convert(str(n3_file))
        assert len(edges) == 2
        assert ("Alice", "Bob", "knows") in edges
        assert ("Bob", "Charlie", "likes") in edges

    def test_example_file(self):
        """Test the bundled example file."""
        example = Path(__file__).resolve().parent.parent / "examples" / "web-of-knowledge.ttl"
        if not example.exists():
            pytest.skip("Example file not found")
        vertices, edges = convert(str(example))
        assert len(vertices) > 0
        assert len(edges) > 0
        # Known content from the example
        assert "Python" in vertices
        assert ("C", "Python", "influences") in edges


# ---------------------------------------------------------------------------
# Deterministic ordering
# ---------------------------------------------------------------------------

class TestOrdering:
    def test_edges_are_sorted(self):
        ttl = """\
        @prefix ex: <http://example.org/> .
        ex:Z ex:rel ex:Y .
        ex:A ex:rel ex:B .
        ex:M ex:rel ex:N .
        """
        _, edges = convert(_ttl_io(ttl))
        assert edges == sorted(edges)

    def test_repeated_convert_same_result(self):
        """Multiple calls produce identical output (deterministic)."""
        ttl = """\
        @prefix ex: <http://example.org/> .
        ex:C ex:r1 ex:D .
        ex:A ex:r2 ex:B .
        ex:E ex:r3 ex:F .
        """
        results = [convert(_ttl_io(ttl)) for _ in range(5)]
        for v, e in results[1:]:
            assert v == results[0][0]
            assert e == results[0][1]


# ---------------------------------------------------------------------------
# format_output() tests
# ---------------------------------------------------------------------------

class TestFormatOutput:
    @pytest.fixture()
    def sample_data(self):
        return ({"Alice", "Bob", "Charlie"}, [("Alice", "Bob", "knows"), ("Bob", "Charlie", "likes")])

    def test_plain_format(self, sample_data):
        vertices, edges = sample_data
        out = format_output(vertices, edges, "plain")
        lines = out.strip().split("\n")
        assert lines[0] == "3 2"
        assert lines[1] == "Alice Bob knows"
        assert lines[2] == "Bob Charlie likes"

    def test_csv_format(self, sample_data):
        vertices, edges = sample_data
        out = format_output(vertices, edges, "csv")
        lines = out.strip().split("\n")
        assert lines[0] == "from,to,label"
        assert lines[1] == "Alice,Bob,knows"
        assert lines[2] == "Bob,Charlie,likes"

    def test_jsonl_format(self, sample_data):
        vertices, edges = sample_data
        out = format_output(vertices, edges, "jsonl")
        lines = out.strip().split("\n")
        assert len(lines) == 2
        obj1 = json.loads(lines[0])
        assert obj1 == {"from": "Alice", "to": "Bob", "label": "knows"}
        obj2 = json.loads(lines[1])
        assert obj2 == {"from": "Bob", "to": "Charlie", "label": "likes"}

    def test_plain_empty(self):
        out = format_output(set(), [], "plain")
        assert out.strip() == "0 0"

    def test_csv_empty(self):
        out = format_output(set(), [], "csv")
        assert out.strip() == "from,to,label"

    def test_jsonl_empty(self):
        out = format_output(set(), [], "jsonl")
        assert out.strip() == ""

    def test_output_ends_with_newline(self, sample_data):
        for fmt in ("plain", "csv", "jsonl"):
            out = format_output(*sample_data, fmt)
            assert out.endswith("\n")


# ---------------------------------------------------------------------------
# Validation against direct rdflib parsing
# ---------------------------------------------------------------------------

class TestValidateAgainstRdflib:
    """Parse the same TTL with rdflib directly and compare to convert()."""

    TTL_COMPLEX = textwrap.dedent("""\
        @prefix ex: <http://example.org/> .
        @prefix foaf: <http://xmlns.com/foaf/0.1/> .

        ex:Alice foaf:knows ex:Bob ;
                 foaf:name "Alice" ;
                 ex:age "30" .

        ex:Bob foaf:knows ex:Charlie, ex:Dave .
        ex:Charlie ex:likes ex:Eve .
    """)

    def _rdflib_parse(self, ttl_text):
        """Parse with rdflib directly and extract local-name triples."""
        g = RDFGraph()
        g.parse(io.StringIO(ttl_text), format="turtle")
        edges = []
        vertices = set()
        for s, p, o in g:
            sn = _local_name(s)
            pn = _local_name(p)
            on = _local_name(o)
            vertices.add(sn)
            vertices.add(on)
            edges.append((sn, on, pn))
        edges.sort()
        return vertices, edges

    def test_same_triple_count(self):
        v1, e1 = convert(_ttl_io(self.TTL_COMPLEX))
        v2, e2 = self._rdflib_parse(self.TTL_COMPLEX)
        assert len(e1) == len(e2)

    def test_same_vertices(self):
        v1, e1 = convert(_ttl_io(self.TTL_COMPLEX))
        v2, e2 = self._rdflib_parse(self.TTL_COMPLEX)
        assert v1 == v2

    def test_same_edges(self):
        v1, e1 = convert(_ttl_io(self.TTL_COMPLEX))
        v2, e2 = self._rdflib_parse(self.TTL_COMPLEX)
        assert e1 == e2

    def test_example_file_matches_rdflib(self):
        """Validate the bundled example against direct rdflib parsing."""
        example = Path(__file__).resolve().parent.parent / "examples" / "web-of-knowledge.ttl"
        if not example.exists():
            pytest.skip("Example file not found")
        ttl_text = example.read_text()
        v1, e1 = convert(str(example))
        v2, e2 = self._rdflib_parse(ttl_text)
        assert v1 == v2
        assert e1 == e2

    def test_semicolon_comma_matches_rdflib(self):
        ttl = textwrap.dedent("""\
            @prefix ex: <http://example.org/> .
            ex:A ex:r1 ex:B, ex:C ;
                 ex:r2 ex:D .
            ex:E ex:r3 ex:F .
        """)
        v1, e1 = convert(_ttl_io(ttl))
        v2, e2 = self._rdflib_parse(ttl)
        assert v1 == v2
        assert e1 == e2
