"""Small browser UI server for Math OS."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

try:
    from math_os_prototype.math_os import run_pipeline
    from math_os_prototype.reasoning_pipeline import extract_answer, run_reasoning_pipeline
    from math_os_prototype.lift_backend import solve_from_lift_certificates
    from math_os_prototype.tool_adapters import ToolRegistry
except ImportError:  # Allows `python math_os_prototype\web_app.py`.
    from math_os import run_pipeline
    from reasoning_pipeline import extract_answer, run_reasoning_pipeline
    from lift_backend import solve_from_lift_certificates
    from tool_adapters import ToolRegistry


UI_DIR = Path(__file__).with_name("ui")
MAX_BODY_BYTES = 256_000


def solve_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    problem = str(payload.get("problem", "")).strip()
    if not problem:
        return {
            "ok": False,
            "error": "問題文を入力してください。",
        }

    full_pipeline = bool(payload.get("full_pipeline", True))
    external_tools = bool(payload.get("external_tools", False))
    live_retrieval = bool(payload.get("live_retrieval", False))
    allow_specialized = bool(payload.get("allow_specialized", False))
    allow_theorem_kernels_value = payload.get("allow_theorem_kernels")
    allow_theorem_kernels = (
        None if allow_theorem_kernels_value is None else bool(allow_theorem_kernels_value)
    )

    if full_pipeline:
        result = run_reasoning_pipeline(
            problem,
            external_tools=external_tools,
            live_retrieval=live_retrieval,
            allow_specialized=allow_specialized,
            allow_theorem_kernels=allow_theorem_kernels,
        )
        data = json.loads(result.to_json())
        return {
            "ok": True,
            "mode": "full_pipeline",
            "reply": result.explanation,
            "answer": extract_answer_from_pipeline_data(data),
            "data": data,
            "tool_status": ToolRegistry().status(),
        }

    ir = run_pipeline(
        problem,
        execute=True,
        external_tools=external_tools,
        allow_specialized=allow_specialized,
        allow_theorem_kernels=allow_theorem_kernels,
    )
    data = json.loads(ir.to_json())
    return {
        "ok": True,
        "mode": "direct_ir",
        "reply": build_ir_reply(ir),
        "answer": extract_answer(ir),
        "data": data,
        "tool_status": ToolRegistry().status(),
    }


def extract_answer_from_pipeline_data(data: dict[str, Any]) -> str | None:
    verifier_gate = data.get("verifier_gate") or {}
    if verifier_gate.get("status") == "rejected" or verifier_gate.get("rejection"):
        return None
    semantic_query_answer = extract_named_tool_answer(data, "sympy.semantic_query")
    if semantic_query_answer:
        return semantic_query_answer
    matrix_query_answer = extract_named_tool_answer(data, "sympy.matrix_semantic_query")
    if matrix_query_answer:
        return matrix_query_answer
    semantic_answer = extract_semantic_backend_answer(data)
    if semantic_answer:
        return semantic_answer
    dedicated_answer = extract_tool_answer(data, prefer_dedicated=True)
    if dedicated_answer:
        return dedicated_answer
    math_search = data.get("math_search", {})
    search_answer = math_search.get("answer")
    search_compatible = generic_search_matches_query(data)
    if math_search.get("status") == "solved_generic" and search_answer and search_compatible:
        return str(search_answer)
    tool_answer = extract_tool_answer(data, prefer_dedicated=False)
    if tool_answer:
        return tool_answer
    if search_answer and search_compatible:
        return str(search_answer)
    return None


def extract_named_tool_answer(data: dict[str, Any], tool_name: str) -> str | None:
    execution = data.get("tool_execution", {})
    for call in execution.get("tool_calls", []):
        if call.get("name") != tool_name or call.get("status") != "executed":
            continue
        result = call.get("result")
        if isinstance(result, dict) and result.get("answer_exact") is not None:
            return str(result["answer_exact"])
    return None


def generic_search_matches_query(data: dict[str, Any]) -> bool:
    structure = data.get("structural_ir") or {}
    operation_kinds = {
        str(item.get("kind") or "")
        for item in structure.get("operations", [])
        if isinstance(item, dict)
    }
    actions = {
        str(item.get("name") or "")
        for item in (data.get("math_search") or {}).get("actions", [])
        if isinstance(item, dict) and item.get("status") == "executed"
    }
    unresolved_observations = operation_kinds & {
        "aggregate",
        "measure",
        "optimize",
        "limit",
        "integral",
        "expectation",
        "correlation",
        "locus",
        "envelope",
        "passing_region",
    }
    if unresolved_observations and actions <= {"generic_sympy_solve", "generic_sympy_system_solve", "generic_wolfram_experiment"}:
        return False
    return True


def extract_semantic_backend_answer(data: dict[str, Any]) -> str | None:
    semantic_graph = data.get("semantic_graph")
    if not isinstance(semantic_graph, dict):
        return None
    try:
        result = solve_from_lift_certificates(semantic_graph)
    except Exception:
        return None
    if not isinstance(result, dict):
        return None
    if result.get("answer_exact") is not None:
        return str(result["answer_exact"])
    return None


def extract_tool_answer(data: dict[str, Any], *, prefer_dedicated: bool) -> str | None:
    execution = data.get("tool_execution", {})
    for call in execution.get("tool_calls", []):
        if prefer_dedicated and call.get("name") in {"sympy.solve", "sympy.algebra", "sympy.calculus"}:
            continue
        if call.get("status") != "executed":
            continue
        result = call.get("result")
        if not isinstance(result, dict):
            continue
        if result.get("answer_exact"):
            return str(result["answer_exact"])
        for key in ("solutions", "derivative", "remainder", "vertices"):
            if key in result:
                return str(result[key])
        inner = result.get("result")
        if isinstance(inner, dict):
            if inner.get("answer_exact"):
                return str(inner["answer_exact"])
            for key in ("solutions", "derivative", "remainder", "vertices"):
                if key in inner:
                    return str(inner[key])
            closed_form = inner.get("closed_form")
            if isinstance(closed_form, dict):
                return str(closed_form.get("inequality") or closed_form)
            for key in ("envelope_relation", "locus_relation", "readable"):
                if key in inner:
                    return str(inner[key])
    return None


def build_ir_reply(ir: Any) -> str:
    lines = [
        f"Intent: {ir.intent}",
        f"Route: {ir.route}",
    ]
    answer = extract_answer(ir)
    if answer:
        lines.append(f"Answer: {answer}")
    executed = [call.name for call in ir.tool_calls if call.status == "executed"]
    if executed:
        lines.append("Executed: " + ", ".join(executed))
    if ir.notes:
        lines.append("Notes: " + " / ".join(ir.notes))
    return "\n".join(lines)


class MathOsRequestHandler(BaseHTTPRequestHandler):
    server_version = "MathOSUI/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/status":
            self.write_json({"ok": True, "tool_status": ToolRegistry().status()})
            return
        if parsed.path == "/api/solve":
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/solve":
            self.write_json({"ok": False, "error": "unknown endpoint"}, status=404)
            return
        try:
            payload = self.read_json()
            result = solve_request_payload(payload)
            self.write_json(result, status=200 if result.get("ok") else 400)
        except Exception as exc:  # pragma: no cover - defensive HTTP boundary.
            self.write_json({"ok": False, "error": str(exc)}, status=500)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            raise ValueError("request body is too large")
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def serve_static(self, request_path: str) -> None:
        if request_path in ("", "/"):
            file_path = UI_DIR / "index.html"
        else:
            relative = unquote(request_path).lstrip("/")
            file_path = (UI_DIR / relative).resolve()
            if not str(file_path).startswith(str(UI_DIR.resolve())):
                self.send_error(403)
                return

        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return

        content = file_path.read_bytes()
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Math OS browser UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), MathOsRequestHandler)
    url = f"http://{args.host}:{args.port}/"
    print(f"Math OS UI running at {url}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Math OS UI.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
