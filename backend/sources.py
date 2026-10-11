"""Non-executing UTF-8 extraction and bounded evidence selection."""

import re
from uuid import uuid4

from fastapi import HTTPException

from backend.models import SourceFile, SourceSpan

MAX_SOURCE_CHARS = 200_000
MAX_CONVERSATION_CHARS = 500_000
SPAN_CHARS = 1600


def extract_text(source: SourceFile, text: str) -> None:
    if len(text) > MAX_SOURCE_CHARS:
        raise HTTPException(413, "Text source exceeds 200,000 characters. Split it into smaller files.")
    if not text.strip():
        raise HTTPException(422, "Provide nonblank source text.")
    if any(ord(c) < 32 and c not in "\t\n\r\f" for c in text):
        raise HTTPException(422, "Source text contains binary control characters.")
    parts = []
    size = 0
    start = 1
    end = 1

    def flush():
        nonlocal parts, size
        content = "".join(parts)
        if content.strip():
            source.spans.append(SourceSpan(id=str(uuid4()), file_id=source.id,
                position=len(source.spans), location=f"lines {start}-{end}", content=content))
        parts, size = [], 0

    for line_number, line in enumerate(text.splitlines(keepends=True), 1):
        # Very long lines become several spans with the same valid line location.
        for offset in range(0, len(line), SPAN_CHARS):
            segment = line[offset:offset + SPAN_CHARS]
            if parts and size + len(segment) > SPAN_CHARS:
                flush()
            if not parts:
                start = line_number
            end = line_number
            parts.append(segment)
            size += len(segment)
    flush()


def select_evidence(files: list[SourceFile], question: str, budget: int) -> tuple[list[dict], bool]:
    spans = [{"id": span.id, "file_id": source.id, "filename": source.filename,
              "location": span.location, "content": span.content}
             for source in files for span in sorted(source.spans, key=lambda s: s.position)]
    terms = set(re.findall(r"\w{3,}", question.lower()))
    # Keep source order when scores tie; targeted follow-ups promote relevant spans.
    ranked = sorted(enumerate(spans), key=lambda item: (
        -len(terms & set(re.findall(r"\w{3,}", item[1]["content"].lower()))), item[0]))
    chosen, used = [], 0
    for index, span in ranked:
        cost = len(span["content"]) + len(span["filename"]) + 160
        if used + cost <= budget:
            chosen.append((index, span))
            used += cost
    chosen.sort(key=lambda item: item[0])
    return [span for _, span in chosen], len(chosen) < len(spans)
