"""Check proposed edits on in-memory copies. Never execute or save proposed code."""

import time

from backend.python_analysis import analyze_python
from backend.ruff_analysis import run_ruff
from backend.source_tools import SourceTools


def apply_corrections(text: str, corrections: list[dict]) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines(keepends=True)
    ordered = sorted(corrections, key=lambda item: item["start_line"])
    previous_end = 0
    for correction in ordered:
        start, end = correction["start_line"], correction["end_line"]
        if not previous_end < start <= end <= len(lines):
            raise ValueError("Invalid or overlapping replacement line ranges.")
        previous_end = end
    # Apply from the bottom so inserted/deleted lines cannot shift later edits.
    for correction in reversed(ordered):
        start, end = correction["start_line"], correction["end_line"]
        replacement = correction["replacement_code"].replace("\r\n", "\n").replace("\r", "\n")
        if lines[end - 1].endswith("\n") and not replacement.endswith("\n"):
            replacement += "\n"
        lines[start - 1:end] = [replacement]
    return "".join(lines)


def validate_corrections(tools: SourceTools, corrections: list[dict]) -> list[dict]:
    """Validate all proposed edits together per file within a five-second budget."""
    grouped = {}
    for correction in corrections:
        grouped.setdefault(correction["file_id"], []).append(correction)
    results = []
    deadline = time.monotonic() + 5
    for file_id, edits in grouped.items():
        result = {"file_id": file_id, "filename": edits[0]["filename"], "status": "incomplete",
                  "syntax": {"status": "not_checked", "diagnostics": []},
                  "ruff": {"status": "skipped", "findings": [], "truncated": False}}
        original = tools.get_python_text(file_id)
        if original is None:
            result["message"] = "Original source cannot be reconstructed with reliable line locations."
        elif time.monotonic() >= deadline:
            result["message"] = "Correction validation time budget exceeded."
        else:
            try:
                proposed = apply_corrections(original, edits)
            except ValueError as exc:
                result.update(status="invalid_edit", message=str(exc))
            else:
                syntax = analyze_python(proposed)
                result["syntax"] = {"status": syntax["status"], "diagnostics": syntax["diagnostics"]}
                remaining = deadline - time.monotonic()
                if syntax["status"] == "limited":
                    result["message"] = "Proposed code exceeds Python analysis limits."
                elif remaining <= 0:
                    result["message"] = "Correction validation time budget exceeded."
                else:
                    result["ruff"] = run_ruff(proposed, timeout=min(3, remaining))
                if syntax["status"] == "syntax_error":
                    result["status"] = "syntax_error"
                elif (syntax["status"] != "ok" or result["ruff"]["status"] != "ok"
                      or result["ruff"]["truncated"]):
                    result["status"] = "incomplete"
                elif result["ruff"]["findings"]:
                    result["status"] = "issues_remaining"
                else:
                    result["status"] = "checks_passed"
        for correction in edits:
            correction["validation_status"] = result["status"]
        results.append(result)
    return results


def render_validation(results: list[dict]) -> str:
    labels = {
        "checks_passed": "Python syntax and configured Ruff checks passed. Runtime behavior has not been tested.",
        "syntax_error": "Proposed code has a Python syntax error; review the replacement.",
        "issues_remaining": "Python syntax passed, but Ruff still reports potential issues.",
        "incomplete": "Checks could not complete; this proposal has not passed validation.",
        "invalid_edit": "Replacement ranges could not be applied to the original file.",
    }
    text = "\n\nCorrection validation (all suggested edits applied together per file):"
    for result in results:
        text += f"\n{result['filename']}: {labels[result['status']]}"
        if result.get("message"):
            text += "\n" + result["message"]
        text += f"\nPython syntax: {result['syntax']['status']}; Ruff: {result['ruff']['status']}."
        for diagnostic in result["syntax"]["diagnostics"]:
            text += f"\nProposed file, line {diagnostic.get('line', '?')}: {diagnostic['message']}"
        for finding in result["ruff"]["findings"]:
            text += f"\nProposed file, line {finding['line']}, Ruff {finding['rule']}: {finding['message']}"
        if result["ruff"]["truncated"]:
            text += "\nRemaining findings were shortened; additional issues may be omitted."
    return text
