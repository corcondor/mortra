"""Hand stored fold constructions to the existing abstraction learner.

Nothing here is a new primitive. The fold side keeps the generators it already
has (`FOLD_GENERATORS`, the alphabet A/C/G/T), the composition order it already
has (a word, read left to right), and the kinematics it already has
(`apply_fold_generator`, reached through `build_square_fold_chain`). The learner
is `library_compression`, unmodified except that the one question it asks about a
node -- *is this a term of the language?* -- is now answerable by a predicate
supplied here instead of by the eight-operation series grammar.

Two properties of the existing learner force the encoding, and neither is a
choice made here:

* `holonomic_relation_reuse.occurrences` descends into dict-valued fields and
  **not into lists**, so a word held as a list of letters would expose no
  subterm at all. The word is therefore a right-nested pair.

* `library_compression.generalise` refuses a disagreement whose two sides are
  not both dicts carrying an `op` (it raises "a disagreement that is not between
  two programs" before it ever reaches the grammar check). A letter therefore
  has to *be* a node rather than sit in a field of one, so the generator symbol
  is the `op`: `{"op": "A"}`. That also keeps the alphabet literally the stored
  one.

Right-nesting exposes every suffix as a subterm, and a program hole may bind the
remaining tail, so a motif in the middle of a word is still matched: the suffix
that starts at the motif matches a template whose last hole takes the rest.
"""
from __future__ import annotations

from math_os_prototype.rigid_fold_problem_discovery import (
    FOLD_GENERATORS, build_square_fold_chain, search_collision_free_fold_chain)

SCHEMA = "mortra.fold-library-bridge.v1"
ALPHABET = tuple(generator.symbol for generator in FOLD_GENERATORS)
THEN, END = "then", "end"

#: the fold term language, in the shape `validate` uses for the series grammar
FIELDS = dict({symbol: {"op"} for symbol in ALPHABET},
              **{THEN: {"op", "head", "tail"}, END: {"op"}})


def validate_fold(node, depth=0):
    """Is this a term of the fold language? Raise if not, as `validate` does.

    The contract is the one `library_compression` expects of a grammar: return
    for a term, raise `ValueError` or `TypeError` for anything else. Holes and
    calls are not this predicate's business -- the learner tests those itself.
    """
    if depth > 4096:
        raise ValueError("fold program nested past the depth limit")
    if not isinstance(node, dict):
        raise TypeError("a fold term is a dict")
    op = node.get("op")
    if op not in FIELDS:
        raise ValueError(f"unknown fold operation {op!r}")
    if set(node) != FIELDS[op]:
        raise ValueError(f"{op!r} takes exactly {sorted(FIELDS[op])}")
    if op == THEN:
        validate_fold(node["head"], depth + 1)
        validate_fold(node["tail"], depth + 1)


# ---- the stored word, as a term, and back ---------------------------------

def program(word):
    """A fold word as a right-nested term, generators and order preserved."""
    built = {"op": END}
    for symbol in reversed(str(word)):
        if symbol not in ALPHABET:
            raise ValueError(f"{symbol!r} is not one of the stored generators")
        built = {"op": THEN, "head": {"op": symbol}, "tail": built}
    return built


def word(node):
    """The word a term denotes, flattening nested sequences.

    `validate_fold` admits a `then` whose head is itself a sequence -- that is
    what lets a learned definition take a whole construction as an argument --
    so the decoder has to read the tree, not just a flat chain. `then(X, Y)` is
    "do X, then do Y" whether X is one generator or a hundred. A term still has
    to bottom out in generators: a hole or a call left standing is refused here,
    which is where the execution boundary is.
    """
    letters = []

    def walk(current, depth=0):
        if depth > 4096:
            raise ValueError("fold term nested past the depth limit")
        validate_fold(current)
        op = current["op"]
        if op == END:
            return
        if op in ALPHABET:
            letters.append(op)
            return
        walk(current["head"], depth + 1)
        walk(current["tail"], depth + 1)

    walk(node)
    return "".join(letters)


def run(node):
    """Execute a fold term with the existing kinematics. Nothing new is added."""
    return build_square_fold_chain(word(node))


def length(node):
    """How many folds the term performs, nesting included."""
    return len(word(node))


# ---- the stored constructions this is learned from ------------------------

def stored_constructions(counts, *, beam_width=64, seed=20260904):
    """Collision-free chains from the existing fold search, as a corpus.

    `search_collision_free_fold_chain` is the fold side's own candidate
    generation: a beam over the fixed alphabet that rejects a relative-interior
    crossing at every extension, using the stored kinematics. Its output is
    taken as given; no word is written by hand and none is filtered afterwards.
    """
    corpus, seen = [], set()
    for fold_count in counts:
        result = search_collision_free_fold_chain(
            fold_count, beam_width=beam_width, seed=seed)
        chain = getattr(result, "chain", None) or getattr(result, "best", None)
        text = getattr(chain, "word", None) if chain is not None else None
        if text is None:
            text = getattr(result, "word", None)
        if not text or text in seen:
            continue
        seen.add(text)
        corpus.append({"id": f"fold-{len(text)}-{len(corpus)}",
                       "program": program(text),
                       "source": "search_collision_free_fold_chain",
                       "folds": len(text), "word": text})
    return corpus


def prefix_corpus(entries):
    """Every proper prefix of each stored chain, which the search also visited.

    A beam search reaches a long chain through its prefixes, and each prefix is
    itself a collision-free construction it actually held. Counting them is not
    a replay: they are distinct stored constructions, and the learner is told so
    by giving each its own id.
    """
    corpus, seen = [], set()
    for entry in entries:
        text = entry["word"]
        for cut in range(2, len(text) + 1):
            piece = text[:cut]
            if piece in seen:
                continue
            seen.add(piece)
            corpus.append({"id": f"prefix-{len(piece)}-{len(corpus)}",
                           "program": program(piece),
                           "source": entry["id"], "folds": len(piece),
                           "word": piece})
    return corpus
