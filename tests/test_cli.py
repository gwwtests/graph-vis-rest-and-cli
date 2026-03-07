"""Tests for graph-rest-cli GraphClient and REPL parsing."""

import io
import json
from unittest.mock import patch, MagicMock
from graph_rest_cli import GraphClient, GraphREPL, parse_args


def test_parse_args_defaults():
    with patch("sys.argv", ["prog"]):
        args = parse_args()
        assert args.host == "127.0.0.1"
        assert args.port == 7849
        assert args.verbose == 0


def test_parse_args_custom():
    with patch("sys.argv", ["prog", "--host", "10.0.0.1", "--port", "9999", "-vvv"]):
        args = parse_args()
        assert args.host == "10.0.0.1"
        assert args.port == 9999
        assert args.verbose == 3


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
