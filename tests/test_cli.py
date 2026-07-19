"""Tests for graph-vis-cli GraphClient, REPL, and mode resolution."""

import importlib.util
import json
import os
import subprocess
import sys
from unittest.mock import patch
import pytest
from graph_vis_cli import (GraphClient, GraphREPL, CONVERTER_MAP, EXPORT_MAP,
                           parse_args, execute_command, MultilineProcessor,
                           execute_commands, run_converter)


def test_parse_args_defaults():
    args = parse_args([])
    assert args.host == "127.0.0.1"
    assert args.port == 7849
    assert args.verbose == 0
    assert args.commands == []
    assert args.load == []
    assert args.repl is False
    assert args.stdin is False
    assert args.input is None


def test_parse_args_custom():
    args = parse_args(["--host", "10.0.0.1", "--port", "9999", "-vvv"])
    assert args.host == "10.0.0.1"
    assert args.port == 9999
    assert args.verbose == 3


def test_parse_args_env_vars():
    with patch.dict(os.environ, {"GRAPH_VIS_HOST": "10.0.0.5", "GRAPH_VIS_PORT": "8888"}):
        args = parse_args([])
        assert args.host == "10.0.0.5"
        assert args.port == 8888


def test_parse_args_flags_override_env():
    with patch.dict(os.environ, {"GRAPH_VIS_HOST": "10.0.0.5", "GRAPH_VIS_PORT": "8888"}):
        args = parse_args(["--host", "1.2.3.4", "--port", "5555"])
        assert args.host == "1.2.3.4"
        assert args.port == 5555


def test_parse_args_positional_commands():
    args = parse_args(["Alice knows Bob", "g"])
    assert args.commands == ["Alice knows Bob", "g"]


def test_parse_args_load_repeatable():
    args = parse_args(["-l", "a.csv", "-l", "b.ttl", "--load", "c.dot"])
    assert args.load == ["a.csv", "b.ttl", "c.dot"]


def test_parse_args_repl_flag():
    args = parse_args(["--repl"])
    assert args.repl is True


def test_parse_args_stdin_flag():
    args = parse_args(["--stdin"])
    assert args.stdin is True


def test_parse_args_input_file():
    args = parse_args(["-i", "commands.txt"])
    assert args.input == "commands.txt"


def test_parse_args_combined():
    args = parse_args(["-l", "data.csv", "-v", "--repl"])
    assert args.load == ["data.csv"]
    assert args.verbose == 1
    assert args.repl is True


def test_client_base_url():
    c = GraphClient("10.0.0.5", 8080)
    assert c.base_url == "http://10.0.0.5:8080"


def test_repl_prompt():
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    assert repl.prompt == "graph@127.0.0.1:7849> "


def test_repl_default_three_words(capsys):
    """3 bare words should be treated as add triplet."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "add_triplet", return_value={"ok": True}):
        repl.default("Alice knows Bob")
        c.add_triplet.assert_called_once_with("Alice", "knows", "Bob")


def test_repl_default_unknown_command(capsys):
    """Non-3-word input should print unknown command."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    repl.default("badcommand")
    out = capsys.readouterr().out
    assert "Unknown command" in out


def test_repl_default_two_words(capsys):
    """2 bare words should add edge without label."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "add_edge", return_value={"ok": True}):
        repl.default("Alice Bob")
        c.add_edge.assert_called_once_with("Alice", "Bob", "")


def test_repl_plus_two_words(capsys):
    """+ with 2 words should add edge without label."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "add_edge", return_value={"ok": True}):
        repl.default("+ Alice Bob")
        c.add_edge.assert_called_once_with("Alice", "Bob", "")


def test_execute_command_skips_empty():
    """Empty lines and comments are skipped."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(repl, "onecmd") as mock:
        execute_command(repl, "")
        execute_command(repl, "   ")
        execute_command(repl, "# this is a comment")
        mock.assert_not_called()


def test_execute_command_calls_onecmd():
    """Non-empty lines are dispatched to onecmd."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(repl, "onecmd") as mock:
        execute_command(repl, "  g  ")
        mock.assert_called_once_with("g")


def test_converter_map_jsonl():
    """JSONL extension is in CONVERTER_MAP."""
    assert ".jsonl" in CONVERTER_MAP
    assert CONVERTER_MAP[".jsonl"] == "jsonl2graph"


def test_load_jsonl_with_extras(tmp_path, capsys):
    """Loading JSONL passes styling extras to server."""
    f = tmp_path / "test.jsonl"
    f.write_text('\n'.join([
        json.dumps({"type": "node", "id": "A", "label": "A", "color": "red"}),
        json.dumps({"type": "edge", "from": "A", "to": "B", "label": "x", "width": 3}),
    ]))
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    add_node_calls = []
    add_edge_calls = []
    with patch.object(c, "add_node", side_effect=lambda *a, **kw: (add_node_calls.append((a, kw)), {"ok": True})[1]):
        with patch.object(c, "add_edge", side_effect=lambda *a, **kw: (add_edge_calls.append((a, kw)), {"ok": True})[1]):
            repl.do_Load(str(f))
    # Verify extras passed through
    assert any(kw.get("color") == "red" for _, kw in add_node_calls)
    assert any(kw.get("width") == 3 for _, kw in add_edge_calls)


def test_multiline_plain_block():
    """Plain +++ block executes each line as a command."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)

    with patch.object(c, "add_triplet", return_value={"ok": True}):
        assert proc.feed("+++") is True  # entered block
        assert proc.feed("Alice knows Bob") is True  # buffered
        assert proc.feed("Bob likes Charlie") is True  # buffered
        assert proc.feed("+++") is True  # closed + executed
        c.add_triplet.assert_any_call("Alice", "knows", "Bob")
        c.add_triplet.assert_any_call("Bob", "likes", "Charlie")


def test_multiline_jsonl_block():
    """+++jsonl block feeds content through JSONL processor."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)

    with patch.object(c, "add_node", return_value={"ok": True}):
        proc.feed("+++jsonl")
        proc.feed('{"type":"node","id":"X","label":"X","color":"red"}')
        proc.feed("+++")
        c.add_node.assert_called_once_with("X", "X", color="red")


def test_multiline_jsonl_block_edge_extras():
    """+++jsonl block passes edge styling extras through."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)

    add_node_calls = []
    add_edge_calls = []
    with patch.object(c, "add_node", side_effect=lambda *a, **kw: (add_node_calls.append((a, kw)), {"ok": True})[1]):
        with patch.object(c, "add_edge", side_effect=lambda *a, **kw: (add_edge_calls.append((a, kw)), {"ok": True})[1]):
            proc.feed("+++jsonl")
            proc.feed('{"type":"node","id":"A","label":"Alpha","color":"blue","shape":"box"}')
            proc.feed('{"type":"edge","from":"A","to":"B","label":"links","width":3,"dashes":true}')
            proc.feed('{"type":"edge","from":"B","to":"C"}')
            proc.feed("+++")

    # Node extras
    assert len(add_node_calls) == 1
    args, kwargs = add_node_calls[0]
    assert args == ("A", "Alpha")
    assert kwargs == {"color": "blue", "shape": "box"}

    # Edge with extras
    assert len(add_edge_calls) == 2
    args1, kwargs1 = add_edge_calls[0]
    assert args1 == ("A", "B", "links")
    assert kwargs1["width"] == 3
    assert kwargs1["dashes"] is True

    # Edge without label
    args2, kwargs2 = add_edge_calls[1]
    assert args2 == ("B", "C", "")


def test_multiline_not_in_block():
    """Lines outside block return False (not consumed)."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)
    assert proc.feed("Alice knows Bob") is False
    assert proc.feed("g") is False


def test_multiline_closes_block():
    """Second +++ closes the block."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)

    with patch.object(c, "add_triplet", return_value={"ok": True}):
        proc.feed("+++")
        assert proc.in_block is True
        proc.feed("A B C")
        proc.feed("+++")
        assert proc.in_block is False


def test_multiline_csv_block():
    """+++csv block feeds content through csv converter."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)

    with patch.object(c, "add_triplet", return_value={"ok": True}):
        proc.feed("+++csv")
        proc.feed("source,target,relationship")
        proc.feed("Alice,Bob,knows")
        proc.feed("+++")
        c.add_triplet.assert_called_once_with("Alice", "knows", "Bob")


def test_execute_commands_with_block():
    """execute_commands handles multiline blocks in a stream."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    lines = [
        "+++",
        "X Y Z",
        "+++",
    ]
    with patch.object(c, "add_triplet", return_value={"ok": True}):
        execute_commands(repl, lines)
        c.add_triplet.assert_called_once_with("X", "Y", "Z")


def test_execute_commands_mixed():
    """execute_commands handles mix of regular and block lines."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    lines = [
        "A B C",
        "+++",
        "D E F",
        "+++",
        "g",
    ]
    with patch.object(c, "add_triplet", return_value={"ok": True}):
        with patch.object(repl, "do_graph"):
            execute_commands(repl, lines)
            assert c.add_triplet.call_count == 2  # A B C + D E F


def test_multiline_invalid_format():
    """Invalid format after +++ is not consumed."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    proc = MultilineProcessor(repl)
    assert proc.feed("+++invalidformat") is False
    assert proc.in_block is False


# ===========================================================================
# Store command tests
# ===========================================================================

import subprocess
import sys
import tempfile


def test_export_map_formats():
    """EXPORT_MAP covers all expected formats."""
    assert EXPORT_MAP[".jsonl"] == "graph2jsonl"
    assert EXPORT_MAP[".csv"] == "graph2csv"
    assert EXPORT_MAP[".dot"] == "graph2dot"
    assert EXPORT_MAP[".gv"] == "graph2dot"
    assert EXPORT_MAP[".ttl"] == "graph2ttl"
    assert EXPORT_MAP[".n3"] == "graph2ttl"
    assert EXPORT_MAP[".mermaid"] == "graph2mermaid"
    assert EXPORT_MAP[".mmd"] == "graph2mermaid"


def test_parse_args_store_flag():
    """--store / -s flag is parsed correctly."""
    args = parse_args(["-s", "output.jsonl"])
    assert args.store == "output.jsonl"
    args2 = parse_args(["--store", "graph.csv"])
    assert args2.store == "graph.csv"


def test_parse_args_store_default():
    """--store defaults to None."""
    args = parse_args([])
    assert args.store is None


def test_parse_args_store_combined():
    """-l and -s can be combined."""
    args = parse_args(["-l", "data.csv", "-s", "out.jsonl", "g"])
    assert args.load == ["data.csv"]
    assert args.store == "out.jsonl"
    assert args.commands == ["g"]


SAMPLE_GRAPH = {
    "nodes": [{"id": "Alice", "label": "Alice"}, {"id": "Bob", "label": "Bob"}],
    "edges": [{"id": "Alice-knows-Bob", "from": "Alice", "to": "Bob", "label": "knows"}],
}


def test_store_jsonl(capsys):
    """store command writes JSONL output to file."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "get_graph", return_value=SAMPLE_GRAPH):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            tmppath = f.name
        try:
            repl.do_store(tmppath)
            output = capsys.readouterr().out
            assert "Stored" in output
            assert "jsonl" in output
            with open(tmppath) as f:
                content = f.read()
            assert "Alice" in content
            assert "knows" in content
        finally:
            os.unlink(tmppath)


def test_store_csv(capsys):
    """store command writes CSV output to file."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "get_graph", return_value=SAMPLE_GRAPH):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            tmppath = f.name
        try:
            repl.do_store(tmppath)
            output = capsys.readouterr().out
            assert "Stored" in output
            assert "csv" in output
            with open(tmppath) as f:
                content = f.read()
            assert "from,to,label" in content
            assert "Alice" in content
        finally:
            os.unlink(tmppath)


def test_store_dot(capsys):
    """store command writes DOT output to file."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "get_graph", return_value=SAMPLE_GRAPH):
        with tempfile.NamedTemporaryFile(suffix=".dot", delete=False, mode="w") as f:
            tmppath = f.name
        try:
            repl.do_store(tmppath)
            output = capsys.readouterr().out
            assert "Stored" in output
            assert "dot" in output
            with open(tmppath) as f:
                content = f.read()
            assert "digraph" in content
            assert "Alice" in content
        finally:
            os.unlink(tmppath)


def test_store_no_extension_defaults_jsonl(capsys):
    """store without extension defaults to .jsonl."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "get_graph", return_value=SAMPLE_GRAPH):
        with tempfile.NamedTemporaryFile(delete=False, mode="w", prefix="graph") as f:
            tmppath = f.name
        try:
            repl.do_store(tmppath)
            output = capsys.readouterr().out
            assert "jsonl" in output
            assert os.path.isfile(tmppath + ".jsonl")
        finally:
            if os.path.isfile(tmppath + ".jsonl"):
                os.unlink(tmppath + ".jsonl")
            if os.path.isfile(tmppath):
                os.unlink(tmppath)


def test_store_unsupported_format(capsys):
    """store with unsupported extension shows error."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "get_graph", return_value=SAMPLE_GRAPH):
        repl.do_store("graph.xml")
        output = capsys.readouterr().out
        assert "Unsupported" in output


def test_store_empty_arg(capsys):
    """store without filepath shows usage."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    repl.do_store("")
    output = capsys.readouterr().out
    assert "Usage" in output


def test_store_aliases():
    """Store and S are aliases for store."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    assert repl.do_Store == repl.do_store
    assert repl.do_S == repl.do_store


def test_store_empty_graph(capsys):
    """store works with an empty graph."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    empty = {"nodes": [], "edges": []}
    with patch.object(c, "get_graph", return_value=empty):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            tmppath = f.name
        try:
            repl.do_store(tmppath)
            output = capsys.readouterr().out
            assert "Stored 0 edges, 0 nodes" in output
        finally:
            os.unlink(tmppath)


def test_store_roundtrip_jsonl():
    """JSONL store → load round-trip preserves graph data."""
    c = GraphClient("127.0.0.1", 7849)
    repl = GraphREPL(c)
    with patch.object(c, "get_graph", return_value=SAMPLE_GRAPH):
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            tmppath = f.name
        try:
            repl.do_store(tmppath)
            # Read back and verify through jsonl2graph
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from scripts.converters.jsonl2graph.jsonl2graph import convert
            result = convert(tmppath)
            assert len(result["edges"]) == 1
            assert result["edges"][0]["from"] == "Alice"
            assert result["edges"][0]["to"] == "Bob"
            assert result["edges"][0]["label"] == "knows"
        finally:
            os.unlink(tmppath)


# ===========================================================================
# run_converter: prefer the script's own shebang (uv run) over sys.executable
# ===========================================================================


def test_run_converter_prefers_executable_shebang():
    """When the converter script is executable, run it directly so its
    PEP-723 uv shebang resolves dependencies (rdflib etc.)."""
    with patch("graph_vis_cli.os.access", return_value=True):
        with patch("graph_vis_cli.subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess([], 0, "out", "")
            run_converter("/conv/ttl2graph.py", ["data.ttl"])
            cmd = m.call_args[0][0]
            assert cmd == ["/conv/ttl2graph.py", "data.ttl"]
            # sys.executable must NOT be prepended
            assert cmd[0] != sys.executable


def test_run_converter_falls_back_when_not_executable():
    """Non-executable script falls back to the current interpreter."""
    with patch("graph_vis_cli.os.access", return_value=False):
        with patch("graph_vis_cli.subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess([], 0, "out", "")
            run_converter("/conv/csv2graph.py", ["data.csv"])
            cmd = m.call_args[0][0]
            assert cmd == [sys.executable, "/conv/csv2graph.py", "data.csv"]


def test_run_converter_passes_input_and_timeout():
    """input_text and a 60s timeout are forwarded to subprocess.run."""
    with patch("graph_vis_cli.os.access", return_value=True):
        with patch("graph_vis_cli.subprocess.run") as m:
            m.return_value = subprocess.CompletedProcess([], 0, "out", "")
            run_converter("/conv/graph2ttl.py", [], input_text="graph-json")
            assert m.call_args.kwargs["input"] == "graph-json"
            assert m.call_args.kwargs["timeout"] == 60


@pytest.mark.skipif(
    importlib.util.find_spec("rdflib") is not None,
    reason="only meaningful when system python lacks rdflib (uv shebang path)",
)
def test_ttl_converter_runs_via_uv_shebang(tmp_path):
    """Integration: a .ttl converter runs via its uv shebang even without
    rdflib installed in the current interpreter."""
    script = os.path.join(
        os.path.dirname(__file__), "..",
        "scripts", "converters", "ttl2graph", "ttl2graph.py",
    )
    if not os.access(script, os.X_OK):
        pytest.skip("converter script not executable")
    ttl = tmp_path / "g.ttl"
    ttl.write_text("@prefix : <http://example.org/> .\n:Alice :knows :Bob .\n")
    try:
        result = run_converter(script, [str(ttl)])
    except subprocess.TimeoutExpired:
        pytest.skip("uv dependency resolution timed out (offline)")
    assert result.returncode == 0, result.stderr
    # Intermediate format: header line "<nodes> <edges>" then triplets
    assert "Alice" in result.stdout and "Bob" in result.stdout
