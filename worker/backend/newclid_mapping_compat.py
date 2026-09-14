"""Pinned Newclid 3.0 mapping boundaries, without adding mathematical rules.

Keep literal arguments literal, skip syntactically inadmissible predicate
instances, and preserve the type of a triangle under its existing symmetries.
"""
from itertools import permutations

from newclid.rule_matching import mapping_matcher as mm
from newclid.rule_matching import efficient_statement as es
from newclid.predicates import predicate_class_from_type, predicate_from_construction
from newclid.predicates._index import PredicateType
from newclid.problem import PredicateConstruction
from newclid.justifications.justification import RuleApplication
from newclid.symbols.lines_registry import LineMerge


def install_triangle_mapping_compat():
    if LineMerge.__hash__ is None:
        # Match the existing CircleMerge/Assumption hash contract.
        LineMerge.__hash__ = lambda self: hash(self.predicate)
    original = mm.efficient_version
    if getattr(original, "_mortra_triangle_compat", False):
        return

    def efficient_version(predicate):
        if predicate.predicate_type in {PredicateType.CONTRI_CLOCK, PredicateType.CONTRI_REFLECT}:
            return es.TriangleStatement(predicate.predicate_type.value, *predicate.to_tokens())
        try:
            return original(predicate)
        except NotImplementedError:
            return (predicate.predicate_type.value, *predicate.to_tokens())

    original_permutations = mm.generate_permutations

    def predicate_permutations(statement):
        if type(statement) is not tuple:
            yield from original_permutations(statement)
            return
        kind = predicate_class_from_type(PredicateType(statement[0]))
        args = statement[1:]
        canonical = kind.preparse(args)
        positions = [i for i, a in enumerate(args) if str(a)[0].isalpha()]
        for values in permutations([args[i] for i in positions]):
            candidate = list(args)
            for index, value in zip(positions, values):
                candidate[index] = value
            if kind.preparse(tuple(candidate)) == canonical:
                yield (statement[0], *candidate)

    def triangle_perms(statement):
        for order in permutations(range(3)):
            left = tuple(statement[1+i] for i in order)
            right = tuple(statement[4+i] for i in order)
            yield es.TriangleStatement(statement[0], *left, *right)
            yield es.TriangleStatement(statement[0], *right, *left)

    efficient_version._mortra_triangle_compat = True
    mm.efficient_version = efficient_version
    mm.generate_permutations = predicate_permutations
    es.triangle_perms = triangle_perms


class ValidatedMappingMatcher(mm.MappingMatcher):
    def __init__(self):
        install_triangle_mapping_compat()
        super().__init__(mm.FilterMapper())
        self.unsupported = set()

    def _match_generic(self, rule, proof):
        result = set()
        # The pinned predicate factory explicitly has no constructor for
        # these two types. Record the missing interface, never assume a result.
        unsupported = {PredicateType.ANGLE_EQUATION, PredicateType.LENGTH_EQUATION}
        if any(PredicateType(c.name) in unsupported for c in rule.premises+rule.conclusions):
            self.unsupported.add(rule.id)
            return result
        points = [p.name for p in proof.symbols.points]

        def instantiate(construction, mapping):
            args = tuple(mapping[a] if str(a)[0].isalpha() else a for a in construction.variables)
            kind = PredicateType(construction.name)
            if predicate_class_from_type(kind).preparse(args) is None:
                return None
            return predicate_from_construction(
                PredicateConstruction.from_predicate_type_and_args(kind, args), proof.symbols.points)

        for mapping in self.theorem_mapper.mappings(rule, points, proof=proof):
            premises = tuple(instantiate(p, mapping) for p in rule.premises)
            if any(p is None or not proof.check(p) for p in premises):
                continue
            for conclusion in rule.conclusions:
                predicate = instantiate(conclusion, mapping)
                if predicate is not None:
                    result.add(RuleApplication(predicate=predicate, rule=rule, premises=premises))
        return result
