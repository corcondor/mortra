from __future__ import annotations

import math
import unittest

from math_os_prototype.visual_reasoning import (
    INCREMENTAL_INTERSECTION,
    ORBIT_TO_DISK_UNION,
    PIVOT_ROTATION_TO_ORBIT,
    apply_plane_scene_actions,
    compile_plane_scene_timeline,
    compose_visual_explanation,
    function_plot_diagram,
    plane_scene_diagram,
    pivot_rotation_diagram,
    progressive_diagram_frames,
    radial_intersection_diagram,
    regular_polygon_disk_family,
    regular_polygon_vertices,
    state_transition_diagram,
    variation_table_diagram,
    visual_step,
)


class VisualReasoningTests(unittest.TestCase):
    def test_pivot_rotation_accepts_an_unrelated_polygon_order(self) -> None:
        diagram = pivot_rotation_diagram(
            regular_polygon_vertices(8),
            total_angle=math.pi / 2,
            title="正八角形の支点回転",
            caption="開始・中間・終了を同じ構成から描く。",
        )

        self.assertEqual(diagram["kind"], "plane")
        self.assertEqual(len([s for s in diagram["shapes"] if s["kind"] == "polyline"]), 4)
        self.assertEqual(len([s for s in diagram["shapes"] if s["kind"] == "arc"]), 1)

    def test_radial_intersection_accepts_arbitrary_disk_families(self) -> None:
        families = [regular_polygon_disk_family(order) for order in (4, 6, 8)]

        diagram = radial_intersection_diagram(
            families,
            current_family_index=2,
            scale=1.0,
            title="三つの円板族の共通部分",
            caption="問題番号に依存しない有限円板族の共通部分。",
        )

        self.assertEqual(diagram["kind"], "plane")
        self.assertGreater(len(diagram["shapes"]), 3)

    def test_composition_rejects_a_broken_typed_chain(self) -> None:
        orbit = visual_step(
            step_id="orbit",
            title="軌跡",
            explanation_ja="支点回転を軌跡へ移す。",
            formula_tex="",
            morphism=PIVOT_ROTATION_TO_ORBIT,
            source_state_id="polygon",
            target_state_id="orbit-state",
            diagram={"kind": "morphism", "version": 1, "title": "軌跡", "caption": "", "nodes": ["P", "O"]},
        )
        intersection = visual_step(
            step_id="intersection",
            title="共通部分",
            explanation_ja="円板族の共通部分を取る。",
            formula_tex="",
            morphism=INCREMENTAL_INTERSECTION,
            source_state_id="orbit-state",
            target_state_id="common",
            diagram={"kind": "morphism", "version": 1, "title": "共通部分", "caption": "", "nodes": ["O", "G"]},
        )

        with self.assertRaisesRegex(ValueError, "visual type chain breaks"):
            compose_visual_explanation([orbit, intersection], title="壊れた列")

    def test_orbit_and_disk_union_form_a_valid_typed_pair(self) -> None:
        first = visual_step(
            step_id="orbit",
            title="軌跡",
            explanation_ja="支点回転を軌跡へ移す。",
            formula_tex="",
            morphism=PIVOT_ROTATION_TO_ORBIT,
            source_state_id="polygon",
            target_state_id="orbit-state",
            diagram={"kind": "morphism", "version": 1, "title": "軌跡", "caption": "", "nodes": ["P", "O"]},
        )
        second = visual_step(
            step_id="disk-union",
            title="円板合併",
            explanation_ja="頂点軌跡を円板合併へ移す。",
            formula_tex="",
            morphism=ORBIT_TO_DISK_UNION,
            source_state_id="orbit-state",
            target_state_id="radial-body",
            diagram={"kind": "morphism", "version": 1, "title": "円板", "caption": "", "nodes": ["O", "F"]},
        )

        explanation = compose_visual_explanation([first, second], title="有効な列")
        self.assertTrue(explanation["composition_verified"])

    def test_function_plot_is_generated_from_an_unrelated_cubic(self) -> None:
        diagram = function_plot_diagram(
            [("f", lambda x: x**3 - 3 * x, "primary")],
            x_min=-2.2,
            x_max=2.2,
            marked_points=[(-1.0, 2.0, "極大"), (1.0, -2.0, "極小")],
            title="三次関数の概形",
            caption="厳密に得た臨界点を標本曲線へ重ねる。",
        )

        self.assertTrue(diagram["axes"])
        self.assertEqual(diagram["kind"], "plane")
        self.assertEqual(len([shape for shape in diagram["shapes"] if shape["kind"] == "point"]), 2)

    def test_probability_process_and_variation_table_use_the_same_visual_contract(self) -> None:
        process = state_transition_diagram(
            [
                {"id": "s0", "label": "0", "active": True},
                {"id": "s1", "label": "1"},
                {"id": "s2", "label": "2", "terminal": True},
            ],
            [
                {"from": "s0", "to": "s1", "label": "表"},
                {"from": "s1", "to": "s2", "label": "表"},
            ],
            title="二回成功するまでの状態",
            caption="確率過程を有限状態として描く。",
        )
        variation = variation_table_diagram(
            ["(-∞,-1)", "-1", "(-1,1)", "1", "(1,∞)"],
            [
                {"label": "f'(x)", "cells": ["+", "0", "-", "0", "+"]},
                {"label": "f(x)", "cells": ["↗", "極大", "↘", "極小", "↗"]},
            ],
            title="増減表",
            caption="導関数の符号から概形を読む。",
        )

        self.assertEqual(process["kind"], "state")
        self.assertEqual(variation["kind"], "variation")
        self.assertEqual(len(progressive_diagram_frames(process, 3)[0]["states"]), 1)
        self.assertEqual(progressive_diagram_frames(variation, 2)[-1], variation)

    def test_progressive_plane_frames_end_at_the_exact_original_scene(self) -> None:
        diagram = radial_intersection_diagram(
            [regular_polygon_disk_family(order) for order in (3, 4, 5)],
            current_family_index=2,
            scale=1.0,
            title="段階表示",
            caption="図形要素を順に開示する。",
        )
        frames = progressive_diagram_frames(diagram, 5)

        self.assertEqual(len(frames), 5)
        self.assertLessEqual(len(frames[0]["shapes"]), len(frames[-1]["shapes"]))
        self.assertEqual(frames[-1], diagram)

    def test_scene_actions_draw_and_zoom_an_unrelated_triangle_proof(self) -> None:
        initial = plane_scene_diagram(
            title="三角形の中点構成",
            caption="証明器が確定した対象だけを置く。",
            viewport={"xMin": -1, "xMax": 5, "yMin": -1, "yMax": 4},
            shapes=[
                {
                    "id": "triangle",
                    "kind": "polyline",
                    "points": [
                        {"x": 0, "y": 0},
                        {"x": 4, "y": 0},
                        {"x": 1, "y": 3},
                    ],
                    "closed": True,
                    "tone": "secondary",
                },
                {"id": "A", "kind": "point", "point": {"x": 0, "y": 0}, "label": "A"},
                {"id": "B", "kind": "point", "point": {"x": 4, "y": 0}, "label": "B"},
                {"id": "C", "kind": "point", "point": {"x": 1, "y": 3}, "label": "C"},
            ],
        )
        frames = compile_plane_scene_timeline(
            initial,
            [
                {
                    "actions": [
                        {
                            "op": "add",
                            "shape": {
                                "id": "M",
                                "kind": "point",
                                "point": {"x": 2.5, "y": 1.5},
                                "label": "M",
                                "tone": "accent",
                            },
                        },
                        {
                            "op": "add",
                            "shape": {
                                "id": "AM",
                                "kind": "polyline",
                                "points": [{"x": 0, "y": 0}, {"x": 2.5, "y": 1.5}],
                                "tone": "primary",
                            },
                        },
                    ]
                },
                {
                    "actions": [
                        {"op": "highlight", "shape_ids": ["M", "AM"], "tone": "accent"},
                        {"op": "focus", "shape_ids": ["A", "M", "AM"], "margin": 0.25},
                        {"op": "caption", "caption": "中点Mと線分AMへ拡大する。"},
                    ]
                },
            ],
        )

        self.assertEqual(len(frames), 2)
        self.assertEqual(len(initial["shapes"]), 4)
        self.assertEqual(len(frames[0]["shapes"]), 6)
        self.assertLess(frames[1]["viewport"]["xMax"], initial["viewport"]["xMax"])
        self.assertEqual(frames[1]["caption"], "中点Mと線分AMへ拡大する。")

    def test_scene_actions_reject_unverified_target_ids(self) -> None:
        scene = plane_scene_diagram(
            title="空の図",
            caption="",
            viewport={"xMin": -1, "xMax": 1, "yMin": -1, "yMax": 1},
            shapes=[],
        )
        with self.assertRaisesRegex(ValueError, "visible shape"):
            apply_plane_scene_actions(
                scene,
                [{"op": "highlight", "shape_ids": ["not-proved"], "tone": "accent"}],
            )

    def test_progressive_calculus_frames_reveal_table_and_plot(self) -> None:
        variation = variation_table_diagram(
            ["(-∞,0)", "0", "(0,∞)"],
            [
                {"label": "f'(x)", "cells": ["-", "0", "+"]},
                {"label": "f(x)", "cells": ["↘", "極小", "↗"]},
            ],
            title="増減表",
            caption="符号を読む。",
        )
        plot = function_plot_diagram(
            [("f", lambda x: x * x, "primary")],
            x_min=-2,
            x_max=2,
            marked_points=[(0, 0, "極小")],
            title="放物線",
            caption="増減と概形を対応させる。",
        )
        calculus = {
            "version": 1,
            "kind": "calculus",
            "title": "微分から概形へ",
            "caption": "",
            "variable": "x",
            "functionTex": "x^2",
            "derivativeTex": "2x",
            "domainTex": "\\mathbb R",
            "variation": variation,
            "plot": plot,
            "certificateMethod": "symbolic derivative",
        }
        frames = progressive_diagram_frames(calculus, 3)

        self.assertEqual(len(frames[0]["variation"]["rows"]), 1)
        self.assertLessEqual(
            len(frames[0]["plot"]["shapes"]),
            len(frames[-1]["plot"]["shapes"]),
        )
        self.assertEqual(frames[-1], calculus)


if __name__ == "__main__":
    unittest.main()
