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
    basis_engine: str
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
    certificate_degree: int | None = None
    lift_matrix_rows: int | None = None
    lift_matrix_columns: int | None = None
    lift_nonzero_entries: int | None = None
    bounded_column_count: int | None = None
    runtime_diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class SingularRadicalCertificate:
    """Exact source-level witness that a power of the goal is in the ideal."""

    initial_polynomials: tuple[str, ...]
    variables: tuple[str, ...]
    monomial_order: str
    basis_engine: str
    goal_polynomial: str
    radical_exponent: int | None
    source_multipliers: tuple[str, ...]
    replay_residual: str
    augmented_certificate_sha256: str
    proved: bool
    replayed: bool
    status: str
    elapsed_seconds: float
    certificate_sha256: str


@dataclass(frozen=True)
class SingularMembershipProbe:
    variables: tuple[str, ...]
    monomial_order: str
    engine: str
    remainder: str
    basis_size: int
    member: bool
    status: str
    elapsed_seconds: float
    singular_stdout_sha256: str


def _singular_expression(
    expression: sp.Expr,
    symbol_map: dict[sp.Symbol, str],
    *,
    variables: tuple[sp.Symbol, ...] = (),
    coefficient_parameters: tuple[sp.Symbol, ...] = (),
) -> str:
    # Singular accepts factored polynomial expressions directly.  Rebuilding a
    # very large coefficient-chart expression as a SymPy ``Poly`` first can be
    # more expensive than the actual backend search and destroys the compact
    # DAG produced by the relational elaborator.  Keep bounded inputs on the
    # canonical term path used by existing certificates; stream large inputs
    # structurally with only a deterministic symbol rename.
    operation_count = int(sp.count_ops(expression))
    structurally_large = operation_count > 2_048 or (
        len(variables) >= 8 and operation_count > 512
    )
    if structurally_large:
        substituted = expression.xreplace(
            {symbol: sp.Symbol(name) for symbol, name in symbol_map.items()}
        )
        return sp.sstr(substituted).replace("**", "^")
    if coefficient_parameters:
        coefficient_domain = sp.QQ.frac_field(*coefficient_parameters)
        polynomial = sp.Poly(expression, *variables, domain=coefficient_domain)
        rendered_terms: list[str] = []
        for powers, coefficient in polynomial.terms():
            coefficient_expression = coefficient.as_expr()
            if int(sp.count_ops(coefficient_expression)) <= 256:
                coefficient_expression = sp.factor(coefficient_expression)
            coefficient_expression = coefficient_expression.xreplace(
                {symbol: sp.Symbol(name) for symbol, name in symbol_map.items()}
            )
            coefficient_text = sp.sstr(coefficient_expression).replace("**", "^")
            monomial_factors = [
                symbol_map[variable]
                if power == 1
                else f"{symbol_map[variable]}^{power}"
                for variable, power in zip(variables, powers, strict=True)
                if power
            ]
            if monomial_factors:
                rendered_terms.append(
                    f"({coefficient_text})*{'*'.join(monomial_factors)}"
                )
            else:
                rendered_terms.append(f"({coefficient_text})")
        return "+".join(rendered_terms) if rendered_terms else "0"

    substituted = expression.xreplace(
        {symbol: sp.Symbol(name) for symbol, name in symbol_map.items()}
    )
    return sp.sstr(substituted).replace("**", "^")


def _bounded_monomial_powers(
    variable_count: int,
    max_total_degree: int,
) -> tuple[tuple[int, ...], ...]:
    powers: list[tuple[int, ...]] = []

    def visit(prefix: tuple[int, ...], remaining: int, slots: int) -> None:
        if slots == 1:
            powers.append((*prefix, remaining))
            return
        for current in range(remaining + 1):
            visit((*prefix, current), remaining - current, slots - 1)

    for total_degree in range(max_total_degree + 1):
        visit((), total_degree, variable_count)
    return tuple(powers)


def _render_bounded_linear_batch_program(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goals: tuple[sp.Expr, ...],
    *,
    coefficient_parameters: tuple[sp.Symbol, ...],
    certificate_degree: int,
) -> tuple[
    str,
    dict[str, sp.Symbol],
    tuple[tuple[int, tuple[int, ...]], ...],
]:
    if not goals:
        raise ValueError("at least one bounded membership target is required")
    if not coefficient_parameters:
        coefficient_domain = sp.QQ
    else:
        coefficient_domain = sp.QQ.frac_field(*coefficient_parameters)
    polynomial_inputs = tuple(
        sp.Poly(item, *variables, domain=coefficient_domain)
        for item in polynomials
    )
    polynomial_goals = tuple(
        sp.Poly(goal, *variables, domain=coefficient_domain) for goal in goals
    )
    if any(
        certificate_degree < polynomial_goal.total_degree()
        for polynomial_goal in polynomial_goals
    ):
        raise ValueError("certificate degree must cover the goal degree")

    multiplier_terms: list[tuple[int, tuple[int, ...]]] = []
    columns: list[sp.Poly] = []
    for source_index, polynomial in enumerate(polynomial_inputs):
        multiplier_degree = certificate_degree - polynomial.total_degree()
        if multiplier_degree < 0:
            continue
        for powers in _bounded_monomial_powers(len(variables), multiplier_degree):
            monomial = sp.Poly.from_dict(
                {powers: coefficient_domain.one},
                variables,
                domain=coefficient_domain,
            )
            multiplier_terms.append((source_index, powers))
            columns.append(polynomial * monomial)

    support = tuple(
        sorted(
            set().union(
                *(set(polynomial_goal.monoms()) for polynomial_goal in polynomial_goals),
                *(set(column.monoms()) for column in columns)
            ),
            reverse=True,
        )
    )
    symbol_map = {
        symbol: f"p{index}"
        for index, symbol in enumerate(coefficient_parameters, 1)
    }
    reverse_map = {name: symbol for symbol, name in symbol_map.items()}

    def render_coefficient(coefficient: object) -> str:
        expression = sp.sympify(coefficient)
        if int(sp.count_ops(expression)) <= 256:
            expression = sp.factor(expression)
        expression = expression.xreplace(
            {symbol: sp.Symbol(name) for symbol, name in symbol_map.items()}
        )
        return sp.sstr(expression).replace("**", "^")

    module_columns = ",".join(
        "["
        + ",".join(
            render_coefficient(column.coeff_monomial(monomial))
            for monomial in support
        )
        + "]"
        for column in columns
    )
    target_columns = tuple(
        "["
        + ",".join(
            render_coefficient(polynomial_goal.coeff_monomial(monomial))
            for monomial in support
        )
        + "]"
        for polynomial_goal in polynomial_goals
    )
    coefficient_field = (
        "("
        + ",".join(("0", *(symbol_map[item] for item in coefficient_parameters)))
        + ")"
        if coefficient_parameters
        else "0"
    )
    lines = [
        f"ring mortra={coefficient_field},(mortraDummy),(c,dp);",
        "short=0;",
        f"module M={module_columns};",
        f'attrib(M,"rank",{len(support)});',
        "module G=std(M);",
        'print("MORTRA_STATUS=COMPUTED");',
        f'print("MORTRA_BASIS_SIZE={len(columns)}");',
        f'print("MORTRA_BOUNDED_COLUMN_COUNT={len(columns)}");',
        f'print("MORTRA_TARGET_COUNT={len(target_columns)}");',
    ]
    for target_index, target_column in enumerate(target_columns, 1):
        prefix = f"MORTRA_TARGET_{target_index}"
        lines.extend(
            (
                f"module N{target_index}={target_column};",
                f'attrib(N{target_index},"rank",{len(support)});',
                f"module rem{target_index}=reduce(N{target_index},G);",
                (
                    f'if (size(rem{target_index})==0) '
                    f'{{ print("{prefix}_REMAINDER=0"); }}'
                ),
                (
                    f'else {{ print("{prefix}_REMAINDER=NONZERO"); }}'
                ),
                f"if (size(rem{target_index})==0)",
                "{",
                f"  matrix H{target_index}=lift(M,N{target_index});",
                (
                    f"  module source_residual{target_index}="
                    f"N{target_index}-M*H{target_index};"
                ),
                (
                    f'  print("{prefix}_LIFT_ROWS="+'
                    f"string(nrows(H{target_index})));"
                ),
                (
                    f'  print("{prefix}_LIFT_COLUMNS="+'
                    f"string(ncols(H{target_index})));"
                ),
                f"  int mortraNonzeroEntries{target_index}=0;",
                f"  for (int i=1; i<={len(columns)}; i++)",
                "  {",
                (
                    f"    if (H{target_index}[i,1] != 0) "
                    f"{{ mortraNonzeroEntries{target_index}++; }}"
                ),
                (
                    f'    print("{prefix}_LINEAR_COEFFICIENT_"+'
                    'string(i)+"_BEGIN");'
                ),
                f"    print(H{target_index}[i,1]);",
                (
                    f'    print("{prefix}_LINEAR_COEFFICIENT_"+'
                    'string(i)+"_END");'
                ),
                "  }",
                (
                    f'  print("{prefix}_LIFT_NONZERO_ENTRIES="+'
                    f"string(mortraNonzeroEntries{target_index}));"
                ),
                (
                    f'  if (size(source_residual{target_index})==0) '
                    f'{{ print("{prefix}_SOURCE_RESIDUAL=0"); }}'
                ),
                (
                    f'  else {{ print("{prefix}_SOURCE_RESIDUAL=NONZERO"); }}'
                ),
                "}",
            )
        )
    lines.extend(('print("MORTRA_DONE=1");', "quit;"))
    return "\n".join(lines) + "\n", reverse_map, tuple(multiplier_terms)


def _render_bounded_linear_program(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goal: sp.Expr,
    *,
    coefficient_parameters: tuple[sp.Symbol, ...],
    certificate_degree: int,
) -> tuple[
    str,
    dict[str, sp.Symbol],
    tuple[tuple[int, tuple[int, ...]], ...],
]:
    program, reverse_map, multiplier_terms = _render_bounded_linear_batch_program(
        polynomials,
        variables,
        (goal,),
        coefficient_parameters=coefficient_parameters,
        certificate_degree=certificate_degree,
    )
    # Preserve the legacy marker names for callers and stored parser fixtures.
    program = program.replace("MORTRA_TARGET_1_", "MORTRA_")
    for batch_name, legacy_name in (
        ("source_residual1", "source_residual"),
        ("mortraNonzeroEntries1", "mortraNonzeroEntries"),
        ("rem1", "rem"),
        ("H1", "H"),
        ("N1", "N"),
    ):
        program = program.replace(batch_name, legacy_name)
    return program, reverse_map, multiplier_terms


def _render_program(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goal: sp.Expr,
    *,
    monomial_order: str,
    coefficient_parameters: tuple[sp.Symbol, ...] = (),
    basis_engine: str = "liftstd",
) -> tuple[str, dict[str, sp.Symbol]]:
    if monomial_order not in {"dp", "lp"}:
        raise ValueError("Singular order must be dp or lp")
    if not variables:
        raise ValueError("at least one variable is required")
    if basis_engine not in {
        "liftstd",
        "slimgb_lift",
        "direct_lift",
        "module_slimgb",
    }:
        raise ValueError(
            "Singular basis engine must be liftstd, slimgb_lift, direct_lift, "
            "or module_slimgb"
        )
    if set(variables) & set(coefficient_parameters):
        raise ValueError("coefficient parameters must not also be ring variables")
    symbol_map = {symbol: f"x{index}" for index, symbol in enumerate(variables, 1)}
    symbol_map.update(
        {
            symbol: f"p{index}"
            for index, symbol in enumerate(coefficient_parameters, 1)
        }
    )
    reverse_map = {name: symbol for symbol, name in symbol_map.items()}
    inputs = ",".join(
        _singular_expression(
            item,
            symbol_map,
            variables=variables,
            coefficient_parameters=coefficient_parameters,
        )
        for item in polynomials
    )
    goal_text = _singular_expression(
        goal,
        symbol_map,
        variables=variables,
        coefficient_parameters=coefficient_parameters,
    )
    ring_variables = ",".join(symbol_map[symbol] for symbol in variables)
    coefficient_field = (
        "(" + ",".join(("0", *(symbol_map[item] for item in coefficient_parameters))) + ")"
        if coefficient_parameters
        else "0"
    )
    if basis_engine == "liftstd":
        basis_lines = ("matrix T;", "ideal G=liftstd(I,T);")
    elif basis_engine == "slimgb_lift":
        basis_lines = ("ideal G=slimgb(I);", "matrix T=lift(I,G);")
    elif basis_engine == "module_slimgb":
        module_generators = ",".join(
            "["
            + ",".join(
                (
                    f"I[{source_index}]",
                    *(
                        "1" if marker_index == source_index else "0"
                        for marker_index in range(1, len(polynomials) + 1)
                    ),
                )
            )
            + "]"
            for source_index in range(1, len(polynomials) + 1)
        )
        basis_lines = (
            f"module M={module_generators};",
            "module GM=slimgb(M);",
            "int mortra_basis_size=0;",
            "for (int mortra_j=1; mortra_j<=size(GM); mortra_j++)",
            "{",
            "  if (GM[mortra_j][1]!=0) { mortra_basis_size++; }",
            "}",
            "ideal G;",
            f"matrix T[{len(polynomials)}][mortra_basis_size];",
            "int mortra_column=0;",
            "for (mortra_j=1; mortra_j<=size(GM); mortra_j++)",
            "{",
            "  if (GM[mortra_j][1]!=0)",
            "  {",
            "    mortra_column++;",
            "    G[mortra_column]=GM[mortra_j][1];",
            f"    for (int mortra_i=1; mortra_i<={len(polynomials)}; mortra_i++)",
            "    {",
            "      T[mortra_i,mortra_column]=GM[mortra_j][mortra_i+1];",
            "    }",
            "  }",
            "}",
            'attrib(G,"isSB",1);',
        )
    else:
        basis_lines = ("ideal G=slimgb(I);",)
    lift_lines = (
        ("  matrix U=lift(G,J);", "  matrix H=T*U;")
        if basis_engine != "direct_lift"
        else ("  matrix H=lift(I,J);",)
    )
    ring_order = (
        f"(c,{monomial_order})"
        if basis_engine == "module_slimgb"
        else monomial_order
    )
    lines = [
        f"ring mortra={coefficient_field},({ring_variables}),{ring_order};",
        "short=0;",
        f"ideal I={inputs};",
        *basis_lines,
        f"poly target={goal_text};",
        "poly rem=reduce(target,G);",
        'print("MORTRA_STATUS=COMPUTED");',
        'print("MORTRA_BASIS_SIZE="+string(size(G)));',
        "for (int j=1; j<=size(G); j++)",
        "{",
        '  print("MORTRA_BASIS_"+string(j)+"_BEGIN");',
        "  print(G[j]);",
        '  print("MORTRA_BASIS_"+string(j)+"_END");',
        "}",
        'print("MORTRA_REMAINDER_BEGIN");',
        "print(rem);",
        'print("MORTRA_REMAINDER_END");',
        "if (rem==0)",
        "{",
        "  ideal J=target;",
        *lift_lines,
        "  poly source_residual=target;",
        f"  for (int i=1; i<={len(polynomials)}; i++)",
        "  {",
        "    source_residual=source_residual-H[i,1]*I[i];",
        '    print("MORTRA_MULTIPLIER_"+string(i)+"_BEGIN");',
        "    print(H[i,1]);",
        '    print("MORTRA_MULTIPLIER_"+string(i)+"_END");',
        "  }",
        '  if (source_residual==0) { print("MORTRA_SOURCE_RESIDUAL=0"); }',
        '  else { print("MORTRA_SOURCE_RESIDUAL=NONZERO"); }',
        "}",
        'print("MORTRA_DONE=1");',
        "quit;",
    ]
    return "\n".join(lines) + "\n", reverse_map


def _render_probe_program(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goal: sp.Expr,
    *,
    monomial_order: str,
    coefficient_parameters: tuple[sp.Symbol, ...] = (),
    engine: str = "slimgb",
) -> tuple[str, dict[str, sp.Symbol]]:
    if engine not in {"std", "slimgb"}:
        raise ValueError("Singular probe engine must be std or slimgb")
    program, reverse_map = _render_program(
        polynomials,
        variables,
        goal,
        monomial_order=monomial_order,
        coefficient_parameters=coefficient_parameters,
    )
    prefix = program.split("matrix T;", 1)[0]
    symbol_map = {symbol: f"x{index}" for index, symbol in enumerate(variables, 1)}
    symbol_map.update(
        {
            symbol: f"p{index}"
            for index, symbol in enumerate(coefficient_parameters, 1)
        }
    )
    goal_text = _singular_expression(
        goal,
        symbol_map,
        variables=variables,
        coefficient_parameters=coefficient_parameters,
    )
    lines = [
        prefix.rstrip(),
        f"ideal G={engine}(I);",
        f"poly target={goal_text};",
        "poly rem=reduce(target,G);",
        'print("MORTRA_STATUS=COMPUTED");',
        'print("MORTRA_BASIS_SIZE="+string(size(G)));',
        'print("MORTRA_REMAINDER="+string(rem));',
        'print("MORTRA_DONE=1");',
        "quit;",
    ]
    return "\n".join(lines) + "\n", reverse_map


def _render_raw_source_replay_program(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goal: sp.Expr,
    multiplier_texts: tuple[str, ...],
    *,
    monomial_order: str,
    coefficient_parameters: tuple[sp.Symbol, ...] = (),
) -> str:
    """Render a second-process replay without rebuilding large multipliers."""

    if len(multiplier_texts) != len(polynomials):
        raise ValueError("one source multiplier is required per polynomial")
    symbol_map = {symbol: f"x{index}" for index, symbol in enumerate(variables, 1)}
    symbol_map.update(
        {
            symbol: f"p{index}"
            for index, symbol in enumerate(coefficient_parameters, 1)
        }
    )
    inputs = ",".join(
        _singular_expression(
            item,
            symbol_map,
            variables=variables,
            coefficient_parameters=coefficient_parameters,
        )
        for item in polynomials
    )
    target = _singular_expression(
        goal,
        symbol_map,
        variables=variables,
        coefficient_parameters=coefficient_parameters,
    )
    coefficient_field = (
        "(" + ",".join(("0", *(symbol_map[item] for item in coefficient_parameters))) + ")"
        if coefficient_parameters
        else "0"
    )
    ring_variables = ",".join(symbol_map[symbol] for symbol in variables)
    lines = [
        f"ring mortra={coefficient_field},({ring_variables}),{monomial_order};",
        "short=0;",
        f"ideal I={inputs};",
        f"poly source_residual={target};",
    ]
    lines.extend(
        f"source_residual=source_residual-({multiplier})*I[{index}];"
        for index, multiplier in enumerate(multiplier_texts, 1)
    )
    lines.extend(
        (
            'if (source_residual==0) { print("MORTRA_SOURCE_RESIDUAL=0"); }',
            'else { print("MORTRA_SOURCE_RESIDUAL=NONZERO"); }',
            'print("MORTRA_DONE=1");',
            "quit;",
        )
    )
    return "\n".join(lines) + "\n"


def _rename_backend_symbols(
    text: str,
    reverse_map: dict[str, sp.Symbol],
) -> str:
    if not reverse_map:
        return text
    pattern = re.compile(
        r"(?<![A-Za-z0-9_])(" + "|".join(
            sorted(map(re.escape, reverse_map), key=len, reverse=True)
        ) + r")(?![A-Za-z0-9_])"
    )
    return pattern.sub(lambda match: str(reverse_map[match.group(1)]), text)


def _marker_map(stdout: str) -> dict[str, str]:
    markers: dict[str, str] = {}
    lines = stdout.splitlines()
    for line in lines:
        line = line.strip()
        if not line.startswith("MORTRA_") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        markers[key] = value
    active_key: str | None = None
    active_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if (
            active_key is None
            and line.startswith("MORTRA_")
            and line.endswith("_BEGIN")
        ):
            active_key = line[: -len("_BEGIN")]
            active_lines = []
            continue
        if active_key is not None and line == f"{active_key}_END":
            markers[active_key] = "".join(active_lines)
            active_key = None
            active_lines = []
            continue
        if active_key is not None:
            active_lines.append(line)
    return markers


def _parse_expression(text: str, reverse_map: dict[str, sp.Symbol]) -> sp.Expr:
    return sp.sympify(text.replace("^", "**"), locals=reverse_map)


def _replay_source_lift(
    goal: sp.Expr,
    multipliers: tuple[sp.Expr, ...],
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    coefficient_parameters: tuple[sp.Symbol, ...],
) -> sp.Expr:
    """Replay a lift coefficientwise without expanding one giant expression."""

    domain = (
        sp.QQ.frac_field(*coefficient_parameters)
        if coefficient_parameters
        else sp.QQ
    )
    residual = sp.Poly(goal, *variables, domain=domain)
    for multiplier, polynomial in zip(multipliers, polynomials, strict=True):
        residual -= sp.Poly(multiplier, *variables, domain=domain) * sp.Poly(
            polynomial,
            *variables,
            domain=domain,
        )
    return residual.as_expr()


def _empty_certificate(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goal: sp.Expr,
    *,
    monomial_order: str,
    basis_engine: str,
    status: str,
    elapsed_seconds: float,
    stdout: str = "",
    certificate_degree: int | None = None,
) -> SingularLiftCertificate:
    material = "|".join(
        (
            status,
            monomial_order,
            basis_engine,
            *(sp.sstr(item) for item in polynomials),
            sp.sstr(goal),
        )
    )
    return SingularLiftCertificate(
        initial_polynomials=tuple(sp.sstr(item) for item in polynomials),
        variables=tuple(str(item) for item in variables),
        monomial_order=monomial_order,
        basis_engine=basis_engine,
        basis_polynomials=(),
        goal_polynomial=sp.sstr(goal),
        remainder="",
        initial_multipliers=(),
        replay_residual="",
        proved=False,
        replayed=False,
        status=status,
        elapsed_seconds=elapsed_seconds,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        singular_stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
        certificate_degree=certificate_degree,
    )


def _singular_command(
    *,
    singular_root: Path,
    wsl_distribution: str,
    timeout_seconds: float,
) -> tuple[str, ...]:
    executable = (singular_root / "usr" / "bin" / "Singular").as_posix()
    library_path = (
        singular_root / "usr" / "lib" / "x86_64-linux-gnu"
    ).as_posix()
    command = [
        "wsl.exe",
        "-d",
        wsl_distribution,
        "--",
        "env",
        f"LD_LIBRARY_PATH={library_path}",
    ]
    if timeout_seconds > 0:
        command.extend(
            (
                "timeout",
                "--signal=TERM",
                "--kill-after=5s",
                f"{timeout_seconds}s",
            )
        )
    command.extend((executable, "-q"))
    return tuple(command)


def _replay_raw_source_lift_with_singular(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goal: sp.Expr,
    multiplier_texts: tuple[str, ...],
    *,
    monomial_order: str,
    coefficient_parameters: tuple[sp.Symbol, ...],
    timeout_seconds: float,
    wsl_distribution: str,
    singular_root: Path,
) -> tuple[bool, str, float, str]:
    program = _render_raw_source_replay_program(
        polynomials,
        variables,
        goal,
        multiplier_texts,
        monomial_order=monomial_order,
        coefficient_parameters=coefficient_parameters,
    )
    command = _singular_command(
        singular_root=singular_root,
        wsl_distribution=wsl_distribution,
        timeout_seconds=timeout_seconds,
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
            timeout=None if timeout_seconds <= 0 else timeout_seconds + 10.0,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed = time.perf_counter() - started
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        return False, "timeout", elapsed, hashlib.sha256(stdout.encode()).hexdigest()
    elapsed = time.perf_counter() - started
    output = completed.stdout + completed.stderr
    markers = _marker_map(completed.stdout)
    if completed.returncode in {124, 137, 143}:
        status = "timeout"
    elif completed.returncode != 0 or markers.get("MORTRA_DONE") != "1":
        status = f"execution_error:{completed.returncode}"
    elif markers.get("MORTRA_SOURCE_RESIDUAL") == "0":
        status = "replayed"
    else:
        status = "nonzero_residual"
    return (
        status == "replayed",
        status,
        elapsed,
        hashlib.sha256(output.encode()).hexdigest(),
    )


def _prove_bounded_linear_membership(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goal: sp.Expr,
    *,
    certificate_degree: int,
    coefficient_parameters: tuple[sp.Symbol, ...],
    timeout_seconds: float,
    wsl_distribution: str,
    singular_root: Path,
) -> SingularLiftCertificate:
    program, reverse_map, multiplier_terms = _render_bounded_linear_program(
        polynomials,
        variables,
        goal,
        coefficient_parameters=coefficient_parameters,
        certificate_degree=certificate_degree,
    )
    command = _singular_command(
        singular_root=singular_root,
        wsl_distribution=wsl_distribution,
        timeout_seconds=timeout_seconds,
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
            timeout=None if timeout_seconds <= 0 else timeout_seconds + 10.0,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed = time.perf_counter() - started
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        return _empty_certificate(
            polynomials,
            variables,
            goal,
            monomial_order="bounded_total_degree",
            basis_engine="bounded_linear",
            status="timeout",
            elapsed_seconds=elapsed,
            stdout=stdout,
            certificate_degree=certificate_degree,
        )

    elapsed = time.perf_counter() - started
    stdout = completed.stdout
    markers = _marker_map(stdout)
    if completed.returncode in {124, 137, 143}:
        return _empty_certificate(
            polynomials,
            variables,
            goal,
            monomial_order="bounded_total_degree",
            basis_engine="bounded_linear",
            status="timeout",
            elapsed_seconds=elapsed,
            stdout=stdout + completed.stderr,
            certificate_degree=certificate_degree,
        )
    if completed.returncode != 0 or markers.get("MORTRA_DONE") != "1":
        return _empty_certificate(
            polynomials,
            variables,
            goal,
            monomial_order="bounded_total_degree",
            basis_engine="bounded_linear",
            status=f"execution_error:{completed.returncode}",
            elapsed_seconds=elapsed,
            stdout=stdout + completed.stderr,
            certificate_degree=certificate_degree,
        )

    runtime_errors = tuple(
        line.strip()
        for line in stdout.splitlines()
        if line.lstrip().startswith("?")
    )
    proved = markers.get("MORTRA_REMAINDER") == "0" and not runtime_errors
    source_residual_zero = markers.get("MORTRA_SOURCE_RESIDUAL") == "0"
    lift_matrix_rows = (
        int(markers["MORTRA_LIFT_ROWS"])
        if "MORTRA_LIFT_ROWS" in markers
        else None
    )
    lift_matrix_columns = (
        int(markers["MORTRA_LIFT_COLUMNS"])
        if "MORTRA_LIFT_COLUMNS" in markers
        else None
    )
    lift_nonzero_entries = (
        int(markers["MORTRA_LIFT_NONZERO_ENTRIES"])
        if "MORTRA_LIFT_NONZERO_ENTRIES" in markers
        else None
    )
    bounded_column_count = (
        int(markers["MORTRA_BOUNDED_COLUMN_COUNT"])
        if "MORTRA_BOUNDED_COLUMN_COUNT" in markers
        else None
    )
    runtime_diagnostics = tuple(
        line.strip()
        for line in stdout.splitlines()
        if line.lstrip().startswith(("?", "// **"))
    )
    multipliers: list[sp.Expr] = [sp.S.Zero] * len(polynomials)
    if proved:
        for index, (source_index, powers) in enumerate(multiplier_terms, 1):
            coefficient = _parse_expression(
                markers.get(f"MORTRA_LINEAR_COEFFICIENT_{index}", "0"),
                reverse_map,
            )
            monomial = sp.prod(
                variable**power
                for variable, power in zip(variables, powers, strict=True)
            )
            multipliers[source_index] += coefficient * monomial
    multiplier_tuple = tuple(multipliers)
    replay_residual = (
        _replay_source_lift(
            goal,
            multiplier_tuple,
            polynomials,
            variables,
            coefficient_parameters,
        )
        if proved
        else goal
    )
    replayed = proved and source_residual_zero and replay_residual == 0
    multiplier_text = tuple(sp.sstr(item) for item in multiplier_tuple)
    material = "|".join(
        (
            "bounded_linear",
            str(certificate_degree),
            *(sp.sstr(item) for item in polynomials),
            sp.sstr(goal),
            *multiplier_text,
            sp.sstr(replay_residual),
        )
    )
    return SingularLiftCertificate(
        initial_polynomials=tuple(sp.sstr(item) for item in polynomials),
        variables=tuple(str(item) for item in variables),
        monomial_order="bounded_total_degree",
        basis_engine="bounded_linear",
        basis_polynomials=(),
        goal_polynomial=sp.sstr(goal),
        remainder="0" if proved else markers.get("MORTRA_REMAINDER", ""),
        initial_multipliers=multiplier_text,
        replay_residual=sp.sstr(replay_residual),
        proved=proved,
        replayed=replayed,
        status=("proved" if replayed else "execution_error" if runtime_errors else "not_proved"),
        elapsed_seconds=elapsed,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        singular_stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
        certificate_degree=certificate_degree,
        lift_matrix_rows=lift_matrix_rows,
        lift_matrix_columns=lift_matrix_columns,
        lift_nonzero_entries=lift_nonzero_entries,
        bounded_column_count=bounded_column_count,
        runtime_diagnostics=runtime_diagnostics,
    )


def _prove_bounded_linear_memberships(
    polynomials: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goals: tuple[sp.Expr, ...],
    *,
    certificate_degree: int,
    coefficient_parameters: tuple[sp.Symbol, ...],
    timeout_seconds: float,
    wsl_distribution: str,
    singular_root: Path,
) -> tuple[SingularLiftCertificate, ...]:
    program, reverse_map, multiplier_terms = _render_bounded_linear_batch_program(
        polynomials,
        variables,
        goals,
        coefficient_parameters=coefficient_parameters,
        certificate_degree=certificate_degree,
    )
    command = _singular_command(
        singular_root=singular_root,
        wsl_distribution=wsl_distribution,
        timeout_seconds=timeout_seconds,
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
            timeout=None if timeout_seconds <= 0 else timeout_seconds + 10.0,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed = time.perf_counter() - started
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        return tuple(
            _empty_certificate(
                polynomials,
                variables,
                goal,
                monomial_order="bounded_total_degree",
                basis_engine="bounded_linear",
                status="timeout",
                elapsed_seconds=elapsed,
                stdout=stdout,
                certificate_degree=certificate_degree,
            )
            for goal in goals
        )

    elapsed = time.perf_counter() - started
    stdout = completed.stdout
    combined_output = stdout + completed.stderr
    markers = _marker_map(stdout)
    if completed.returncode in {124, 137, 143}:
        status = "timeout"
    elif completed.returncode != 0 or markers.get("MORTRA_DONE") != "1":
        status = f"execution_error:{completed.returncode}"
    else:
        status = None
    if status is not None:
        return tuple(
            _empty_certificate(
                polynomials,
                variables,
                goal,
                monomial_order="bounded_total_degree",
                basis_engine="bounded_linear",
                status=status,
                elapsed_seconds=elapsed,
                stdout=combined_output,
                certificate_degree=certificate_degree,
            )
            for goal in goals
        )

    runtime_errors = tuple(
        line.strip()
        for line in stdout.splitlines()
        if line.lstrip().startswith("?")
    )
    runtime_diagnostics = tuple(
        line.strip()
        for line in stdout.splitlines()
        if line.lstrip().startswith(("?", "// **"))
    )
    bounded_column_count = (
        int(markers["MORTRA_BOUNDED_COLUMN_COUNT"])
        if "MORTRA_BOUNDED_COLUMN_COUNT" in markers
        else None
    )
    stdout_sha256 = hashlib.sha256(stdout.encode()).hexdigest()
    results: list[SingularLiftCertificate] = []
    for target_index, goal in enumerate(goals, 1):
        prefix = f"MORTRA_TARGET_{target_index}"
        proved = (
            markers.get(f"{prefix}_REMAINDER") == "0" and not runtime_errors
        )
        source_residual_zero = (
            markers.get(f"{prefix}_SOURCE_RESIDUAL") == "0"
        )
        multipliers: list[sp.Expr] = [sp.S.Zero] * len(polynomials)
        if proved:
            for index, (source_index, powers) in enumerate(multiplier_terms, 1):
                coefficient = _parse_expression(
                    markers.get(
                        f"{prefix}_LINEAR_COEFFICIENT_{index}",
                        "0",
                    ),
                    reverse_map,
                )
                monomial = sp.prod(
                    variable**power
                    for variable, power in zip(variables, powers, strict=True)
                )
                multipliers[source_index] += coefficient * monomial
        multiplier_tuple = tuple(multipliers)
        replay_residual = (
            _replay_source_lift(
                goal,
                multiplier_tuple,
                polynomials,
                variables,
                coefficient_parameters,
            )
            if proved
            else goal
        )
        replayed = proved and source_residual_zero and replay_residual == 0
        multiplier_text = tuple(sp.sstr(item) for item in multiplier_tuple)
        material = "|".join(
            (
                "bounded_linear",
                str(certificate_degree),
                *(sp.sstr(item) for item in polynomials),
                sp.sstr(goal),
                *multiplier_text,
                sp.sstr(replay_residual),
            )
        )
        results.append(
            SingularLiftCertificate(
                initial_polynomials=tuple(sp.sstr(item) for item in polynomials),
                variables=tuple(str(item) for item in variables),
                monomial_order="bounded_total_degree",
                basis_engine="bounded_linear",
                basis_polynomials=(),
                goal_polynomial=sp.sstr(goal),
                remainder=(
                    "0"
                    if proved
                    else markers.get(f"{prefix}_REMAINDER", "")
                ),
                initial_multipliers=multiplier_text,
                replay_residual=sp.sstr(replay_residual),
                proved=proved,
                replayed=replayed,
                status=(
                    "proved"
                    if replayed
                    else "execution_error"
                    if runtime_errors
                    else "not_proved"
                ),
                elapsed_seconds=elapsed,
                certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
                singular_stdout_sha256=stdout_sha256,
                certificate_degree=certificate_degree,
                lift_matrix_rows=(
                    int(markers[f"{prefix}_LIFT_ROWS"])
                    if f"{prefix}_LIFT_ROWS" in markers
                    else None
                ),
                lift_matrix_columns=(
                    int(markers[f"{prefix}_LIFT_COLUMNS"])
                    if f"{prefix}_LIFT_COLUMNS" in markers
                    else None
                ),
                lift_nonzero_entries=(
                    int(markers[f"{prefix}_LIFT_NONZERO_ENTRIES"])
                    if f"{prefix}_LIFT_NONZERO_ENTRIES" in markers
                    else None
                ),
                bounded_column_count=bounded_column_count,
                runtime_diagnostics=runtime_diagnostics,
            )
        )
    return tuple(results)


def probe_ideal_membership_with_singular(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal: sp.Expr,
    *,
    timeout_seconds: float = 30.0,
    monomial_order: str = "dp",
    coefficient_parameters: Iterable[sp.Symbol] = (),
    engine: str = "slimgb",
    wsl_distribution: str = "Ubuntu",
    singular_root: Path = DEFAULT_SINGULAR_ROOT,
) -> SingularMembershipProbe:
    """Probe exact ideal membership without constructing source multipliers."""

    initial = tuple(sp.sympify(item) for item in polynomials)
    ordered_variables = tuple(variables)
    ordered_parameters = tuple(coefficient_parameters)
    program, reverse_map = _render_probe_program(
        initial,
        ordered_variables,
        sp.sympify(goal),
        monomial_order=monomial_order,
        coefficient_parameters=ordered_parameters,
        engine=engine,
    )
    command = _singular_command(
        singular_root=singular_root,
        wsl_distribution=wsl_distribution,
        timeout_seconds=timeout_seconds,
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
            timeout=None if timeout_seconds <= 0 else timeout_seconds + 10.0,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        elapsed = time.perf_counter() - started
        stdout = error.stdout if isinstance(error.stdout, str) else ""
        return SingularMembershipProbe(
            variables=tuple(str(item) for item in ordered_variables),
            monomial_order=monomial_order,
            engine=engine,
            remainder="",
            basis_size=0,
            member=False,
            status="timeout",
            elapsed_seconds=elapsed,
            singular_stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
        )
    elapsed = time.perf_counter() - started
    stdout = completed.stdout
    markers = _marker_map(stdout)
    status = "computed"
    if completed.returncode in {124, 137, 143}:
        status = "timeout"
    elif completed.returncode != 0 or markers.get("MORTRA_DONE") != "1":
        status = f"execution_error:{completed.returncode}"
    remainder = ""
    member = False
    basis_size = 0
    if status == "computed":
        parsed_remainder = _parse_expression(
            markers.get("MORTRA_REMAINDER", "0"), reverse_map
        )
        remainder = sp.sstr(parsed_remainder)
        member = sp.expand(parsed_remainder) == 0
        basis_size = int(markers.get("MORTRA_BASIS_SIZE", "0"))
    return SingularMembershipProbe(
        variables=tuple(str(item) for item in ordered_variables),
        monomial_order=monomial_order,
        engine=engine,
        remainder=remainder,
        basis_size=basis_size,
        member=member,
        status=status,
        elapsed_seconds=elapsed,
        singular_stdout_sha256=hashlib.sha256(
            (stdout + completed.stderr).encode()
        ).hexdigest(),
    )


def prove_ideal_memberships_with_singular(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goals: Iterable[sp.Expr],
    *,
    timeout_seconds: float = 300.0,
    max_certificate_degree: int | None = None,
    coefficient_parameters: Iterable[sp.Symbol] = (),
    wsl_distribution: str = "Ubuntu",
    singular_root: Path = DEFAULT_SINGULAR_ROOT,
) -> tuple[SingularLiftCertificate, ...]:
    """Check several bounded ideal targets against one exact Macaulay basis."""

    initial = tuple(sp.sympify(item) for item in polynomials)
    ordered_variables = tuple(variables)
    ordered_parameters = tuple(coefficient_parameters)
    expanded_goals = tuple(sp.sympify(goal) for goal in goals)
    if not expanded_goals:
        raise ValueError("at least one ideal membership target is required")
    all_symbols = set().union(
        *(goal.free_symbols for goal in expanded_goals),
        *(item.free_symbols for item in initial),
    )
    unknown = all_symbols - set((*ordered_variables, *ordered_parameters))
    if unknown:
        raise ValueError(f"variables omitted from ring: {sorted(map(str, unknown))}")
    coefficient_domain = (
        sp.QQ.frac_field(*ordered_parameters) if ordered_parameters else sp.QQ
    )
    minimum_degree = max(
        *(
            sp.Poly(goal, *ordered_variables, domain=coefficient_domain).total_degree()
            for goal in expanded_goals
        ),
        *(
            sp.Poly(item, *ordered_variables, domain=coefficient_domain).total_degree()
            for item in initial
        ),
    )
    certificate_degree = (
        minimum_degree + 2
        if max_certificate_degree is None
        else max_certificate_degree
    )
    return _prove_bounded_linear_memberships(
        initial,
        ordered_variables,
        expanded_goals,
        certificate_degree=certificate_degree,
        coefficient_parameters=ordered_parameters,
        timeout_seconds=timeout_seconds,
        wsl_distribution=wsl_distribution,
        singular_root=singular_root,
    )


def prove_ideal_membership_with_singular(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal: sp.Expr,
    *,
    timeout_seconds: float = 300.0,
    monomial_order: str = "dp",
    basis_engine: str = "liftstd",
    max_certificate_degree: int | None = None,
    coefficient_parameters: Iterable[sp.Symbol] = (),
    wsl_distribution: str = "Ubuntu",
    singular_root: Path = DEFAULT_SINGULAR_ROOT,
) -> SingularLiftCertificate:
    """Run liftstd and replay the returned source-level linear combination."""

    initial = tuple(sp.sympify(item) for item in polynomials)
    ordered_variables = tuple(variables)
    ordered_parameters = tuple(coefficient_parameters)
    expanded_goal = sp.sympify(goal)
    unknown = set().union(expanded_goal.free_symbols, *(item.free_symbols for item in initial)) - set(
        (*ordered_variables, *ordered_parameters)
    )
    if unknown:
        raise ValueError(f"variables omitted from ring: {sorted(map(str, unknown))}")
    if basis_engine == "bounded_linear":
        coefficient_domain = (
            sp.QQ.frac_field(*ordered_parameters)
            if ordered_parameters
            else sp.QQ
        )
        minimum_degree = max(
            sp.Poly(expanded_goal, *ordered_variables, domain=coefficient_domain).total_degree(),
            *(sp.Poly(item, *ordered_variables, domain=coefficient_domain).total_degree() for item in initial),
        )
        certificate_degree = (
            minimum_degree + 2
            if max_certificate_degree is None
            else max_certificate_degree
        )
        return _prove_bounded_linear_membership(
            initial,
            ordered_variables,
            expanded_goal,
            certificate_degree=certificate_degree,
            coefficient_parameters=ordered_parameters,
            timeout_seconds=timeout_seconds,
            wsl_distribution=wsl_distribution,
            singular_root=singular_root,
        )
    program, reverse_map = _render_program(
        initial,
        ordered_variables,
        expanded_goal,
        monomial_order=monomial_order,
        coefficient_parameters=ordered_parameters,
        basis_engine=basis_engine,
    )
    command = _singular_command(
        singular_root=singular_root,
        wsl_distribution=wsl_distribution,
        timeout_seconds=timeout_seconds,
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
            timeout=None if timeout_seconds <= 0 else timeout_seconds + 10.0,
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
            basis_engine=basis_engine,
            status="timeout",
            elapsed_seconds=elapsed,
            stdout=stdout,
        )
    elapsed = time.perf_counter() - started
    stdout = completed.stdout
    markers = _marker_map(stdout)
    if completed.returncode in {124, 137, 143}:
        return _empty_certificate(
            initial,
            ordered_variables,
            goal,
            monomial_order=monomial_order,
            basis_engine=basis_engine,
            status="timeout",
            elapsed_seconds=elapsed,
            stdout=stdout + completed.stderr,
        )
    if completed.returncode != 0 or markers.get("MORTRA_DONE") != "1":
        return _empty_certificate(
            initial,
            ordered_variables,
            goal,
            monomial_order=monomial_order,
            basis_engine=basis_engine,
            status=f"execution_error:{completed.returncode}",
            elapsed_seconds=elapsed,
            stdout=stdout + completed.stderr,
        )

    basis_size = int(markers.get("MORTRA_BASIS_SIZE", "0"))
    raw_basis_text = tuple(
        markers[f"MORTRA_BASIS_{index}"] for index in range(1, basis_size + 1)
    )
    remainder_text = markers.get("MORTRA_REMAINDER", "")
    raw_multiplier_text = tuple(
        markers.get(f"MORTRA_MULTIPLIER_{index}", "")
        for index in range(1, len(initial) + 1)
    )
    source_residual_zero = markers.get("MORTRA_SOURCE_RESIDUAL") == "0"
    proved = remainder_text.strip() == "0" and source_residual_zero
    raw_multiplier_chars = sum(map(len, raw_multiplier_text))
    runtime_diagnostics: list[str] = []
    if proved and raw_multiplier_chars > 250_000:
        replayed, replay_status, replay_elapsed, replay_stdout_sha256 = (
            _replay_raw_source_lift_with_singular(
                initial,
                ordered_variables,
                expanded_goal,
                raw_multiplier_text,
                monomial_order=monomial_order,
                coefficient_parameters=ordered_parameters,
                timeout_seconds=min(max(timeout_seconds, 1.0), 120.0),
                wsl_distribution=wsl_distribution,
                singular_root=singular_root,
            )
        )
        residual = sp.S.Zero if replayed else sp.Symbol("unreplayed")
        runtime_diagnostics.extend(
            (
                f"raw_source_replay_status={replay_status}",
                f"raw_source_replay_seconds={replay_elapsed}",
                f"raw_source_replay_stdout_sha256={replay_stdout_sha256}",
                f"raw_multiplier_chars={raw_multiplier_chars}",
            )
        )
        basis_text = tuple(
            _rename_backend_symbols(item, reverse_map) for item in raw_basis_text
        )
        multiplier_text = tuple(
            _rename_backend_symbols(item, reverse_map)
            for item in raw_multiplier_text
        )
    else:
        basis = tuple(
            _parse_expression(item, reverse_map) for item in raw_basis_text
        )
        multipliers = tuple(
            _parse_expression(item or "0", reverse_map)
            for item in raw_multiplier_text
        )
        residual = _replay_source_lift(
            expanded_goal,
            multipliers,
            initial,
            ordered_variables,
            ordered_parameters,
        )
        replayed = (
            proved
            and residual == 0
            and len(multipliers) == len(initial)
        )
        basis_text = tuple(sp.sstr(item) for item in basis)
        multiplier_text = tuple(sp.sstr(item) for item in multipliers)
    material = "|".join(
        (
            monomial_order,
            basis_engine,
            *(sp.sstr(item) for item in initial),
            *basis_text,
            sp.sstr(goal),
            remainder_text,
            *multiplier_text,
            sp.sstr(residual),
        )
    )
    return SingularLiftCertificate(
        initial_polynomials=tuple(sp.sstr(item) for item in initial),
        variables=tuple(str(item) for item in ordered_variables),
        monomial_order=monomial_order,
        basis_engine=basis_engine,
        basis_polynomials=basis_text,
        goal_polynomial=sp.sstr(goal),
        remainder=remainder_text,
        initial_multipliers=multiplier_text,
        replay_residual=sp.sstr(residual),
        proved=proved,
        replayed=replayed,
        status="proved" if replayed else "not_proved",
        elapsed_seconds=elapsed,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        singular_stdout_sha256=hashlib.sha256(stdout.encode()).hexdigest(),
        runtime_diagnostics=tuple(runtime_diagnostics),
    )


def prove_radical_membership_with_singular(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal: sp.Expr,
    *,
    timeout_seconds: float = 300.0,
    monomial_order: str = "dp",
    basis_engine: str = "slimgb_lift",
    coefficient_parameters: Iterable[sp.Symbol] = (),
    wsl_distribution: str = "Ubuntu",
    singular_root: Path = DEFAULT_SINGULAR_ROOT,
) -> SingularRadicalCertificate:
    """Prove ``goal`` is in the radical by an exact Rabinowitsch lift.

    Singular proves ``1`` belongs to ``<I, 1 - t*goal>``.  Substituting
    ``t = 1/goal`` in that source lift and clearing the bounded power of
    ``goal`` yields a directly replayable certificate ``goal**N in I``.
    """

    started = time.perf_counter()
    initial = tuple(sp.sympify(item) for item in polynomials)
    ordered_variables = tuple(variables)
    ordered_parameters = tuple(coefficient_parameters)
    expanded_goal = sp.sympify(goal)
    known_symbols = set((*ordered_variables, *ordered_parameters))
    unknown = set().union(
        expanded_goal.free_symbols,
        *(item.free_symbols for item in initial),
    ) - known_symbols
    if unknown:
        raise ValueError(f"variables omitted from ring: {sorted(map(str, unknown))}")

    def build_result(
        *,
        exponent: int | None,
        multipliers: tuple[sp.Expr, ...] = (),
        residual: sp.Expr | str = "",
        augmented_sha256: str = "",
        proved: bool = False,
        replayed: bool = False,
        status: str,
    ) -> SingularRadicalCertificate:
        multiplier_text = tuple(sp.sstr(item) for item in multipliers)
        residual_text = sp.sstr(residual) if not isinstance(residual, str) else residual
        material = "|".join(
            (
                monomial_order,
                basis_engine,
                *(sp.sstr(item) for item in initial),
                sp.sstr(expanded_goal),
                str(exponent),
                *multiplier_text,
                residual_text,
                augmented_sha256,
                status,
            )
        )
        return SingularRadicalCertificate(
            initial_polynomials=tuple(sp.sstr(item) for item in initial),
            variables=tuple(str(item) for item in ordered_variables),
            monomial_order=monomial_order,
            basis_engine=basis_engine,
            goal_polynomial=sp.sstr(expanded_goal),
            radical_exponent=exponent,
            source_multipliers=multiplier_text,
            replay_residual=residual_text,
            augmented_certificate_sha256=augmented_sha256,
            proved=proved,
            replayed=replayed,
            status=status,
            elapsed_seconds=time.perf_counter() - started,
            certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        )

    if expanded_goal == 0:
        zeros = tuple(sp.S.Zero for _ in initial)
        return build_result(
            exponent=1,
            multipliers=zeros,
            residual=sp.S.Zero,
            proved=True,
            replayed=True,
            status="proved",
        )

    occupied_names = {str(symbol) for symbol in known_symbols}
    suffix = 0
    while True:
        name = "_mortra_rabinowitsch" + (f"_{suffix}" if suffix else "")
        if name not in occupied_names:
            rabinowitsch_variable = sp.Symbol(name)
            break
        suffix += 1

    augmented = prove_ideal_membership_with_singular(
        (*initial, 1 - rabinowitsch_variable * expanded_goal),
        (*ordered_variables, rabinowitsch_variable),
        sp.S.One,
        timeout_seconds=timeout_seconds,
        monomial_order=monomial_order,
        basis_engine=basis_engine,
        coefficient_parameters=ordered_parameters,
        wsl_distribution=wsl_distribution,
        singular_root=singular_root,
    )
    if not augmented.replayed:
        return build_result(
            exponent=None,
            augmented_sha256=augmented.certificate_sha256,
            status=(
                "not_proved"
                if augmented.status == "not_proved"
                else f"augmented_{augmented.status}"
            ),
        )

    reverse_locals = {
        str(symbol): symbol
        for symbol in (*ordered_variables, *ordered_parameters, rabinowitsch_variable)
    }
    augmented_multipliers = tuple(
        sp.sympify(text, locals=reverse_locals)
        for text in augmented.initial_multipliers
    )
    if len(augmented_multipliers) != len(initial) + 1:
        return build_result(
            exponent=None,
            augmented_sha256=augmented.certificate_sha256,
            status="invalid_augmented_lift",
        )

    source_augmented_multipliers = augmented_multipliers[: len(initial)]
    exponent = max(
        (
            int(sp.Poly(item, rabinowitsch_variable, domain=sp.EX).degree())
            for item in source_augmented_multipliers
            if item != 0
        ),
        default=0,
    )
    try:
        domain = (
            sp.QQ.frac_field(*ordered_parameters)
            if ordered_parameters
            else sp.QQ
        )
        source_multipliers = tuple(
            sp.Poly(
                sp.cancel(
                    expanded_goal**exponent
                    * multiplier.subs(rabinowitsch_variable, 1 / expanded_goal)
                ),
                *ordered_variables,
                domain=domain,
            ).as_expr()
            for multiplier in source_augmented_multipliers
        )
        residual = _replay_source_lift(
            expanded_goal**exponent,
            source_multipliers,
            initial,
            ordered_variables,
            ordered_parameters,
        )
    except (sp.PolynomialError, ValueError, ZeroDivisionError):
        return build_result(
            exponent=exponent,
            augmented_sha256=augmented.certificate_sha256,
            status="power_lift_not_polynomial",
        )

    replayed = residual == 0 and exponent >= 1
    return build_result(
        exponent=exponent,
        multipliers=source_multipliers,
        residual=residual,
        augmented_sha256=augmented.certificate_sha256,
        proved=replayed,
        replayed=replayed,
        status="proved" if replayed else "source_replay_failed",
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
