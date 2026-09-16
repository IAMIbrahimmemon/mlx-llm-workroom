import pytest

from agent.toolcall import (
    ToolCall, ToolCallError, format_result, parse_all, parse_block, strip_calls,
)


def test_native_xml_form():
    c = parse_block("<function=bash><parameter=cmd>ls -la</parameter></function>")
    assert c.name == "bash"
    assert c.args == {"cmd": "ls -la"}


def test_multiple_parameters_and_coercion():
    c = parse_block(
        "<function=bash><parameter=cmd>sleep 1</parameter>"
        "<parameter=timeout>30</parameter></function>"
    )
    assert c.args == {"cmd": "sleep 1", "timeout": 30}


def test_multiline_parameter_keeps_internal_whitespace():
    body = "<function=write_file><parameter=path>/tmp/x.py</parameter>" \
           "<parameter=content>\ndef f():\n    return 1\n</parameter></function>"
    c = parse_block(body)
    assert c.args["content"] == "def f():\n    return 1"


def test_template_newlines_around_values_are_stripped():
    """The 4-bit quant writes every value on its own line; without this the
    path arguments arrive unusable."""
    c = parse_block("<function=read_file><parameter=path>\npyproject.toml\n</parameter></function>")
    assert c.args["path"] == "pyproject.toml"


def test_only_one_newline_is_taken_from_each_end():
    c = parse_block("<function=w><parameter=c>\n\nkeep\n\n</parameter></function>")
    assert c.args["c"] == "\nkeep\n"


def test_booleans_and_null():
    c = parse_block(
        "<function=t><parameter=a>true</parameter><parameter=b>false</parameter>"
        "<parameter=c>null</parameter></function>"
    )
    assert c.args == {"a": True, "b": False, "c": None}


def test_json_fallback():
    c = parse_block('{"name": "glob", "arguments": {"pattern": "*.py"}}')
    assert c.name == "glob" and c.args == {"pattern": "*.py"}


def test_openai_function_shape_with_stringified_arguments():
    c = parse_block('{"function": {"name": "grep", "arguments": "{\\"pattern\\": \\"def\\"}"}}')
    assert c.name == "grep" and c.args == {"pattern": "def"}


def test_missing_closing_function_tag_is_recovered():
    c = parse_block("<function=read_file><parameter=path>/etc/hosts</parameter>")
    assert c.name == "read_file" and c.args["path"] == "/etc/hosts"


def test_parse_all_finds_several():
    text = (
        "I'll check.\n"
        "<tool_call><function=a><parameter=x>1</parameter></function></tool_call>\n"
        "<tool_call><function=b><parameter=y>2</parameter></function></tool_call>"
    )
    calls = parse_all(text)
    assert [c.name for c in calls] == ["a", "b"]
    assert calls[0].args == {"x": 1}


def test_parse_all_handles_stream_stopped_before_close():
    text = "ok<tool_call><function=bash><parameter=cmd>pwd</parameter></function>"
    assert parse_all(text)[0].args == {"cmd": "pwd"}


def test_parse_all_skips_garbage_between_good_calls():
    text = (
        "<tool_call>total nonsense</tool_call>"
        "<tool_call><function=ok><parameter=v>1</parameter></function></tool_call>"
    )
    assert [c.name for c in parse_all(text)] == ["ok"]


def test_bare_json_with_no_wrapper():
    assert parse_all('{"name": "glob", "args": {"pattern": "*.md"}}')[0].name == "glob"


def test_no_calls_returns_empty():
    assert parse_all("just talking, no tools here") == []


def test_unreadable_block_raises():
    with pytest.raises(ToolCallError):
        parse_block("<nothing useful/>")


def test_strip_calls_keeps_prose_and_drops_calls():
    text = "Let me look.\n<tool_call><function=a></function></tool_call>\ntrailing"
    out = strip_calls(text)
    assert "tool_call" not in out
    assert out.startswith("Let me look.") and out.endswith("trailing")


def test_strip_calls_drops_an_unterminated_trailing_call():
    assert strip_calls("Checking.\n<tool_call><function=a>") == "Checking."


def test_format_result_marks_errors():
    assert 'status="error"' in format_result("bash", "boom", ok=False)
    assert 'status="error"' not in format_result("bash", "fine")
