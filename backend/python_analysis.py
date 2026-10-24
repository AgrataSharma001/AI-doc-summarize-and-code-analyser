"""Bounded structural inspection. Uploaded Python is parsed, never imported or run."""

import ast
import io
import tokenize

MAX_CHARS = 200_000
MAX_TOKENS = 50_000
MAX_NESTING = 80
MAX_NODES = 50_000
MAX_SYMBOLS = 1000


def _syntax_result(result: dict, exc: SyntaxError) -> dict:
    return {**result, "status": "syntax_error", "diagnostics": [{
        "message": exc.msg[:200], "line": exc.lineno, "column": exc.offset,
        "error_type": type(exc).__name__}]}


def analyze_python(text: str) -> dict:
    result = {"status": "ok", "symbols": [], "diagnostics": []}
    if len(text) > MAX_CHARS:
        return {**result, "status": "limited", "diagnostics": [{"message": "Python analysis character limit exceeded."}]}
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    try:
        nesting = 0
        try:
            for count, token in enumerate(tokenize.generate_tokens(io.StringIO(text).readline), 1):
                if token.type == tokenize.OP:
                    nesting += int(token.string in "([{") - int(token.string in ")]}")
                if count > MAX_TOKENS or nesting > MAX_NESTING:
                    return {**result, "status": "limited", "diagnostics": [{"message": "Python token/nesting limit exceeded."}]}
        except tokenize.TokenError:
            # The parser locates an unclosed delimiter/string at its origin,
            # whereas tokenize often points beyond the end of the file.
            pass
        tree = ast.parse(text, filename="<uploaded Python>")
        stack = [(tree, "")]
        visited = 0
        while stack:
            node, scope = stack.pop()
            visited += 1
            if visited > MAX_NODES or len(result["symbols"]) >= MAX_SYMBOLS:
                return {**result, "status": "limited", "diagnostics": [{"message": "Python node/symbol limit exceeded; outline is partial."}]}
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified = f"{scope}.{node.name}" if scope else node.name
                start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
                result["symbols"].append({"name": node.name, "qualified_name": qualified,
                    "kind": "class" if isinstance(node, ast.ClassDef) else
                        "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                    "start_line": start, "definition_line": node.lineno, "end_line": node.end_lineno})
                scope = qualified
            stack.extend((child, scope) for child in reversed(list(ast.iter_child_nodes(node))))
        # AST parsing alone accepts e.g. `return` outside a function. Compile
        # the bounded tree to catch those errors; never execute the bytecode.
        compile(tree, "<uploaded Python>", "exec")
    except SyntaxError as exc:
        return _syntax_result(result, exc)
    except (RecursionError, MemoryError):
        return {**result, "status": "limited", "diagnostics": [{"message": "Python parser resource limit reached."}]}
    return result
