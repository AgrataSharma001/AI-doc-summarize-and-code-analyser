"""Bounded Ruff subprocess. Source is stdin data, never a program or filename."""

import json
import subprocess
import sys
import threading

MAX_OUTPUT_BYTES = 1024 * 1024
MAX_FINDINGS = 100
RULES = "F,B,S"


def _capture(command: list[str], text: str, timeout: float) -> tuple[str, bytes]:
    output = bytearray()
    overflow = threading.Event()
    try:
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, shell=False,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) as process:
            def write_input():
                try:
                    process.stdin.write(text.encode("utf-8"))
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

            def read_output():
                while chunk := process.stdout.read(65536):
                    if len(output) + len(chunk) > MAX_OUTPUT_BYTES:
                        overflow.set()
                        process.kill()
                        return
                    output.extend(chunk)

            writer = threading.Thread(target=write_input, daemon=True)
            reader = threading.Thread(target=read_output, daemon=True)
            writer.start()
            reader.start()
            status = "ok"
            try:
                process.wait(timeout=max(0.01, timeout))
            except subprocess.TimeoutExpired:
                status = "timeout"
                process.kill()
                process.wait()
            writer.join()
            reader.join()
            if overflow.is_set():
                status = "output_limit"
            elif status == "ok" and process.returncode not in {0, 1}:
                status = "unavailable"
            return status, bytes(output)
    except OSError:
        return "unavailable", b""


def run_ruff(text: str, timeout: float = 3) -> dict:
    if len(text) > 200_000:
        return {"status": "input_limit", "findings": [], "truncated": False}
    command = [sys.executable, "-I", "-B", "-m", "ruff", "check", "--isolated", "--no-cache",
               "--no-fix", "--ignore-noqa", "--select", RULES, "--output-format", "json",
               "--stdin-filename", "uploaded.py", "-"]
    status, output = _capture(command, text, timeout)
    if status != "ok":
        return {"status": status, "findings": [], "truncated": False}
    try:
        rows = json.loads(output)
        if not isinstance(rows, list):
            raise TypeError("Invalid Ruff output")
        findings = []
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        for row in rows[:MAX_FINDINGS]:
            code, message, location = row["code"], row["message"], row["location"]
            line, column = location["row"], location["column"]
            if (not isinstance(code, str) or not isinstance(message, str)
                    or type(line) is not int or type(column) is not int
                    or not 1 <= line <= len(lines) or not 1 <= column <= len(lines[line - 1]) + 1):
                raise ValueError("Invalid Ruff finding")
            # Screening priorities, not claims of exploitability or proven runtime failure.
            severity = "high" if code in {
                "S102", "S301", "S302", "S307", "S506", "S602", "S605", "S608"
            } else "medium" if code.startswith("S") or code in {
                "F821", "F822", "F823", "F631", "B006", "B008", "B023", "invalid-syntax"} else "low"
            reason = {
                "F821": "An undefined name may raise NameError when this path runs.",
                "F401": "An unused import may be unnecessary or indicate unfinished code.",
                "B006": "A mutable default is shared across calls and may retain unintended state.",
                "B008": "A call in a default argument runs at definition time rather than on each call.",
                "B023": "A closure may observe a changed loop variable instead of the intended value.",
                "S307": "Evaluating source strings can execute unintended code if input is untrusted.",
            }.get(code, f"Ruff matched rule {code}: {message[:500]}.")
            findings.append({"tool": "ruff", "rule": code, "severity": severity,
                             "line": line, "column": column, "message": message[:500],
                             "reasoning": reason + " This is a potential issue; verify its relevance in context."})
        return {"status": "ok", "findings": findings, "truncated": len(rows) > MAX_FINDINGS}
    except (ValueError, KeyError, TypeError, UnicodeError):
        return {"status": "invalid_output", "findings": [], "truncated": False}
