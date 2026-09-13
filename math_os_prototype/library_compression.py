"""Which abstraction, once learned, makes the stored corpus shorter.

The question here is not what else can be proved. It is: given a fixed corpus of
constructions that were already built and already certified, is there a
parameterised piece of structure such that naming it once and rewriting every
place it occurs costs fewer bits than leaving the corpus as it is.

What this reuses rather than rebuilds
    cost                `representation_progress.description_bits` -- the
                        repository's declared description cost, length-prefixed
                        canonical JSON in bits. It counts every node, every field
                        name and every constant, so a call site pays for its
                        arguments and the definition is paid for once. Renaming a
                        node or hiding a body cannot earn anything under it.
    match locations     `holonomic_relation_reuse.occurrences` for the positions
                        and `holonomic_parametric_learning.match` for the test,
                        which already knows both hole kinds.
    rewriting           `holonomic_relation_reuse.replace_at`, which detaches
                        every edge on the path it rewrites, so a subtree shared
                        elsewhere is not rewritten without its own site.
    expansion           `holonomic_parametric_learning.instantiate`, which
                        validates what it produces.

The objective, and where it comes from
    Stitch (Bowers et al., POPL 2023) states the utility of an abstraction A on a
    corpus P under a rewrite strategy R as

        U(A) = -cost(A) + cost(P) - cost(Rewrite_R(P, A))          (their eq. 8)

    which is exactly the quantity asked for here: the corpus cost before, minus
    the corpus cost after actually rewriting, minus the cost of the new
    definition. `utility` computes it from the programs that were really
    rewritten, so overlapping sites cannot be counted twice.

The bound, and what makes it sound here
    Stitch prunes a partial abstraction by

        Ubar(A??) = sum over e in Matches(P, A??) of cost(e)         (their sec. 4.2)

    resting on their Lemma 2: the match locations of a partial abstraction
    over-approximate those of any abstraction below it in the branch. Two facts
    are what carry that argument over to this representation, and both are
    checked rather than assumed (`audit_bound`):

        * `description_bits` is non-negative, so the saving at one site is at
          most the cost of the subterm that was there;
        * `match` is monotone under specialisation -- filling a hole can only
          shrink the set of sites -- so a completion never matches anywhere its
          parent did not.

    The bound ignores what the call site itself costs, so it is loose. How loose
    is measured, not asserted.

What the bound needs from this particular cost
    Stitch's equation (9) gives cost recursively over the term, with
    non-negative constants for each construct, and equations (10)-(12) rewrite
    the utility as a sum of per-site local utilities on that basis. Equations
    (13)-(14) then bound it. `description_bits` is *not* of that shape: it is
    `8 * (prefix_bytes(n) + n)` on the canonical JSON encoding, and the parent's
    encoding is not the sum of its children's.

    Two facts are what make the same bound hold here, and they are narrower than
    the paper's:

        substitution is additive in bytes -- the encoding of a subterm occurs as
        a contiguous run inside the encoding of the whole, so replacing a
        subterm of `L` bytes by a call of `M` bytes changes the total by exactly
        `M - L`, and `M >= 0`;

        the length prefix is monotone -- shrinking a program never grows
        `prefix_bytes`, and it shrinks by at most one byte per rewritten
        program at these sizes, while each counted site contributes at least one
        prefix byte of its own to the bound.

    The second is a condition, not an identity: a corpus where a program's
    length descriptor shrank by more bytes than it had rewritten sites would
    break it. `audit_bound` therefore checks the bound against the measured
    utility on the corpus at hand instead of relying on the argument, and the
    run reports every violation it finds. Appendix A of Stitch, which lists the
    full algorithm, was not reachable in the HTML rendering that could be read,
    so nothing here is taken from it.

What is deliberately not claimed
    No global optimality. No claim that the rewritten programs are runnable: a
    rewritten program carries a `use` node, which is not in the executable
    grammar, and `expand` is what takes it back. Compression is reported as
    whatever the objective gives, including zero.
"""
from __future__ import annotations

from copy import deepcopy

from math_os_prototype.holonomic_parametric_learning import (
    instantiate, match, numeric, parameter, series_parameter)
from math_os_prototype.holonomic_route_discovery import rational
from math_os_prototype.holonomic_relation_reuse import occurrences, replace_at
from math_os_prototype.holonomic_route_discovery import key
from math_os_prototype.holonomic_route_discovery import validate as _series_validate
from math_os_prototype.representation_progress import description_bits, digest

from contextlib import contextmanager

SCHEMA = "mortra.library-compression.v1"
USE = "use"
COST = ("length-prefixed canonical JSON in bits, from "
        "representation_progress.description_bits")


_ACCEPTS = _series_validate


@contextmanager
def grammar(accepts):
    """Run the learner over another term language.

    Everything in this module is structural except one question: *is this node a
    term of the language?* That question is asked in exactly four places
    (`generalise`, `library_term`, `safe_program_holes`, `call_candidates`) and
    at the expansion boundary, and it is the only thing that ties the module to
    the eight-operation series grammar. Supplying another predicate re-points
    those five places and nothing else; the subterm walk, the anti-unification,
    the matcher, the substitution, the rewrite, the expansion and the cost model
    are unchanged, because none of them names an operation.

    The predicate has the same contract as `validate`: return for a term of the
    language, raise `ValueError` or `TypeError` otherwise.
    """
    global _ACCEPTS
    previous = _ACCEPTS
    _ACCEPTS = accepts
    try:
        yield
    finally:
        _ACCEPTS = previous


def accepts(node):
    """The grammar currently in force, as a predicate."""
    try:
        _ACCEPTS(node)
        return True
    except (ValueError, TypeError):
        return False


def cost(value):
    """The corpus cost, in bits. The repository's declared description cost."""
    return description_bits(value)


# ---- holes, in the representation the existing matcher already reads --------

def value_hole(index):
    """A hole standing for a rational constant."""
    return {"parameter": f"p{index}"}


def program_hole(index):
    """A hole standing for a whole subprogram.

    `match` validates what it binds here and `instantiate` validates what it
    puts back, so a function-valued argument is safe exactly when the subterm
    bound to it is a well-formed program of the grammar. `safe_program_holes`
    checks that this holds for every site actually used.
    """
    return {"series_parameter": f"f{index}"}


def is_hole(node):
    return isinstance(node, dict) and ("parameter" in node or "series_parameter" in node)


def holes(template, found=None):
    found = [] if found is None else found
    if is_hole(template):
        name = template.get("parameter") or template.get("series_parameter")
        if name not in found:
            found.append(name)
        return found
    if isinstance(template, dict):
        for field in sorted(template):
            holes(template[field], found)
    elif isinstance(template, list):
        for item in template:
            holes(item, found)
    return found


def structure_size(template):
    """Nodes that are not holes. A template of only holes abstracts nothing."""
    if is_hole(template):
        return 0
    if isinstance(template, dict):
        return 1 + sum(structure_size(template[f]) for f in sorted(template))
    if isinstance(template, list):
        return sum(structure_size(item) for item in template)
    return 1


# ---- proposing candidates by generalising two stored subterms ---------------

def generalise(first, second, *, limit=6):
    """The least general template both subterms are instances of.

    A numeric disagreement becomes a value hole, and a structural disagreement
    between two well-formed programs becomes a program hole. Equal parts are
    kept, which is what makes the result a pattern rather than a hole.

    This is the anti-unification step the existing `anti_unify` performs for
    whole relations, widened to disagreements that are not numeric -- which is
    what lets a candidate carry an argument that is itself a computation, and
    what keeps the candidate space from being the polynomial fragment only.
    """
    counters = {"value": 0, "program": 0}
    samples = {}
    shared = {}

    def fresh(kind, left, right):
        pair = (kind, key(left), key(right))
        if pair in shared:
            return deepcopy(shared[pair])
        if counters["value"] + counters["program"] >= limit:
            raise ValueError("too many holes for one candidate")
        if kind == "value":
            node = value_hole(counters["value"])
            counters["value"] += 1
            name = node["parameter"]
        else:
            node = program_hole(counters["program"])
            counters["program"] += 1
            name = node["series_parameter"]
        samples[name] = [left, right]
        shared[pair] = node
        return node

    def walk(a, b):
        if is_call(a) or is_call(b):
            # Which definition is called is structure, not an argument: a hole
            # there would have to be filled with a name, and `instantiate` puts
            # rationals and programs into holes, not names.
            if not (is_call(a) and is_call(b)):
                raise ValueError("a call and a program cannot be generalised together")
            if a["abstraction"] != b["abstraction"]:
                raise ValueError("two calls naming different definitions")
            if set(a["arguments"]) != set(b["arguments"]):
                raise ValueError("two calls of the same definition with different "
                                 "argument names")
            return {"op": USE, "abstraction": a["abstraction"],
                    "arguments": {name: walk(a["arguments"][name],
                                             b["arguments"][name])
                                  for name in sorted(a["arguments"])}}
        left, right = numeric(a), numeric(b)
        if left is not None and right is not None:
            return str(left) if left == right else fresh("value", str(left), str(right))
        if isinstance(a, dict) and isinstance(b, dict) and set(a) == set(b):
            if a.get("op") == b.get("op"):
                # Symbol names are structural, but differing leaves may be
                # abstracted as whole typed programs, never as arbitrary strings.
                if a != b and (a.get("op") == "var" or a.get("args") == []):
                    _ACCEPTS(a)
                    _ACCEPTS(b)
                    return fresh("program", deepcopy(a), deepcopy(b))
                return {f: walk(a[f], b[f]) for f in sorted(a)}
        if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            return [walk(x, y) for x, y in zip(a, b)]
        if type(a) is type(b) and a == b:
            return a
        for side in (a, b):
            if not isinstance(side, dict) or "op" not in side:
                raise ValueError("a disagreement that is not between two programs")
            if is_call(side):
                # A call could only become an argument, and an argument has to
                # be something the evaluator accepts. Keeping calls out of the
                # holes is what makes every binding expandable on its own.
                raise ValueError("a call cannot be abstracted into an argument")
            _ACCEPTS(side)
        return fresh("program", deepcopy(a), deepcopy(b))

    template = walk(first, second)
    if not samples:
        raise ValueError("the two subterms are identical, so nothing was abstracted")
    if structure_size(template) == 0:
        raise ValueError("the template is a bare hole and abstracts nothing")
    return template, samples


# ---- where a candidate occurs, and which of those places may be rewritten ---

def library_term(node):
    """A term the library may talk about: an executable program, or a call.

    A call is not executable -- `validate` refuses it -- but it is a term of the
    library language, so a later definition can be built around one. What a call
    may *take* is still an executable program: `match` validates whatever it
    binds to a program hole, so an argument is always something the existing
    evaluator and certifier can be handed directly.
    """
    try:
        _ACCEPTS(node)
        return True
    except (ValueError, TypeError):
        return is_call(node)


def subterms(program):
    """Every position whose subtree is a term of the library language."""
    found = []
    for path, node in occurrences(program):
        if library_term(node):
            found.append((path, node))
    return found


def match_term(template, term, binding):
    """Match over library terms, where a program hole may bind a call.

    The distinction the two kinds of nesting need:

        a call in the *body* of a definition is fixed structure, matched the
        way any other node is, and `generalise` refuses to abstract over which
        definition is named;

        a call in an *argument* is a value, so a program hole may bind it. What
        it may not do is stay unexpanded past the execution boundary: `expand`
        drives the arguments before the body, and `validate` at the boundary is
        what the evaluator and the certifier actually see.

    `match` in `holonomic_parametric_learning` validates whatever it binds, so it
    refuses a call outright. This is the same matcher with that one rule widened
    to library terms, and it delegates everything else.
    """
    if series_parameter(template):
        if not library_term(term):
            return False
        name = template["series_parameter"]
        if name in binding:
            return key(binding[name]) == key(term)
        binding[name] = deepcopy(term)
        return True
    if parameter(template):
        return match(template, term, binding)
    if is_call(template) or is_call(term):
        if not (is_call(template) and is_call(term)):
            return False
        if template["abstraction"] != term["abstraction"]:
            return False
        if set(template["arguments"]) != set(term["arguments"]):
            return False
        return all(match_term(template["arguments"][name],
                              term["arguments"][name], binding)
                   for name in sorted(template["arguments"]))
    if isinstance(template, dict):
        return (isinstance(term, dict) and set(template) == set(term)
                and all(match_term(template[field], term[field], binding)
                        for field in sorted(template)))
    if isinstance(template, list):
        return (isinstance(term, list) and len(template) == len(term)
                and all(match_term(a, b, binding) for a, b in zip(template, term)))
    quantity = numeric(template)
    return quantity == numeric(term) if quantity is not None else template == term


def instantiate_term(template, binding):
    """Fill a template with library terms, leaving the boundary check to `expand`.

    `instantiate` validates a program-hole binding, which refuses a call. Here a
    call is allowed into an argument and stays a call; nothing is claimed to be
    executable until `expand` has driven every call out and `validate` has looked
    at the result.
    """
    if series_parameter(template):
        name = template["series_parameter"]
        if name not in binding:
            raise ValueError(f"no term was bound to {name}")
        return deepcopy(binding[name])
    if parameter(template):
        name = template["parameter"]
        if name not in binding:
            raise ValueError(f"no value was bound to {name}")
        return str(rational(template.get("multiplier", 1))
                   * rational(binding[name]))
    if isinstance(template, dict):
        return {field: instantiate_term(template[field], binding)
                for field in template}
    if isinstance(template, list):
        return [instantiate_term(item, binding) for item in template]
    return template


def match_sites(template, program):
    """Every position where the template matches, with what it binds there."""
    sites = []
    for path, node in subterms(program):
        binding = {}
        if match_term(template, node, binding):
            sites.append({"path": list(path), "binding": binding, "subterm": node})
    return sites


def _nested(inner, outer):
    return len(outer) <= len(inner) and tuple(inner[:len(outer)]) == tuple(outer)


def select_sites(sites):
    """Outermost first, and never two sites where one contains the other.

    This is the rewrite strategy the utility is computed under. Taking nested
    sites as well would count the same bits twice, because rewriting the outer
    one removes the inner one from the program.
    """
    chosen = []
    for site in sorted(sites, key=lambda s: (len(s["path"]), s["path"])):
        if any(_nested(site["path"], taken["path"]) for taken in chosen):
            continue
        chosen.append(site)
    return chosen


# ---- rewriting, and getting back what was there ----------------------------

def definition_id(template):
    """A definition's identity: its own content."""
    return digest({"schema": SCHEMA, "template": template})[:16]


def definition_table(templates):
    """The table calls are resolved against, sealed by its own contents.

    A call carries a short local name, because that is what makes a call cheap
    and the definition paid for once. What stops a call from resolving against
    the wrong body is therefore not the name but the table: it is sealed, the
    rewritten corpus records which seal it was rewritten against, and `expand`
    refuses a table whose seal does not match what it is handed. Arity is
    checked per call besides, so a table of the right size but the wrong shape
    is refused where it is used rather than silently applied.
    """
    if not isinstance(templates, dict):
        templates = dict(enumerate(templates))
    definitions = {str(name): deepcopy(template)
                   for name, template in templates.items()}
    table = {"schema": SCHEMA, "definitions": definitions,
             "ids": {str(name): definition_id(template)
                     for name, template in templates.items()}}
    table["sha256"] = digest(table)
    return table


def resolve(table, name):
    """The body a call names, or nothing, with the table checked once."""
    if table.get("sha256") != digest({k: v for k, v in table.items()
                                      if k != "sha256"}):
        raise ValueError("the definition table does not match its own seal")
    return table["definitions"].get(str(name))


def use_node(index, template, binding):
    """The call the rewritten program carries in place of a matched subterm."""
    return {"op": USE, "abstraction": index,
            "arguments": {name: deepcopy(binding[name]) for name in holes(template)}}


def is_call(node):
    return (isinstance(node, dict) and node.get("op") == USE
            and isinstance(node.get("arguments"), dict)
            and set(node) == {"op", "abstraction", "arguments"})


def rewrite(program, index, template, sites):
    """Replace each selected site by a call. Nothing else about the program moves."""
    rewritten = deepcopy(program)
    for site in sites:
        rewritten = replace_at(rewritten, tuple(site["path"]),
                               use_node(index, template, site["binding"]))
    return rewritten


def canonical_literals(value):
    """Every rational literal in its canonical form, nothing else touched.

    `instantiate` writes a rational back as a string, so an expansion can return
    `"1"` where the stored program had `1`. `validate`, `rational` and the
    evaluator read those as the same number, and `key` does not. Comparing under
    this normalisation is what lets the expansion check be about the program
    rather than about how its constants happened to be typed; `verify_semantics`
    is the separate check that they really are the same series.
    """
    if isinstance(value, dict):
        return {field: canonical_literals(value[field]) for field in value}
    if isinstance(value, list):
        return [canonical_literals(item) for item in value]
    quantity = numeric(value)
    return str(quantity) if quantity is not None else value


def expand(node, definitions):
    """Put back every call this definition table knows about, by definition alone.

    A call to an abstraction that is not in the table is left standing, with its
    arguments expanded. That is what lets a later round be scored against a
    corpus an earlier round already rewrote: the check is whether *these* sites
    come back, not whether the corpus is returned to its original form.
    """
    if is_call(node):
        arguments = {name: expand(value, definitions)
                     for name, value in node["arguments"].items()}
        template = resolve(definitions, node["abstraction"])
        if template is None:
            return dict(node, arguments=arguments)
        if sorted(holes(template)) != sorted(arguments):
            raise ValueError(
                f"the call names {node['abstraction']} but supplies "
                f"{sorted(arguments)} where that definition takes "
                f"{sorted(holes(template))}")
        for name, value in arguments.items():
            # what `instantiate` checked: a program-hole argument has to be a
            # term of the language by the time the body is filled in
            if name.startswith("f"):
                _ACCEPTS(value)
        return instantiate_term(template, arguments)
    if isinstance(node, dict):
        return {f: expand(node[f], definitions) for f in node}
    if isinstance(node, list):
        return [expand(item, definitions) for item in node]
    return node


class ExpansionError(ValueError):
    """A term could not be made executable, with the reason it could not."""


def calls_in(node, found=None):
    """Every abstraction index a term still calls."""
    found = [] if found is None else found
    if isinstance(node, dict):
        if is_call(node):
            found.append(node["abstraction"])
        for value in node.values():
            calls_in(value, found)
    elif isinstance(node, list):
        for value in node:
            calls_in(value, found)
    return found


def expand_for_execution(node, definitions, *, steps=200_000, stats=None, charge=None):
    """Drive every call out and check what is left can actually be run.

    This is the **execution boundary**, and it is deliberately not the same
    thing as `expand`. `expand` is the local rewrite check the learner uses: it
    leaves a call to an abstraction the table does not know standing, on purpose,
    so a later round can be scored against a corpus an earlier round rewrote.
    Silencing that everywhere would break the scoring. Here the question is
    different -- *is this runnable?* -- and a call left standing is a failure.

    The contract:

    * the call's arguments are expanded;
    * the body is fetched from the **same** definition environment;
    * the arguments are substituted into it;
    * the substituted body is expanded again, because a body may itself be a
      call -- this is what `expand` does not do;
    * no call and no unbound hole may remain;
    * the result is put through the domain's own `validate`, whichever one is in
      force.

    A definition reached from inside its own body is refused. Finite nesting in
    an *argument* is not that: `H0(f0=H0(f0=p))` is a term, not a cycle, so
    arguments are driven with a fresh chain. Running out of steps raises; a
    partial expansion is never returned as a result.
    """
    budget = [int(steps)]

    def drive(current, chain):
        if charge is not None:
            charge("expansion_visits", 1)
        if stats is not None:
            stats["expansion_visits"] = stats.get("expansion_visits", 0)+1
        budget[0] -= 1
        if budget[0] <= 0:
            raise ExpansionError(
                f"expansion exceeded its {steps}-step budget; a partial "
                "expansion is not a result")
        if is_call(current):
            if stats is not None:
                stats["macro_expansions"] = stats.get("macro_expansions", 0)+1
            index = current["abstraction"]
            if index in chain:
                raise ExpansionError(
                    "a definition is reached from inside its own body: "
                    + " -> ".join(str(i) for i in chain + (index,)))
            arguments = {name: drive(value, ())
                         for name, value in current.get("arguments", {}).items()}
            template = resolve(definitions, index)
            if template is None:
                raise ExpansionError(
                    f"the call names abstraction {index}, which this definition "
                    "table does not hold")
            expected = sorted(holes(template))
            if expected != sorted(arguments):
                raise ExpansionError(
                    f"the call names abstraction {index} and supplies "
                    f"{sorted(arguments)} where that definition takes {expected}")
            return drive(instantiate_term(template, arguments), chain + (index,))
        if isinstance(current, dict):
            return {field: drive(current[field], chain) for field in current}
        if isinstance(current, list):
            return [drive(item, chain) for item in current]
        return current

    expanded = drive(node, ())
    remaining = sorted(set(calls_in(expanded)))
    if remaining:
        raise ExpansionError(f"calls to {remaining} remain after expansion")
    open_holes = sorted(holes(expanded))
    if open_holes:
        raise ExpansionError(f"unbound holes {open_holes} remain after expansion")
    _ACCEPTS(expanded)
    return expanded


def safe_program_holes(template, sites):
    """Is every program-valued argument a well-formed program at every site?"""
    for site in sites:
        for name, value in site["binding"].items():
            if not name.startswith("f"):
                continue
            try:
                _ACCEPTS(value)
            except (ValueError, TypeError) as exc:
                return {"safe": False, "reason": f"{name} at {site['path']}: {exc}"}
    return {"safe": True, "reason": "every program-valued argument validates"}


# ---- the objective ---------------------------------------------------------

def utility(corpus, template, *, index=0):
    """cost(P) - cost(Rewrite(P, A)) - cost(A), from the programs really rewritten.

    Every rewritten site is expanded again and compared with what was there. A
    site whose expansion does not return the original subterm is not counted and
    is reported; the abstraction is not admitted on the strength of the others.
    """
    before = sum(cost(entry["program"]) for entry in corpus)
    definition_bits = cost(template)
    rewritten, used, failures = [], 0, []
    for entry in corpus:
        sites = select_sites(match_sites(template, entry["program"]))
        if not sites:
            rewritten.append({"id": entry["id"], "program": deepcopy(entry["program"]),
                              "sites": 0, "before_bits": cost(entry["program"]),
                              "after_bits": cost(entry["program"])})
            continue
        safety = safe_program_holes(template, sites)
        if not safety["safe"]:
            failures.append({"id": entry["id"], "reason": safety["reason"]})
            rewritten.append({"id": entry["id"], "program": deepcopy(entry["program"]),
                              "sites": 0, "before_bits": cost(entry["program"]),
                              "after_bits": cost(entry["program"])})
            continue
        try:
            replaced = rewrite(entry["program"], index, template, sites)
            restored = expand(replaced, definition_table({index: template}))
            returned = (key(canonical_literals(restored))
                        == key(canonical_literals(entry["program"])))
            reason = (None if returned else
                      "expanding the rewrite did not return the original")
        except (ValueError, TypeError, KeyError) as exc:
            returned, reason = False, f"the rewrite could not be expanded: {exc}"
        if not returned:
            # Not compression. The program is left exactly as it was and its
            # sites are not counted, so a rewrite nobody could undo can never
            # appear as a saving.
            failures.append({"id": entry["id"], "reason": reason})
            rewritten.append({"id": entry["id"], "program": deepcopy(entry["program"]),
                              "sites": 0, "before_bits": cost(entry["program"]),
                              "after_bits": cost(entry["program"])})
            continue
        used += len(sites)
        rewritten.append({"id": entry["id"], "program": replaced, "sites": len(sites),
                          "site_paths": [s["path"] for s in sites],
                          "before_bits": cost(entry["program"]),
                          "after_bits": cost(replaced)})
    after = sum(entry["after_bits"] for entry in rewritten)
    return {"schema": SCHEMA, "template": deepcopy(template), "index": index,
            "corpus_bits_before": before, "corpus_bits_after": after,
            "definition_bits": definition_bits,
            "utility_bits": before - after - definition_bits,
            "sites_used": used,
            "programs_touched": sum(1 for e in rewritten if e["sites"]),
            "rewritten": rewritten, "failures": failures,
            "holes": holes(template), "structure_size": structure_size(template),
            "cost_model": COST,
            "rewrite_strategy": ("outermost, non-overlapping; a site inside an "
                                 "already chosen site is not taken"),
            "verification": ("every counted site was expanded by definition and "
                             "compared with the original subterm"),
            "sha256": digest({"template": template, "index": index})}


def upper_bound(corpus, template):
    """Stitch's bound: the total cost of everything the pattern currently covers.

    Every completion of this template matches a subset of these positions, and
    the most any site can give back is the cost of what was there, so no
    completion can exceed this. It ignores the cost of the call the rewrite puts
    in, which is why it is an over-approximation and not the answer.
    """
    total, sites = 0, 0
    for entry in corpus:
        # Every match, not the non-overlapping selection: the paper's bound is
        # over `Matches`, and a completion may rewrite an inner position this
        # template's own greedy selection would have dropped.
        for site in match_sites(template, entry["program"]):
            total += cost(site["subterm"])
            sites += 1
    return {"bound_bits": total, "sites": sites,
            "argument": ("cost is non-negative, so a site gives back at most what "
                         "was there; and filling a hole only removes sites, so a "
                         "completion never matches where this one does not")}


def prefix_bytes(size):
    """What the length-prefixed encoding spends on saying how long it is."""
    return max(1, (size.bit_length() + 6) // 7)


def bound_precondition(corpus):
    """Does the bound hold on this corpus for *every* candidate, enumerated or not?

    The utility of one program rewritten at a set S of non-overlapping sites is

        8 * (sum over S of L_e - sum over S of M_e)      the body text
      + 8 * (prefix(n) - prefix(n'))                     the length descriptor

    with L_e the bytes the site occupied, M_e >= 0 the bytes the call occupies,
    n the program's byte length and n' its length after rewriting. The bound
    sums `cost(e) = 8 * (prefix(L_e) + L_e)` over the matches, so it covers the
    body-text term outright, and what it must also cover is the second term.
    Since the two sums are separate, the requirement separates too:

        for each program:   prefix(n) - prefix(n') <= number of sites in it

    because each site contributes at least one prefix byte of its own to the
    bound. That still mentions n', which is only known after a rewrite. The
    weaker requirement below does not, and it is what makes the bound a
    guarantee rather than an observation:

        for each program:   prefix(n) - 1 <= 1,  i.e.  n < 16384 bytes

    A program shorter than 16384 bytes has a two-byte length descriptor at most,
    so it can lose at most one prefix byte however far it is rewritten, and one
    rewritten site already puts one back. This is a property of the corpus, is
    checked before any candidate is enumerated, and holds for every candidate,
    including the ones the enumeration never reaches.
    """
    programs = [{"id": entry["id"], "bytes": len(key(entry["program"]).encode()),
                 "prefix": prefix_bytes(len(key(entry["program"]).encode()))}
                for entry in corpus]
    over = [row for row in programs if row["prefix"] > 2]
    return {"holds": not over,
            "limit_bytes": 1 << 14,
            "largest_program_bytes": max((row["bytes"] for row in programs),
                                         default=0),
            "programs_over_the_limit": over,
            "argument": ("body text and length descriptor are bounded separately; "
                         "the bound covers the body text outright, and a program "
                         "under 16384 bytes can lose at most one descriptor byte, "
                         "which one rewritten site already returns"),
            "checked": "before enumeration, over the whole corpus"}


# ---- the search ------------------------------------------------------------

def _spread(size):
    """Index pairs at increasing separation, deterministically."""
    for gap in range(1, size):
        for first in range(size - gap):
            yield first, first + gap


def candidates(corpus, *, pairs=4000, limit=6, source_filter=None, deduplicate_sources=False):
    """Templates generalising stored subterms, within a pair-attempt budget.

    An optional source filter must be a necessary condition for either operand
    of an admissible generalisation, not an arbitrary preference or evaluation
    result. Corpus occurrences remain intact for utility and proof checks.
    Exact source deduplication changes order under a finite budget, but cannot
    remove a distinct generalisation from the exhaustive candidate set.
    """
    pool = []
    source_seen = set()
    source_count, source_excluded, source_duplicates = 0, 0, 0
    for entry in corpus:
        for _, node in subterms(entry["program"]):
            source_count += 1
            if source_filter is not None and not source_filter(node):
                source_excluded += 1
                continue
            if deduplicate_sources:
                encoded = key(node)
                if encoded in source_seen:
                    source_duplicates += 1
                    continue
                source_seen.add(encoded)
            pool.append(node)
    seen, offered, tried = set(), [], 0
    # Pairs at increasing separation rather than lexicographic order: the first
    # element would otherwise be paired against everything before the second is
    # reached at all, and the whole budget would be spent inside one program.
    for first, second in _spread(len(pool)):
        if tried >= pairs:
            break
        tried += 1
        try:
            template, samples = generalise(pool[first], pool[second], limit=limit)
        except (ValueError, TypeError, KeyError):
            continue
        encoded = key(template)
        if encoded in seen:
            continue
        seen.add(encoded)
        offered.append({"id": digest(template)[:16], "template": template,
                        "samples": samples})
    return {"candidates": offered, "pairs_tried": tried, "subterms": source_count,
            "source_pool": {"positions_scanned": source_count, "excluded": source_excluded,
                            "duplicates": source_duplicates, "retained": len(pool),
                            "possible_pairs": len(pool)*(len(pool)-1)//2,
                            "stop_reason": ("pair_budget" if tried < len(pool)*(len(pool)-1)//2
                                            else "source_pairs_exhausted")}}


def learn(corpus, *, pairs=4000, limit=6, keep=8, admissible=None,
          source_filter=None, deduplicate_sources=False):
    """Rank candidates by the objective, pruning by the bound before evaluating.

    The bound is computed first because it is the cheap half: it needs the match
    locations but not the rewrite, the expansion or the re-costing.
    """
    precondition = bound_precondition(corpus)
    offered = candidates(corpus, pairs=pairs, limit=limit, source_filter=source_filter,
                         deduplicate_sources=deduplicate_sources)
    scored, pruned, audits, excluded = [], 0, [], []
    best = 0
    for entry in offered["candidates"]:
        if admissible is not None and not admissible(entry["template"]):
            excluded.append(entry["id"])
            continue
        bound = upper_bound(corpus, entry["template"])
        if bound["sites"] < 2:
            pruned += 1
            continue
        if bound["bound_bits"] <= best:
            pruned += 1
            continue
        # A scoring index no corpus can already contain, so a call an earlier
        # round put there is never expanded with this round's definition.
        verdict = utility(corpus, entry["template"], index=-1)
        audits.append({"id": entry["id"], "bound_bits": bound["bound_bits"],
                       "utility_bits": verdict["utility_bits"],
                       "bound_holds": bound["bound_bits"] >= verdict["utility_bits"]})
        scored.append(dict(entry, bound=bound, verdict=verdict))
        best = max(best, verdict["utility_bits"])
    scored.sort(key=lambda e: (-e["verdict"]["utility_bits"], e["id"]))
    return {"schema": SCHEMA, "corpus_size": len(corpus),
            "corpus_bits": sum(cost(e["program"]) for e in corpus),
            "offered": len(offered["candidates"]), "subterms": offered["subterms"],
            "pairs_tried": offered["pairs_tried"], "pruned_by_bound": pruned,
            "source_pool": offered["source_pool"],
            "excluded_by_contract": excluded,
            "evaluated": len(scored), "bound_audit": audits,
            "bound_violations": [a for a in audits if not a["bound_holds"]],
            "ranked": scored[:keep], "cost_model": COST,
            "bound_precondition": precondition,
            "pruning_scope": ("the bound filters the candidates this enumeration "
                              "offered; it is not a priority over a queue of "
                              "partial abstractions, so pruning here says nothing "
                              "about candidates the enumeration never produced"),
            "global_optimality_claimed": False}


def audit_bound(corpus, template, *, fills=4):
    """Check the two facts the bound rests on, on this corpus and this template.

    Specialising a hole must not add match locations, and the bound must not fall
    below the utility. Neither is taken on trust.
    """
    parent = upper_bound(corpus, template)
    checks = []
    for name in holes(template)[:fills]:
        for entry in corpus:
            for site in select_sites(match_sites(template, entry["program"])):
                if name not in site["binding"]:
                    continue
                filled = _fill_hole(template, name, site["binding"][name])
                child = upper_bound(corpus, filled)
                checks.append({"hole": name, "parent_sites": parent["sites"],
                               "child_sites": child["sites"],
                               "monotone": child["sites"] <= parent["sites"]})
                break
            if checks and checks[-1]["hole"] == name:
                break
    verdict = utility(corpus, template)
    return {"parent": parent, "utility_bits": verdict["utility_bits"],
            "bound_holds": parent["bound_bits"] >= verdict["utility_bits"],
            "slack_bits": parent["bound_bits"] - verdict["utility_bits"],
            "monotonicity_checks": checks,
            "monotone": all(c["monotone"] for c in checks)}


def _fill_hole(template, name, value):
    if is_hole(template):
        if (template.get("parameter") or template.get("series_parameter")) == name:
            return deepcopy(value)
        return deepcopy(template)
    if isinstance(template, dict):
        return {f: _fill_hole(template[f], name, value) for f in template}
    if isinstance(template, list):
        return [_fill_hole(item, name, value) for item in template]
    return template


def learn_library(corpus, *, rounds=3, pairs=20000, limit=6, keep=8,
                  progress=None):
    """Learn several abstractions, each measured on what the last one left.

    Applying the winner and then searching again is what keeps the total honest:
    the second abstraction is scored against a corpus that already contains the
    first one's call sites, so structure the first abstraction already removed
    cannot be sold twice. The net figure at the end is the original corpus cost
    minus the final corpus cost minus every definition kept.
    """
    current = [dict(entry) for entry in corpus]
    original_bits = sum(cost(entry["program"]) for entry in current)
    kept, rounds_log = [], []
    for index in range(rounds):
        if progress:
            progress(f"round {index}: searching over "
                     f"{sum(len(subterms(e['program'])) for e in current)} subterm "
                     f"positions in {len(current)} programs")
        found = learn(current, pairs=pairs, limit=limit, keep=keep)
        if progress:
            best_bits = (found["ranked"][0]["verdict"]["utility_bits"]
                         if found["ranked"] else 0)
            progress(f"round {index}: {found['offered']} offered, "
                     f"{found['pruned_by_bound']} pruned, {found['evaluated']} "
                     f"evaluated, best {best_bits:+d} bits")
        best = found["ranked"][0] if found["ranked"] else None
        record = {"round": index, "offered": found["offered"],
                  "pruned_by_bound": found["pruned_by_bound"],
                  "evaluated": found["evaluated"],
                  "bound_violations": found["bound_violations"],
                  "corpus_bits": found["corpus_bits"]}
        if best is None or best["verdict"]["utility_bits"] <= 0:
            record["accepted"] = None
            record["reason"] = ("no candidate had positive utility on this corpus"
                                if best else "no candidate survived the bound")
            rounds_log.append(record)
            break
        verdict = utility(current, best["template"], index=len(kept))
        current = [{"id": row["id"], "program": row["program"],
                    "proved": entry.get("proved"), "source": entry.get("source")}
                   for row, entry in zip(verdict["rewritten"], current)]
        kept.append({"index": len(kept), "id": best["id"],
                     "template": deepcopy(best["template"]),
                     "arguments": holes(best["template"]),
                     "definition_bits": verdict["definition_bits"],
                     "utility_bits": verdict["utility_bits"],
                     "sites_used": verdict["sites_used"],
                     "programs_touched": verdict["programs_touched"],
                     "failures": verdict["failures"],
                     "use_sites": [{"id": row["id"], "paths": row.get("site_paths", [])}
                                   for row in verdict["rewritten"] if row["sites"]],
                     "bound_bits": best["bound"]["bound_bits"]})
        record["accepted"] = best["id"]
        record["utility_bits"] = verdict["utility_bits"]
        rounds_log.append(record)
    final_bits = sum(cost(entry["program"]) for entry in current)
    definition_bits = sum(entry["definition_bits"] for entry in kept)
    return {"schema": SCHEMA, "rounds": rounds_log, "library": kept,
            "bound_precondition": bound_precondition(corpus),
            "pruning_scope": ("the bound filters the candidates this enumeration "
                              "offered; it is not a priority over a queue of "
                              "partial abstractions, so pruning here says nothing "
                              "about candidates the enumeration never produced"),
            "corpus_bits_before": original_bits, "corpus_bits_after": final_bits,
            "definition_bits": definition_bits,
            "net_compression_bits": original_bits - final_bits - definition_bits,
            "rewritten_corpus": current, "cost_model": COST,
            "counting": ("each round is measured on the corpus the previous round "
                         "left, so no structure is counted twice"),
            "global_optimality_claimed": False}


def verify_semantics(library, corpus, *, sample=4, terms=12):
    """Are the rewritten programs the same series, not merely the same tree?

    The expansion check is about the program. This one runs the existing series
    certifier on the expansion of what was actually rewritten, which is the
    prover the rest of the loop uses and the one whose scope is already
    declared: Q[[x]] at zero, analytic germs only.
    """
    from math_os_prototype.holonomic_route_discovery import certify_equal

    definitions = definition_table({entry["index"]: entry["template"]
                                    for entry in library["library"]})
    original = {entry["id"]: entry["program"] for entry in corpus}
    checked, failures = [], []
    for row in library["rewritten_corpus"]:
        if len(checked) >= sample:
            break
        if key(row["program"]) == key(original.get(row["id"], row["program"])):
            continue
        restored = expand_for_execution(row["program"], definitions)
        try:
            proof = certify_equal(restored, original[row["id"]])
            status = proof["status"]
        except Exception as exc:                       # noqa: BLE001 - reported
            status = f"{type(exc).__name__}: {exc}"[:90]
        record = {"id": row["id"], "status": status,
                  "route": "definitional expansion, then the series certifier"}
        checked.append(record)
        if status != "exact_formal_series_equality":
            failures.append(record)
    return {"checked": checked, "failures": failures,
            "scope": "Q[[x]] at zero; analytic germs only",
            "route_note": ("every site here was rewritten by definition alone; no "
                           "existing equality was used to move to another "
                           "representation, so nothing beyond definitional "
                           "unfolding is being claimed")}


# ---- calls a search can propose ------------------------------------------

def rationals_in(program, found=None):
    """The rational constants a program already mentions."""
    found = [] if found is None else found
    if isinstance(program, dict):
        for field in sorted(program):
            rationals_in(program[field], found)
    elif isinstance(program, list):
        for item in program:
            rationals_in(item, found)
    else:
        quantity = numeric(program)
        if quantity is not None and str(quantity) not in found:
            found.append(str(quantity))
    return found


def _offers_of(entry, program_pool, value_pool, excluded, seen, table,
               normalise, revisits, budget, argument_pools=None):
    """Every call of ONE definition the pools allow, in the fixed order.

    Lazily, so that the caller can take one at a time. `seen` and `excluded` are
    shared across definitions, so a program already offered by another definition
    is still skipped here.

    Sameness is decided on `normalise(program)`, not on the term as it happens to
    be written. Two calls can expand to the same object through different
    argument nestings; comparing the terms as written lets the second one through
    and it then consumes a slot it cannot use. A candidate skipped that way goes
    to `revisits` when the caller asks for them: it is another route to something
    already held, which is worth keeping and is not a new construction.

    `budget` is a one-element list counting expansions examined, so filling the
    limit cannot become an unbounded scan.
    """
    names = holes(entry["template"])
    pools = [argument_pools[name] if argument_pools is not None else
             program_pool if name.startswith("f") else value_pool
             for name in names]
    if not names or any(not pool for pool in pools):
        return
    for combination in _combinations(pools):
        if budget[0] <= 0:
            return
        budget[0] -= 1
        binding = dict(zip(names, combination))
        call = {"op": USE, "abstraction": entry["index"],
                "arguments": {name: deepcopy(value)
                              for name, value in binding.items()}}
        try:
            # The same full expansion the executor uses. Building the body first
            # and expanding that would drive one level more than expanding the
            # call does, so a nested definition could pass here and fail there.
            program = expand_for_execution(call, table)
        except (ValueError, TypeError, KeyError):
            continue
        encoded = key(normalise(program))
        if encoded in excluded or encoded in seen:
            if revisits is not None:
                revisits.append({"id": digest(call)[:16], "call": call,
                                 "definition": entry["index"],
                                 "reason": "already held under this normalisation",
                                 "call_bits": cost(call),
                                 "expanded_bits": cost(program)})
            continue
        seen.add(encoded)
        yield {"id": digest(call)[:16], "call": call,
               "definition": entry["index"],
               "call_bits": cost(call),
               "expanded_bits": cost(program)}


def call_candidates(library, program_pool, *, limit=12, exclude=(), value_pool=None,
                    table=None, normalise=None, scan=None, revisits=None, stats=None,
                    argument_pools=None):
    """Calls of the learned definitions, with arguments taken from a pool.

    The arguments are drawn from what the search already has -- its own seeds and
    whatever it has acquired -- and the rationals those programs already mention.
    Nothing about which combination is worth trying is supplied: every one the
    pool allows is offered, in a fixed order, and the budget decides how far the
    search gets.

    A combination whose expansion is already in `exclude` is not offered. That is
    what makes this different from putting the stored programs back in as seeds:
    what is offered is the combinations the corpus does *not* already contain.

    **Round robin, one offer per definition per pass.** Taking each definition to
    exhaustion in turn is what starves the rest: a definition with six program
    holes over an n-entry pool has n^6 combinations of its own, so the first one
    reached fills any limit and the iteration never advances. Whether that
    happens has nothing to do with which definitions they are -- it is the shape
    of the product. Interleaving gives every definition that still has a
    candidate an offer before any of them gets a second one. No definition is
    named, preferred or excluded here, and neither the objective, the utility nor
    the cost is consulted: the library arrives in whatever order the caller
    passes it, and each entry is drawn from equally.
    """
    # Sameness is decided after `normalise`, which a caller supplies when its
    # language can write one object more than one way; the default changes
    # nothing. `scan` bounds how many expansions may be examined, so a limit
    # cannot be chased indefinitely. `revisits` collects candidates skipped
    # because what they expand to is already held.
    normalise = normalise or (lambda program: program)
    excluded = set(exclude)
    budget = [int(scan) if scan is not None else max(200, 50 * int(limit))]
    initial_budget = budget[0]
    def measured(result):
        if stats is not None:
            stats.update(expansions_examined=initial_budget-budget[0], offers=len(result))
        return result
    # the environment a call is expanded in is the one its own library defines
    if table is None:
        table = definition_table({entry["index"]: entry["template"]
                                  for entry in library})
    if value_pool is None:
        value_pool = []
        for program in program_pool:
            for value in rationals_in(program):
                if value not in value_pool:
                    value_pool.append(value)
    offered, seen = [], set()
    streams = [_offers_of(entry, program_pool, value_pool, excluded, seen, table,
                          normalise, revisits, budget,
                          argument_pools.get(entry["index"]) if argument_pools is not None else None)
               for entry in library]
    while streams:
        alive = []
        for stream in streams:
            try:
                offered.append(next(stream))
            except StopIteration:
                continue
            alive.append(stream)
            if len(offered) >= limit:
                return measured(offered)
        streams = alive
    return measured(offered)


def _combinations(pools):
    """Every choice from each pool, in a fixed order."""
    if not pools:
        yield ()
        return
    for head in pools[0]:
        for tail in _combinations(pools[1:]):
            yield (head,) + tail


# ---- what the next search should do differently ----------------------------

def search_bias(learned, *, weight=2):
    # Accepts either a `learn` result (ranked candidates) or a `learn_library`
    # result (the abstractions actually kept).
    """Reweight candidates that match what was learned; add no axiom.

    Twitch (Axelrod, Johansson and Smallbone, 2026) reports that handing learned
    abstractions to an equational prover as extra axioms enlarges the search
    space and can make it much slower, while using the same abstractions only to
    lower the weight of matching terms is robust. The same distinction is kept
    here: an accepted abstraction changes which candidate is looked at first and
    nothing about what may be derived.
    """
    entries = []
    source = learned.get("library")
    if source is None:
        source = [{"id": e["id"], "template": e["template"],
                   "utility_bits": e["verdict"]["utility_bits"]}
                  for e in learned["ranked"]]
    for rank, entry in enumerate(source):
        if entry["utility_bits"] <= 0:
            continue
        entries.append({"id": entry["id"], "template": deepcopy(entry["template"]),
                        "weight_multiplier": weight,
                        "utility_bits": entry["utility_bits"], "rank": rank})
    return {"schema": SCHEMA, "entries": entries,
            "effect": "candidate ordering only; the derivable set is unchanged",
            "not_done": "no abstraction is added to the controller as a rule"}


def matches_bias(bias, program):
    """Which learned abstractions occur in this program, and how many times."""
    hits = []
    for entry in bias["entries"]:
        sites = select_sites(match_sites(entry["template"], program))
        if sites:
            hits.append({"id": entry["id"], "sites": len(sites),
                         "weight_multiplier": entry["weight_multiplier"]})
    return hits
