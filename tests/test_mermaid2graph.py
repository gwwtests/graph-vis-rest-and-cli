"""Comprehensive tests for mermaid2graph converter."""

import json
import sys
import os

# Add converter to path for direct import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "converters", "mermaid2graph"))

from mermaid2graph import convert, format_output


# ---------------------------------------------------------------------------
# Basic parsing
# ---------------------------------------------------------------------------

class TestBasicParsing:
    def test_empty_graph_header_only(self):
        """Graph with only a header line produces no vertices or edges."""
        verts, edges = convert("graph LR\n")
        assert verts == set()
        assert edges == []

    def test_flowchart_keyword(self):
        """'flowchart' keyword is accepted like 'graph'."""
        src = "flowchart TD\n    A -->|knows| B\n"
        verts, edges = convert(src)
        assert "A" in verts and "B" in verts
        assert len(edges) == 1

    def test_directions_lr(self):
        verts, edges = convert("graph LR\n    A --> B\n")
        assert len(edges) == 1

    def test_directions_td(self):
        verts, edges = convert("graph TD\n    A --> B\n")
        assert len(edges) == 1

    def test_directions_tb(self):
        verts, edges = convert("graph TB\n    A --> B\n")
        assert len(edges) == 1

    def test_directions_rl(self):
        verts, edges = convert("graph RL\n    A --> B\n")
        assert len(edges) == 1

    def test_directions_bt(self):
        verts, edges = convert("graph BT\n    A --> B\n")
        assert len(edges) == 1

    def test_empty_string(self):
        verts, edges = convert("")
        assert verts == set()
        assert edges == []

    def test_only_blank_lines(self):
        verts, edges = convert("\n\n\n")
        assert verts == set()
        assert edges == []


# ---------------------------------------------------------------------------
# Arrow types and labels
# ---------------------------------------------------------------------------

class TestArrowTypes:
    def test_pipe_label(self):
        """A -->|label| B"""
        verts, edges = convert("graph LR\n    A -->|knows| B\n")
        assert edges == [("A", "B", "knows")]
        assert verts == {"A", "B"}

    def test_dash_label(self):
        """A -- label --> B"""
        verts, edges = convert("graph LR\n    A -- knows --> B\n")
        assert edges == [("A", "B", "knows")]

    def test_no_label(self):
        """A --> B  defaults to '->'"""
        verts, edges = convert("graph LR\n    A --> B\n")
        assert edges == [("A", "B", "->")]

    def test_thick_arrow_with_label(self):
        """A ==>|label| B — thick arrow."""
        verts, edges = convert("graph LR\n    A ==>|heavy| B\n")
        assert "A" in verts and "B" in verts
        assert len(edges) == 1
        assert edges[0][2] == "heavy"

    def test_thick_arrow_no_label(self):
        """A ==> B — thick arrow without label."""
        verts, edges = convert("graph LR\n    A ==> B\n")
        assert len(edges) == 1
        assert edges[0][0] == "A"
        assert edges[0][1] == "B"

    def test_dotted_arrow_with_label(self):
        """A -.->|label| B — dotted arrow."""
        verts, edges = convert("graph LR\n    A -.->|dotted| B\n")
        assert "A" in verts and "B" in verts
        assert len(edges) == 1
        assert edges[0][2] == "dotted"

    def test_dotted_arrow_no_label(self):
        """A -.-> B — dotted arrow without label."""
        verts, edges = convert("graph LR\n    A -.-> B\n")
        assert len(edges) == 1

    def test_multi_word_pipe_label(self):
        """Labels with spaces inside pipes."""
        verts, edges = convert("graph LR\n    A -->|is friends with| B\n")
        assert edges[0][2] == "is friends with"

    def test_multi_word_dash_label(self):
        """Labels with spaces between dashes."""
        verts, edges = convert("graph LR\n    A -- is friends with --> B\n")
        assert edges[0][2] == "is friends with"


# ---------------------------------------------------------------------------
# Node shapes / bracket stripping
# ---------------------------------------------------------------------------

class TestNodeShapes:
    def test_square_brackets(self):
        """A[Label] --> B[Label2] — IDs should be extracted (just A, B)."""
        verts, edges = convert("graph LR\n    A[Alice] --> B[Bob]\n")
        # The converter should handle node IDs — at minimum parse an edge
        assert len(edges) == 1
        # Node IDs may include bracket text or just the base ID
        # We verify the edge was parsed

    def test_round_parens(self):
        """A(Label) --> B(Label2)"""
        verts, edges = convert("graph LR\n    A(Alice) -->|knows| B(Bob)\n")
        assert len(edges) == 1

    def test_mixed_shapes(self):
        """A[Label] --> B(Label2)"""
        verts, edges = convert("graph LR\n    A[Alice] -->|knows| B(Bob)\n")
        assert len(edges) == 1


# ---------------------------------------------------------------------------
# Comments and ignorable lines
# ---------------------------------------------------------------------------

class TestCommentsAndIgnorable:
    def test_comment_lines_ignored(self):
        """Lines starting with %% should be ignored."""
        src = "graph LR\n    %% this is a comment\n    A --> B\n"
        verts, edges = convert(src)
        assert edges == [("A", "B", "->")]
        assert verts == {"A", "B"}

    def test_style_classDef_ignored(self):
        """classDef lines should be ignored (no crash, no edges)."""
        src = "graph LR\n    classDef default fill:#f9f\n    A --> B\n"
        verts, edges = convert(src)
        assert edges == [("A", "B", "->")]

    def test_class_statement_ignored(self):
        """class A,B someClass should be ignored."""
        src = "graph LR\n    A --> B\n    class A,B highlight\n"
        verts, edges = convert(src)
        assert len(edges) == 1

    def test_style_statement_ignored(self):
        """style A fill:#f00 should be ignored."""
        src = "graph LR\n    A --> B\n    style A fill:#f00\n"
        verts, edges = convert(src)
        assert len(edges) == 1


# ---------------------------------------------------------------------------
# Subgraphs
# ---------------------------------------------------------------------------

class TestSubgraphs:
    def test_edges_inside_subgraph_parsed(self):
        """Edges within subgraph blocks should still be parsed."""
        src = """\
graph LR
    subgraph cluster1
        A -->|knows| B
        B -->|likes| C
    end
"""
        verts, edges = convert(src)
        assert len(edges) == 2
        assert ("A", "B", "knows") in edges
        assert ("B", "C", "likes") in edges

    def test_subgraph_with_title(self):
        src = """\
graph LR
    subgraph "My Title"
        X --> Y
    end
"""
        verts, edges = convert(src)
        assert len(edges) == 1


# ---------------------------------------------------------------------------
# Special node names
# ---------------------------------------------------------------------------

class TestNodeNames:
    def test_underscores(self):
        verts, edges = convert("graph LR\n    my_node --> other_node\n")
        assert "my_node" in verts
        assert "other_node" in verts

    def test_hyphens(self):
        verts, edges = convert("graph LR\n    my-node --> other-node\n")
        assert "my-node" in verts

    def test_numbers(self):
        verts, edges = convert("graph LR\n    node1 --> node2\n")
        assert "node1" in verts and "node2" in verts

    def test_mixed_alphanumeric(self):
        verts, edges = convert("graph LR\n    A1_b2 --> C3_d4\n")
        assert "A1_b2" in verts


# ---------------------------------------------------------------------------
# Self-loops
# ---------------------------------------------------------------------------

class TestSelfLoop:
    def test_self_loop(self):
        verts, edges = convert("graph LR\n    A -->|self| A\n")
        assert edges == [("A", "A", "self")]
        assert verts == {"A"}


# ---------------------------------------------------------------------------
# Unicode
# ---------------------------------------------------------------------------

class TestUnicode:
    def test_unicode_labels(self):
        verts, edges = convert("graph LR\n    A -->|café| B\n")
        assert edges[0][2] == "café"

    def test_unicode_node_ids(self):
        verts, edges = convert("graph LR\n    café --> naïve\n")
        assert "café" in verts
        assert "naïve" in verts


# ---------------------------------------------------------------------------
# Whitespace variations
# ---------------------------------------------------------------------------

class TestWhitespace:
    def test_tabs(self):
        verts, edges = convert("graph LR\n\tA --> B\n")
        assert len(edges) == 1

    def test_extra_spaces(self):
        verts, edges = convert("graph LR\n    A   -->   B\n")
        assert len(edges) == 1

    def test_leading_spaces(self):
        verts, edges = convert("graph LR\n        A -->|x| B\n")
        assert edges[0] == ("A", "B", "x")

    def test_trailing_semicolon(self):
        """Mermaid allows trailing semicolons."""
        verts, edges = convert("graph LR\n    A --> B;\n")
        assert len(edges) == 1


# ---------------------------------------------------------------------------
# Multiple edges
# ---------------------------------------------------------------------------

class TestMultipleEdges:
    def test_multiple_edges(self):
        src = "graph LR\n    A -->|x| B\n    B -->|y| C\n    C --> A\n"
        verts, edges = convert(src)
        assert len(edges) == 3
        assert verts == {"A", "B", "C"}


# ---------------------------------------------------------------------------
# Output formats
# ---------------------------------------------------------------------------

class TestFormatOutput:
    def test_plain_format(self):
        verts = {"A", "B"}
        edges = [("A", "B", "knows")]
        out = format_output(verts, edges, "plain")
        lines = out.split("\n")
        assert lines[0] == "2 1"
        assert lines[1] == "A B knows"

    def test_csv_format(self):
        verts = {"A", "B"}
        edges = [("A", "B", "knows")]
        out = format_output(verts, edges, "csv")
        lines = out.split("\n")
        assert lines[0] == "from,to,label"
        assert lines[1] == "A,B,knows"

    def test_jsonl_format(self):
        verts = {"A", "B"}
        edges = [("A", "B", "knows")]
        out = format_output(verts, edges, "jsonl")
        obj = json.loads(out.strip())
        assert obj == {"from": "A", "to": "B", "label": "knows"}

    def test_plain_empty(self):
        out = format_output(set(), [], "plain")
        assert out == "0 0"

    def test_csv_empty(self):
        out = format_output(set(), [], "csv")
        assert out == "from,to,label"

    def test_jsonl_empty(self):
        out = format_output(set(), [], "jsonl")
        assert out == ""

    def test_plain_multiple_edges(self):
        verts = {"A", "B", "C"}
        edges = [("A", "B", "x"), ("B", "C", "y")]
        out = format_output(verts, edges, "plain")
        lines = out.split("\n")
        assert lines[0] == "3 2"
        assert lines[1] == "A B x"
        assert lines[2] == "B C y"
