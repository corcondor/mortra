"""Auditable diagnostics for symmetric prime-power primality problems.

Target family::

    x = a**a, d = b**b - c**c,
    x + d and x - d are prime,
    where a, b, and c are prime.

The search is exhaustive inside the requested bound after applying proved
necessary conditions.  It is still a computational result, not a formal proof
for unbounded primes.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import asdict, dataclass
from hashlib import sha256
from math import isqrt
from time import perf_counter
from typing import Any, Callable

try:
    import gmpy2
except ImportError:  # pragma: no cover
    gmpy2 = None

try:
    import sympy
    from sympy import isprime as sympy_isprime
    from sympy import primerange
except ImportError:  # pragma: no cover
    sympy = None
    sympy_isprime = None
    primerange = None


ProgressCallback = Callable[[int, int, int], None]


CONDITIONS_1_TO_5 = (
    "C1: none of a,b,c equals 2",
    "C2: a,b,c are odd primes",
    "C3: a,b,c are pairwise distinct",
    "C4: a is the largest of a,b,c",
    "C5: b<a and c<a",
)


@dataclass(frozen=True)
class PrimePowerSymmetricPrimalityIR:
    """Typed structural form of x+d and x-d simultaneous primality."""

    family_id: str
    center_variable: str
    positive_offset_variable: str
    negative_offset_variable: str
    prime_variables: tuple[str, str, str]
    target_coefficient_vectors: tuple[dict[str, int], dict[str, int]]
    query: str
    symmetry_action: str
    necessary_conditions: tuple[str, ...] = CONDITIONS_1_TO_5

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PrimePowerSymmetryReport:
    problem: str
    status: str
    reductions: list[str]
    necessary_conditions: list[str]
    search_limit: int
    sieve_bound: int
    candidate_a_values: int
    canonical_pairs_checked: int
    ordered_triples_covered: int
    rejected_by_modulo_3: int
    rejected_by_modular_factor: int
    exact_compositeness_checks: int
    candidate_triples_after_sieve: int
    sieve_checkpoint_survivors: dict[str, int]
    sieve_survivor_sample: list[tuple[int, int, int]]
    primality_checks_enabled: bool
    examples: list[tuple[int, int, int, str, str]]
    audit_sha256: str
    backend: str
    backend_version: str
    elapsed_seconds: float
    warnings: list[str]

    @property
    def checked_triples(self) -> int:
        """Backward-compatible name used by the first diagnostic."""
        return self.ordered_triples_covered

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["checked_triples"] = self.checked_triples
        return data


def analyze_prime_power_symmetry(
    search_limit: int = 100,
    sieve_bound: int = 200,
    run_primality_checks: bool = True,
    survivor_sample_size: int = 20,
    progress: ProgressCallback | None = None,
) -> PrimePowerSymmetryReport:
    """Search all prime triples with ``a <= search_limit``.

    Swapping b and c only swaps the two target values.  Therefore b<c is a
    complete set of representatives for the S2 action on ordered pairs (b,c).
    ``ordered_triples_covered`` reports the corresponding unquotiented count.
    """
    reductions = [
        "If one of a,b,c is 2, parity or positivity rules out a solution.",
        "Hence any solution has a,b,c odd primes.",
        "If two variables are equal, one target is a nontrivial prime power; hence a,b,c are distinct.",
        "Monotonicity of p^p implies b,c<a; otherwise one target is non-positive.",
        "Modulo a gives PQ≡-(b^b-c^c)^2, but this alone imposes no congruence class on a.",
        "Modulo 3 rules out b=3 or c=3 and otherwise requires b and c to have the same residue.",
        "The S2 action (b,c)->(c,b) swaps the targets, so b<c is a complete symmetry quotient.",
    ]
    warnings = [
        "The bound is exhaustive, but it is not a proof for a above search_limit.",
        "The result depends on the recorded software backend and should be reproduced independently.",
    ]
    if primerange is None:
        return _empty_report(
            status="missing_sympy",
            reductions=reductions,
            search_limit=search_limit,
            sieve_bound=sieve_bound,
            run_primality_checks=run_primality_checks,
            warnings=warnings + ["sympy is unavailable"],
        )
    if search_limit < 2:
        return _empty_report(
            status="no_example_in_bounded_search",
            reductions=reductions,
            search_limit=search_limit,
            sieve_bound=sieve_bound,
            run_primality_checks=run_primality_checks,
            warnings=warnings,
        )

    started = perf_counter()
    primes = list(primerange(3, search_limit + 1))
    sieve_primes = list(primerange(3, max(4, sieve_bound + 1)))
    candidate_as = primes
    powers = {p: p**p for p in primes} if run_primality_checks else {}
    residues = {
        p: tuple(pow(p, p, modulus) for modulus in sieve_primes)
        for p in primes
    }
    audit = sha256()
    canonical_checked = 0
    modulo_3_rejections = 0
    modular_rejections = 0
    first_factor_counts: dict[int, int] = {}
    exact_checks = 0
    after_sieve = 0
    sieve_survivors: list[tuple[int, int, int]] = []
    examples: list[tuple[int, int, int, str, str]] = []

    for a_index, a in enumerate(candidate_as, start=1):
        x_residues = residues[a]
        lower_primes = [p for p in primes if p < a]
        for b_index, b in enumerate(lower_primes):
            b_residues = residues[b]
            for c in lower_primes[b_index + 1 :]:
                canonical_checked += 1
                if b == 3 or c == 3 or b % 3 != c % 3:
                    modulo_3_rejections += 1
                    audit.update(f"{a},{b},{c}:modulo:3\n".encode("ascii"))
                    continue
                c_residues = residues[c]
                factor = first_small_factor(
                    x_residues,
                    b_residues,
                    c_residues,
                    sieve_primes,
                )
                if factor is not None:
                    modular_rejections += 1
                    first_factor_counts[factor[1]] = first_factor_counts.get(factor[1], 0) + 1
                    audit.update(f"{a},{b},{c}:factor:{factor}\n".encode("ascii"))
                    continue

                after_sieve += 1
                if len(sieve_survivors) < survivor_sample_size:
                    sieve_survivors.append((a, b, c))
                if not run_primality_checks:
                    audit.update(f"{a},{b},{c}:sieve_survivor\n".encode("ascii"))
                    continue
                x = powers[a]
                delta = powers[b] - powers[c]
                first = x + delta
                second = x - delta
                exact_checks += 1
                first_status = primality_status(first)
                if first_status == 0:
                    audit.update(f"{a},{b},{c}:composite:first\n".encode("ascii"))
                    continue
                second_status = primality_status(second)
                if second_status == 0:
                    audit.update(f"{a},{b},{c}:composite:second\n".encode("ascii"))
                    continue

                audit.update(f"{a},{b},{c}:survivor\n".encode("ascii"))
                examples.append((a, b, c, str(first), str(second)))
                break
            if examples:
                break
        if progress is not None:
            progress(a, a_index, len(candidate_as))
        if examples:
            break

    if run_primality_checks:
        backend, backend_version = primality_backend()
    else:
        backend, backend_version = "builtin modular pow", "python"
    after_modulo_3 = canonical_checked - modulo_3_rejections
    checkpoint_bounds = sorted(
        {bound for bound in (100, 500, 1000, 5000, 20000, sieve_bound) if bound <= sieve_bound}
    )
    sieve_checkpoint_survivors = {
        str(bound): after_modulo_3
        - sum(count for factor, count in first_factor_counts.items() if factor <= bound)
        for bound in checkpoint_bounds
    }
    if examples:
        status = "found_probable_example"
    elif not run_primality_checks and after_sieve:
        status = "sieve_survivors_remaining"
    elif not run_primality_checks:
        status = "no_example_by_modular_sieve"
    else:
        status = "no_example_in_bounded_search"
    return PrimePowerSymmetryReport(
        problem="prime_power_symmetric_primality",
        status=status,
        reductions=reductions,
        necessary_conditions=list(CONDITIONS_1_TO_5),
        search_limit=search_limit,
        sieve_bound=sieve_bound,
        candidate_a_values=len(candidate_as),
        canonical_pairs_checked=canonical_checked,
        ordered_triples_covered=2 * canonical_checked,
        rejected_by_modulo_3=modulo_3_rejections,
        rejected_by_modular_factor=modular_rejections,
        exact_compositeness_checks=exact_checks,
        candidate_triples_after_sieve=after_sieve,
        sieve_checkpoint_survivors=sieve_checkpoint_survivors,
        sieve_survivor_sample=sieve_survivors,
        primality_checks_enabled=run_primality_checks,
        examples=examples,
        audit_sha256=audit.hexdigest(),
        backend=backend,
        backend_version=backend_version,
        elapsed_seconds=round(perf_counter() - started, 6),
        warnings=warnings,
    )


def first_small_factor(
    x_residues: tuple[int, ...],
    y_residues: tuple[int, ...],
    z_residues: tuple[int, ...],
    sieve_primes: list[int],
) -> tuple[str, int] | None:
    """Return a certified small divisor of one target, when available."""
    for index, modulus in enumerate(sieve_primes):
        delta = (y_residues[index] - z_residues[index]) % modulus
        if (x_residues[index] + delta) % modulus == 0:
            return ("first", modulus)
        if (x_residues[index] - delta) % modulus == 0:
            return ("second", modulus)
    return None


def compile_prime_power_symmetric_ir(text: str) -> PrimePowerSymmetricPrimalityIR | None:
    """Lift text by algebraic structure, independent of term order and wording."""
    normalized = (
        text.replace("−", "-")
        .replace("－", "-")
        .replace("＋", "+")
        .replace("\\,", "")
        .replace("$", "")
    )
    prime_variables = _declared_prime_variables(normalized)
    vectors = _self_power_expression_vectors(normalized)
    for left_index, left in enumerate(vectors):
        for right in vectors[left_index + 1 :]:
            variables = set(left) | set(right)
            summed = {name: left.get(name, 0) + right.get(name, 0) for name in variables}
            difference = {name: left.get(name, 0) - right.get(name, 0) for name in variables}
            if any(value % 2 for value in (*summed.values(), *difference.values())):
                continue
            center = {name: value // 2 for name, value in summed.items() if value}
            offset = {name: value // 2 for name, value in difference.items() if value}
            if sorted(center.values()) != [1] or sorted(offset.values()) != [-1, 1]:
                continue
            center_variable = next(iter(center))
            positive = next(name for name, value in offset.items() if value == 1)
            negative = next(name for name, value in offset.items() if value == -1)
            triple = (center_variable, positive, negative)
            if len(set(triple)) != 3 or not set(triple).issubset(prime_variables):
                continue
            return PrimePowerSymmetricPrimalityIR(
                family_id="elementary_number_theory.prime_power_symmetric_primality",
                center_variable=center_variable,
                positive_offset_variable=positive,
                negative_offset_variable=negative,
                prime_variables=triple,
                target_coefficient_vectors=(left, right),
                query="ExistsPrimeTriple",
                symmetry_action="S2 swaps offset variables and target expressions",
            )
    return None


def _declared_prime_variables(text: str) -> set[str]:
    declared: set[str] = set()
    patterns = (
        r"素数\s*([A-Za-z](?:\s*[,、]\s*[A-Za-z]){1,})",
        r"(?:prime numbers?|primes?)\s+([A-Za-z](?:\s*[,、]\s*[A-Za-z]){1,})",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            declared.update(re.findall(r"[A-Za-z]", match.group(1)))
    return declared


def _self_power_expression_vectors(text: str) -> list[dict[str, int]]:
    token = re.compile(
        r"(?P<sign>[+-]?)\s*(?P<base>[A-Za-z])\s*"
        r"(?:\^\s*\{?\s*(?P<exp_caret>[A-Za-z])\s*\}?|\*\*\s*(?P<exp_star>[A-Za-z]))"
    )
    runs: list[list[tuple[str, int]]] = []
    current: list[tuple[str, int]] = []
    previous_end: int | None = None
    for match in token.finditer(text):
        gap = text[previous_end : match.start()] if previous_end is not None else ""
        if current and gap.strip():
            runs.append(current)
            current = []
        base = match.group("base")
        exponent = match.group("exp_caret") or match.group("exp_star")
        if base != exponent:
            if current:
                runs.append(current)
                current = []
            previous_end = match.end()
            continue
        current.append((base, -1 if match.group("sign") == "-" else 1))
        previous_end = match.end()
    if current:
        runs.append(current)

    vectors: list[dict[str, int]] = []
    for run in runs:
        if len(run) != 3:
            continue
        vector: dict[str, int] = {}
        for name, coefficient in run:
            vector[name] = vector.get(name, 0) + coefficient
        vectors.append(vector)
    return vectors


def passes_small_prime_sieve(
    x_residues: tuple[int, ...],
    y_residues: tuple[int, ...],
    z_residues: tuple[int, ...],
    sieve_primes: list[int],
) -> bool:
    return first_small_factor(x_residues, y_residues, z_residues, sieve_primes) is None


def primality_status(value: int) -> int:
    """Return 0 for composite, 1 for probable prime, and 2 for proven prime."""
    if value <= 1:
        return 0
    if gmpy2 is not None:
        return int(gmpy2.is_prime(value))
    if sympy_isprime is not None:
        return 2 if sympy_isprime(value) else 0
    if value % 2 == 0:
        return 2 if value == 2 else 0
    for divisor in range(3, isqrt(value) + 1, 2):
        if value % divisor == 0:
            return 0
    return 2


def is_probable_prime(value: int) -> bool:
    return primality_status(value) > 0


def primality_backend() -> tuple[str, str]:
    if gmpy2 is not None:
        version = getattr(gmpy2, "version", lambda: "unknown")()
        return "gmpy2.is_prime", str(version)
    if sympy_isprime is not None:
        return "sympy.isprime", str(getattr(sympy, "__version__", "unknown"))
    return "trial_division", "builtin"


def _empty_report(
    *,
    status: str,
    reductions: list[str],
    search_limit: int,
    sieve_bound: int,
    run_primality_checks: bool,
    warnings: list[str],
) -> PrimePowerSymmetryReport:
    backend, backend_version = primality_backend()
    return PrimePowerSymmetryReport(
        problem="prime_power_symmetric_primality",
        status=status,
        reductions=reductions,
        necessary_conditions=list(CONDITIONS_1_TO_5),
        search_limit=search_limit,
        sieve_bound=sieve_bound,
        candidate_a_values=0,
        canonical_pairs_checked=0,
        ordered_triples_covered=0,
        rejected_by_modulo_3=0,
        rejected_by_modular_factor=0,
        exact_compositeness_checks=0,
        candidate_triples_after_sieve=0,
        sieve_checkpoint_survivors={},
        sieve_survivor_sample=[],
        primality_checks_enabled=run_primality_checks,
        examples=[],
        audit_sha256=sha256(b"").hexdigest(),
        backend=backend,
        backend_version=backend_version,
        elapsed_seconds=0.0,
        warnings=warnings,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="inclusive upper bound for a")
    parser.add_argument("--sieve-bound", type=int, default=200)
    parser.add_argument(
        "--sieve-only",
        action="store_true",
        help="stop after certified congruence filtering; do not run primality tests",
    )
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args()

    progress = None
    if args.progress:
        progress = lambda a, index, total: print(
            f"progress a={a} ({index}/{total})", flush=True
        )
    report = analyze_prime_power_symmetry(
        search_limit=args.limit,
        sieve_bound=args.sieve_bound,
        run_primality_checks=not args.sieve_only,
        progress=progress,
    )
    import json

    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
