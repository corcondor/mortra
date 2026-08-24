from __future__ import annotations

import unittest

from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.typed_construction_contracts import (
    ObligationBranchReduction,
    TypedConstructionContract,
    carry_construction_requirements,
    consistent_branch_closure_score,
    reduce_obligation_branches,
    synthesize_contract_candidates,
)
from worker.backend.typed_geometry_stalk import ConstructionFamily


class TypedConstructionContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.on_line = TypedConstructionContract(
            ConstructionFamily("on_line", 2, "all", ("coll",)),
            "?OUT",
            ("?A", "?B"),
            (Atom("coll", ("?OUT", "?A", "?B")),),
        )

    def test_witness_obligation_compiles_to_construction(self) -> None:
        candidates, audit = synthesize_contract_candidates(
            (Atom("coll", ("?X", "a", "b")),),
            (self.on_line,),
            visible_entities=("a", "b", "c"),
            output_entity="d",
        )
        self.assertEqual([item.key for item in candidates], ["on_line(a,b)"])
        self.assertEqual(audit.matched_obligations, 1)

    def test_ground_proposition_does_not_invent_a_witness(self) -> None:
        candidates, audit = synthesize_contract_candidates(
            (Atom("coll", ("a", "b", "c")),),
            (self.on_line,),
            visible_entities=("a", "b", "c"),
            output_entity="d",
        )
        self.assertEqual(candidates, ())
        self.assertEqual(audit.witness_obligations, 0)

    def test_alpha_renaming_preserves_family_and_inputs(self) -> None:
        first, _ = synthesize_contract_candidates(
            (Atom("coll", ("?X", "a", "b")),),
            (self.on_line,),
            visible_entities=("a", "b"),
            output_entity="c",
        )
        second, _ = synthesize_contract_candidates(
            (Atom("coll", ("?W", "p", "q")),),
            (self.on_line,),
            visible_entities=("p", "q"),
            output_entity="r",
        )
        self.assertEqual(first[0].family, second[0].family)
        self.assertEqual(len(first[0].inputs), len(second[0].inputs))

    def test_shared_holes_are_scored_with_one_consistent_binding(self) -> None:
        atoms = (
            Atom("perp", ("z", "a", "i", "o")),
            Atom("para", ("z", "a", "m", "n")),
        )
        coherent = (
            Atom("perp", ("?C", "?D", "i", "o")),
            Atom("para", ("?C", "?D", "m", "n")),
        )
        conflicting = (
            Atom("perp", ("?C", "?D", "i", "o")),
            Atom("para", ("?C", "?D", "m", "n")),
        )

        self.assertEqual(consistent_branch_closure_score(atoms, coherent)[0], 2)
        self.assertEqual(
            consistent_branch_closure_score(
                (atoms[0], Atom("para", ("x", "b", "m", "n"))),
                conflicting,
            )[0],
            1,
        )

    def test_branch_reduction_preserves_binding_in_remaining_atoms(self) -> None:
        branch = (
            Atom("perp", ("?C", "?D", "a", "c")),
            Atom("para", ("?C", "?D", "p", "q")),
        )
        reduction = reduce_obligation_branches(
            (Atom("para", ("a", "g", "p", "q")),),
            (branch,),
        )

        self.assertEqual(reduction.matched_atom_count, 1)
        self.assertEqual(
            reduction.progressed_branches,
            ((Atom("perp", ("a", "g", "a", "c")).canonical(),),),
        )

    def test_branch_reduction_rejects_inconsistent_rebinding(self) -> None:
        branch = (
            Atom("perp", ("?C", "?D", "a", "c")),
            Atom("para", ("?C", "?D", "p", "q")),
        )
        reduction = reduce_obligation_branches(
            (
                Atom("perp", ("a", "g", "a", "c")),
                Atom("para", ("b", "h", "p", "q")),
            ),
            (branch,),
        )

        self.assertEqual(reduction.matched_atom_count, 1)
        self.assertEqual(reduction.fully_closed_branch_count, 0)

    def test_construction_requirements_remain_open_proof_obligations(self) -> None:
        contract = TypedConstructionContract(
            self.on_line.family,
            self.on_line.output_variable,
            self.on_line.input_variables,
            self.on_line.relation_atoms,
            (Atom("diff", ("?A", "?B")),),
        )
        candidates, audit = synthesize_contract_candidates(
            (Atom("coll", ("?X", "a", "b")),),
            (contract,),
            visible_entities=("a", "b"),
            output_entity="c",
        )

        self.assertEqual(candidates[0].requirement_atoms, (Atom("diff", ("a", "b")),))
        self.assertEqual(candidates[0].open_requirements, (Atom("diff", ("a", "b")),))
        self.assertEqual(candidates[0].residual_reduction, 1)
        self.assertFalse(candidates[0].fully_closes_branch)
        self.assertFalse(candidates[0].executable)
        self.assertEqual(len(candidates[0].plan_certificate_sha256), 64)
        self.assertEqual(audit.open_requirement_atoms, 1)
        self.assertEqual(audit.fully_closing_candidates, 0)

    def test_known_fact_discharges_construction_requirement(self) -> None:
        contract = TypedConstructionContract(
            self.on_line.family,
            self.on_line.output_variable,
            self.on_line.input_variables,
            self.on_line.relation_atoms,
            (Atom("diff", ("?A", "?B")),),
        )
        candidates, audit = synthesize_contract_candidates(
            (Atom("coll", ("?X", "a", "b")),),
            (contract,),
            visible_entities=("a", "b"),
            output_entity="c",
            known_facts=(Atom("diff", ("a", "b")),),
        )

        self.assertEqual(candidates[0].open_requirements, ())
        self.assertEqual(audit.open_requirement_atoms, 0)

    def test_noncollinearity_discharges_distinct_endpoint_requirement(self) -> None:
        contract = TypedConstructionContract(
            self.on_line.family,
            self.on_line.output_variable,
            self.on_line.input_variables,
            self.on_line.relation_atoms,
            (Atom("diff", ("?A", "?B")),),
        )
        candidates, _audit = synthesize_contract_candidates(
            (Atom("coll", ("?X", "a", "b")),),
            (contract,),
            visible_entities=("a", "b", "c"),
            output_entity="d",
            known_facts=(Atom("ncoll", ("a", "b", "c")),),
        )

        self.assertTrue(candidates[0].executable)

    def test_reflexive_distinct_requirement_is_statically_rejected(self) -> None:
        family = ConstructionFamily(
            "on_line_repeated", 2, "ordered", ("coll",), True
        )
        contract = TypedConstructionContract(
            family,
            "?OUT",
            ("?A", "?B"),
            (Atom("coll", ("?OUT", "?A", "?B")),),
            (Atom("diff", ("?A", "?B")),),
        )
        candidates, audit = synthesize_contract_candidates(
            (Atom("coll", ("?X", "a", "a")),),
            (contract,),
            visible_entities=("a",),
            output_entity="b",
        )

        self.assertEqual(candidates, ())
        self.assertEqual(audit.statically_rejected_candidates, 1)

    def test_open_requirements_prevent_false_branch_closure(self) -> None:
        reduction = ObligationBranchReduction(
            branches=((),),
            progressed_branches=((),),
            matched_atom_count=1,
            fully_closed_branch_count=1,
        )

        carried = carry_construction_requirements(
            reduction,
            (Atom("diff", ("a", "b")),),
            (),
        )

        self.assertEqual(
            carried.progressed_branches,
            ((Atom("diff", ("a", "b")),),),
        )
        self.assertEqual(carried.fully_closed_branch_count, 0)

    def test_proved_requirements_preserve_true_branch_closure(self) -> None:
        reduction = ObligationBranchReduction(
            branches=((),),
            progressed_branches=((),),
            matched_atom_count=1,
            fully_closed_branch_count=1,
        )

        carried = carry_construction_requirements(
            reduction,
            (Atom("diff", ("a", "b")),),
            (Atom("diff", ("a", "b")),),
        )

        self.assertEqual(carried.progressed_branches, ((),))
        self.assertEqual(carried.fully_closed_branch_count, 1)

    def test_metric_chart_compiles_length_equation_witness_to_perpendicular_contract(
        self,
    ) -> None:
        on_tline = TypedConstructionContract(
            ConstructionFamily("on_tline", 3, "ordered", ("perp",)),
            "?OUT",
            ("?P", "?A", "?B"),
            (Atom("perp", ("?OUT", "?P", "?A", "?B")),),
        )
        demand = Atom(
            "lequation",
            (
                "1/1", "?X", "a", "*", "?X", "a",
                "1/1", "p", "b", "*", "p", "b",
                "-1/1", "?X", "b", "*", "?X", "b",
                "-1/1", "p", "a", "*", "p", "a",
                "0",
            ),
        )

        candidates, audit = synthesize_contract_candidates(
            (demand,),
            (on_tline,),
            visible_entities=("p", "a", "b"),
            output_entity="x",
            obligation_branches=((demand,),),
        )

        self.assertEqual(
            {item.inputs for item in candidates},
            {("p", "a", "b"), ("p", "b", "a")},
        )
        self.assertTrue(all(item.family == "on_tline" for item in candidates))
        self.assertTrue(all(item.matched_via_chart for item in candidates))
        self.assertTrue(
            all(item.chart_name == "metric_squared_distance" for item in candidates)
        )
        self.assertTrue(
            all(len(item.chart_certificate_sha256 or "") == 64 for item in candidates)
        )
        self.assertTrue(all(item.fully_closes_branch for item in candidates))
        self.assertEqual(audit.chart_matched_candidates, 2)


if __name__ == "__main__":
    unittest.main()
