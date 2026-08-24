from __future__ import annotations

from geometry_proof_hypergraph import Atom, _FactIndex, _unify_all


def test_fact_index_is_exact_for_symmetric_partially_bound_atoms() -> None:
    facts = (
        Atom("eqangle", ("a", "b", "c", "d", "e", "f", "g", "h")),
        Atom("eqangle", ("a", "b", "c", "d", "i", "j", "k", "l")),
        Atom("eqangle", ("m", "n", "o", "p", "e", "f", "g", "h")),
        Atom("cong", ("a", "b", "c", "d")),
    )
    index = _FactIndex(facts)
    patterns = (
        (
            Atom(
                "eqangle",
                ("?A", "?B", "?C", "?D", "?E", "?F", "?G", "?H"),
            ),
            {"?A": "a", "?B": "b", "?E": "e"},
        ),
        (
            Atom("cong", ("?A", "?B", "?C", "?D")),
            {"?A": "b", "?B": "a"},
        ),
    )

    for pattern, substitution in patterns:
        expected = tuple(
            fact for fact in facts if tuple(_unify_all(pattern, fact, substitution))
        )
        assert index.candidates(pattern, substitution) == expected
