import asyncio
import json

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.agent import BoundedAgent
from backend.answers import CodeAnswer, validate_citations
from backend.code_findings import model_corrections, preserve_correction_indentation
from backend.config import Settings
from backend.models import SourceFile
from backend.ollama import OllamaAdapter
from backend.sources import extract_text


EVIDENCE = [{"id": "span", "file_id": "file", "filename": "original.py", "location": "lines 1-3",
             "content": "def add(a, b):\n    return a - b\n"}]
CORRECTION = {"source_id": "span", "start_line": 2, "end_line": 2,
              "replacement_code": "    return a + b", "explanation": "Use addition to compute the sum."}


def payload(correction=None):
    return {"reply": "Potential issue with addition.", "source_ids": ["span"], "findings": [],
            "corrections": [CORRECTION if correction is None else correction]}


def test_correction_preserves_indentation_and_server_metadata():
    answer = CodeAnswer.model_validate(payload())
    validate_citations(answer, EVIDENCE)
    correction = model_corrections(answer.model_dump(), EVIDENCE)[0]
    assert correction["replacement_code"] == "    return a + b"
    assert correction["filename"] == "original.py" and correction["file_id"] == "file"
    assert correction["source_ids"] == ["span"]
    assert correction["validation_status"] == "not_checked"
    assert CodeAnswer.model_validate({"reply": "No issues.", "source_ids": ["span"], "findings": []}).corrections == []


@pytest.mark.parametrize("replacement,expected", [
    ("return a + b", "\treturn a + b"),
    ("\treturn a + b", "\treturn a + b"),
    ("if a:\n    return a + b", "if a:\n    return a + b"),
])
def test_single_line_indentation_comes_from_original_code(replacement, expected):
    correction = {**CORRECTION, "replacement_code": replacement,
                  "code_excerpt": {"lines": [{"line": 2, "code": "\treturn a - b"}], "truncated": False}}
    preserve_correction_indentation(correction)
    assert correction["replacement_code"] == expected


@pytest.mark.parametrize("change", [
    {"source_id": "foreign"}, {"start_line": 0}, {"end_line": 4}, {"start_line": 3, "end_line": 2},
    {"start_line": True}, {"replacement_code": " "}, {"explanation": " "},
    {"replacement_code": "x" * 4001}, {"explanation": "[source: forged]"},
    {"filename": "forged.py"}, {"validation_status": "passed"},
])
def test_malformed_corrections_are_rejected(change):
    with pytest.raises((ValueError, ValidationError)):
        validate_citations(CodeAnswer.model_validate(payload({**CORRECTION, **change})), EVIDENCE)


def test_overlapping_corrections_across_spans_in_same_file_are_rejected():
    evidence = [*EVIDENCE, {**EVIDENCE[0], "id": "second"}]
    answer = {**payload(), "corrections": [CORRECTION, {**CORRECTION, "source_id": "second"}]}
    with pytest.raises(ValueError, match="Overlapping"):
        validate_citations(CodeAnswer.model_validate(answer), evidence)


def test_separate_files_and_nonoverlapping_edits_are_supported():
    evidence = [*EVIDENCE, {**EVIDENCE[0], "id": "second", "file_id": "other"}]
    answer = {**payload(), "corrections": [CORRECTION, {**CORRECTION, "source_id": "second"},
                                          {**CORRECTION, "start_line": 3, "end_line": 3}]}
    validate_citations(CodeAnswer.model_validate(answer), evidence)


def test_invalid_correction_retries_and_recovers():
    calls = []

    def model(request):
        calls.append(json.loads(request.content))
        answer = payload({**CORRECTION, "source_id": "foreign"}) if len(calls) == 1 else payload()
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(answer)}})

    adapter = OllamaAdapter(Settings(), httpx.MockTransport(model))
    answer = asyncio.run(adapter.answer("code", "Correct the addition function", EVIDENCE, []))
    assert answer["corrections"] == [CORRECTION]
    assert len(calls) == 2
    assert calls[0]["format"]["properties"]["source_ids"]["items"]["enum"] == ["span"]
    assert calls[0]["format"]["properties"]["source_ids"]["maxItems"] == 1
    assert calls[0]["format"]["$defs"]["ModelCorrection"]["properties"]["source_id"]["enum"] == ["span"]
    assert "nonoverlapping line ranges" in calls[1]["messages"][-1]["content"]


def test_agent_rejects_unscoped_corrections_from_replacement_adapter():
    class Adapter:
        async def answer(self, *args):
            return {**payload(), "source_ids": [args[2][0]["id"]]}

    source = SourceFile(id="file", filename="original.py")
    extract_text(source, EVIDENCE[0]["content"])
    prepared = BoundedAgent().prepare("code", "Correct this function", [source], 4000)
    with pytest.raises(HTTPException) as error:
        asyncio.run(BoundedAgent().run(prepared, [], Adapter()))
    assert error.value.status_code == 502


def test_correction_sources_are_added_to_citations():
    class Adapter:
        async def answer(self, *args):
            return {**payload(), "source_ids": ["other"]}

    files = []
    for file_id, span_id in [("file", "span"), ("other-file", "other")]:
        source = SourceFile(id=file_id, filename=file_id + ".py")
        extract_text(source, EVIDENCE[0]["content"])
        source.spans[0].id = span_id
        files.append(source)
    prepared = BoundedAgent().prepare("code", "Correct this function", files, 6000)
    result = asyncio.run(BoundedAgent().run(prepared, [], Adapter()))
    assert result.answer["source_ids"] == ["other", "span"]
