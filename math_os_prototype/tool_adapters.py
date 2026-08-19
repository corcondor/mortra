"""Tool adapters and local tool discovery for Math OS."""

from __future__ import annotations

import json
import importlib.util
import os
import signal
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolExecution:
    tool: str
    available: bool
    command: list[str] | str
    status: str
    result: Any | None = None
    stdout: str | None = None
    stderr: str | None = None
    error: str | None = None
    executable_path: str | None = None
    elapsed_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SymPyAdapter:
    name = "sympy"

    def is_available(self) -> bool:
        try:
            import sympy  # noqa: F401
        except ImportError:
            return False
        return True

    def describe_geometry_result(self, problem: Any, result: dict[str, Any]) -> ToolExecution:
        return ToolExecution(
            tool=self.name,
            available=self.is_available(),
            command=sympy_command_for_geometry(problem),
            status="executed" if self.is_available() else "unavailable",
            result=result if self.is_available() else None,
            error=None if self.is_available() else "SymPy is not installed.",
        )


class WolframAdapter:
    name = "wolfram"

    def __init__(self, executable: str | None = None, timeout_seconds: int = 120):
        self.executable = executable or find_wolfram_executable()
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        return self.executable is not None

    def status(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "available": self.is_available(),
            "executable_path": self.executable,
            "timeout_seconds": self.timeout_seconds,
        }

    def execute_geometry(self, problem: Any) -> ToolExecution:
        code = wolfram_code_for_geometry(problem)
        return self.execute_code(code, label="geometry")

    def execute_code(self, code: str, *, label: str = "code") -> ToolExecution:
        command = [self.executable or "wolframscript", "-code", code]
        if not self.executable:
            return ToolExecution(
                tool=self.name,
                available=False,
                command=command,
                status="unavailable",
                error="wolframscript was not found on PATH or in known Wolfram install folders.",
            )

        started = time.monotonic()
        creationflags = (
            subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        )
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creationflags,
                start_new_session=os.name != "nt",
            )
            stdout, stderr = process.communicate(timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            else:  # pragma: no cover - exercised by GitHub Actions if available
                os.killpg(process.pid, signal.SIGKILL)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout, stderr = exc.stdout or "", exc.stderr or ""
            return ToolExecution(
                tool=self.name,
                available=True,
                executable_path=self.executable,
                command=command,
                status="timeout",
                stdout=(stdout or None),
                stderr=(stderr or None),
                error=f"wolframscript timed out after {self.timeout_seconds}s",
                elapsed_seconds=round(time.monotonic() - started, 3),
            )
        except OSError as exc:
            return ToolExecution(
                tool=self.name,
                available=True,
                executable_path=self.executable,
                command=command,
                status="failed",
                error=str(exc),
                elapsed_seconds=round(time.monotonic() - started, 3),
            )

        status = "executed" if process.returncode == 0 else "failed"
        stdout = stdout.strip()
        stderr = stderr.strip()
        return ToolExecution(
            tool=self.name,
            available=True,
            executable_path=self.executable,
            command=command,
            status=status,
            result={"label": label, "wolfram_inputform": stdout}
            if process.returncode == 0
            else None,
            stdout=stdout or None,
            stderr=stderr or None,
            error=None
            if process.returncode == 0
            else f"wolframscript exited with code {process.returncode}",
            elapsed_seconds=round(time.monotonic() - started, 3),
        )


class PythonPackageAdapter:
    def __init__(self, name: str, module_name: str):
        self.name = name
        self.module_name = module_name

    def is_available(self) -> bool:
        return importlib.util.find_spec(self.module_name) is not None

    def status(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "available": self.is_available(),
            "module": self.module_name,
        }


class LeanAdapter:
    name = "lean"

    def __init__(self):
        self.executable = shutil.which("lean")
        self.lake = shutil.which("lake")

    def is_available(self) -> bool:
        return self.executable is not None

    def status(self) -> dict[str, Any]:
        return {
            "tool": self.name,
            "available": self.is_available(),
            "executable_path": self.executable,
            "lake_path": self.lake,
        }


class ToolRegistry:
    def __init__(self, wolfram_timeout_seconds: int = 120):
        self.sympy = SymPyAdapter()
        self.wolfram = WolframAdapter(timeout_seconds=wolfram_timeout_seconds)
        self.z3 = PythonPackageAdapter("z3", "z3")
        self.shapely = PythonPackageAdapter("shapely", "shapely")
        self.lean = LeanAdapter()

    def status(self) -> dict[str, Any]:
        return {
            "sympy": {"tool": "sympy", "available": self.sympy.is_available()},
            "wolfram": self.wolfram.status(),
            "z3": self.z3.status(),
            "shapely": self.shapely.status(),
            "lean": self.lean.status(),
        }

    def status_json(self) -> str:
        return json.dumps(self.status(), ensure_ascii=False, indent=2)

    def geometry_tool_results(
        self,
        problem: Any,
        primary_result: dict[str, Any],
        *,
        external_tools: bool,
    ) -> list[dict[str, Any]]:
        results = [self.sympy.describe_geometry_result(problem, primary_result).to_dict()]
        if external_tools:
            results.append(self.wolfram.execute_geometry(problem).to_dict())
        else:
            results.append(
                ToolExecution(
                    tool="wolfram",
                    available=self.wolfram.is_available(),
                    executable_path=self.wolfram.executable,
                    command=["wolframscript", "-code", wolfram_code_for_geometry(problem)],
                    status="planned",
                    error=None if self.wolfram.is_available() else "wolframscript not found.",
                ).to_dict()
            )
        return results


def find_wolfram_executable() -> str | None:
    from_path = shutil.which("wolframscript")
    if from_path:
        return from_path

    candidates = [
        Path(r"C:\Program Files\Wolfram Research\WolframScript\wolframscript.exe"),
        Path(r"C:\Program Files\Wolfram Research\Wolfram\14.2\wolframscript.exe"),
        Path(r"C:\Program Files\Wolfram Research\Wolfram\14.1\wolframscript.exe"),
        Path(r"C:\Program Files\Wolfram Research\Wolfram\14.0\wolframscript.exe"),
        Path(r"C:\Program Files\Wolfram Research\Mathematica\14.2\wolframscript.exe"),
        Path(r"C:\Program Files\Wolfram Research\Mathematica\14.1\wolframscript.exe"),
        Path(r"C:\Program Files\Wolfram Research\Mathematica\14.0\wolframscript.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def sympy_command_for_geometry(problem: Any) -> str:
    if problem.task == "envelope":
        return f"resultant(y - ({problem.equations['y']}), d/d{problem.parameter}, {problem.parameter})"
    if problem.task == "region":
        return f"exists {problem.parameter} in {problem.domain.label()}: y = {problem.equations.get('y')}"
    return f"resultant(x - ({problem.equations.get('x')}), y - ({problem.equations.get('y')}), {problem.parameter})"


def wolfram_code_for_geometry(problem: Any) -> str:
    if problem.task == "envelope":
        expr = to_wolfram_expr(problem.equations["y"])
        param = problem.parameter
        formula = f"Eliminate[{{y == {expr}, D[y - ({expr}), {param}] == 0}}, {param}]"
        return inputform_code(formula)

    if problem.task == "region":
        expr = to_wolfram_expr(problem.equations["y"])
        param = problem.parameter
        domain_condition = wolfram_domain_condition(problem)
        exists_body = f"{domain_condition} && y == {expr}" if domain_condition else f"y == {expr}"
        formula = f"Reduce[Exists[{param}, {exists_body}], {{x, y}}, Reals]"
        return inputform_code(formula)

    if problem.task == "locus":
        x_expr = to_wolfram_expr(problem.equations["x"])
        y_expr = to_wolfram_expr(problem.equations["y"])
        param = problem.parameter
        formula = f"Eliminate[{{x == {x_expr}, y == {y_expr}}}, {param}]"
        return inputform_code(formula)

    raise ValueError(f"unsupported geometry task for Wolfram: {problem.task}")


def wolfram_domain_condition(problem: Any) -> str:
    param = problem.parameter
    if problem.domain.kind == "real":
        return f"Element[{param}, Reals]"
    if problem.domain.kind == "interval":
        lower_op = "<=" if problem.domain.lower_closed else "<"
        upper_op = "<=" if problem.domain.upper_closed else "<"
        lower = to_wolfram_expr(problem.domain.lower or "-Infinity")
        upper = to_wolfram_expr(problem.domain.upper or "Infinity")
        return f"{lower} {lower_op} {param} && {param} {upper_op} {upper}"
    return ""


def inputform_code(formula: str) -> str:
    return f"ToString[InputForm[FullSimplify[{formula}]]]"


def to_wolfram_expr(expr: str) -> str:
    return (
        expr.replace("**", "^")
        .replace("oo", "Infinity")
        .replace("sqrt", "Sqrt")
        .replace("sin", "Sin")
        .replace("cos", "Cos")
        .replace("tan", "Tan")
        .replace("exp", "Exp")
        .replace("log", "Log")
    )
