"""Shared schema adapters moved from experiment_newclid_construction_stalk.

Newclid supplies declarative data only. Importing this module neither starts
an external deductor nor loads the experiment's Yuclid execution machinery.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:                   # for the annotation only; see the helpers below
    from newclid.jgex.formulation import JGEXFormulation
from worker.backend.geometry_proof_hypergraph import Atom, Theorem, euclidean_relation_theorems
from worker.backend.typed_candidate_alignment import instantiate_relation_templates
from worker.backend.typed_construction_contracts import TypedConstructionContract
from worker.backend.typed_geometry_stalk import ConstructionFamily


@lru_cache(maxsize=1)
def definitions():
    """Newclid's construction definitions, read the first time one is asked for.

    This used to be a module-level constant, which made importing this module
    require Newclid even to look at the adapters around it.
    """
    from newclid.jgex.constructions import ALL_JGEX_CONSTRUCTIONS
    from newclid.jgex.definition import JGEXDefinition
    return JGEXDefinition.to_dict(ALL_JGEX_CONSTRUCTIONS)


def construction_relation_atoms(family: str, output: str, inputs: tuple[str, ...]) -> tuple[Atom, ...]:
    """Instantiate the formal conclusion atoms declared by a JGEX construction."""
    definition = definitions()[family]
    templates = []
    for clause in definition.clauses:
        for construction in clause.constructions:
            tokens = tuple(str(construction.string).split())
            if tokens:
                templates.append(Atom(tokens[0], tokens[1:]))
    return instantiate_relation_templates(tuple(map(str, definition.args)), templates, (output, *inputs))


def construction_requirement_atoms(family: str, output: str, inputs: tuple[str, ...]) -> tuple[Atom, ...]:
    """Instantiate the declared existence/nondegeneracy side conditions."""
    definition = definitions()[family]
    templates = tuple(Atom(tokens[0], tokens[1:])
        for construction in definition.requirements.constructions
        if (tokens := tuple(str(construction.string).split())))
    return instantiate_relation_templates(tuple(map(str, definition.args)), templates, (output, *inputs))


def typed_construction_contracts(families: tuple[ConstructionFamily, ...]) -> tuple[TypedConstructionContract, ...]:
    """Expose JGEX definitions as alpha-renamable construction contracts."""
    contracts = []
    for family in families:
        output_variable = "?OUT"
        input_variables = tuple(f"?INPUT{index}" for index in range(family.input_arity))
        contracts.append(TypedConstructionContract(family=family, output_variable=output_variable,
            input_variables=input_variables,
            relation_atoms=construction_relation_atoms(family.name, output_variable, input_variables),
            requirement_atoms=construction_requirement_atoms(family.name, output_variable, input_variables)))
    return tuple(contracts)


def _rule_atom(construction: Any) -> Atom:
    arguments = tuple(f"?{value}" if value and value[0].isalpha() else value
                      for value in map(str, construction.variables))
    return Atom(str(construction.name), arguments)


def native_rule_theorems() -> tuple[Theorem, ...]:
    """Expose explicit Newclid rules plus universal Euclidean AR morphisms."""
    theorems = []
    from newclid.all_rules import DEFAULT_RULES

    for rule in sorted(DEFAULT_RULES, key=lambda item: item.id):
        premises = tuple(_rule_atom(item) for item in rule.premises)
        for index, conclusion in enumerate(rule.conclusions):
            theorems.append(Theorem(f"{rule.id}:{index}", premises, _rule_atom(conclusion)))
    return (*theorems, *euclidean_relation_theorems())


def formulation_goal_atoms(formulation: JGEXFormulation) -> tuple[Atom, ...]:
    goals = []
    for goal in formulation.goals:
        raw_name = getattr(goal, "name", None)
        if hasattr(raw_name, "value"):
            raw_name = raw_name.value
        if not raw_name:
            raw_name = str(goal).split()[0]
        goals.append(Atom(str(raw_name), tuple(map(str, goal.args))).canonical())
    return tuple(goals)
