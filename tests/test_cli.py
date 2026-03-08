"""Tests for graph-vis-cli GraphClient, REPL, and mode resolution."""

import json
import os
from unittest.mock import patch
from graph_vis_cli import (GraphClient, GraphREPL, CONVERTER_MAP, parse_args,
                           execute_command, MultilineProcessor, execute_commands)


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
