from __future__ import annotations

import unittest

from math_os_prototype.origami_fold_dna import (
    build_radial_panel_tree,
    execute_fold_program,
    make_fold_programs,
    state_to_spatial_figure,
    validate_fold_state,
)
from math_os_prototype.spatial_visual_basis import new_morphism_count, semantic_hash


class OrigamiFoldDnaTest(unittest.TestCase):
    def test_same_crease_graph_produces_three_distinct_folded_states(self) -> None:
        initial = build_radial_panel_tree()
        figures = []
        for program in make_fold_programs():
            final = execute_fold_program(initial, program)[-1]
            figures.append(state_to_spatial_figure(final, program.program_id, program))
        self.assertEqual(len({semantic_hash(figure) for figure in figures}), 3)

    def test_every_intermediate_state_preserves_panels_and_hinges(self) -> None:
        initial = build_radial_panel_tree()
        for program in make_fold_programs():
            for index, state in enumerate(execute_fold_program(initial, program)):
                validation = validate_fold_state(initial, state)
                self.assertTrue(validation["passed"], (program.program_id, index, validation))

    def test_fold_dna_compiles_only_to_existing_geometry(self) -> None:
        initial = build_radial_panel_tree()
        for program in make_fold_programs():
            self.assertEqual(len(program.genes), 24)
            self.assertTrue(all(gene.direction in {"M", "V"} for gene in program.genes))
            final = execute_fold_program(initial, program)[-1]
            figure = state_to_spatial_figure(final, program.program_id, program)
            self.assertEqual(new_morphism_count(figure), 0)
            self.assertIn("Rotate3", figure.operations_used)
            self.assertGreater(sum(len(item.moved_point_ids) for item in final.applied), 100)


if __name__ == "__main__":
    unittest.main()
