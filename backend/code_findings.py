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


def render_finding(finding: dict) -> str:
    label = "Model review" if finding["tool"] == "model" else f"Ruff {finding['rule']}"
    lines = str(finding["line"])
    if finding.get("end_line", finding["line"]) != finding["line"]:
        lines += f"-{finding['end_line']}"
    column = f", column {finding['column']}" if finding.get("column") is not None else ""
    return (f"\n[{finding['severity']}] {label} — {finding['filename']}, line {lines}{column}: "
            f"{finding['message']} {finding['reasoning']}")
