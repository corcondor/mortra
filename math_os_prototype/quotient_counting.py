"""Counting words of a given length by a layered dynamic programme.

One routine, used for every route, so that the concrete run and the abstract run
produce the same kind of answer under the same legality and are therefore
comparable at all. What changes between routes is only which state is carried:
the concrete state, or its image under a representation that has been certified
to preserve what the task needs.

THE LEMMA THIS IMPLEMENTS
-------------------------

Let `X` be the concrete states, `x0` the start, `G` the labels, `T_g` the update,
`legal(x, g)` the legality of applying `g` at `x`, and `q(x)` the evaluation.
Let `~` be an equivalence on `X` with, for all `x ~ y`:

    (i)   for every g:  legal(x, g) = legal(y, g)  and  T_g(x) ~ T_g(y)
    (ii)  q(x) = q(y)

Write `[x]` for the class. Define

    c_0([x0]) = 1,   c_0 = 0 elsewhere
    c_{k+1}([z']) = SUM over [z] of  c_k([z]) * #{ g : legal([z], g), [T_g(z)] = [z'] }

Claim: for every k >= 0 and every class [z],

    c_k([z]) = #{ legal words w of length k : [x_w] = [z] }

Proof. Induction on k. Base: the only word of length 0 is the empty word and it
reaches `x0`, so both sides are 1 at `[x0]` and 0 elsewhere. Step: every legal
word of length k+1 is uniquely `w g` with `w` legal of length k and `g` legal at
`x_w`; by (i) both the legality of `g` and the class of `T_g(x_w)` depend only on
`[x_w]` and `g`. Grouping the words of length k+1 by their prefix class and last
letter therefore gives exactly the displayed sum. []

Corollary. With `qbar` the evaluation induced on classes by (ii),

    v_max     = max{ qbar(z) : c_n(z) > 0 }
    count_max = SUM over z with qbar(z) = v_max of c_n(z)

are the maximum of `q` over legal words of length `n` and the number of legal
words of length `n` attaining it. If no legal word of length `n` exists then
`v_max` is undefined and is reported as such rather than as any number.

This lemma is general knowledge supplied by the implementer. It is not a
discovery of any run, and nothing here should be reported as one.

WHAT THE IMPLEMENTATION IS CAREFUL ABOUT
----------------------------------------

* Two different labels that land on the same successor contribute twice. The
  successors are never collected into a set and counted once; the multiplicity
  is added per label, which is what makes the count a count of words rather than
  of reachable classes.
* States are merged only inside one layer. States of different depths are never
  identified, and the certificate that licenses the merging is only ever asked
  about states of equal depth for the same reason.
* Legality is applied as `legal(state, label)` before the successor is taken, so
  an illegal step contributes nothing rather than contributing a state that is
  filtered later.
* No macro, compound label or shortcut is mixed in as an extra branch. The
  alphabet the DP walks is the task's own, so one word is counted once.
"""
from __future__ import annotations

SCHEMA = "mortra.quotient-counting.v1"


def layered_count(*, start, step, legal, value, alphabet, length,
                  key=lambda state: state):
    """The DP above, with what it walked reported beside what it found.

    `key` is what states are merged on inside a layer -- the identity for a
    concrete run, the observation for an abstract one. `step`, `legal` and
    `value` are the task's, or the certified abstract versions of them.
    """
    if length < 0:
        raise ValueError("a non-negative length is required")
    layer = {key(start): (start, 1)}
    nodes, transitions, illegal, per_layer = 1, 0, 0, [1]
    for _ in range(length):
        following = {}
        for _, (state, multiplicity) in layer.items():
            for symbol in alphabet:
                nodes += 1
                if not legal(state, symbol):
                    illegal += 1
                    continue
                moved = step(state, symbol)
                transitions += 1
                identity = key(moved)
                if identity in following:
                    kept, count = following[identity]
                    following[identity] = (kept, count + multiplicity)
                else:
                    following[identity] = (moved, multiplicity)
        layer = following
        per_layer.append(len(layer))

    distribution = {}
    for _, (state, multiplicity) in layer.items():
        found = value(state)
        distribution[found] = distribution.get(found, 0) + multiplicity
    total = sum(distribution.values())
    if not distribution:
        answer = {"v_max": None, "count_max": 0, "total_words": 0,
                  "distinct_values": 0,
                  "undefined_because": ("no legal word of this length exists, so "
                                        "the maximum is undefined rather than "
                                        "any particular number")}
    else:
        best = max(distribution)
        answer = {"v_max": str(best), "count_max": distribution[best],
                  "total_words": total, "distinct_values": len(distribution)}
    return {"answer": answer,
            "distribution": {str(k): v for k, v in sorted(distribution.items())},
            "states_per_layer": per_layer,
            "classes_at_end": len(layer),
            "nodes": nodes, "transitions": transitions,
            "illegal_steps": illegal,
            "merged_on": ("one layer at a time; states of different depths are "
                          "never identified"),
            "multiplicity": ("added once per label, so two labels reaching the "
                             "same successor contribute twice")}


def enumerate_count(*, start, step, legal, value, alphabet, length):
    """The same answer by walking every word. For checking the DP at small n.

    Nothing is merged here, so this is the statement the DP has to reproduce.
    """
    if length < 0:
        raise ValueError("a non-negative length is required")
    distribution, nodes, words, illegal = {}, 0, 0, 0
    frontier = [("", start)]
    for _ in range(length):
        following = []
        for word, state in frontier:
            for symbol in alphabet:
                nodes += 1
                if not legal(state, symbol):
                    illegal += 1
                    continue
                following.append((word + symbol, step(state, symbol)))
        frontier = following
    for word, state in frontier:
        found = value(state)
        distribution[found] = distribution.get(found, 0) + 1
        words += 1
    if not distribution:
        answer = {"v_max": None, "count_max": 0, "total_words": 0,
                  "distinct_values": 0,
                  "undefined_because": ("no legal word of this length exists, so "
                                        "the maximum is undefined rather than "
                                        "any particular number")}
    else:
        best = max(distribution)
        answer = {"v_max": str(best), "count_max": distribution[best],
                  "total_words": words, "distinct_values": len(distribution)}
    return {"answer": answer,
            "distribution": {str(k): v for k, v in sorted(distribution.items())},
            "nodes": nodes, "transitions": nodes - illegal,
            "illegal_steps": illegal,
            "words_walked": words,
            "merged_on": "nothing; every word is walked separately"}
