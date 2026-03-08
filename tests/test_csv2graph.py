"""Comprehensive tests for csv2graph converter.

Tests the convert() library API, format_output(), and CLI invocation.
"""

import csv
import io
import json
import os
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.converters.csv2graph.csv2graph import convert, format_output

FIXTURES = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "converters", "csv2graph", "input"
)
CONVERTER = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "converters", "csv2graph", "csv2graph.py"
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _sio(text):
    """Wrap text in a StringIO for convert()."""
    return io.StringIO(text)


# ===========================================================================
# convert() -- library API tests
# ===========================================================================


class TestConvertBasic:
    """Basic convert() functionality."""

    def test_sample_file(self):
        vertices, edges = convert(os.path.join(FIXTURES, "sample.csv"))
        assert vertices == {"Alice", "Bob", "Charlie"}
        assert edges == [
            ("Alice", "Bob", "knows"),
            ("Bob", "Charlie", "likes"),
            ("Charlie", "Alice", "helps"),
        ]

    def test_social_network_file(self):
        path = os.path.join(os.path.dirname(__file__), "..", "examples", "social-network.csv")
        vertices, edges = convert(path)
        assert len(vertices) == 6  # Alice, Bob, Charlie, Diana, Eve, Frank
        assert len(edges) == 8

    def test_single_edge(self):
        vertices, edges = convert(_sio("h1,h2,h3\nA,B,rel\n"))
        assert vertices == {"A", "B"}
        assert edges == [("A", "B", "rel")]

    def test_stringio_input(self):
        data = "source,target,rel\nX,Y,connects\nY,Z,links\n"
        vertices, edges = convert(_sio(data))
        assert vertices == {"X", "Y", "Z"}
        assert len(edges) == 2


class TestConvertEdgeCases:
    """Edge cases for convert()."""

    def test_empty_csv_header_only(self):
        vertices, edges = convert(os.path.join(FIXTURES, "header_only.csv"))
        assert vertices == set()
        assert edges == []

    def test_extra_columns_ignored(self):
        vertices, edges = convert(os.path.join(FIXTURES, "extra_columns.csv"))
        assert edges == [("Alice", "Bob", "knows"), ("Charlie", "Dave", "likes")]
        # Extra columns (weight, color) should not appear
        for frm, to, label in edges:
            assert "5" not in (frm, to, label)
            assert "red" not in (frm, to, label)

    def test_two_columns_skipped(self):
        """Rows with fewer than 3 columns should be skipped."""
        vertices, edges = convert(os.path.join(FIXTURES, "two_columns.csv"))
        assert vertices == set()
        assert edges == []

    def test_two_columns_inline(self):
        data = "a,b,c\nonly_two,columns\nA,B,C\n"
        vertices, edges = convert(_sio(data))
        assert edges == [("A", "B", "C")]
        assert "only_two" not in vertices

    def test_quoted_fields_with_commas(self):
        vertices, edges = convert(os.path.join(FIXTURES, "quoted_commas.csv"))
        assert ("New York", "London", "flies_to") in edges
        assert "New York" in vertices

    def test_quoted_fields_with_spaces(self):
        vertices, edges = convert(os.path.join(FIXTURES, "quoted_spaces.csv"))
        assert ("Alice Smith", "Bob Jones", "knows") in edges

    def test_unicode_values(self):
        vertices, edges = convert(os.path.join(FIXTURES, "unicode.csv"))
        assert "München" in vertices
        assert "Tokyo" in vertices
        assert ("München", "Tokyo", "connects") in edges

    def test_whitespace_only_values(self):
        data = 'a,b,c\n" "," "," "\n'
        vertices, edges = convert(_sio(data))
        assert len(edges) == 1
        assert edges[0] == (" ", " ", " ")

    def test_crlf_line_endings(self):
        data = "a,b,c\r\nAlice,Bob,knows\r\nBob,Carol,likes\r\n"
        vertices, edges = convert(_sio(data))
        assert len(edges) == 2
        assert vertices == {"Alice", "Bob", "Carol"}

    def test_duplicate_edges(self):
        vertices, edges = convert(os.path.join(FIXTURES, "duplicates.csv"))
        # Duplicates should be preserved (not deduped)
        assert len(edges) == 3
        assert edges[0] == edges[1] == ("Alice", "Bob", "knows")

    def test_large_row_count(self):
        lines = ["src,tgt,rel"]
        for i in range(150):
            lines.append(f"node{i},node{i+1},edge{i}")
        data = "\n".join(lines) + "\n"
        vertices, edges = convert(_sio(data))
        assert len(edges) == 150
        # 151 unique nodes: node0..node150
        assert len(vertices) == 151

    def test_mixed_short_and_long_rows(self):
        data = "a,b,c\nA,B\nC,D,E\nF\nG,H,I,J,K\n"
        vertices, edges = convert(_sio(data))
        assert edges == [("C", "D", "E"), ("G", "H", "I")]


# ===========================================================================
# Validation against native csv.reader
# ===========================================================================


class TestValidateAgainstNativeCSV:
    """Parse the same CSV with Python csv.reader and compare to convert()."""

    @pytest.mark.parametrize("fixture", [
        "sample.csv", "quoted_commas.csv", "quoted_spaces.csv",
        "unicode.csv", "extra_columns.csv", "duplicates.csv",
    ])
    def test_native_csv_parity(self, fixture):
        path = os.path.join(FIXTURES, fixture)

        # Parse with native csv.reader
        with open(path, newline="") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            expected_edges = []
            expected_vertices = set()
            for row in reader:
                if len(row) < 3:
                    continue
                frm, to, label = row[0], row[1], row[2]
                expected_vertices.update((frm, to))
                expected_edges.append((frm, to, label))

        # Parse with convert()
        vertices, edges = convert(path)

        assert vertices == expected_vertices
        assert edges == expected_edges


# ===========================================================================
# format_output() tests
# ===========================================================================


class TestFormatOutputPlain:
    """Plain text format."""

    def test_basic(self):
        vertices = {"A", "B", "C"}
        edges = [("A", "B", "knows"), ("B", "C", "likes")]
        out = format_output(vertices, edges, fmt="plain")
        lines = out.split("\n")
        assert lines[0] == "3 2"  # 3 vertices, 2 edges
        assert lines[1] == "A B knows"
        assert lines[2] == "B C likes"

    def test_empty_graph(self):
        out = format_output(set(), [], fmt="plain")
        assert out == "0 0"

    def test_single_edge(self):
        out = format_output({"X", "Y"}, [("X", "Y", "rel")], fmt="plain")
        lines = out.split("\n")
        assert lines[0] == "2 1"
        assert lines[1] == "X Y rel"


class TestFormatOutputCSV:
    """CSV output format."""

    def test_header_present(self):
        out = format_output({"A", "B"}, [("A", "B", "r")], fmt="csv")
        lines = out.split("\n")
        assert lines[0] == "from,to,label"

    def test_proper_quoting(self):
        edges = [("New York", "London", "flies_to")]
        out = format_output({"New York", "London"}, edges, fmt="csv")
        # csv.writer should quote fields with spaces
        reader = csv.reader(io.StringIO(out))
        rows = list(reader)
        assert rows[0] == ["from", "to", "label"]
        assert rows[1] == ["New York", "London", "flies_to"]

    def test_empty_csv(self):
        out = format_output(set(), [], fmt="csv")
        assert out == "from,to,label"

    def test_csv_roundtrip(self):
        """CSV output should be parseable back through convert()."""
        original_edges = [("A", "B", "knows"), ("C", "D", "likes")]
        original_verts = {"A", "B", "C", "D"}
        csv_out = format_output(original_verts, original_edges, fmt="csv")
        # Feed CSV output back into convert
        vertices, edges = convert(_sio(csv_out))
        assert edges == original_edges
        assert vertices == original_verts


class TestFormatOutputJSONL:
    """JSONL output format."""

    def test_valid_json_per_line(self):
        edges = [("A", "B", "knows"), ("C", "D", "likes")]
        out = format_output({"A", "B", "C", "D"}, edges, fmt="jsonl")
        lines = out.strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert set(obj.keys()) == {"from", "to", "label"}

    def test_correct_values(self):
        edges = [("Alice", "Bob", "knows")]
        out = format_output({"Alice", "Bob"}, edges, fmt="jsonl")
        obj = json.loads(out)
        assert obj == {"from": "Alice", "to": "Bob", "label": "knows"}

    def test_unicode_in_jsonl(self):
        edges = [("München", "Tokyo", "connects")]
        out = format_output({"München", "Tokyo"}, edges, fmt="jsonl")
        obj = json.loads(out)
        assert obj["from"] == "München"
        assert obj["to"] == "Tokyo"

    def test_empty_jsonl(self):
        out = format_output(set(), [], fmt="jsonl")
        assert out == ""

    def test_unknown_format_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            format_output(set(), [], fmt="xml")


# ===========================================================================
# CLI invocation tests (subprocess)
# ===========================================================================


class TestCLI:
    """Test CLI invocation via subprocess."""

    def _run(self, *args, stdin_data=None):
        cmd = [sys.executable, CONVERTER] + list(args)
        result = subprocess.run(
            cmd, capture_output=True, text=True, input=stdin_data,
            timeout=10,
        )
        return result

    def test_file_arg_plain(self):
        r = self._run(os.path.join(FIXTURES, "sample.csv"))
        assert r.returncode == 0
        lines = r.stdout.strip().split("\n")
        assert lines[0] == "3 3"

    def test_file_arg_csv(self):
        r = self._run(os.path.join(FIXTURES, "sample.csv"), "--csv")
        assert r.returncode == 0
        lines = r.stdout.strip().split("\n")
        assert lines[0] == "from,to,label"
        assert len(lines) == 4  # header + 3 edges

    def test_file_arg_jsonl(self):
        r = self._run(os.path.join(FIXTURES, "sample.csv"), "--jsonl")
        assert r.returncode == 0
        lines = r.stdout.strip().split("\n")
        assert len(lines) == 3
        for line in lines:
            obj = json.loads(line)
            assert "from" in obj

    def test_stdin_plain(self):
        data = "a,b,c\nX,Y,rel\n"
        r = self._run(stdin_data=data)
        assert r.returncode == 0
        assert "2 1" in r.stdout

    def test_stdin_csv(self):
        data = "a,b,c\nX,Y,rel\n"
        r = self._run("--csv", stdin_data=data)
        assert r.returncode == 0
        assert "from,to,label" in r.stdout

    def test_stdin_jsonl(self):
        data = "a,b,c\nX,Y,rel\n"
        r = self._run("--jsonl", stdin_data=data)
        assert r.returncode == 0
        obj = json.loads(r.stdout.strip())
        assert obj == {"from": "X", "to": "Y", "label": "rel"}

    def test_quoted_fields_cli(self):
        r = self._run(os.path.join(FIXTURES, "quoted_commas.csv"), "--jsonl")
        assert r.returncode == 0
        lines = r.stdout.strip().split("\n")
        obj = json.loads(lines[0])
        assert obj["from"] == "New York"

    def test_header_only_cli(self):
        r = self._run(os.path.join(FIXTURES, "header_only.csv"))
        assert r.returncode == 0
        assert r.stdout.strip() == "0 0"

    def test_large_input_cli(self):
        lines = ["src,tgt,rel"]
        for i in range(120):
            lines.append(f"n{i},n{i+1},e{i}")
        data = "\n".join(lines) + "\n"
        r = self._run(stdin_data=data)
        assert r.returncode == 0
        header = r.stdout.strip().split("\n")[0]
        assert header == "121 120"


# ===========================================================================
# End-to-end: file -> convert -> format -> re-parse
# ===========================================================================


class TestEndToEnd:
    """Full round-trip tests."""

    def test_csv_format_roundtrip_from_file(self):
        path = os.path.join(FIXTURES, "sample.csv")
        vertices, edges = convert(path)
        csv_out = format_output(vertices, edges, fmt="csv")
        v2, e2 = convert(_sio(csv_out))
        assert v2 == vertices
        assert e2 == edges

    def test_tempfile_roundtrip(self):
        """Write CSV to tempfile, convert, verify."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            f.write("src,tgt,rel\nA,B,knows\nB,C,likes\n")
            tmppath = f.name
        try:
            vertices, edges = convert(tmppath)
            assert vertices == {"A", "B", "C"}
            assert len(edges) == 2
        finally:
            os.unlink(tmppath)
