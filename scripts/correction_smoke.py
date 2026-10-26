"""Live synthetic correction check: python -m scripts.correction_smoke."""

import asyncio
import json

import httpx

from backend.config import Settings
from backend.code_findings import model_corrections, preserve_correction_indentation
from backend.correction_validation import validate_corrections
from backend.models import SourceFile
from backend.ollama import OllamaAdapter
from backend.source_tools import SourceTools
from backend.sources import extract_text


async def main():
    evidence = [{"id": "sample", "file_id": "synthetic", "filename": "add.py", "location": "lines 1-3",
                 "content": 'def add(a, b):\n    """Return the sum of a and b."""\n    return a - b\n'}]
    class RecordingTransport(httpx.AsyncHTTPTransport):
        async def handle_async_request(self, request):
            response = await super().handle_async_request(request)
            await response.aread()
            self.last_response = response.json()
            return response

    transport = RecordingTransport()
    try:
        answer = await OllamaAdapter(Settings(), transport).answer(
            "code", "Correct this function so it returns the sum promised by its docstring. "
            "Return a correction replacing only line 3 with the addition statement, and explain it.", evidence, [])
    except Exception:
        # Only synthetic source is submitted by this diagnostic script.
        print(json.dumps(getattr(transport, "last_response", {}), indent=2))
        raise
    source = SourceFile(id="synthetic", filename="add.py")
    extract_text(source, evidence[0]["content"])
    tools = SourceTools([source])
    corrections = model_corrections(answer, evidence)
    for correction in corrections:
        correction["code_excerpt"] = tools.get_code_excerpt(
            correction["file_id"], correction["start_line"], correction["end_line"])
        preserve_correction_indentation(correction)
    validation = validate_corrections(tools, corrections)
    print(json.dumps({"findings": answer["findings"], "corrections": corrections,
                      "validation": validation}, indent=2))
    assert any(correction["start_line"] == correction["end_line"] == 3
               and correction["replacement_code"] == "    return a + b" for correction in corrections), (
        "The model did not propose the expected indented addition statement at line 3.")
    assert validation and all(result["status"] == "checks_passed" for result in validation)


if __name__ == "__main__":
    asyncio.run(main())
