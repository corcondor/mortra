"""Replayable Wolfram polynomial certificates for typed JGEX obligations.

Wolfram Language is used only to search for quotient polynomials.  MORTRA
accepts a result only after SymPy independently replays the returned identity
against the exact equations produced by the typed JGEX elaborator.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import sympy as sp
from sympy.parsing.mathematica import parse_mathematica
from sympy.printing.mathematica import mathematica_code

from worker.backend.jgex_exact_constraint_bridge import (
    _canonical_nonconstant_factor_keys,
    inspect_jgex_exact_system,
    inspect_jgex_local_elimination,
)


@dataclass(frozen=True)
class WolframPolynomialCertificate:
    status: str
    exact_replay: bool
    equation_count: int
    variable_count: int
    initial_equation_count: int
    initial_variable_count: int
    initial_total_expanded_terms: int
    reduced_total_expanded_terms: int
    quotient_certificate: tuple[str, ...]
    remainder: str
    replay_residual: str
    elapsed_seconds: float
    certificate_sha256: str | None
    reduction_strategy: str | None = None
    preprocessing: str = "local_relational"
    backend_stdout: str = ""
    backend_stderr: str = ""
    reason: str | None = None
    saturation_multiplier: str = "1"
    saturation_assumptions_used: tuple[str, ...] = ()
    preprocessing_replayed: bool = True
    preprocessing_certificate_sha256: str | None = None
    denominator_branch_closed: bool = False
    denominator_branch_quotients: tuple[str, ...] = ()
    denominator_branch_remainder: str = "unknown"
    denominator_branch_replay_residual: str = "unknown"
    denominator_branch_basis: tuple[str, ...] = ()
    denominator_branch_method: str | None = None
    coefficient_denominator_is_construction_equation: bool = False


def _wolfram_expression(expression: sp.Expr) -> str:
    return mathematica_code(sp.expand(expression))


def _parse_wolfram_expression(
    text: str,
    inverse_symbols: dict[sp.Symbol, sp.Symbol],
) -> sp.Expr:
    parsed = sp.sympify(parse_mathematica(text))
    return sp.expand(parsed.xreplace(inverse_symbols))


def replay_polynomial_reduction(
    goal: sp.Expr,
    equations: tuple[sp.Expr, ...],
    quotients: tuple[sp.Expr, ...],
    remainder: sp.Expr,
    multiplier: sp.Expr = sp.Integer(1),
) -> sp.Expr:
    """Return the exact residual of a polynomial-reduction witness."""

    if len(equations) != len(quotients):
        raise ValueError("quotient count must equal equation count")
    residual = sp.together(
        goal * multiplier
        - sum(
            (
                quotient * equation
                for quotient, equation in zip(quotients, equations)
            ),
            sp.Integer(0),
        )
        - remainder
    )
    # PolynomialReduce may use geometric parameters as rational-function
    # coefficients.  Equality in that exact field is decided by the
    # normalized numerator, not by an uncombined expanded fraction.
    numerator, _ = sp.cancel(residual).as_numer_denom()
    return sp.expand(numerator)


def _clear_rational_certificate_denominators(
    quotients: tuple[sp.Expr, ...],
    remainder: sp.Expr,
    known_nonzero_factor_keys: frozenset[str],
) -> tuple[
    tuple[sp.Expr, ...],
    sp.Expr,
    sp.Expr,
    tuple[str, ...],
    tuple[str, ...],
]:
    """Clear coefficient-field denominators and expose their assumptions."""

    denominators: dict[str, sp.Expr] = {}
    for expression in (*quotients, remainder):
        denominator = sp.factor(sp.cancel(expression).as_numer_denom()[1])
        if denominator.could_extract_minus_sign():
            denominator = -denominator
        if denominator not in (1, -1):
            denominators.setdefault(str(denominator), denominator)
    common_denominator = sp.factor(
        sp.prod(denominators.values(), start=sp.Integer(1))
    )
    required_keys = tuple(
        sorted(_canonical_nonconstant_factor_keys(common_denominator))
    )
    unsupported_keys = tuple(
        key for key in required_keys if key not in known_nonzero_factor_keys
    )
    cleared_quotients = tuple(
        sp.cancel(common_denominator * quotient) for quotient in quotients
    )
    cleared_remainder = sp.cancel(common_denominator * remainder)
    return (
        cleared_quotients,
        cleared_remainder,
        common_denominator,
        required_keys,
        unsupported_keys,
    )


def _extract_json(stdout: str) -> dict[str, object]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start >= 0 and end > start:
        payload = json.loads(stdout[start : end + 1])
        if isinstance(payload, dict):
            return payload
    raise ValueError("wolframscript did not emit a JSON result")


def certify_jgex_with_wolfram(
    text: str,
    *,
    executable: Path,
    timeout_seconds: int = 60,
    local_max_output_terms: int = 64,
    local_max_separator_variables: int = 12,
    reduction_mode: str = "extended_groebner",
    preprocessing: str = "local_relational",
    saturation_mode: str = "none",
    max_saturation_factors: int = 12,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> WolframPolynomialCertificate:
    """Search and independently replay a direct ideal-membership witness.

    Extended Groebner reduction returns a conversion matrix ``G = M.F``.
    Combining it with ``goal = q.G + remainder`` yields cofactors ``q.M`` for
    the original reduced hypotheses.  MORTRA replays that final identity, so
    Wolfram remains a certificate search backend rather than the truth plane.
    """

    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if reduction_mode not in {"direct", "extended_groebner"}:
        raise ValueError("reduction_mode must be direct or extended_groebner")
    if preprocessing not in {"local_relational", "relational", "explicit"}:
        raise ValueError(
            "preprocessing must be local_relational, relational, or explicit"
        )
    if saturation_mode not in {"none", "single", "cumulative"}:
        raise ValueError("saturation_mode must be none, single, or cumulative")
    if max_saturation_factors < 0:
        raise ValueError("max_saturation_factors must be non-negative")
    started = time.perf_counter()
    nonzero_condition_text: tuple[str, ...] = ()
    preprocessing_replayed = True
    preprocessing_certificate_sha256: str | None = None
    if preprocessing == "local_relational":
        analysis = inspect_jgex_local_elimination(
            text,
            max_output_terms=local_max_output_terms,
            max_resultant_degree=1,
            max_separator_variables=local_max_separator_variables,
            ordering_strategy="min_fill",
        )
        equations = tuple(
            sp.expand(sp.sympify(item))
            for item in analysis.local_elimination.remaining_polynomials
        )
        variable_names = tuple(analysis.local_elimination.remaining_variables)
        goal_text = analysis.goal_polynomial
        initial_equation_count = analysis.initial_equation_count
        initial_variable_count = analysis.initial_variable_count
        initial_total_expanded_terms = analysis.initial_total_expanded_terms
        reduced_total_expanded_terms = analysis.reduced_total_expanded_terms
        exact_analysis = inspect_jgex_exact_system(text, representation="relational")
        local_conditions = tuple(
            condition
            for step in analysis.local_elimination.steps
            for condition in step.nonzero_conditions
        )
        nonzero_condition_text = tuple(
            dict.fromkeys((*exact_analysis.nondegeneracy_conditions, *local_conditions))
        )
        preprocessing_replayed = analysis.all_local_certificates_replayed
        preprocessing_certificate_sha256 = hashlib.sha256(
            "|".join(
                step.certificate_sha256 for step in analysis.local_elimination.steps
            ).encode()
        ).hexdigest()
    else:
        exact_analysis = inspect_jgex_exact_system(
            text,
            representation=preprocessing,
        )
        equations = tuple(
            sp.expand(sp.sympify(item))
            for item in exact_analysis.construction_equations
        )
        variable_names = exact_analysis.variables
        goal_text = exact_analysis.goal_polynomial
        initial_equation_count = exact_analysis.equation_count
        initial_variable_count = exact_analysis.variable_count
        initial_total_expanded_terms = exact_analysis.total_expanded_terms
        reduced_total_expanded_terms = exact_analysis.total_expanded_terms
        nonzero_condition_text = exact_analysis.nondegeneracy_conditions
    goal = sp.expand(sp.sympify(goal_text))
    factors_by_text: dict[str, sp.Expr] = {}
    for condition in nonzero_condition_text:
        expression = condition.removesuffix(" != 0").strip()
        factor = sp.factor(sp.together(sp.sympify(expression)).as_numer_denom()[0])
        if factor.could_extract_minus_sign():
            factor = -factor
        if factor != 0 and factor.free_symbols:
            factors_by_text.setdefault(str(factor), factor)
    factors = tuple(factors_by_text.values())[:max_saturation_factors]
    multiplier_specs: list[tuple[sp.Expr, tuple[str, ...]]] = [(sp.Integer(1), ())]
    if saturation_mode == "single":
        multiplier_specs.extend((factor, (str(factor),)) for factor in factors)
    elif saturation_mode == "cumulative":
        product = sp.Integer(1)
        assumptions: list[str] = []
        for factor in factors:
            product = sp.factor(product * factor)
            assumptions.append(str(factor))
            multiplier_specs.append((product, tuple(assumptions)))

    reduction_symbols = tuple(sp.Symbol(name) for name in variable_names)
    all_symbol_sets = [item.free_symbols for item in (*equations, goal)]
    all_symbol_sets.extend(multiplier.free_symbols for multiplier, _ in multiplier_specs)
    symbol_universe = tuple(sorted(set().union(*all_symbol_sets), key=str))
    wolfram_symbols = tuple(
        sp.Symbol(f"x{index + 1}") for index in range(len(symbol_universe))
    )
    forward_symbols = dict(zip(symbol_universe, wolfram_symbols))
    inverse_symbols = dict(zip(wolfram_symbols, symbol_universe))
    renamed_equations = tuple(item.xreplace(forward_symbols) for item in equations)
    renamed_goal = goal.xreplace(forward_symbols)
    renamed_reduction_symbols = tuple(
        forward_symbols[item] for item in reduction_symbols if item in forward_symbols
    )
    renamed_multiplier_specs = tuple(
        (multiplier.xreplace(forward_symbols), assumptions)
        for multiplier, assumptions in multiplier_specs
    )
    equation_code = "{" + ",".join(map(_wolfram_expression, renamed_equations)) + "}"
    variable_code = "{" + ",".join(map(str, renamed_reduction_symbols)) + "}"
    target_codes = tuple(
        _wolfram_expression(sp.expand(renamed_goal * multiplier))
        for multiplier, _ in renamed_multiplier_specs
    )
    reversed_variable_code = "{" + ",".join(map(str, reversed(renamed_reduction_symbols))) + "}"
    if reduction_mode == "extended_groebner":
        reduction_code = "{" + ",".join(
            f"PolynomialReduce[{target}, First[extended], {variable_code}, MonomialOrder -> DegreeReverseLexicographic]"
            for target in target_codes
        ) + "}"
        computation = (
            f"Module[{{extended, reductions, selectedIndex, reduction, originalQuotients}}, "
            f"extended = ResourceFunction[\"ExtendedGroebnerBasis\"][{equation_code}, {variable_code}, MonomialOrder -> DegreeReverseLexicographic]; "
            f"reductions = {reduction_code}; "
            "selectedIndex = SelectFirst[Range[Length[reductions]], Last[reductions[[#]]] === 0 &, 1]; "
            "reduction = reductions[[selectedIndex]]; "
            "originalQuotients = Expand[First[reduction].Last[extended]]; "
            "<|\"strategy\" -> \"extended-groebner-grevlex\", \"multiplierIndex\" -> selectedIndex, \"quotients\" -> originalQuotients, \"remainder\" -> Last[reduction], \"basisSize\" -> Length[First[extended]]|>]"
        )
    else:
        attempt_items: list[str] = []
        for index, target in enumerate(target_codes, start=1):
            attempt_items.extend(
                (
                    f"<|\"strategy\" -> \"grevlex-forward\", \"multiplierIndex\" -> {index}, \"reduction\" -> PolynomialReduce[{target}, {equation_code}, {variable_code}, MonomialOrder -> DegreeReverseLexicographic]|>",
                    f"<|\"strategy\" -> \"lex-forward\", \"multiplierIndex\" -> {index}, \"reduction\" -> PolynomialReduce[{target}, {equation_code}, {variable_code}, MonomialOrder -> Lexicographic]|>",
                    f"<|\"strategy\" -> \"grevlex-reverse\", \"multiplierIndex\" -> {index}, \"reduction\" -> PolynomialReduce[{target}, {equation_code}, {reversed_variable_code}, MonomialOrder -> DegreeReverseLexicographic]|>",
                    f"<|\"strategy\" -> \"lex-reverse\", \"multiplierIndex\" -> {index}, \"reduction\" -> PolynomialReduce[{target}, {equation_code}, {reversed_variable_code}, MonomialOrder -> Lexicographic]|>",
                )
            )
        attempts_code = "{" + ",".join(attempt_items) + "}"
        computation = (
            f"Module[{{attempts}}, attempts = {attempts_code}; "
            "With[{selected = SelectFirst[attempts, Last[#[\"reduction\"]] === 0 &, First[attempts]]}, <|\"strategy\" -> selected[\"strategy\"], \"multiplierIndex\" -> selected[\"multiplierIndex\"], \"quotients\" -> First[selected[\"reduction\"]], \"remainder\" -> Last[selected[\"reduction\"]], \"basisSize\" -> 0|>]]"
        )
    script = "\n".join(
        (
            f"result = TimeConstrained[{computation}, {timeout_seconds}, $Failed];",
            'payload = If[result === $Failed, <|"status" -> "timeout"|>, <|"status" -> "complete", "strategy" -> result["strategy"], "multiplierIndex" -> result["multiplierIndex"], "basisSize" -> result["basisSize"], "quotients" -> (ToString[InputForm[#]] & /@ result["quotients"]), "remainder" -> ToString[InputForm[result["remainder"]]]|>];',
            'WriteString[$Output, ExportString[payload, "RawJSON"], "\\n"];',
        )
    )

    with tempfile.TemporaryDirectory(prefix="mortra-wolfram-certificate-") as raw:
        script_path = Path(raw) / "certificate.wl"
        script_path.write_text(script, encoding="utf-8")
        try:
            completed = runner(
                [str(executable.resolve()), "-file", str(script_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds + 180,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return WolframPolynomialCertificate(
                status="right_censored_timeout",
                exact_replay=False,
                equation_count=len(equations),
                variable_count=len(reduction_symbols),
                initial_equation_count=initial_equation_count,
                initial_variable_count=initial_variable_count,
                initial_total_expanded_terms=initial_total_expanded_terms,
                reduced_total_expanded_terms=reduced_total_expanded_terms,
                quotient_certificate=(),
                remainder="unknown",
                replay_residual="unknown",
                elapsed_seconds=time.perf_counter() - started,
                certificate_sha256=None,
                preprocessing=preprocessing,
                backend_stdout=str(exc.stdout or ""),
                backend_stderr=str(exc.stderr or ""),
                reason="wolframscript process timeout",
            )

    try:
        payload = _extract_json(completed.stdout)
    except (ValueError, json.JSONDecodeError) as exc:
        return WolframPolynomialCertificate(
            status="execution_error",
            exact_replay=False,
            equation_count=len(equations),
            variable_count=len(reduction_symbols),
            initial_equation_count=initial_equation_count,
            initial_variable_count=initial_variable_count,
            initial_total_expanded_terms=initial_total_expanded_terms,
            reduced_total_expanded_terms=reduced_total_expanded_terms,
            quotient_certificate=(),
            remainder="unknown",
            replay_residual="unknown",
            elapsed_seconds=time.perf_counter() - started,
            certificate_sha256=None,
            preprocessing=preprocessing,
            backend_stdout=completed.stdout,
            backend_stderr=completed.stderr,
            reason=str(exc),
        )
    if payload.get("status") == "timeout":
        return WolframPolynomialCertificate(
            status="right_censored_timeout",
            exact_replay=False,
            equation_count=len(equations),
            variable_count=len(reduction_symbols),
            initial_equation_count=initial_equation_count,
            initial_variable_count=initial_variable_count,
            initial_total_expanded_terms=initial_total_expanded_terms,
            reduced_total_expanded_terms=reduced_total_expanded_terms,
            quotient_certificate=(),
            remainder="unknown",
            replay_residual="unknown",
            elapsed_seconds=time.perf_counter() - started,
            certificate_sha256=None,
            preprocessing=preprocessing,
            backend_stdout=completed.stdout,
            backend_stderr=completed.stderr,
            reason="Wolfram PolynomialReduce timeout",
        )

    quotient_text = tuple(str(item) for item in payload.get("quotients", ()))
    remainder_text = str(payload.get("remainder", "unknown"))
    reduction_strategy = str(payload.get("strategy", "unknown"))
    multiplier_index = int(payload.get("multiplierIndex", 1)) - 1
    if multiplier_index < 0 or multiplier_index >= len(multiplier_specs):
        multiplier_index = 0
    multiplier, saturation_assumptions_used = multiplier_specs[multiplier_index]
    try:
        quotients = tuple(
            _parse_wolfram_expression(item, inverse_symbols) for item in quotient_text
        )
        remainder = _parse_wolfram_expression(remainder_text, inverse_symbols)
        known_nonzero_factor_keys = frozenset(
            key
            for condition in nonzero_condition_text
            for key in _canonical_nonconstant_factor_keys(
                sp.sympify(condition.removesuffix(" != 0").strip())
            )
        )
        (
            quotients,
            remainder,
            coefficient_denominator,
            denominator_assumptions,
            unsupported_denominator_assumptions,
        ) = _clear_rational_certificate_denominators(
            quotients,
            remainder,
            known_nonzero_factor_keys,
        )
        multiplier = sp.factor(multiplier * coefficient_denominator)
        coefficient_denominator_is_construction_equation = any(
            sp.expand(equation - coefficient_denominator) == 0
            or sp.expand(equation + coefficient_denominator) == 0
            for equation in equations
        )
        saturation_assumptions_used = tuple(
            dict.fromkeys(
                (*saturation_assumptions_used, *denominator_assumptions)
            )
        )
        residual = replay_polynomial_reduction(
            goal, equations, quotients, remainder, multiplier
        )
    except Exception as exc:
        return WolframPolynomialCertificate(
            status="invalid_certificate",
            exact_replay=False,
            equation_count=len(equations),
            variable_count=len(reduction_symbols),
            initial_equation_count=initial_equation_count,
            initial_variable_count=initial_variable_count,
            initial_total_expanded_terms=initial_total_expanded_terms,
            reduced_total_expanded_terms=reduced_total_expanded_terms,
            quotient_certificate=quotient_text,
            remainder=remainder_text,
            replay_residual="parse_or_replay_failed",
            elapsed_seconds=time.perf_counter() - started,
            certificate_sha256=None,
            reduction_strategy=reduction_strategy,
            preprocessing=preprocessing,
            backend_stdout=completed.stdout,
            backend_stderr=completed.stderr,
            reason=f"{type(exc).__name__}: {exc}",
        )

    exact_replay = residual == 0
    denominator_branch_closed = False
    denominator_branch_quotients: tuple[sp.Expr, ...] = ()
    denominator_branch_remainder = sp.Symbol("unknown")
    denominator_branch_replay_residual = sp.Symbol("unknown")
    denominator_branch_basis: tuple[sp.Expr, ...] = ()
    denominator_branch_method: str | None = None
    if exact_replay and remainder == 0 and unsupported_denominator_assumptions:
        renamed_denominator = coefficient_denominator.xreplace(forward_symbols)
        branch_equation_code = (
            "{"
            + ",".join(
                (
                    *map(_wolfram_expression, renamed_equations),
                    _wolfram_expression(renamed_denominator),
                )
            )
            + "}"
        )
        all_variable_code = "{" + ",".join(map(str, wolfram_symbols)) + "}"
        reversed_all_variable_code = (
            "{" + ",".join(map(str, reversed(wolfram_symbols))) + "}"
        )
        branch_target = _wolfram_expression(renamed_goal)
        branch_attempts = "{" + ",".join(
            (
                f'<|"strategy" -> "grevlex-forward", "reduction" -> PolynomialReduce[{branch_target}, {branch_equation_code}, {all_variable_code}, MonomialOrder -> DegreeReverseLexicographic]|>',
                f'<|"strategy" -> "lex-forward", "reduction" -> PolynomialReduce[{branch_target}, {branch_equation_code}, {all_variable_code}, MonomialOrder -> Lexicographic]|>',
                f'<|"strategy" -> "grevlex-reverse", "reduction" -> PolynomialReduce[{branch_target}, {branch_equation_code}, {reversed_all_variable_code}, MonomialOrder -> DegreeReverseLexicographic]|>',
                f'<|"strategy" -> "lex-reverse", "reduction" -> PolynomialReduce[{branch_target}, {branch_equation_code}, {reversed_all_variable_code}, MonomialOrder -> Lexicographic]|>',
            )
        ) + "}"
        branch_computation = (
            f"Module[{{fullBasis, fullReduction, attempts, selected, basis, reduction}}, "
            f"fullBasis = GroebnerBasis[{equation_code}, {all_variable_code}, MonomialOrder -> DegreeReverseLexicographic]; "
            f"fullReduction = PolynomialReduce[{branch_target}, fullBasis, {all_variable_code}, MonomialOrder -> DegreeReverseLexicographic]; "
            "If[Last[fullReduction] === 0, "
            '<|"method" -> "full-ring-groebner", "strategy" -> "full-ring-groebner-grevlex", "basis" -> fullBasis, "quotients" -> First[fullReduction], "remainder" -> Last[fullReduction]|>, '
            f"attempts = {branch_attempts}; "
            'selected = SelectFirst[attempts, Last[#["reduction"]] === 0 &, First[attempts]]; '
            'If[Last[selected["reduction"]] === 0, '
            '<|"method" -> "direct", "strategy" -> selected["strategy"], "basis" -> {}, "quotients" -> First[selected["reduction"]], "remainder" -> Last[selected["reduction"]]|>, '
            f'basis = GroebnerBasis[{branch_equation_code}, {all_variable_code}, MonomialOrder -> DegreeReverseLexicographic]; '
            f'reduction = PolynomialReduce[{branch_target}, basis, {all_variable_code}, MonomialOrder -> DegreeReverseLexicographic]; '
            '<|"method" -> "denominator-zero-groebner", "strategy" -> "groebner-grevlex", "basis" -> basis, "quotients" -> First[reduction], "remainder" -> Last[reduction]|>]]]'
        )
        branch_script = "\n".join(
            (
                f"result = TimeConstrained[{branch_computation}, {timeout_seconds}, $Failed];",
                'payload = If[result === $Failed, <|"status" -> "timeout"|>, <|"status" -> "complete", "method" -> result["method"], "strategy" -> result["strategy"], "basis" -> (ToString[InputForm[#]] & /@ result["basis"]), "quotients" -> (ToString[InputForm[#]] & /@ result["quotients"]), "remainder" -> ToString[InputForm[result["remainder"]]]|>];',
                'WriteString[$Output, ExportString[payload, "RawJSON"], "\\n"];',
            )
        )
        with tempfile.TemporaryDirectory(
            prefix="mortra-wolfram-denominator-branch-"
        ) as raw:
            branch_path = Path(raw) / "branch.wl"
            branch_path.write_text(branch_script, encoding="utf-8")
            try:
                branch_completed = runner(
                    [str(executable.resolve()), "-file", str(branch_path)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout_seconds + 180,
                    check=False,
                )
                branch_payload = _extract_json(branch_completed.stdout)
                if branch_payload.get("status") == "complete":
                    denominator_branch_method = str(
                        branch_payload.get("method", "direct")
                    )
                    denominator_branch_basis = tuple(
                        _parse_wolfram_expression(str(item), inverse_symbols)
                        for item in branch_payload.get("basis", ())
                    )
                    denominator_branch_quotients = tuple(
                        _parse_wolfram_expression(str(item), inverse_symbols)
                        for item in branch_payload.get("quotients", ())
                    )
                    denominator_branch_remainder = _parse_wolfram_expression(
                        str(branch_payload.get("remainder", "unknown")),
                        inverse_symbols,
                    )
                    branch_replay_equations = (
                        denominator_branch_basis
                        if denominator_branch_method
                        in {"full-ring-groebner", "denominator-zero-groebner"}
                        else (*equations, coefficient_denominator)
                    )
                    denominator_branch_replay_residual = replay_polynomial_reduction(
                        goal,
                        branch_replay_equations,
                        denominator_branch_quotients,
                        denominator_branch_remainder,
                    )
                    denominator_branch_closed = (
                        denominator_branch_remainder == 0
                        and denominator_branch_replay_residual == 0
                    )
            except (subprocess.TimeoutExpired, ValueError, json.JSONDecodeError):
                denominator_branch_closed = False
    proved = (
        exact_replay
        and remainder == 0
        and preprocessing_replayed
        and (
            not unsupported_denominator_assumptions
            or denominator_branch_closed
        )
    )
    material = "|".join(
        (
            *map(str, equations),
            str(goal),
            str(multiplier),
            *saturation_assumptions_used,
            *map(str, quotients),
            str(remainder),
            str(preprocessing_replayed),
            str(preprocessing_certificate_sha256),
            str(denominator_branch_closed),
            *map(str, denominator_branch_quotients),
            *map(str, denominator_branch_basis),
            str(denominator_branch_method),
            str(denominator_branch_remainder),
            str(denominator_branch_replay_residual),
        )
    )
    return WolframPolynomialCertificate(
        status="proved" if proved else "unproved",
        exact_replay=exact_replay,
        equation_count=len(equations),
        variable_count=len(reduction_symbols),
        initial_equation_count=initial_equation_count,
        initial_variable_count=initial_variable_count,
        initial_total_expanded_terms=initial_total_expanded_terms,
        reduced_total_expanded_terms=reduced_total_expanded_terms,
        quotient_certificate=tuple(map(str, quotients)),
        remainder=str(remainder),
        replay_residual=str(residual),
        elapsed_seconds=time.perf_counter() - started,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        reduction_strategy=reduction_strategy,
        preprocessing=preprocessing,
        backend_stdout=completed.stdout,
        backend_stderr=completed.stderr,
        reason=(
            None
            if not unsupported_denominator_assumptions or denominator_branch_closed
            else (
                "coefficient denominator vanishes by a construction equation"
                if coefficient_denominator_is_construction_equation
                else "coefficient denominator is not source-semantically nonzero: "
                + ", ".join(unsupported_denominator_assumptions)
            )
        ),
        saturation_multiplier=str(multiplier),
        saturation_assumptions_used=saturation_assumptions_used,
        preprocessing_replayed=preprocessing_replayed,
        preprocessing_certificate_sha256=preprocessing_certificate_sha256,
        denominator_branch_closed=denominator_branch_closed,
        denominator_branch_quotients=tuple(
            map(str, denominator_branch_quotients)
        ),
        denominator_branch_remainder=str(denominator_branch_remainder),
        denominator_branch_replay_residual=str(
            denominator_branch_replay_residual
        ),
        denominator_branch_basis=tuple(map(str, denominator_branch_basis)),
        denominator_branch_method=denominator_branch_method,
        coefficient_denominator_is_construction_equation=(
            coefficient_denominator_is_construction_equation
        ),
    )
