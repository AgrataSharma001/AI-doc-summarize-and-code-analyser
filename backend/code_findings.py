"""Derive model finding provenance and render validated potential issues."""


def model_findings(answer: dict, evidence: list[dict]) -> list[dict]:
    spans = {span["id"]: span for span in evidence}
    findings = []
    for finding in answer.get("findings", []):
        span = spans[finding["source_id"]]
        findings.append({"tool": "model", "rule": None, "severity": finding["severity"],
                         "file_id": span["file_id"], "filename": span["filename"],
                         "line": finding["start_line"], "end_line": finding["end_line"], "column": None,
                         "message": finding["message"].strip(), "reasoning": finding["reasoning"].strip(),
                         "source_ids": [span["id"]]})
    return findings


def model_corrections(answer: dict, evidence: list[dict]) -> list[dict]:
    spans = {span["id"]: span for span in evidence}
    return [{"file_id": spans[correction["source_id"]]["file_id"],
             "filename": spans[correction["source_id"]]["filename"],
             "source_ids": [correction["source_id"]],
             "start_line": correction["start_line"], "end_line": correction["end_line"],
             "replacement_code": correction["replacement_code"],
             "explanation": correction["explanation"].strip(), "validation_status": "not_checked"}
            for correction in answer.get("corrections", [])]


def render_correction(correction: dict) -> str:
    result = (f"\n{correction['filename']} — replace lines {correction['start_line']}-{correction['end_line']}\n"
              "Suggested replacement code:\n" + correction["replacement_code"])
    return result + f"\nWhy this helps: {correction['explanation']}\n"


def preserve_correction_indentation(correction: dict) -> None:
    """Restore omitted indentation for a single replacement statement."""
    excerpt = correction.get("code_excerpt")
    code = correction["replacement_code"]
    if (correction["start_line"] != correction["end_line"] or not excerpt or excerpt["truncated"]
            or len(code.splitlines()) != 1 or code[0].isspace()):
        return
    original = excerpt["lines"][0]["code"]
    indentation = original[:len(original) - len(original.lstrip(" \t"))]
    if len(indentation + code) <= 4000:
        correction["replacement_code"] = indentation + code


def render_finding(finding: dict) -> str:
    label = ("Model review" if finding["tool"] == "model" else
             f"Python {finding['rule']}" if finding["tool"] == "python" else f"Ruff {finding['rule']}")
    lines = str(finding["line"])
    if finding.get("end_line", finding["line"]) != finding["line"]:
        lines += f"-{finding['end_line']}"
    column = f", column {finding['column']}" if finding.get("column") is not None else ""
    result = (f"\n[{finding['severity']}] {label} — {finding['filename']}, line {lines}{column}\n"
              f"Issue: {finding['message']}\nOriginal code:")
    excerpt = finding.get("code_excerpt")
    if excerpt:
        result += "".join(f"\n  {row['line']} | {row['code']}" for row in excerpt["lines"])
        if excerpt["truncated"]:
            result += "\n  [Code excerpt shortened; see the original file for the full range.]"
    else:
        result += "\n  Unavailable for this source line mapping."
    return result + f"\nReason: {finding['reasoning']}\n"
