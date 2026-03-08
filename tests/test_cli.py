"""Tests for graph-vis-cli GraphClient, REPL, and mode resolution."""

import os
from unittest.mock import patch
from graph_vis_cli import GraphClient, GraphREPL, parse_args, execute_command


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
