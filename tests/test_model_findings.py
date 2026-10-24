import asyncio
import copy
import json

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.agent import BoundedAgent
from backend.answers import CodeAnswer, ModelAnswer, validate_citations
from backend.code_findings import model_findings
from backend.config import Settings
from backend.models import SourceFile
from backend.ollama import OllamaAdapter
from backend.sources import extract_text

EVIDENCE = [{"id": "visible", "file_id": "file", "filename": "real.py", "location": "lines 5-8",
             "content": "def ratio(total, count):\n    return total / count\n"}]
FINDING = {"severity": "medium", "source_id": "visible", "start_line": 6, "end_line": 6,
           "message": "Potential division by zero", "reasoning": "If count is zero, division may raise ZeroDivisionError."}


def payload(finding=None):
    return {"reply": "This function computes a ratio.", "source_ids": ["visible"],
            "findings": [copy.deepcopy(FINDING if finding is None else finding)]}


def test_valid_finding_preserves_schema_and_line_range():
    answer = CodeAnswer.model_validate(payload())
    validate_citations(answer, EVIDENCE)
    assert answer.findings[0].start_line == 6
    assert CodeAnswer.model_validate({**payload(), "findings": []}).findings == []
    with pytest.raises(ValidationError):
        ModelAnswer.model_validate(payload())


@pytest.mark.parametrize("change", [
    {"source_id": "stored-but-not-selected"}, {"start_line": 4}, {"end_line": 9},
    {"start_line": 7, "end_line": 6}, {"severity": "critical"}, {"start_line": True},
    {"start_line": "6"}, {"message": " "}, {"reasoning": " "},
    {"filename": "forged.py"}, {"file_id": "foreign"},
    {"message": "[source: forged]"}, {"reasoning": "[SOURCE: forged]"},
])
def test_invalid_finding_is_rejected(change):
    finding = {**FINDING, **change}
    with pytest.raises((ValueError, ValidationError)):
        validate_citations(CodeAnswer.model_validate(payload(finding)), EVIDENCE)


def test_missing_excess_and_duplicate_findings_are_rejected():
    for invalid in [
        {"reply": "answer", "source_ids": ["visible"]},
        {**payload(), "findings": [FINDING] * 9},
        {**payload(), "findings": [FINDING, FINDING]},
    ]:
        with pytest.raises((ValueError, ValidationError)):
            validate_citations(CodeAnswer.model_validate(invalid), EVIDENCE)
    with pytest.raises(ValueError):
        validate_citations(CodeAnswer.model_validate(payload()), [{**EVIDENCE[0], "location": "page 1, lines 5-8"}])


@pytest.mark.parametrize("recover", [False, True])
def test_adapter_retries_invalid_finding_once(recover):
    calls = []

    def model(request):
        body = json.loads(request.content)
        calls.append(body)
        answer = payload() if recover and len(calls) == 2 else payload({**FINDING, "end_line": 99})
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(answer)}})

    adapter = OllamaAdapter(Settings(), httpx.MockTransport(model))
    if recover:
        answer = asyncio.run(adapter.answer("code", "Review", EVIDENCE, []))
        assert answer["findings"] == [FINDING]
    else:
        with pytest.raises(HTTPException) as error:
            asyncio.run(adapter.answer("code", "Review", EVIDENCE, []))
        assert error.value.status_code == 502
    assert len(calls) == 2
    assert "findings" in calls[0]["format"]["required"]
    assert calls[0]["options"]["num_predict"] == 2048
    assert "valid severity and line range" in calls[1]["messages"][-1]["content"]


def test_replacement_adapter_cannot_bypass_finding_validation(monkeypatch):
    class InvalidAdapter:
        async def answer(self, *args):
            return payload()

    source = SourceFile(id="file", filename="real.py")
    extract_text(source, "def ratio(total, count):\n    return total / count\n")
    monkeypatch.setattr("backend.source_tools.SourceTools.check_python", lambda self: {
        "findings": [], "sources": [], "warnings": [], "checks": []})
    request = BoundedAgent().prepare("code", "Review", [source], 4000)
    with pytest.raises(HTTPException) as error:
        asyncio.run(BoundedAgent().run(request, [], InvalidAdapter()))
    assert error.value.status_code == 502


def test_finding_source_is_added_to_answer_citations_and_metadata_is_server_derived(monkeypatch):
    class Adapter:
        async def answer(self, *args):
            return {"reply": "Two functions.", "source_ids": ["first-span"], "findings": [{
                **FINDING, "source_id": "second-span", "start_line": 2, "end_line": 2,
            }]}

    files = []
    for name, span_id in [("first.py", "first-span"), ("second.py", "second-span")]:
        source = SourceFile(id=name, filename=name)
        extract_text(source, "def ratio(total, count):\n    return total / count\n")
        source.spans[0].id = span_id
        files.append(source)
    monkeypatch.setattr("backend.source_tools.SourceTools.check_python", lambda self: {
        "findings": [], "sources": [], "warnings": [], "checks": []})
    prepared = BoundedAgent().prepare("code", "Review", files, 6000)
    result = asyncio.run(BoundedAgent().run(prepared, [], Adapter()))
    assert result.answer["source_ids"] == ["first-span", "second-span"]
    finding = model_findings(result.answer, prepared.evidence)[0]
    assert finding["filename"] == finding["file_id"] == "second.py"
    assert finding["source_ids"] == ["second-span"]
