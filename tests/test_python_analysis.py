import json

import pytest

from backend.agent import BoundedAgent
from backend.models import SourceFile
from backend.python_analysis import analyze_python
from backend.source_tools import SourceTools
from backend.sources import extract_text


def source_for(text, file_id="file"):
    source = SourceFile(id=file_id, filename="sample.py")
    extract_text(source, text)
    return source


def test_nested_async_and_decorated_symbols_have_original_lines():
    text = "# heading\r\n@decorate\r\nclass Café:\r\n    @other\r\n    async def work(self):\r\n        def inner():\r\n            return 1\r\n        return inner()\r\n"
    result = analyze_python(text)
    assert result["status"] == "ok"
    assert [(s["qualified_name"], s["kind"], s["start_line"], s["definition_line"], s["end_line"])
            for s in result["symbols"]] == [
        ("Café", "class", 2, 3, 8),
        ("Café.work", "async_function", 4, 5, 8),
        ("Café.work.inner", "function", 6, 6, 7),
    ]


@pytest.mark.parametrize("text", ["def broken(:\n    pass", "x = '''unfinished", "def f():\n  pass\n pass"])
def test_malformed_python_produces_diagnostic(text):
    result = analyze_python(text)
    assert result["status"] == "syntax_error"
    assert result["symbols"] == []
    assert result["diagnostics"][0]["line"] >= 1


@pytest.mark.parametrize("text,line,error_type", [
    ("# example\ndef broken(:\n    pass", 2, "SyntaxError"),
    ("# example\nvalues = (\n    1", 2, "SyntaxError"),
    ("# example\nx = '''unfinished", 2, "SyntaxError"),
    ("def f():\npass", 2, "IndentationError"),
    ("# example\nreturn 1", 2, "SyntaxError"),
    ("# example\nbreak", 2, "SyntaxError"),
    ("# example\nawait task()", 2, "SyntaxError"),
])
def test_syntax_diagnostics_locate_parser_and_compile_errors(text, line, error_type):
    result = analyze_python(text)
    assert result["status"] == "syntax_error"
    diagnostic = result["diagnostics"][0]
    assert diagnostic["line"] == line
    assert diagnostic["error_type"] == error_type
    assert diagnostic["column"] >= 1


@pytest.mark.parametrize("text", ["x" * 200001, "x = " + "(" * 81 + "1" + ")" * 81],
                         ids=["character-limit", "nesting-limit"])
def test_analysis_bounds(text):
    assert analyze_python(text)["status"] == "limited"


def test_tools_reconstruct_split_lines_and_omitted_blank_chunks():
    text = "# " + "a" * 5000 + "\n" + "\n" * 2000 + "def target():\n    return 42\n"
    source = source_for(text)
    tools = SourceTools([source])
    assert tools.get_python_symbols(source.id)["symbols"][0]["definition_line"] == 2002
    span = tools.get_source_span(source.spans[0].id)
    span["content"] = "tampered"
    assert tools.get_source_span(span["id"])["content"] != "tampered"
    outline = tools.get_python_symbols(source.id)
    outline["symbols"].clear()
    assert tools.get_python_symbols(source.id)["symbols"]
    assert [s["source_id"] for s in tools.list_sections(source.id)] == [s.id for s in source.spans]
    with pytest.raises(KeyError):
        tools.get_source_span("foreign-span")
    with pytest.raises(KeyError):
        tools.get_python_symbols("foreign-file")


def test_code_excerpts_preserve_indentation_unicode_and_line_numbers():
    source = source_for("# Ren\u00e9e\r\ndef work():\r\n\tvalue = 42\r\n\treturn value\r\n")
    tools = SourceTools([source])
    assert tools.get_code_excerpt(source.id, 3, 4) == {"lines": [
        {"line": 3, "code": "\tvalue = 42"}, {"line": 4, "code": "\treturn value"}], "truncated": False}
    with pytest.raises(KeyError):
        tools.get_code_excerpt("foreign-file", 1, 1)
    assert tools.get_code_excerpt(source.id, 0, 1) is None
    assert tools.get_code_excerpt(source.id, 4, 3) is None
    assert tools.get_code_excerpt(source.id, 99, 100) is None


def test_code_excerpt_uses_full_split_line_and_restores_skipped_blank_lines():
    text = "# " + "a" * 5000 + "\n" + "\n" * 2000 + "print(missing)\n"
    source = source_for(text)
    tools = SourceTools([source])
    assert tools.get_code_excerpt(source.id, 2002, 2002) == {
        "lines": [{"line": 2002, "code": "print(missing)"}], "truncated": False}
    excerpt = tools.get_code_excerpt(source.id, 1, 1)
    assert len(excerpt["lines"][0]["code"]) == 2000
    assert excerpt["truncated"]


def test_code_excerpts_limit_multiline_ranges_and_return_independent_copies():
    source = source_for("\n".join(f"value_{i} = {i}" for i in range(20)))
    tools = SourceTools([source])
    excerpt = tools.get_code_excerpt(source.id, 1, 20)
    assert len(excerpt["lines"]) == 8 and excerpt["truncated"]
    excerpt["lines"][0]["code"] = "tampered"
    assert tools.get_code_excerpt(source.id, 1, 1)["lines"][0]["code"] == "value_0 = 0"


def test_code_excerpt_does_not_guess_unsupported_mapping():
    source = source_for("# comment\fdef work(): pass")
    assert SourceTools([source]).get_code_excerpt(source.id, 1, 1) is None


def test_inspection_never_executes_upload(tmp_path):
    marker = tmp_path / "executed"
    text = f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\nraise RuntimeError('boom')\ndef safe(): pass"
    assert analyze_python(text)["symbols"][0]["name"] == "safe"
    assert not marker.exists()


def test_agent_attaches_only_overlapping_symbols_within_budget():
    source = source_for("def early():\n    return 1\n" + "# filler\n" * 700 + "def target():\n    return 42\n")
    prepared = BoundedAgent().prepare("code", "Explain target", [source], 2600)
    assert prepared.partial
    assert any(s["name"] == "target" for span in prepared.evidence
               for s in span["python_analysis"]["symbols"])
    assert sum(len(s["content"]) + len(s["filename"]) + 160
               + len(json.dumps(s["python_analysis"], ensure_ascii=False)) for s in prepared.evidence) <= 2600
    assert {s["id"] for s in prepared.evidence} <= {s.id for s in source.spans}


def test_syntax_errors_warn_without_rejecting_source_and_document_mode_is_unchanged():
    source = source_for("def broken(:")
    code = BoundedAgent().prepare("code", "Explain", [source], 4000)
    assert code.warnings and code.evidence[0]["python_analysis"]["status"] == "syntax_error"
    document = BoundedAgent().prepare("document", "Summarize", [source], 4000)
    assert not document.warnings
    assert "python_analysis" not in document.evidence[0]


def test_small_context_keeps_source_even_when_outline_will_not_fit():
    source = source_for("def " + "a" * 500 + "(): pass")
    prepared = BoundedAgent().prepare("code", "Explain", [source], 750)
    assert prepared.evidence[0]["content"].startswith("def ")
    assert prepared.warnings


def test_unusual_line_mapping_is_disclosed():
    source = source_for("# comment\fdef work(): pass")
    prepared = BoundedAgent().prepare("code", "Explain", [source], 4000)
    assert prepared.evidence[0]["python_analysis"]["status"] == "unavailable"
    assert prepared.warnings
