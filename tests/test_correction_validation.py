from types import SimpleNamespace

import pytest

from backend.correction_validation import apply_corrections, render_validation, validate_corrections
from backend.models import SourceFile
from backend.source_tools import SourceTools
from backend.sources import extract_text


def tools_for(text, file_id="file"):
    source = SourceFile(id=file_id, filename=file_id + ".py")
    extract_text(source, text)
    return SourceTools([source])


def edit(start, end, replacement, file_id="file"):
    return {"file_id": file_id, "filename": file_id + ".py", "start_line": start, "end_line": end,
            "replacement_code": replacement, "validation_status": "not_checked"}


def test_edits_apply_using_original_line_numbers_despite_inserted_lines():
    original = "a = 1\r\nb = 2\r\nprint(a + b)\r\n"
    edits = [edit(1, 1, "a = 3\nextra = 4"), edit(3, 3, "print(a + b + extra)")]
    assert apply_corrections(original, edits) == "a = 3\nextra = 4\nb = 2\nprint(a + b + extra)\n"


def test_last_line_without_terminating_newline_is_preserved():
    assert apply_corrections("a = 1\nprint(a)", [edit(2, 2, "print(a + 1)")]) == "a = 1\nprint(a + 1)"


@pytest.mark.parametrize("edits", [
    [edit(0, 1, "x")], [edit(3, 3, "x")], [edit(2, 1, "x")],
    [edit(1, 2, "x"), edit(2, 2, "y")],
])
def test_invalid_ranges_cannot_be_applied(edits):
    with pytest.raises(ValueError):
        apply_corrections("a = 1\nprint(a)\n", edits)


def test_real_syntax_and_ruff_validation_detects_success_without_changing_source():
    tools = tools_for("print(missing)\n")
    corrections = [edit(1, 1, "value = 42\nprint(value)")]
    results = validate_corrections(tools, corrections)
    assert results[0]["status"] == corrections[0]["validation_status"] == "checks_passed"
    assert results[0]["syntax"]["status"] == results[0]["ruff"]["status"] == "ok"
    assert tools.get_python_text("file") == "print(missing)\n"
    assert "Runtime behavior has not been tested" in render_validation(results)


def test_syntax_error_in_full_file_is_reported_with_proposed_line_number():
    tools = tools_for("def work():\n    return 1\n")
    results = validate_corrections(tools, [edit(2, 2, "    return (")])
    assert results[0]["status"] == "syntax_error"
    assert results[0]["syntax"]["diagnostics"][0]["line"] == 2
    assert "Proposed file, line 2" in render_validation(results)


def test_remaining_ruff_findings_use_updated_file_line_numbers():
    tools = tools_for("value = 1\nprint(value)\n")
    results = validate_corrections(tools, [edit(1, 1, "first = 1\nsecond = 2")])
    assert results[0]["status"] == "issues_remaining"
    finding = next(f for f in results[0]["ruff"]["findings"] if f["rule"] == "F821")
    assert finding["line"] == 3
    assert "Proposed file, line 3" in render_validation(results)


def test_all_edits_are_validated_together_for_each_file():
    tools = tools_for("value = 1\nprint(value)\n")
    edits = [edit(1, 1, "updated = 2"), edit(2, 2, "print(updated)")]
    results = validate_corrections(tools, edits)
    assert len(results) == 1 and results[0]["status"] == "checks_passed"
    assert all(item["validation_status"] == "checks_passed" for item in edits)


@pytest.mark.parametrize("status", ["unavailable", "timeout", "output_limit"])
def test_checker_failures_do_not_claim_validation_passed(monkeypatch, status):
    monkeypatch.setattr("backend.correction_validation.run_ruff", lambda *args, **kwargs: {
        "status": status, "findings": [], "truncated": False})
    results = validate_corrections(tools_for("value = 1\n"), [edit(1, 1, "value = 2")])
    assert results[0]["status"] == "incomplete"
    assert results[0]["ruff"]["status"] == status
    assert "has not passed validation" in render_validation(results)


def test_truncated_results_are_incomplete(monkeypatch):
    monkeypatch.setattr("backend.correction_validation.run_ruff", lambda *args, **kwargs: {
        "status": "ok", "findings": [], "truncated": True})
    results = validate_corrections(tools_for("value = 1\n"), [edit(1, 1, "value = 2")])
    assert results[0]["status"] == "incomplete"


def test_validation_budget_exhaustion_is_explicit(monkeypatch):
    ticks = iter([0, 6])
    monkeypatch.setattr("backend.correction_validation.time", SimpleNamespace(monotonic=lambda: next(ticks)))
    results = validate_corrections(tools_for("value = 1\n"), [edit(1, 1, "value = 2")])
    assert results[0]["status"] == "incomplete"
    assert "time budget exceeded" in results[0]["message"]
    assert results[0]["syntax"]["status"] == "not_checked"


def test_analysis_limits_are_not_treated_as_passing(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Ruff should not run on input exceeding parser limits")

    monkeypatch.setattr("backend.correction_validation.run_ruff", unexpected)
    results = validate_corrections(tools_for("value = 1\n"), [edit(1, 1, "x" * 200001)])
    assert results[0]["status"] == "incomplete"
    assert results[0]["syntax"]["status"] == "limited"


def test_unsupported_source_mapping_is_explicit():
    results = validate_corrections(tools_for("# comment\fvalue = 1"), [edit(1, 1, "value = 2")])
    assert results[0]["status"] == "incomplete"
    assert results[0]["syntax"]["status"] == "not_checked"
    assert "cannot be reconstructed" in results[0]["message"]


def test_replacement_code_is_never_executed(tmp_path):
    marker = tmp_path / "executed"
    replacement = f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')"
    results = validate_corrections(tools_for("value = 1\n"), [edit(1, 1, replacement)])
    assert results[0]["syntax"]["status"] == "ok"
    assert not marker.exists()


def test_multiple_files_are_checked_independently():
    files = []
    for file_id in ("first", "second"):
        source = SourceFile(id=file_id, filename=file_id + ".py")
        extract_text(source, "value = 1\n")
        files.append(source)
    results = validate_corrections(SourceTools(files), [
        edit(1, 1, "value = 2", "first"), edit(1, 1, "value = (", "second")])
    assert [result["status"] for result in results] == ["checks_passed", "syntax_error"]
