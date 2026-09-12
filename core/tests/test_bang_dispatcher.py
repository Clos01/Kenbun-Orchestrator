"""Tests for Universal Bang Command Dispatcher."""

import pytest
from tools.strategy.bang_dispatcher import (
    is_bang_command,
    parse_bang_command,
    dispatch_bang_command,
)


def test_is_bang_command():
    assert is_bang_command("!Supervisor audit code") is True
    assert is_bang_command("!timesfm fix leak") is True
    assert is_bang_command("!help") is True
    assert is_bang_command("!= null") is False
    assert is_bang_command("hello world") is False
    assert is_bang_command("") is False
    assert is_bang_command(None) is False


def test_parse_bang_command():
    directive, payload, kwargs = parse_bang_command("!Supervisor \"Audit connection pool\" \"with get(): pass\"")
    assert directive == "!supervisor"
    assert "Audit connection pool" in payload

    directive, payload, _ = parse_bang_command("!Orchestrate bug_fix Resolve timeout")
    assert directive == "!orchestrate"
    assert payload == "bug_fix Resolve timeout"

    directive, payload, _ = parse_bang_command("!timesfm Build luxury audio chime")
    assert directive == "!timesfm"
    assert payload == "Build luxury audio chime"


def test_dispatch_bang_help():
    res = dispatch_bang_command("!help")
    assert "Kenbun Universal Bang Command Reference" in res
    assert "!Supervisor" in res
    assert "!timesfm" in res


def test_dispatch_unknown_bang():
    res = dispatch_bang_command("!unknown_cmd foo bar")
    assert "Unknown bang directive" in res
