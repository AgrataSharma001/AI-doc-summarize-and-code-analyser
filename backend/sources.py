"""Non-executing UTF-8 extraction and bounded evidence selection."""

import re
from uuid import uuid4

from fastapi import HTTPException

from backend.models import SourceFile, SourceSpan

MAX_SOURCE_CHARS = 200_000
MAX_CONVERSATION_CHARS = 500_000
SPAN_CHARS = 1600


def extract_text(source: SourceFile, text: str, location_prefix: str = "", *, structure: str = "lines") -> None:
    if len(text) > MAX_SOURCE_CHARS:
        raise HTTPException(413, "Text source exceeds 200,000 characters. Split it into smaller files.")
    if not text.strip():
        raise HTTPException(422, "Provide nonblank source text.")
    if any(ord(c) < 32 and c not in "\t\n\r\f" for c in text):
        raise HTTPException(422, "Source text contains binary control characters.")
    section = ""
    fence = ""
    fence_size = 0
    parts = []
    size = 0
    start = 1
    end = 1

    def flush():
        nonlocal parts, size
        content = "".join(parts)
        if content.strip():
            source.spans.append(SourceSpan(id=str(uuid4()), file_id=source.id,
                position=len(source.spans), location=f"{location_prefix}{section}lines {start}-{end}", content=content))
        parts, size = [], 0

    lines = text.splitlines(keepends=True)
    for line_number, line in enumerate(lines, 1):
        # Keep titles as bounded display metadata, with originals in the text.
        if structure == "markdown" and not fence:
            heading = re.match(r"^ {0,3}#{1,6}[ \t]+(.+?)\s*$", line)
            setext = (line.strip() and line_number < len(lines)
                and re.fullmatch(r" {0,3}(?:=+|-+)[ \t]*(?:\r?\n)?", lines[line_number])
                and not line.startswith(("    ", "\t")))
            if heading or setext:
                flush()
                title = heading.group(1) if heading else line.strip()
                title = re.sub(r"[ \t]+#+$", "", title)
                section = f"section {title[:60]}, "
        if structure == "markdown":
            marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line.rstrip("\r\n"))
            if marker:
                run, tail = marker.groups()
                if not fence and (run[0] != "`" or "`" not in tail):
                    fence, fence_size = run[0], len(run)
                elif fence == run[0] and len(run) >= fence_size and not tail.strip():
                    fence = ""
        # Very long lines become several spans with the same valid line location.
        offset = 0
        while offset < len(line):
            length = min(SPAN_CHARS, len(line) - offset)
            # Keep a trailing line ending attached to nonblank text, even
            # when a long line is exactly at the chunk-size boundary.
            tail = line[offset + length:] if len(line) - offset - length <= 2 else ""
            if tail and len(tail) <= 2 and not tail.strip():
                length -= 2
            segment = line[offset:offset + length]
            offset += length
            if parts and size + len(segment) > SPAN_CHARS:
                flush()
            if not parts:
                start = line_number
            end = line_number
            parts.append(segment)
            size += len(segment)
        if structure != "lines" and not fence and not line.strip():
            flush()
    flush()


def select_evidence(files: list[SourceFile], question: str, budget: int) -> tuple[list[dict], bool]:
    spans = [{"id": span.id, "file_id": source.id, "filename": source.filename,
              "location": span.location, "content": span.content}
             for source in files for span in sorted(source.spans, key=lambda s: s.position)]
    terms = set(re.findall(r"\w{3,}", question.lower()))
    # Keep source order when scores tie; targeted follow-ups promote relevant spans.
    ranked = sorted(enumerate(spans), key=lambda item: (
        -len(terms & set(re.findall(r"\w{3,}", (item[1]["content"] + " " + (item[1]["location"] or "")).lower()))), item[0]))
    chosen, used = [], 0
    for index, span in ranked:
        cost = len(span["content"]) + len(span["filename"]) + 160
        if used + cost <= budget:
            chosen.append((index, span))
            used += cost
    chosen.sort(key=lambda item: item[0])
    return [span for _, span in chosen], len(chosen) < len(spans)
