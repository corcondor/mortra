"""Singularのliftstdを、独立再生可能なイデアル所属証明へ変換する。"""

from __future__ import annotations

import hashlib
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import sympy as sp


DEFAULT_SINGULAR_ROOT = Path(
    "/home/shibahara/.local/mortra-singular/root"
)


@dataclass(frozen=True)
class SingularLiftCertificate:
    initial_polynomials: tuple[str, ...]
    variables: tuple[str, ...]
    monomial_order: str
    basis_polynomials: tuple[str, ...]
    goal_polynomial: str
    remainder: str
    initial_multipliers: tuple[str, ...]
    replay_residual: str
    proved: bool
    replayed: bool
    status: str
    elapsed_seconds: float
    certificate_sha256: str
    singular_stdout_sha256: str


def _singular_expression(
    expression: sp.Expr,
    symbol_map: dict[sp.Symbol, str],
) -> str:
    substituted = sp.expand(expression).xreplace(
        {symbol: sp.Symbol(name) for symbol, name in symbol_map.items()}
    )
    return sp.sstr(substituted).replace("**", "^")


def _render_program(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goal: sp.Expr,
    *,
    monomial_order: str,
) -> tuple[str, dict[str, sp.Symbol]]:
    if monomial_order not in {"dp", "lp"}:
        raise ValueError("Singular order must be dp or lp")
    if not variables:
        raise ValueError("at least one variable is required")
    symbol_map = {symbol: f"x{index}" for index, symbol in enumerate(variables, 1)}
    reverse_map = {name: symbol for symbol, name in symbol_map.items()}
    inputs = ",".join(
        _singular_expression(item, symbol_map) for item in polynomials
    )
    goal_text = _singular_expression(goal, symbol_map)
    ring_variables = ",".join(reverse_map)
    lines = [
        f"ring mortra=0,({ring_variables}),{monomial_order};",
        "short=0;",
        f"ideal I={inputs};",
        "matrix T;",
        "ideal G=liftstd(I,T);",
        f"poly target={goal_text};",
        "poly rem=reduce(target,G);",
        'print("MORTRA_STATUS=COMPUTED");',
        'print("MORTRA_BASIS_SIZE="+string(size(G)));',
        "for (int j=1; j<=size(G); j++)",
        "{",
        '  print("MORTRA_BASIS_"+string(j)+"="+string(G[j]));',
        "}",
        'print("MORTRA_REMAINDER="+string(rem));',
        "if (rem==0)",
        "{",
        "  ideal J=target;",
        "  matrix U=lift(G,J);",
        "  matrix H=T*U;",
        f"  for (int i=1; i<={len(polynomials)}; i++)",
        "  {",
        '    print("MORTRA_MULTIPLIER_"+string(i)+"="+string(H[i,1]));',
        "  }",
        "}",
        'print("MORTRA_DONE=1");',
        "quit;",
    ]
    return "\n".join(lines) + "\n", reverse_map


def _marker_map(stdout: str) -> dict[str, str]:
    markers: dict[str, str] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("MORTRA_") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        markers[key] = value
    return markers


def _parse_expression(text: str, reverse_map: dict[str, sp.Symbol]) -> sp.Expr:
    return sp.sympify(text.replace("^", "**"), locals=reverse_map)


def _empty_certificate(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goal: sp.Expr,
    *,
    monomial_order: str,
    status: str,
    elapsed_seconds: float,
    stdout: str = "",
) -> SingularLiftCertificate:
    material = "|".join(
        (
            status,
            monomial_order,
            *(sp.sstr(item) for item in polynomials),
            sp.sstr(goal),
        )
    )
    return SingularLiftCertificate(
        initial_polynomials=tuple(sp.sstr(item) for item in polynomials),
        variables=tuple(str(item) for item in variables),
        monomial_order=monomial_order,
        basis_polynomials=(),
        goal_polynomial=sp.sstr(sp.expand(goal)),
        remainder="",
        initial_multipliers=(),
        replay_residual="",
        proved=False,
        replayed=False,
        status=status,
        elapsed_seconds=elapsed_seconds,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        singular_stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
    )


def prove_ideal_membership_with_singular(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal: sp.Expr,
    *,
    timeout_seconds: float = 300.0,
    monomial_order: str = "dp",
    wsl_distribution: str = "Ubuntu",
    singular_root: Path = DEFAULT_SINGULAR_ROOT,
) -> SingularLiftCertificate:
    """Run liftstd and replay the returned source-level linear combination."""

    initial = tuple(sp.expand(item) for item in polynomials)
    ordered_variables = tuple(variables)
    unknown = set().union(goal.free_symbols, *(item.free_symbols for item in initial)) - set(
        ordered_variables
    )
    if unknown:
        raise ValueError(f"variables omitted from ring: {sorted(map(str, unknown))}")
    program, reverse_map = _render_program(
        initial,
        ordered_variables,
        sp.expand(goal),
        monomial_order=monomial_order,
    )
    executable = (singular_root / "usr" / "bin" / "Singular").as_posix()
    library_path = (
        singular_root / "usr" / "lib" / "x86_64-linux-gnu"
    ).as_posix()
    command = (
        "wsl.exe",
        "-d",
        wsl_distribution,
        "--",
        "env",
        f"LD_LIBRARY_PATH={library_path}",
        executable,
        "-q",
    )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            input=program,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=None if timeout_seconds <= 0 else timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed = time.perf_counter() - started
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        return _empty_certificate(
            initial,
            ordered_variables,
            goal,
            monomial_order=monomial_order,
            status="timeout",
            elapsed_seconds=elapsed,
            stdout=stdout,
        )
    elapsed = time.perf_counter() - started
    stdout = completed.stdout
    markers = _marker_map(stdout)
    if completed.returncode != 0 or markers.get("MORTRA_DONE") != "1":
        return _empty_certificate(
            initial,
            ordered_variables,
            goal,
            monomial_order=monomial_order,
            status=f"execution_error:{completed.returncode}",
            elapsed_seconds=elapsed,
            stdout=stdout + completed.stderr,
        )

    basis_size = int(markers.get("MORTRA_BASIS_SIZE", "0"))
    basis = tuple(
        _parse_expression(markers[f"MORTRA_BASIS_{index}"], reverse_map)
        for index in range(1, basis_size + 1)
    )
    remainder = _parse_expression(markers["MORTRA_REMAINDER"], reverse_map)
    proved = sp.expand(remainder) == 0
    multipliers = tuple(
        _parse_expression(markers.get(f"MORTRA_MULTIPLIER_{index}", "0"), reverse_map)
        for index in range(1, len(initial) + 1)
    )
    residual = sp.expand(
        goal
        - sum(
            (multiplier * polynomial for multiplier, polynomial in zip(multipliers, initial)),
            sp.Integer(0),
        )
    )
    replayed = proved and residual == 0 and len(multipliers) == len(initial)
    basis_text = tuple(sp.sstr(item) for item in basis)
    multiplier_text = tuple(sp.sstr(item) for item in multipliers)
    material = "|".join(
        (
            monomial_order,
            *(sp.sstr(item) for item in initial),
            *basis_text,
            sp.sstr(goal),
            sp.sstr(remainder),
            *multiplier_text,
            sp.sstr(residual),
        )
    )
    return SingularLiftCertificate(
        initial_polynomials=tuple(sp.sstr(item) for item in initial),
        variables=tuple(str(item) for item in ordered_variables),
        monomial_order=monomial_order,
        basis_polynomials=basis_text,
        goal_polynomial=sp.sstr(sp.expand(goal)),
        remainder=sp.sstr(remainder),
        initial_multipliers=multiplier_text,
        replay_residual=sp.sstr(residual),
        proved=proved,
        replayed=replayed,
        status="proved" if replayed else "not_proved",
        elapsed_seconds=elapsed,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        singular_stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
    )


def singular_runtime_available(
    *,
    wsl_distribution: str = "Ubuntu",
    singular_root: Path = DEFAULT_SINGULAR_ROOT,
) -> bool:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", wsl_distribution):
        return False
    command = (
        "wsl.exe",
        "-d",
        wsl_distribution,
        "--",
        "test",
        "-x",
        (singular_root / "usr" / "bin" / "Singular").as_posix(),
    )
    try:
        return subprocess.run(command, timeout=60, check=False).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
