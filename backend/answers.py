"""Provider-independent answer schema and evidence-reference validation."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    reply: str = Field(min_length=1, max_length=12000)
    source_ids: list[str] = Field(min_length=1, max_length=20)


class ModelFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    severity: Literal["low", "medium", "high"]
    source_id: str = Field(min_length=1, max_length=64)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=500)
    reasoning: str = Field(min_length=1, max_length=1000)


class ModelCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_id: str = Field(min_length=1, max_length=64)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    replacement_code: str = Field(min_length=1, max_length=4000)
    explanation: str = Field(min_length=1, max_length=1000)


class CodeAnswer(ModelAnswer):
    findings: list[ModelFinding] = Field(max_length=8)
    corrections: list[ModelCorrection] = Field(default_factory=list, max_length=4)


def answer_schema(mode: str) -> type[ModelAnswer]:
    return CodeAnswer if mode == "code" else ModelAnswer


def validate_citations(answer: ModelAnswer, evidence: list[dict]) -> None:
    allowed = {span["id"] for span in evidence}
    if (not answer.reply.strip() or not set(answer.source_ids) <= allowed
            or len(set(answer.source_ids)) != len(answer.source_ids)
            or "[source:" in answer.reply.lower()):
        raise ValueError("Invalid answer references")

    if isinstance(answer, CodeAnswer):
        spans = {span["id"]: span for span in evidence}
        seen = set()
        for finding in answer.findings:
            span = spans.get(finding.source_id)
            bounds = re.fullmatch(r"lines (\d+)-(\d+)", (span.get("location") or "")) if span else None
            key = (finding.source_id, finding.start_line, finding.end_line, finding.message.strip())
            if (bounds is None or not int(bounds[1]) <= finding.start_line <= finding.end_line <= int(bounds[2])
                    or not finding.message.strip() or not finding.reasoning.strip()
                    or "[source:" in (finding.message + finding.reasoning).lower() or key in seen):
                raise ValueError("Invalid model finding or source lines")
            seen.add(key)
        ranges = {}
        for correction in answer.corrections:
            span = spans.get(correction.source_id)
            bounds = re.fullmatch(r"lines (\d+)-(\d+)", (span.get("location") or "")) if span else None
            if (bounds is None or not int(bounds[1]) <= correction.start_line <= correction.end_line <= int(bounds[2])
                    or not correction.replacement_code.strip() or not correction.explanation.strip()
                    or "[source:" in correction.explanation.lower()):
                raise ValueError("Invalid correction or source lines")
            # A single proposal cannot contain conflicting edits to the same file.
            file_id = span["file_id"]
            if any(start <= correction.end_line and end >= correction.start_line
                   for start, end in ranges.get(file_id, [])):
                raise ValueError("Overlapping corrections")
            ranges.setdefault(file_id, []).append((correction.start_line, correction.end_line))
