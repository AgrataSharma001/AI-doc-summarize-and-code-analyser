import json
import sys

import pytest

from backend.models import SourceFile
from backend.ruff_analysis import _capture, run_ruff
from backend.source_tools import SourceTools
from backend.sources import extract_text


def tools_for(text):
    source = SourceFile(id="file", filename="sample.py")
    extract_text(source, text)
    return SourceTools([source]), source


def test_real_ruff_reports_rules_and_locations_and_ignores_noqa():
    result = run_ruff("import os\nprint(missing)  # noqa: F821\ndef fn(items=[]):\n    return items\n")
    assert result["status"] == "ok"
    findings = {f["rule"]: f for f in result["findings"]}
    assert {"F401", "F821", "B006"} <= findings.keys()
    assert (findings["F821"]["line"], findings["F821"]["column"]) == (2, 7)
    assert findings["F821"]["severity"] == "medium"
    assert "potential issue" in findings["F821"]["reasoning"]


def test_isolated_check_ignores_repo_config_and_does_not_execute(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text('[tool.ruff.lint]\nignore = ["ALL"]\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    marker = tmp_path / "executed"
    text = f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\neval('1')\n"
    result = run_ruff(text)
    assert result["status"] == "ok"
    assert any(f["rule"] == "S307" and f["severity"] == "high" for f in result["findings"])
    assert not marker.exists()
    assert not (tmp_path / ".ruff_cache").exists()
    assert not (tmp_path / "uploaded.py").exists()


def test_findings_map_to_retained_source_ids_and_original_lines():
    tools, source = tools_for("# " + "x" * 5000 + "\n" + "\n" * 2000 + "print(missing)\n")
    result = tools.check_python()
    finding = next(f for f in result["findings"] if f["rule"] == "F821")
    assert finding["line"] == 2002
    assert finding["file_id"] == "file" and finding["filename"] == "sample.py"
    assert set(finding["source_ids"]) <= {s.id for s in source.spans}
    assert all("2002" in s["location"] for s in result["sources"])


def test_timeout_kills_checker():
    status, output = _capture([sys.executable, "-I", "-c", "import time; time.sleep(10)"], "", 0.05)
    assert status == "timeout" and output == b""


def test_output_limit_kills_checker(monkeypatch):
    monkeypatch.setattr("backend.ruff_analysis.MAX_OUTPUT_BYTES", 100)
    status, output = _capture([sys.executable, "-I", "-c", "print('x' * 10000)"], "", 2)
    assert status == "output_limit" and len(output) <= 100


@pytest.mark.parametrize("status", ["timeout", "output_limit", "unavailable"])
def test_checker_failures_are_explicit_and_return_no_findings(monkeypatch, status):
    monkeypatch.setattr("backend.ruff_analysis._capture", lambda *args: (status, b"private details"))
    tools, _ = tools_for("x = 1")
    result = tools.check_python()
    assert result["checks"][0]["status"] == status
    assert result["findings"] == [] and result["warnings"]
    assert "private details" not in str(result)


@pytest.mark.parametrize("output", [b"not json", b"{}", b'[{}]',
    b'[{"code":"F821","message":"bad","location":{"row":999,"column":1}}]'])
def test_invalid_checker_output_is_rejected(monkeypatch, output):
    monkeypatch.setattr("backend.ruff_analysis._capture", lambda *args: ("ok", output))
    assert run_ruff("x = 1")["status"] == "invalid_output"


def test_output_count_and_file_count_limits(monkeypatch):
    row = {"code": "F821", "message": "Undefined name", "location": {"row": 1, "column": 1}}
    monkeypatch.setattr("backend.ruff_analysis._capture", lambda *args: ("ok", json.dumps([row] * 150).encode()))
    result = run_ruff("x")
    assert result["truncated"] and len(result["findings"]) == 100
    files = []
    for i in range(6):
        source = SourceFile(id=str(i), filename=f"{i}.py")
        extract_text(source, "x = 1")
        files.append(source)
    monkeypatch.setattr("backend.source_tools.run_ruff", lambda *args, **kwargs: {
        "status": "ok", "findings": [], "truncated": False})
    result = SourceTools(files).check_python()
    assert [c["status"] for c in result["checks"]] == ["ok"] * 5 + ["budget_exceeded"]
    assert result["warnings"]


def test_analysis_limits_skip_ruff(monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Ruff should not run on limited parser input")

    monkeypatch.setattr("backend.source_tools.run_ruff", unexpected)
    tools, _ = tools_for("x = " + "(" * 81 + "1" + ")" * 81)
    result = tools.check_python()
    assert result["checks"][0]["status"] == "skipped"
    assert result["warnings"]
