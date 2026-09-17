"""A discovered structure, entered into the shared operation contract registry.

The point of discovering a structure is that the system can then use it like any
other operation: with a type, an object identity, preconditions, a guarantee, a
proof of that guarantee, and a cost. What is registered is not a route to one
answer. It is an operation that answers every length of its family, whose body is
the compiled cheap route and whose guarantee is that its answer is the one the
expensive route would have given.

The proof is not a sample. It is the pair of exact certificates the discovery
produced: the reachable subspace is closed and contains the start, the
unobservable subspace is closed and is killed by the functional, so merging
changes no value; and `p(A) = 0` holds as a matrix identity, so replacing `A^L` by
`x^L mod p` changes no value either.
"""
from __future__ import annotations

from fractions import Fraction

from math_os_prototype import structure_families as fam
from math_os_prototype.algebraic_operation_domain import PREDICATES, SORTS
from math_os_prototype.operation_contracts import (
    ACQUIRED,
    Condition,
    Contract,
    Predicate,
    Registry,
    Session,
    Sort,
)
from math_os_prototype.representation_progress import digest


def family_key(family):
    return digest([family.name, [[[str(i), str(v)] for i, v in sorted(column.items())]
                                 for matrix in family.matrices for column in matrix.columns],
                   [[str(i), str(v)] for i, v in sorted(family.start.items())],
                   [[str(i), str(v)] for i, v in sorted(family.functional.items())]])[:20]


def check_counts_sequences(family, length, value, *, counter):
    """The expensive route, exactly: apply the sum of the operations `length` times."""
    return fam.count_by_iteration(family, int(length), counter=counter) == value


STRUCTURE_SORTS = SORTS+(
    Sort("Family", family_key),
    Sort("Length", lambda length: str(int(length))),
    Sort("Count", lambda value: str(Fraction(value))),
)

STRUCTURE_PREDICATES = PREDICATES+(
    Predicate("counts_sequences", ("Family", "Length", "Count"), check_counts_sequences,
              "v is the number of accepted operation sequences of that length"),
)


def run_iterate(binding, counter):
    return fam.count_by_iteration(binding["F"], int(binding["L"]), counter=counter)


ITERATE = Contract(
    name="count_by_iterating", params=(("F", "Family"), ("L", "Length")), result="Count",
    post=(Condition.of("counts_sequences", "F", "L", "v"),), run=run_iterate,
    note="the bracket identity: every sequence at once, by applying the sum of the operations L times")


def structure_registry(contracts=(ITERATE,)):
    return Registry(STRUCTURE_SORTS, STRUCTURE_PREDICATES, contracts)


def register_discovered_structure(session, family, structure, *, name, parents=()):
    """Enter a certified structure as an operation of the registry.

    Its guarantee is established by the certificates of the discovery, not by
    recomputing the iteration; in a session that verifies derivations, the exact
    check runs as well and has to agree.
    """
    def run(binding, counter, structure=structure, family=family):
        if session.registry.object_id("Family", binding["F"]) != session.registry.object_id("Family", family):
            return None
        return fam.count_by_structure(structure, int(binding["L"]), counter=counter)

    contract = Contract(
        name=name, params=(("F", "Family"), ("L", "Length")), result="Count",
        post=(Condition.of("counts_sequences", "F", "L", "v"),), run=run,
        provenance=ACQUIRED, parents=tuple(parents),
        generation=1+max((session.registry.contracts[p].generation for p in parents
                          if p in session.registry.contracts), default=0),
        derivation={"kind": "structure",
                    "rule": "merging changes no word value because the reachable subspace is closed and "
                            "contains the start while the unobservable subspace is closed and is killed "
                            "by the functional; the relation changes none either because p(A) = 0 holds "
                            "as an identity, so A^L and x^L mod p agree on every start",
                    "given_dimension": structure["given_dimension"],
                    "merged_dimension": structure["merged_dimension"],
                    "relation_degree": structure["degree"],
                    "relation_coefficients": structure["coefficients"],
                    "relation_certified": structure["certified"],
                    "relation_holds_for_every_start": structure["holds_for_every_start"],
                    "certificate": structure["certificate"]["rule"]},
        note="answers every length of this family; the cost grows with the logarithm of the length")
    session.registry.add(contract)
    return contract


def discovered_session(family, *, verify_derivations=False, name="count_by_structure", counter=None):
    """Discover a structure for the family and hand back a session that can use it."""
    session = Session(structure_registry(), verify_derivations=verify_derivations, counter=counter)
    structure = fam.discover(family, counter=session.counter)
    contract = register_discovered_structure(session, family, structure, name=name,
                                             parents=("count_by_iterating",))
    return session, structure, contract
