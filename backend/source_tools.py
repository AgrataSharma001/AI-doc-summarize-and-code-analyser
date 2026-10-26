"""Read-only snapshots scoped to source files already authorized by the caller."""

import copy
import re
import time

from backend.models import SourceFile
from backend.python_analysis import analyze_python
from backend.ruff_analysis import MAX_FINDINGS, RULES, run_ruff


class SourceTools:
    def __init__(self, files: list[SourceFile]):
        self._files = {source.id: {
            "id": source.id, "filename": source.filename,
            "spans": [{"id": span.id, "file_id": source.id, "filename": source.filename,
                       "location": span.location, "content": span.content, "position": span.position}
                      for span in sorted(source.spans, key=lambda span: span.position)],
        } for source in files}
        self._spans = {span["id"]: span for source in self._files.values() for span in source["spans"]}
        self._analysis = {}
        self._texts = {}

    def get_source_span(self, span_id: str) -> dict:
        return copy.deepcopy(self._spans[span_id])

    def list_sections(self, file_id: str) -> list[dict]:
        return [{"source_id": span["id"], "location": span["location"]}
                for span in self._files[file_id]["spans"]]

    def get_python_text(self, file_id: str) -> str | None:
        """Return reconstructed authorized source, or None for unsupported mappings."""
        self.get_python_symbols(file_id)
        return self._texts.get(file_id)

    def get_code_excerpt(self, file_id: str, start_line: int, end_line: int) -> dict | None:
        """Read bounded original lines from the authorized file, never the model."""
        self.get_python_symbols(file_id)
        if file_id not in self._texts:
            return None
        lines = self._texts[file_id].split("\n")
        if not 1 <= start_line <= end_line <= len(lines):
            return None
        excerpt, remaining = [], 2000
        last_line = min(end_line, start_line + 7)
        truncated = last_line < end_line
        for number in range(start_line, last_line + 1):
            text = lines[number - 1]
            excerpt.append({"line": number, "code": text[:remaining]})
            remaining -= min(len(text), remaining)
            if len(text) > len(excerpt[-1]["code"]) or (remaining == 0 and number < end_line):
                truncated = True
                break
        return {"lines": excerpt, "truncated": truncated}

    def get_python_symbols(self, file_id: str) -> dict:
        if file_id not in self._analysis:
            source = self._files[file_id]
            # Restore skipped whitespace-only chunks using their original line locations.
            pieces = []
            line = 1
            for span in source["spans"]:
                location = re.fullmatch(r"lines (\d+)-(\d+)", span["location"] or "")
                if location is None or any(c in span["content"] for c in "\f\v\x85\u2028\u2029"):
                    self._analysis[file_id] = {"status": "unavailable", "symbols": [], "diagnostics": [{
                        "message": "Python outline unavailable for this source line mapping."}]}
                    break
                start = int(location[1])
                if start - line > 200_000:
                    self._analysis[file_id] = {"status": "limited", "symbols": [], "diagnostics": [{
                        "message": "Python source line limit exceeded."}]}
                    break
                gap = max(0, start - line)
                content = span["content"].replace("\r\n", "\n").replace("\r", "\n")
                pieces.extend(["\n" * gap, content])
                line += gap + content.count("\n")
            else:
                self._texts[file_id] = "".join(pieces)
                self._analysis[file_id] = analyze_python(self._texts[file_id])
        return copy.deepcopy(self._analysis[file_id])

    def python_annotations(self) -> tuple[dict, list[str]]:
        annotations, warnings = {}, []
        for file_id, source in self._files.items():
            analysis = self.get_python_symbols(file_id)
            if analysis["status"] != "ok":
                warnings.append(f"Python structural analysis for {source['filename']}: "
                                + analysis["diagnostics"][0]["message"])
            for span in source["spans"]:
                location = re.fullmatch(r"lines (\d+)-(\d+)", span["location"] or "")
                symbols = [] if location is None else [symbol for symbol in analysis["symbols"]
                    if symbol["start_line"] <= int(location[2]) and symbol["end_line"] >= int(location[1])]
                annotations[span["id"]] = {"python_analysis": {
                    "status": analysis["status"], "symbols": symbols[:20],
                    "symbols_omitted": len(symbols) > 20, "diagnostics": analysis["diagnostics"]}}
        return annotations, warnings


    def check_python(self) -> dict:
        """Run fixed checks within one five-second budget across scoped files."""
        deadline = time.monotonic() + 5
        findings, checks, warnings, sources, syntax_checks = [], [], [], {}, []
        for index, (file_id, source) in enumerate(self._files.items()):
            analysis = self.get_python_symbols(file_id)
            syntax_checks.append({"file_id": file_id, "filename": source["filename"],
                                  "status": analysis["status"]})
            syntax_findings = []
            if analysis["status"] == "syntax_error":
                for diagnostic in analysis["diagnostics"]:
                    syntax_findings.append({"tool": "python", "rule": diagnostic.get("error_type", "SyntaxError"),
                        "severity": "medium", "line": diagnostic["line"], "column": diagnostic["column"],
                        "message": diagnostic["message"],
                        "reasoning": "Python cannot compile this file. Fix this syntax error before checking runtime behavior."})
            remaining = deadline - time.monotonic()
            if index >= 5 or remaining <= 0 or len(findings) >= MAX_FINDINGS:
                result = {"status": "budget_exceeded", "findings": [], "truncated": False}
            elif analysis["status"] in {"limited", "unavailable"} or file_id not in self._texts:
                result = {"status": "skipped", "findings": [], "truncated": False}
            else:
                result = run_ruff(self._texts[file_id], timeout=min(3, remaining))
            checks.append({"file_id": file_id, "filename": source["filename"],
                           "status": result["status"], "rules": RULES, "truncated": result["truncated"]})
            if result["status"] != "ok":
                warnings.append(f"Ruff check for {source['filename']} did not complete ({result['status']}).")
            if result["truncated"]:
                warnings.append(f"Ruff findings for {source['filename']} were truncated.")
            # Prefer Python's precise syntax diagnostic over duplicate Ruff errors.
            ruff_findings = [finding for finding in result["findings"]
                             if not syntax_findings or finding["rule"] != "invalid-syntax"]
            for finding in syntax_findings + ruff_findings:
                matches = []
                for span in source["spans"]:
                    location = re.fullmatch(r"lines (\d+)-(\d+)", span["location"] or "")
                    if location and int(location[1]) <= finding["line"] <= int(location[2]):
                        matches.append(span["id"])
                if not matches:
                    warnings.append(f"An unmappable {finding['tool']} finding for {source['filename']} was omitted.")
                    continue
                if len(findings) >= MAX_FINDINGS:
                    checks[-1]["truncated"] = True
                    warnings.append("Ruff findings were truncated at the conversation limit.")
                    break
                for span_id in matches:
                    span = self._spans[span_id]
                    sources[span_id] = {k: span[k] for k in ("id", "file_id", "filename", "location")}
                findings.append({**finding, "file_id": file_id, "filename": source["filename"],
                                 "source_ids": matches})
        return {"findings": findings, "checks": checks, "warnings": list(dict.fromkeys(warnings)),
                "sources": list(sources.values()), "syntax_checks": syntax_checks}
