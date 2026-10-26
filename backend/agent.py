"""Bounded, read-only orchestration over caller-authorized source files.

The HTTP layer owns authentication, persistence, expiry, and concurrency.
The adapter owns its at-most-two provider attempts. No tools execute uploads.
"""

import asyncio
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from fastapi import HTTPException
from pydantic import ValidationError

from backend.answers import answer_schema, validate_citations
from backend.models import SourceFile
from backend.source_tools import SourceTools
from backend.sources import select_evidence


class Route(StrEnum):
    DOCUMENT_SUMMARY = "document_summary"
    DOCUMENT_QA = "document_qa"
    CODE_EXPLANATION = "code_explanation"
    CODE_REVIEW = "code_review"


class Stage(StrEnum):
    CLASSIFY = "classify"
    SELECT_EVIDENCE = "select_evidence"
    MODEL_CALL = "model_call"
    SCHEMA_VALIDATION = "schema_validation"
    CITATION_VALIDATION = "citation_validation"
    RESPONSE = "response"


ROUTE_INSTRUCTIONS = {
    Route.DOCUMENT_SUMMARY: "Summarize the supplied excerpts, preserving key facts and qualifications.",
    Route.DOCUMENT_QA: "Answer the question using supplied evidence; state when the answer is absent.",
    Route.CODE_EXPLANATION: "Explain Python purpose, structure, and flow using the supplied source lines. "
        "Return findings as an empty array unless a potential issue is supported by the excerpts.",
    Route.CODE_REVIEW: "Review Python as text. Label suspected issues as potential, explain reasoning "
        "and source locations. Use supplied python_analysis only for structure and syntax diagnostics; "
        "Ruff findings are reported separately by the server; do not claim static checks beyond "
        "the supplied evidence or claim code execution. Keep reply to a neutral summary of at most two "
        "sentences; put all potential issues in findings. Each finding must identify a concrete failure "
        "mechanism and condition supported by the source. Do not assume undocumented input contracts "
        "or report ordinary unsupported inputs as bugs. Use medium for ordinary correctness risks; "
        "reserve high for source-supported security or data-loss risks. "
        "For each finding return severity (low/medium/high), source_id, start_line, end_line, "
        "message, and reasoning. Both line numbers must fall within that single supplied excerpt. "
        "Use at most eight findings; return an empty array when no potential issues are supported. "
        "For concrete issues you can fix from the excerpts, provide corrections with source_id, "
        "start_line, end_line, replacement_code, and explanation. Replacement code must replace the "
        "entire inclusive original line range, preserving Python indentation. Do not use Markdown fences, "
        "placeholders, or ellipses. Explain how each change addresses the issue. Keep changes minimal; "
        "do not invent requirements, silently remove behavior, or propose overlapping edits. "
        "Use at most four corrections; return [] when a reliable correction needs more context. "
        "These are untested suggestions; never claim they were executed or verified.",
}


def classify_request(mode: str, question: str) -> Route:
    # Only the explicit UI mode and user request choose a route; sources cannot.
    if mode == "document":
        return (Route.DOCUMENT_SUMMARY if re.search(r"\b(summar\w*|overview|key points)\b", question, re.IGNORECASE)
                else Route.DOCUMENT_QA)
    if mode == "code":
        return (Route.CODE_REVIEW if re.search(
            r"\b(review|bugs?|issues?|vulnerabilit\w*|security|lint|errors?|fix\w*|correct\w*|debug\w*)\b", question, re.IGNORECASE)
                else Route.CODE_EXPLANATION)
    raise HTTPException(422, "Mode must be document or code.")


class ModelAdapter(Protocol):
    async def answer(self, mode: str, question: str, evidence: list[dict],
                     history: list[dict], route: str | None = None) -> dict: ...


@dataclass(frozen=True)
class PreparedRequest:
    mode: str
    question: str
    route: Route
    evidence: list[dict]
    partial: bool
    warnings: tuple[str, ...] = ()
    tools: SourceTools | None = field(default=None, repr=False)


@dataclass(frozen=True)
class AgentResult:
    answer: dict
    stages: tuple[Stage, ...]
    static_analysis: dict | None = None


class BoundedAgent:
    def prepare(self, mode: str, question: str, files: list[SourceFile], budget: int) -> PreparedRequest:
        route = classify_request(mode, question)
        tools = SourceTools(files) if mode == "code" else None
        annotations, warnings = tools.python_annotations() if tools else ({}, [])
        evidence, partial = select_evidence(files, question, budget, annotations=annotations)
        if not evidence:
            raise HTTPException(422, "No source text is available. Reattach a text file or paste content.")
        if mode == "code" and any("python_analysis" not in span
                or span["python_analysis"]["symbols_omitted"] for span in evidence):
            warnings.append("Some Python structural details were omitted to fit the model context.")
        return PreparedRequest(mode, question, route, evidence, partial, tuple(warnings), tools)

    async def run(self, request: PreparedRequest, history: list[dict], adapter: ModelAdapter) -> AgentResult:
        stages = [Stage.CLASSIFY, Stage.SELECT_EVIDENCE, Stage.MODEL_CALL]
        static_analysis = await asyncio.to_thread(request.tools.check_python) if request.tools else None
        raw = await adapter.answer(request.mode, request.question, request.evidence, history, request.route.value)
        # Check every provider at the agent boundary, including replacement adapters.
        stages.append(Stage.SCHEMA_VALIDATION)
        try:
            if not isinstance(raw, dict):
                raise TypeError("Invalid provider answer")
            answer = answer_schema(request.mode).model_validate({k: v for k, v in raw.items()
                                                if k not in {"prompt_tokens", "output_tokens"}})
            stages.append(Stage.CITATION_VALIDATION)
            validate_citations(answer, request.evidence)
        except (ValueError, TypeError, ValidationError) as exc:
            raise HTTPException(502, "The model returned an invalid answer or citation. Please retry.") from exc
        stages.append(Stage.RESPONSE)
        finding_ids = [finding.source_id for finding in getattr(answer, "findings", [])]
        correction_ids = [correction.source_id for correction in getattr(answer, "corrections", [])]
        return AgentResult({**answer.model_dump(), "reply": answer.reply.strip(),
                            "source_ids": list(dict.fromkeys([*answer.source_ids, *finding_ids, *correction_ids])),
                            "prompt_tokens": raw.get("prompt_tokens"),
                            "output_tokens": raw.get("output_tokens")}, tuple(stages), static_analysis)
