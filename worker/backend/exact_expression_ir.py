"""Evaluate MORTRA's binder-aware mathematical expression IR exactly.

Only a small, explicit AST vocabulary is accepted. The evaluator never parses
Python source, consults a problem registry, or loads expected answers.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import sympy as sp


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FUNCTIONS = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
}
_CONSTANTS = {
    "pi": sp.pi,
    "e": sp.E,
    "i": sp.I,
    "Infinity": sp.oo,
}
_UNEVALUATED = (sp.Sum, sp.Integral, sp.Limit, sp.Derivative)


class ExpressionIRError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _expect_arity(node: list[Any], arity: int) -> None:
    if len(node) != arity + 1:
        raise ExpressionIRError(f"{node[0]} expects {arity} operands")


def _symbol(name: str, symbols: dict[str, sp.Symbol]) -> sp.Symbol:
    if not _IDENTIFIER.fullmatch(name):
        raise ExpressionIRError(f"invalid symbol name: {name!r}")
    return symbols.setdefault(name, sp.Symbol(name))


def expression_from_ir(node: Any, symbols: dict[str, sp.Symbol] | None = None) -> sp.Expr:
    symbols = {} if symbols is None else symbols
    if isinstance(node, bool):
        raise ExpressionIRError("boolean is not a mathematical number")
    if isinstance(node, int):
        return sp.Integer(node)
    if isinstance(node, float):
        if not sp.Float(node).is_finite:
            raise ExpressionIRError("non-finite numeric literal")
        return sp.Rational(str(node))
    if isinstance(node, str):
        if node in _CONSTANTS:
            return _CONSTANTS[node]
        return _symbol(node, symbols)
    if not isinstance(node, list) or not node or not isinstance(node[0], str):
        raise ExpressionIRError("expression node must be a tagged array")

    operator = node[0]
    if operator in {"Add", "Multiply"}:
        if len(node) < 3:
            raise ExpressionIRError(f"{operator} expects at least two operands")
        values = [expression_from_ir(value, symbols) for value in node[1:]]
        return sp.Add(*values, evaluate=False) if operator == "Add" else sp.Mul(*values, evaluate=False)
    if operator in {"Subtract", "Divide", "Power", "Binomial"}:
        _expect_arity(node, 2)
        left = expression_from_ir(node[1], symbols)
        right = expression_from_ir(node[2], symbols)
        if operator == "Subtract":
            return sp.Add(left, -right, evaluate=False)
        if operator == "Divide":
            return sp.Mul(left, sp.Pow(right, -1, evaluate=False), evaluate=False)
        if operator == "Power":
            return sp.Pow(left, right, evaluate=False)
        return sp.binomial(left, right)
    if operator in {"Negate", "Sqrt"}:
        _expect_arity(node, 1)
        value = expression_from_ir(node[1], symbols)
        return -value if operator == "Negate" else sp.sqrt(value)
    if operator == "Apply":
        if len(node) < 3 or not isinstance(node[1], str) or node[1] not in _FUNCTIONS:
            raise ExpressionIRError("Apply uses an unsupported function")
        return _FUNCTIONS[node[1]](*[expression_from_ir(value, symbols) for value in node[2:]])
    if operator == "Sum":
        _expect_arity(node, 4)
        if not isinstance(node[1], str):
            raise ExpressionIRError("Sum index must be a symbol")
        index = _symbol(node[1], symbols)
        return sp.Sum(
            expression_from_ir(node[4], symbols),
            (index, expression_from_ir(node[2], symbols), expression_from_ir(node[3], symbols)),
        )
    if operator == "Limit":
        _expect_arity(node, 3)
        if not isinstance(node[1], str):
            raise ExpressionIRError("Limit variable must be a symbol")
        variable = _symbol(node[1], symbols)
        return sp.Limit(
            expression_from_ir(node[3], symbols),
            variable,
            expression_from_ir(node[2], symbols),
        )
    if operator == "Integral":
        _expect_arity(node, 4)
        if not isinstance(node[1], str):
            raise ExpressionIRError("Integral variable must be a symbol")
        variable = _symbol(node[1], symbols)
        return sp.Integral(
            expression_from_ir(node[4], symbols),
            (variable, expression_from_ir(node[2], symbols), expression_from_ir(node[3], symbols)),
        )
    raise ExpressionIRError(f"unsupported expression operator: {operator}")


def _operator_sequence(node: Any) -> list[str]:
    if not isinstance(node, list) or not node:
        return []
    operator = str(node[0])
    start = 2 if operator == "Apply" else 1
    return [operator, *[item for child in node[start:] for item in _operator_sequence(child)]]


def evaluate_expression_ir(expression_ir: Any) -> dict[str, Any]:
    canonical = _canonical_json(expression_ir)
    expression = expression_from_ir(json.loads(canonical))
    if expression.free_symbols:
        return {
            "ok": False,
            "error": "expression has unresolved free symbols",
            "free_symbols": sorted(symbol.name for symbol in expression.free_symbols),
        }

    try:
        result = sp.simplify(expression.doit(deep=True))
    except (ValueError, TypeError, NotImplementedError, RecursionError) as error:
        return {"ok": False, "error": f"exact evaluation failed: {error}"}
    if result.has(*_UNEVALUATED):
        return {"ok": False, "error": "exact evaluation left an unevaluated bound operator"}
    if result.has(sp.nan, sp.zoo) or result in {sp.oo, -sp.oo}:
        return {"ok": False, "error": "exact evaluation did not produce a finite value"}
    if result.free_symbols:
        return {
            "ok": False,
            "error": "exact result still has free symbols",
            "free_symbols": sorted(symbol.name for symbol in result.free_symbols),
        }

    replay_expression = expression_from_ir(json.loads(canonical))
    try:
        replay_result = sp.simplify(replay_expression.doit(deep=True))
    except (ValueError, TypeError, NotImplementedError, RecursionError) as error:
        return {"ok": False, "error": f"certificate replay failed: {error}"}
    if sp.srepr(replay_result) != sp.srepr(result) and sp.simplify(replay_result - result) != 0:
        return {"ok": False, "error": "certificate replay disagreed with the first evaluation"}

    ast_sha256 = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    result_srepr = sp.srepr(result)
    result_sha256 = hashlib.sha256(result_srepr.encode("utf-8")).hexdigest()
    return {
        "ok": True,
        "expression_tex": sp.latex(expression),
        "result_tex": sp.latex(result),
        "result_srepr": result_srepr,
        "operators": _operator_sequence(expression_ir),
        "certificate": {
            "schema": "mortra.exact-expression-ir.v1",
            "verified": True,
            "ast_sha256": ast_sha256,
            "result_sha256": result_sha256,
            "checks": [
                "AST reconstructed using only the finite expression-IR vocabulary",
                "all binders were evaluated with lexical scope preserved",
                "no free symbol or unevaluated bound operator remained",
                "a second reconstruction and exact evaluation produced the same result",
            ],
        },
    }


def main() -> int:
    try:
        request = json.loads(__import__("sys").stdin.buffer.read().decode("utf-8"))
        if not isinstance(request, dict):
            raise ExpressionIRError("request must be an object")
        if isinstance(request.get("expression_irs"), list):
            result = {
                "ok": True,
                "results": [evaluate_expression_ir(item) for item in request["expression_irs"]],
            }
        elif "expression_ir" in request:
            result = evaluate_expression_ir(request["expression_ir"])
        else:
            raise ExpressionIRError("request must contain expression_ir or expression_irs")
    except Exception as error:
        result = {"ok": False, "error": str(error)}
    __import__("sys").stdout.buffer.write(
        json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return 0 if result.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
