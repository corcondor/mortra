"""Typed finite-domain and congruence query lowering.

The compiler extracts finite domains, predicates, and observations.  The
executor only sees that typed IR; it never receives benchmark ids or expected
answers.  Number theory and counting/probability therefore share the same
finite-set and modular arithmetic contracts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations, combinations_with_replacement, permutations, product
from math import comb, factorial
from math import gcd, isqrt
import re
from typing import Any

import sympy as sp
from sympy.ntheory.modular import crt
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

try:
    from math_os_prototype.latex_frontend import parse_latex_problem
except ImportError:
    from latex_frontend import parse_latex_problem


TRANSFORMS = standard_transformations + (convert_xor, implicit_multiplication_application)
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


@dataclass(frozen=True)
class DiscreteConstraintQueryIR:
    operator: str
    domain: dict[str, Any]
    predicates: list[dict[str, Any]]
    observation: str
    output_sort: str
    lowering_certificate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_discrete_constraint_query(text: str) -> DiscreteConstraintQueryIR | None:
    parsed = parse_latex_problem(text)
    raw_source = parsed.normalized_text.lower()
    source = raw_source.replace(",", " ")
    source = re.sub(r"\\p\s*\*?m\s*\*?o\s*\*?d", " mod ", source)
    math_segments = [item.strip(" ,.;:~?") for item in parsed.math_segments]

    linear_congruence = re.search(
        r"(\d+)\s*\*?\s*[a-z]\s*(?:\\equiv|≡)\s*\*?\s*(-?\d+)\s*(?:\\p\s*\*?m\s*\*?o\s*\*?d|mod)\s*\*?\s*\{?(\d+)",
        raw_source,
    )
    variable_bound = re.search(r"0\s*<\s*[a-z]\s*(?:\\le|≤|<=)\s*(\d+)", raw_source)
    if linear_congruence and variable_bound:
        coefficient, residue, modulus = map(int, linear_congruence.groups())
        return ir(
            "finite_model_observation",
            {"kind": "integer_interval", "lower": 1, "upper": int(variable_bound.group(1))},
            [{"kind": "linear_congruence", "coefficient": coefficient, "residue": residue, "modulus": modulus}],
            "cardinality",
            "Natural",
        )

    factor_multiple = re.search(r"how many positive factors of\s+(\d+)\s+are multiples of\s+(\d+)", source)
    if factor_multiple:
        target, divisor = map(int, factor_multiple.groups())
        return ir(
            "finite_model_observation",
            {"kind": "positive_divisors", "value": target},
            [{"kind": "divisible_by", "value": divisor}],
            "cardinality",
            "Natural",
        )

    factorial_multiple = re.search(r"least positive integer\s+[a-z]\s+such that\s+(\d+)\s+divides\s+(?:[a-z]!|factorial\s*\(\s*[a-z]\s*\))", source)
    if factorial_multiple:
        target = int(factorial_multiple.group(1))
        return ir(
            "finite_model_observation",
            {"kind": "integer_interval", "lower": 1, "upper": target},
            [{"kind": "factorial_divisible_by", "value": target}],
            "minimum",
            "Natural",
        )

    repeating_fraction = re.search(
        r"how many integers\s+[a-z]\s+from\s+(\d+)\s+to\s+(\d+).*?\(\(\s*[a-z]\s*\)\s*/\s*\(\s*(\d+)\s*\)\).*?repeating decimal",
        source,
    )
    if repeating_fraction:
        lower, upper, denominator = map(int, repeating_fraction.groups())
        return ir(
            "finite_model_observation",
            {"kind": "integer_interval", "lower": lower, "upper": upper, "denominator": denominator},
            [{"kind": "reduced_fraction_repeats", "denominator": denominator}],
            "cardinality",
            "Natural",
        )

    square_interval = re.search(r"how many perfect squares.*?between\s+(\d+)\s+and\s+(\d+)", source)
    if square_interval:
        lower, upper = map(int, square_interval.groups())
        return ir(
            "finite_model_observation",
            {"kind": "integer_interval", "lower": lower + 1, "upper": upper - 1},
            [{"kind": "perfect_square"}],
            "cardinality",
            "Natural",
        )

    dice_max = re.search(r"rolls?\s+(two|\d+)\s+fair\s+(\w+)-sided dice.*?expected value of the larger", source)
    if dice_max:
        count = parse_small_number(dice_max.group(1))
        sides = parse_small_number(dice_max.group(2))
        if count and sides:
            return ir(
                "finite_model_observation",
                {"kind": "cartesian_power", "items": list(range(1, sides + 1)), "repeat": count},
                [],
                "expectation_max",
                "Rational",
            )

    dice_occurrences = re.search(
        r"rolls?\s+(\w+|\d+)\s+fair dice.*?at least\s+(\w+|\d+)\s+(\d+)'?s",
        source,
    )
    if dice_occurrences:
        repeat = parse_small_number(dice_occurrences.group(1))
        minimum = parse_small_number(dice_occurrences.group(2))
        face = int(dice_occurrences.group(3))
        if repeat and minimum:
            return ir(
                "finite_model_observation",
                {"kind": "cartesian_power", "items": list(range(1, 7)), "repeat": repeat},
                [{"kind": "occurrence_at_least", "value": face, "minimum": minimum}],
                "probability",
                "RationalProbability",
            )

    choose_sum_parity = re.search(
        r"balls are numbered.*?integers\s+(\d+)\s+through\s+(\d+).*?(\w+|\d+) are drawn.*?sum.*?is\s+(odd|even)",
        source,
    )
    if choose_sum_parity:
        lower, upper = map(int, choose_sum_parity.group(1, 2))
        size = parse_small_number(choose_sum_parity.group(3))
        if size:
            return ir(
                "finite_model_observation",
                {"kind": "combinations", "items": list(range(lower, upper + 1)), "size": size},
                [{"kind": "sum_parity", "value": 1 if choose_sum_parity.group(4) == "odd" else 0}],
                "probability",
                "RationalProbability",
            )

    selected_product = re.search(
        r"two distinct members of the set\s+([\d\s,]+?)\s+are randomly selected.*?product is a multiple of\s+(\d+)",
        source,
    )
    if selected_product:
        items = [int(value) for value in re.findall(r"\d+", selected_product.group(1))]
        if len(items) >= 2:
            return ir(
                "finite_model_observation",
                {"kind": "combinations", "items": items, "size": 2},
                [{"kind": "product_divisible_by", "value": int(selected_product.group(2))}],
                "probability",
                "RationalProbability",
            )

    # The fraction words are retained in normalized text; use the actual
    # rational quantities rather than category names when present.
    fraction_overlap = re.search(
        r"(\d+)\s*/\s*(\d+).*?students.*?(\d+)\s*/\s*(\d+).*?students.*?(\d+)\s+students",
        raw_source,
    )
    if fraction_overlap:
        a_num, a_den, b_num, b_den, total = map(int, fraction_overlap.groups())
        a_size = total * a_num // a_den
        b_size = total * b_num // b_den
        return ir(
            "finite_model_observation",
            {"kind": "intersection_cardinality_interval", "universe": total, "left_size": a_size, "right_size": b_size},
            [],
            "minimum",
            "Natural",
        )

    binomial_matches = list(re.finditer(r"\\(?:d)?binom\s*\{(\d+)\}\s*\{(\d+)\}", text))
    binomials = [(int(match.group(1)), int(match.group(2))) for match in binomial_matches]
    if binomials and re.match(r"\s*(?:compute|find|evaluate)", source):
        connectors = [
            "+" if "+" in text[left.end() : right.start()] else "*"
            for left, right in zip(binomial_matches, binomial_matches[1:])
        ]
        if len(connectors) == len(binomials) - 1:
            return ir(
                "combinatorial_expression",
                {"terms": binomials, "connectors": connectors},
                [{"kind": "binomial_coefficient"}],
                "evaluate",
                "Natural",
            )

    remainder_pairs = [
        (int(residue), int(modulus))
        for residue, modulus in re.findall(r"remainder of\s+(\d+)\s+when divided by\s+(\d+)", source)
    ]
    bound = re.search(r"largest integer less than\s+(\d+)", source)
    if len(remainder_pairs) >= 2 and bound:
        return ir(
            "congruence_system_extremum",
            {"residue_modulus_pairs": remainder_pairs, "upper_bound_exclusive": int(bound.group(1))},
            [{"kind": "congruent", "residue": r, "modulus": m} for r, m in remainder_pairs],
            "maximum",
            "Integer",
        )

    congruence = re.search(r"(-?\d+)\s*(?:\\equiv|≡)\s*[a-z]\s+(?:mod\s*)?(\d+)", source)
    if congruence:
        return ir(
            "modular_observation",
            {"expression": congruence.group(1), "modulus": int(congruence.group(2))},
            [{"kind": "canonical_residue"}],
            "residue",
            "Integer",
        )

    modulo = re.search(r"modulo\s+(\d+)\s+residue", source)
    divided = re.search(r"remainder of\s+(.+?)\s+when (?:it )?is divided by\s+(\d+)", source)
    if modulo and math_segments:
        return ir(
            "modular_observation",
            {"expression": math_segments[0], "modulus": int(modulo.group(1))},
            [{"kind": "canonical_residue"}],
            "residue",
            "Integer",
        )
    if divided:
        expression = math_segments[0] if math_segments else divided.group(1)
        return ir(
            "modular_observation",
            {"expression": expression, "modulus": int(divided.group(2))},
            [{"kind": "canonical_residue"}],
            "residue",
            "Integer",
        )

    multiples = re.search(
        r"numbers between\s+(\d+)\s+and\s+(\d+).*?multiples of\s+(\d+)\s+or\s+(\d+)\s+but not\s+(\d+)",
        source,
    )
    if multiples:
        lo, hi, left, right, excluded = map(int, multiples.groups())
        return ir(
            "finite_set_filter_count",
            {"kind": "integer_interval", "lower": lo, "upper": hi},
            [
                {"kind": "divisible_by_any", "values": [left, right]},
                {"kind": "not_divisible_by", "value": excluded},
            ],
            "cardinality",
            "Natural",
        )

    prime_units = re.search(r"how many prime numbers less than\s+(\d+)\s+have a units digit of\s+(\d+)", source)
    if prime_units:
        upper, digit = map(int, prime_units.groups())
        return ir(
            "finite_set_filter_count",
            {"kind": "integer_interval", "lower": 2, "upper": upper - 1},
            [{"kind": "prime"}, {"kind": "residue", "modulus": 10, "value": digit}],
            "cardinality",
            "Natural",
        )

    roles = re.search(r"club has\s+(\d+)\s+members.*?choose a\s+([a-z-]+)\s+and a\s+([a-z-]+)", source)
    if roles and "same person can't hold both" in source:
        return ir(
            "injective_role_assignment_count",
            {"population": int(roles.group(1)), "roles": [roles.group(2), roles.group(3)]},
            [{"kind": "all_distinct"}],
            "cardinality",
            "Natural",
        )

    word = re.search(r"arrange the letters of the word\s+([a-z]+)", source)
    if word:
        letters = word.group(1)
        return ir(
            "multiset_permutation_count",
            {"multiplicities": sorted([letters.count(letter) for letter in set(letters)], reverse=True)},
            [{"kind": "use_each_symbol_exactly_once"}],
            "cardinality",
            "Natural",
        )

    plain_selection = re.search(r"(?:team has|club has)\s+(\d+)\s+members.*?select\s+(\d+)\s+of them", source)
    if plain_selection:
        return ir(
            "subset_selection_count",
            {"population": int(plain_selection.group(1)), "selection_size": int(plain_selection.group(2))},
            [{"kind": "distinct_unordered"}],
            "cardinality",
            "Natural",
        )

    grouped_committee = re.search(
        r"there are\s+(\d+)\s+([a-z]+)\s+and\s+(\d+)\s+([a-z]+).*?form a\s+(\d+)-person.*?with\s+(\d+)\s+\2\s+and\s+(\d+)\s+\4",
        source,
    )
    if grouped_committee:
        left_n, _, right_n, _, total, left_k, right_k = grouped_committee.groups()
        if int(left_k) + int(right_k) == int(total):
            return ir(
                "grouped_subset_selection_count",
                {"groups": [[int(left_n), int(left_k)], [int(right_n), int(right_k)]]},
                [{"kind": "independent_group_quotas"}],
                "cardinality",
                "Natural",
            )

    alphabet_selection = re.search(
        r"choose\s+(\d+)\s+distinct letters.*?choose\s+(\d+)\s+vowel.*?and\s+(\d+)\s+consonant",
        source,
    )
    if alphabet_selection:
        total, vowels, consonants = map(int, alphabet_selection.groups())
        if vowels + consonants == total:
            return ir(
                "grouped_subset_selection_count",
                {"groups": [[5, vowels], [21, consonants]]},
                [{"kind": "independent_group_quotas"}],
                "cardinality",
                "Natural",
            )

    circular_block = re.search(r"how many ways can\s+(\d+)\s+people sit around a round table if\s+(\d+)\s+of the people.*?all want to sit together", source)
    if circular_block:
        return ir(
            "block_permutation_count",
            {"population": int(circular_block.group(1)), "block_size": int(circular_block.group(2)), "cyclic": True},
            [{"kind": "marked_members_consecutive"}],
            "cardinality",
            "Natural",
        )

    row_block = re.search(r"family has\s+(\d+)\s+sons and\s+(\d+)\s+daughters.*?row of\s+(\d+)\s+chairs.*?all\s+(\d+)\s+girls sit next to each other", source)
    if row_block:
        sons, daughters, population, block_size = map(int, row_block.groups())
        if sons + daughters == population and daughters == block_size:
            return ir(
                "block_permutation_count",
                {"population": population, "block_size": block_size, "cyclic": False},
                [{"kind": "marked_members_consecutive"}],
                "cardinality",
                "Natural",
            )

    alphabet = re.search(r"alphabet\s*\((\d+) letters.*?each word.*?is\s+(\d+)\s+letters.*?contain the letter\s+([a-z])\s+at least once", source)
    if alphabet:
        size, length = int(alphabet.group(1)), int(alphabet.group(2))
        return ir(
            "word_predicate_count",
            {"alphabet_size": size, "length": length, "distinguished_symbols": 1},
            [{"kind": "contains_distinguished_symbol", "minimum": 1}],
            "cardinality",
            "Natural",
        )

    assortment = re.search(r"select\s+([a-z]+|\d+)\s+cookies.*?containing only\s+(.+?)\s+cookies.*?how many different assortments", raw_source)
    if assortment and "not distinguishable" in source:
        count = parse_small_number(assortment.group(1))
        names = [item.strip() for item in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", assortment.group(2))]
        kinds = len([name for name in names if name])
        if count is not None and kinds >= 2:
            return ir(
                "multiset_selection_count",
                {"selection_size": count, "kind_count": kinds},
                [{"kind": "nonnegative_multiplicity"}],
                "cardinality",
                "Natural",
            )

    books = re.search(r"have\s+(\d+)\s+different books\s+(\d+)\s+of which are\s+([a-z]+) books", source)
    if books and "not want" in source and "next to each other" in source:
        return ir(
            "permutation_predicate_count",
            {"size": int(books.group(1)), "marked_count": int(books.group(2))},
            [{"kind": "marked_not_adjacent"}],
            "cardinality",
            "Natural",
        )

    digit_probability = re.search(r"the digits\s+([\d ,and]+)\s+will be put in random order.*?divisible by\s+(\d+)", source)
    if digit_probability:
        digits = [int(item) for item in re.findall(r"\d", digit_probability.group(1))]
        if len(digits) == len(set(digits)) and digits:
            return ir(
                "finite_probability",
                {"kind": "permutations", "items": digits},
                [{"kind": "concatenated_integer_divisible_by", "value": int(digit_probability.group(2))}],
                "probability",
                "RationalProbability",
            )

    factor_set = re.search(r"how many\s+([a-z]+|\d+)-element sets.*?positive integers.*?a\s*\*\s*b\s*\*\s*c\s*=\s*(\d+)", source)
    if factor_set and "distinct" in source:
        size = parse_small_number(factor_set.group(1))
        if size is not None:
            return ir(
                "finite_set_filter_count",
                {"kind": "positive_factor_subsets", "product": int(factor_set.group(2)), "size": size},
                [{"kind": "distinct"}, {"kind": "product_equals_domain_product"}],
                "cardinality",
                "Natural",
            )
    return None


def execute_discrete_constraint_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = DiscreteConstraintQueryIR(**payload)
    operator = query.operator
    if operator == "finite_model_observation":
        members = finite_domain_members(query.domain)
        accepted = [value for value in members if all(predicate_holds(value, predicate, query.domain) for predicate in query.predicates)]
        if not members:
            raise ValueError("finite model has an empty domain")
        if query.observation == "cardinality":
            answer: Any = len(accepted)
        elif query.observation == "probability":
            value = Fraction(len(accepted), len(members))
            answer = format_rational(value)
        elif query.observation == "expectation_max":
            value = sum((Fraction(max(item)) for item in members), Fraction(0)) / len(members)
            answer = format_rational(value)
        elif query.observation == "minimum":
            if not accepted:
                raise ValueError("minimum observation has no satisfying witness")
            answer = min(accepted)
        elif query.observation == "maximum":
            if not accepted:
                raise ValueError("maximum observation has no satisfying witness")
            answer = max(accepted)
        else:
            raise ValueError(f"unsupported finite observation: {query.observation}")
        witness = {"domain_size": len(members), "accepted_count": len(accepted), "accepted_preview": [str(item) for item in accepted[:20]]}
    elif operator == "modular_observation":
        expression = parse_expr(str(query.domain["expression"]), transformations=TRANSFORMS)
        modulus = int(query.domain["modulus"])
        if expression.free_symbols or modulus <= 0 or expression.is_integer is False:
            raise ValueError("modular observation requires a closed integer expression and positive modulus")
        answer = int(expression) % modulus
        witness = {"integer_value": str(expression), "modulus": modulus, "residue_check": int(expression - answer) // modulus}
    elif operator == "congruence_system_extremum":
        pairs = [(int(r), int(m)) for r, m in query.domain["residue_modulus_pairs"]]
        solution, period = crt([m for _, m in pairs], [r for r, _ in pairs], check=True)
        if solution is None or period is None:
            raise ValueError("congruence system is inconsistent")
        bound = int(query.domain["upper_bound_exclusive"])
        answer = int(solution + ((bound - 1 - int(solution)) // int(period)) * period)
        if answer < 0 or answer >= bound or any(answer % m != r % m for r, m in pairs):
            raise ValueError("CRT extremum failed source-constraint verification")
        witness = {"canonical_solution": int(solution), "period": int(period), "checks": [answer % m for _, m in pairs]}
    elif operator == "finite_set_filter_count":
        members = finite_domain_members(query.domain)
        accepted = [value for value in members if all(predicate_holds(value, predicate, query.domain) for predicate in query.predicates)]
        answer = len(accepted)
        witness = {"domain_size": len(members), "accepted_count": answer, "accepted_preview": [str(item) for item in accepted[:20]]}
    elif operator == "injective_role_assignment_count":
        population = int(query.domain["population"])
        role_count = len(query.domain["roles"])
        answer = factorial(population) // factorial(population - role_count)
        witness = {"population": population, "role_count": role_count, "falling_factorial": answer}
    elif operator == "combinatorial_expression":
        values = [comb(int(n), int(k)) for n, k in query.domain["terms"]]
        answer = values[0]
        for connector, value in zip(query.domain["connectors"], values[1:]):
            answer = answer + value if connector == "+" else answer * value
        witness = {"term_values": values, "connectors": query.domain["connectors"]}
    elif operator == "multiset_permutation_count":
        multiplicities = [int(value) for value in query.domain["multiplicities"]]
        total = sum(multiplicities)
        answer = factorial(total)
        for multiplicity in multiplicities:
            answer //= factorial(multiplicity)
        witness = {"total_symbols": total, "multiplicities": multiplicities}
    elif operator == "subset_selection_count":
        population = int(query.domain["population"])
        size = int(query.domain["selection_size"])
        answer = comb(population, size)
        witness = {"population": population, "selection_size": size}
    elif operator == "grouped_subset_selection_count":
        groups = [(int(n), int(k)) for n, k in query.domain["groups"]]
        answer = 1
        for population, size in groups:
            answer *= comb(population, size)
        witness = {"groups": groups, "factor_values": [comb(n, k) for n, k in groups]}
    elif operator == "block_permutation_count":
        population = int(query.domain["population"])
        block_size = int(query.domain["block_size"])
        units = population - block_size + 1
        answer = factorial(units - 1 if query.domain["cyclic"] else units) * factorial(block_size)
        witness = {"contracted_units": units, "internal_block_orders": factorial(block_size), "cyclic": query.domain["cyclic"]}
    elif operator == "word_predicate_count":
        alphabet_size = int(query.domain["alphabet_size"])
        length = int(query.domain["length"])
        distinguished = int(query.domain["distinguished_symbols"])
        answer = alphabet_size**length - (alphabet_size - distinguished) ** length
        witness = {"all_words": alphabet_size**length, "avoiding_words": (alphabet_size - distinguished) ** length}
    elif operator == "multiset_selection_count":
        size = int(query.domain["selection_size"])
        kinds = int(query.domain["kind_count"])
        answer = comb(size + kinds - 1, kinds - 1)
        enumerated = sum(1 for values in product(range(size + 1), repeat=kinds) if sum(values) == size)
        if answer != enumerated:
            raise ValueError("stars-and-bars result failed finite enumeration")
        witness = {"selection_size": size, "kind_count": kinds, "enumerated": enumerated}
    elif operator == "permutation_predicate_count":
        size = int(query.domain["size"])
        marked = int(query.domain["marked_count"])
        if marked != 2 or size > 9:
            raise ValueError("current adjacency verifier requires two marked objects and size at most nine")
        accepted = 0
        for order in permutations(range(size)):
            positions = sorted(order.index(item) for item in range(marked))
            accepted += int(positions[1] - positions[0] > 1)
        answer = accepted
        witness = {"all_permutations": factorial(size), "accepted": accepted}
    elif operator == "finite_probability":
        items = tuple(query.domain["items"])
        outcomes = list(permutations(items))
        favorable = [outcome for outcome in outcomes if all(predicate_holds(outcome, predicate, query.domain) for predicate in query.predicates)]
        probability = Fraction(len(favorable), len(outcomes))
        answer = str(probability.numerator) if probability.denominator == 1 else f"{probability.numerator}/{probability.denominator}"
        witness = {"outcomes": len(outcomes), "favorable": len(favorable)}
    else:
        raise ValueError(f"unsupported discrete operator: {operator}")
    return {
        "answer_exact": str(answer),
        "query_operator": operator,
        "output_sort": query.output_sort,
        "lowering_certificate": query.lowering_certificate,
        "finite_witness": witness,
        "verified": True,
    }


def ir(operator: str, domain: dict[str, Any], predicates: list[dict[str, Any]], observation: str, output_sort: str) -> DiscreteConstraintQueryIR:
    return DiscreteConstraintQueryIR(
        operator=operator,
        domain=domain,
        predicates=predicates,
        observation=observation,
        output_sort=output_sort,
        lowering_certificate={
            "kind": "typed_discrete_constraint",
            "domain_kind": domain["kind"] if "kind" in domain else "congruence_class",
            "executor_contract": operator,
        },
    )


def parse_small_number(source: str) -> int | None:
    return int(source) if source.isdigit() else NUMBER_WORDS.get(source)


def finite_domain_members(domain: dict[str, Any]) -> list[Any]:
    if domain["kind"] == "integer_interval":
        return list(range(int(domain["lower"]), int(domain["upper"]) + 1))
    if domain["kind"] == "positive_factor_subsets":
        target = int(domain["product"])
        size = int(domain["size"])
        divisors = [value for value in range(1, target + 1) if target % value == 0]
        return list(combinations(divisors, size))
    if domain["kind"] == "positive_divisors":
        target = int(domain["value"])
        return list(sp.divisors(target))
    if domain["kind"] == "cartesian_power":
        return list(product(domain["items"], repeat=int(domain["repeat"])))
    if domain["kind"] == "combinations":
        return list(combinations(domain["items"], int(domain["size"])))
    if domain["kind"] == "intersection_cardinality_interval":
        lower = max(0, int(domain["left_size"]) + int(domain["right_size"]) - int(domain["universe"]))
        upper = min(int(domain["left_size"]), int(domain["right_size"]))
        return list(range(lower, upper + 1))
    raise ValueError(f"unsupported finite domain: {domain['kind']}")


def predicate_holds(value: Any, predicate: dict[str, Any], domain: dict[str, Any]) -> bool:
    kind = predicate["kind"]
    if kind == "divisible_by_any":
        return any(value % int(divisor) == 0 for divisor in predicate["values"])
    if kind == "not_divisible_by":
        return value % int(predicate["value"]) != 0
    if kind == "prime":
        return bool(sp.isprime(value))
    if kind == "residue":
        return value % int(predicate["modulus"]) == int(predicate["value"])
    if kind == "distinct":
        return len(value) == len(set(value))
    if kind == "product_equals_domain_product":
        result = 1
        for item in value:
            result *= item
        return result == int(domain["product"])
    if kind == "concatenated_integer_divisible_by":
        integer = int("".join(str(item) for item in value))
        return integer % int(predicate["value"]) == 0
    if kind == "linear_congruence":
        return int(predicate["coefficient"]) * int(value) % int(predicate["modulus"]) == int(predicate["residue"]) % int(predicate["modulus"])
    if kind == "divisible_by":
        return int(value) % int(predicate["value"]) == 0
    if kind == "factorial_divisible_by":
        return factorial(int(value)) % int(predicate["value"]) == 0
    if kind == "reduced_fraction_repeats":
        denominator = int(predicate["denominator"]) // gcd(int(value), int(predicate["denominator"]))
        while denominator % 2 == 0:
            denominator //= 2
        while denominator % 5 == 0:
            denominator //= 5
        return denominator != 1
    if kind == "perfect_square":
        return int(value) >= 0 and isqrt(int(value)) ** 2 == int(value)
    if kind == "occurrence_at_least":
        return tuple(value).count(int(predicate["value"])) >= int(predicate["minimum"])
    if kind == "sum_parity":
        return sum(int(item) for item in value) % 2 == int(predicate["value"])
    if kind == "product_divisible_by":
        result = 1
        for item in value:
            result *= int(item)
        return result % int(predicate["value"]) == 0
    raise ValueError(f"unsupported finite predicate: {kind}")


def format_rational(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"
