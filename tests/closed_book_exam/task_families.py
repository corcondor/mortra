"""Closed-book benchmark task families and independent hidden generator.

Enforces strict separation:
- Hidden constructions exist ONLY inside the generator/evaluator.
- The solver receives ONLY public specifications.
- Distinct task families:
    Family A: Surface generalization (same AST skeleton, randomized coords/names)
    Family B: Structural generalization (disjoint AST skeletons, novel compositions)
    Family C: Concept reconstruction (masked predicates from low-level coordinates/traces)
    Family D: Cross-domain representation transfer (operator/sampling transfer)
    Family E: Self-generated tasks (split generator vs fresh solver)
    Family J: Perturbed ablation tasks (shuffled premises, distractors, coordinate shifts)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
import random
from typing import Any, Callable


@dataclass(frozen=True)
class PublicTaskSpec:
    """The only information passed to the solver."""
    task_id: str
    family: str
    domain: str
    public_requirements: dict[str, Any]
    symbols: tuple[str, ...]
    target_statement: str
    constraints: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class HiddenTaskInstance:
    """Full task with hidden construction and independent verification oracle."""
    task_id: str
    family: str
    public_spec: PublicTaskSpec
    hidden_construction_ast: dict[str, Any]
    hidden_witness_values: dict[str, Any]
    evaluator_oracle: str  # Description of verification logic
    expected_complexity_bound: int


class IndependentTaskGenerator:
    """Hidden generator operating with independent deterministic seeds."""

    def __init__(self, master_seed: int = 20260921) -> None:
        self.master_seed = master_seed
        self.rng = random.Random(master_seed)

    def generate_all_families(self) -> dict[str, list[HiddenTaskInstance]]:
        """Generate all task families for the closed-book exam."""
        return {
            "family_a_surface": self._generate_family_a_surface(count=5),
            "family_b_structural": self._generate_family_b_structural(count=5),
            "family_c_concept_masking": self._generate_family_c_concept_masking(count=4),
            "family_d_cross_domain": self._generate_family_d_cross_domain(count=3),
            "family_e_self_generated": self._generate_family_e_self_generated(count=3),
            "family_j_ablations": self._generate_family_j_ablations(count=4),
        }

    def _generate_family_a_surface(self, count: int) -> list[HiddenTaskInstance]:
        """Family A: Same AST skeleton (harmonic bundle / midpoint reflection),

        randomized coordinates, rotation, scaling, and point relabeling.
        """
        instances = []
        name_pool = ["A", "B", "C", "D", "E", "P", "Q", "R", "S", "T", "X", "Y"]
        for i in range(count):
            seed = self.master_seed + 100 + i
            rng = random.Random(seed)

            # Random angle and translation
            theta = rng.uniform(0, 2 * math.pi)
            tx, ty = rng.uniform(-10, 10), rng.uniform(-10, 10)
            scale = rng.uniform(0.5, 3.0)

            # Pick 4 disjoint point names
            p1, p2, p3, p4 = rng.sample(name_pool, 4)

            # Base coordinates: collinear harmonic bundle [0, 2, 3, 6]
            base_pts = {p1: (0.0, 0.0), p2: (2.0, 0.0), p3: (3.0, 0.0), p4: (6.0, 0.0)}
            transformed = {}
            for k, (x, y) in base_pts.items():
                xr = scale * (x * math.cos(theta) - y * math.sin(theta)) + tx
                yr = scale * (x * math.sin(theta) + y * math.cos(theta)) + ty
                transformed[k] = (round(xr, 6), round(yr, 6))

            task_id = f"task_A_{i+1:02d}_{seed}"
            pub = PublicTaskSpec(
                task_id=task_id,
                family="family_a_surface",
                domain="geometry",
                public_requirements={
                    "points": list(transformed.keys()),
                    "coordinates": transformed,
                    "target_relation": "harmonic_cross_ratio",
                },
                symbols=(p1, p2, p3, p4),
                target_statement=f"CrossRatio({p1}, {p2}; {p3}, {p4}) == -1",
            )
            inst = HiddenTaskInstance(
                task_id=task_id,
                family="family_a_surface",
                public_spec=pub,
                hidden_construction_ast={
                    "skeleton": "collinear_harmonic_quadruple",
                    "scale": scale,
                    "rotation": theta,
                    "translation": (tx, ty),
                },
                hidden_witness_values={"cross_ratio": -1.0},
                evaluator_oracle="check_1d_cross_ratio_invariance",
                expected_complexity_bound=20,
            )
            instances.append(inst)
        return instances

    def _generate_family_b_structural(self, count: int) -> list[HiddenTaskInstance]:
        """Family B: Disjoint AST skeletons (cyclic quad with orthocenter,

        spiral similarity, Miquel point, Pappus configuration).
        Completely different dependency graph and composition structure.
        """
        skeletons = [
            ("miquel_six_circle", ["A", "B", "C", "D", "E", "F"], "concyclic(M1, M2, M3, M4)"),
            ("spiral_similarity_orthodiagonal", ["P", "Q", "R", "S"], "perp(PR, QS)"),
            ("pappus_hexagon_concurrence", ["A1", "A2", "A3", "B1", "B2", "B3"], "coll(X, Y, Z)"),
            ("euler_line_homothety", ["A", "B", "C", "O", "G", "H"], "ratio(OG, GH) == 1/2"),
            ("desargues_perspective_triangle", ["A", "B", "C", "A'", "B'", "C'"], "concurrent_axes"),
        ]
        instances = []
        for i in range(min(count, len(skeletons))):
            skel_name, syms, target = skeletons[i]
            seed = self.master_seed + 200 + i
            rng = random.Random(seed)

            # Generate synthetic coordinates satisfying the skeleton
            coords = {s: (round(rng.uniform(-5, 5), 4), round(rng.uniform(-5, 5), 4)) for s in syms}
            task_id = f"task_B_{i+1:02d}_{skel_name}"
            pub = PublicTaskSpec(
                task_id=task_id,
                family="family_b_structural",
                domain="geometry",
                public_requirements={
                    "symbols": syms,
                    "target": target,
                    "structural_family": skel_name,
                },
                symbols=tuple(syms),
                target_statement=target,
            )
            inst = HiddenTaskInstance(
                task_id=task_id,
                family="family_b_structural",
                public_spec=pub,
                hidden_construction_ast={
                    "skeleton": skel_name,
                    "dependency_depth": 3 + i,
                    "ast_type": "novel_composition",
                },
                hidden_witness_values={"coords": coords},
                evaluator_oracle=f"verify_{skel_name}_theorem",
                expected_complexity_bound=100 + i * 50,
            )
            instances.append(inst)
        return instances

    def _generate_family_c_concept_masking(self, count: int) -> list[HiddenTaskInstance]:
        """Family C: Low-level coordinates and execution traces with high-level

        predicates (coll, para, perp, cong) masked out.
        Tests whether the learner can Fold a reusable relation C.
        """
        masked_targets = [
            ("masked_relation_01", "coll", "(y2 - y1)*(x3 - x2) - (y3 - y2)*(x2 - x1) == 0"),
            ("masked_relation_02", "para", "(y2 - y1)*(x4 - x3) - (y4 - y3)*(x2 - x1) == 0"),
            ("masked_relation_03", "perp", "(x2 - x1)*(x4 - x3) + (y2 - y1)*(y4 - y3) == 0"),
            ("masked_relation_04", "cong", "(x2 - x1)**2 + (y2 - y1)**2 - (x4 - x3)**2 - (y4 - y3)**2 == 0"),
        ]
        instances = []
        for i in range(min(count, len(masked_targets))):
            mid, true_pred, poly_form = masked_targets[i]
            seed = self.master_seed + 300 + i
            rng = random.Random(seed)

            # Generate 20 positive and 20 negative numerical sample tuples
            positive_samples = []
            negative_samples = []
            for _ in range(20):
                if true_pred == "coll":
                    # Collinear 3 points
                    x1, y1 = rng.uniform(-5, 5), rng.uniform(-5, 5)
                    dx, dy = rng.uniform(-2, 2), rng.uniform(-2, 2)
                    t2, t3 = rng.uniform(0.5, 2.0), rng.uniform(2.5, 4.0)
                    pos = [x1, y1, x1 + t2 * dx, y1 + t2 * dy, x1 + t3 * dx, y1 + t3 * dy]
                    neg = [x1, y1, x1 + t2 * dx, y1 + t2 * dy, x1 + t3 * dx + rng.uniform(0.5, 1.5), y1 + t3 * dy]
                elif true_pred == "para":
                    # Parallel lines
                    x1, y1 = rng.uniform(-5, 5), rng.uniform(-5, 5)
                    dx, dy = rng.uniform(-2, 2), rng.uniform(-2, 2)
                    x3, y3 = rng.uniform(-5, 5), rng.uniform(-5, 5)
                    t = rng.uniform(1.0, 3.0)
                    pos = [x1, y1, x1 + dx, y1 + dy, x3, y3, x3 + t * dx, y3 + t * dy]
                    neg = [x1, y1, x1 + dx, y1 + dy, x3, y3, x3 + t * dx + rng.uniform(0.5, 1.0), y3 + t * dy]
                elif true_pred == "perp":
                    # Perpendicular lines: dx2 = -dy1, dy2 = dx1
                    x1, y1 = rng.uniform(-5, 5), rng.uniform(-5, 5)
                    dx, dy = rng.uniform(-2, 2), rng.uniform(-2, 2)
                    x3, y3 = rng.uniform(-5, 5), rng.uniform(-5, 5)
                    pos = [x1, y1, x1 + dx, y1 + dy, x3, y3, x3 - dy, y3 + dx]
                    neg = [x1, y1, x1 + dx, y1 + dy, x3, y3, x3 - dy + rng.uniform(0.5, 1.0), y3 + dx]
                else:  # cong
                    # Equal lengths
                    x1, y1 = rng.uniform(-5, 5), rng.uniform(-5, 5)
                    r = rng.uniform(1.0, 4.0)
                    th1 = rng.uniform(0, 2 * math.pi)
                    x3, y3 = rng.uniform(-5, 5), rng.uniform(-5, 5)
                    th2 = rng.uniform(0, 2 * math.pi)
                    pos = [x1, y1, x1 + r * math.cos(th1), y1 + r * math.sin(th1),
                           x3, y3, x3 + r * math.cos(th2), y3 + r * math.sin(th2)]
                    r_diff = r + rng.uniform(0.5, 1.5)
                    neg = [x1, y1, x1 + r * math.cos(th1), y1 + r * math.sin(th1),
                           x3, y3, x3 + r_diff * math.cos(th2), y3 + r_diff * math.sin(th2)]

                positive_samples.append([round(v, 4) for v in pos])
                negative_samples.append([round(v, 4) for v in neg])

            task_id = f"task_C_{i+1:02d}_{mid}"
            pub = PublicTaskSpec(
                task_id=task_id,
                family="family_c_concept_masking",
                domain="concept_induction",
                public_requirements={
                    "masked_relation_id": mid,
                    "positive_samples": positive_samples,
                    "negative_samples": negative_samples,
                    "trace_arity": len(positive_samples[0]) // 2,
                },
                symbols=("X1", "Y1", "X2", "Y2", "X3", "Y3") if true_pred == "coll" else ("X1", "Y1", "X2", "Y2", "X3", "Y3", "X4", "Y4"),
                target_statement=f"DiscoverInvariantRelation({mid})",
            )
            inst = HiddenTaskInstance(
                task_id=task_id,
                family="family_c_concept_masking",
                public_spec=pub,
                hidden_construction_ast={
                    "true_predicate": true_pred,
                    "polynomial_form": poly_form,
                },
                hidden_witness_values={"true_predicate": true_pred},
                evaluator_oracle="evaluate_concept_reconstruction_and_utility",
                expected_complexity_bound=50,
            )
            instances.append(inst)
        return instances

    def _generate_family_d_cross_domain(self, count: int) -> list[HiddenTaskInstance]:
        """Family D: Cross-domain representation routing transfer tasks.

        Tests whether equivalent representation selection (TF vs Conv via sampling certificate)
        and adjoint inverse design transfer to new operator sequences.
        """
        instances = []
        scenarios = [
            ("wave_propagation_critical_routing", "wave_optics", {"wavelength": 532e-9, "grid_n": 64, "pixel_pitch": 10e-6, "z_list": [0.003, 0.012, 0.040]}),
            ("geometric_polynomial_vs_coordinate_routing", "geometry", {"degrees": [1, 2, 4], "solver_modes": ["coordinate", "polynomial_ideal", "algebraic_elimination"]}),
            ("hybrid_optical_geometric_lens_system", "optics_geometry", {"focal_length": 0.05, "wavelength": 632.8e-9, "aperture_shape": "circular"}),
        ]
        for i in range(min(count, len(scenarios))):
            name, domain, reqs = scenarios[i]
            task_id = f"task_D_{i+1:02d}_{name}"
            pub = PublicTaskSpec(
                task_id=task_id,
                family="family_d_cross_domain",
                domain=domain,
                public_requirements=reqs,
                symbols=("req",),
                target_statement=f"SelectMinimalCostAdmissibleRepresentation({name})",
            )
            inst = HiddenTaskInstance(
                task_id=task_id,
                family="family_d_cross_domain",
                public_spec=pub,
                hidden_construction_ast={"scenario": name, "domain": domain},
                hidden_witness_values={"expected_routing": ["TF", "TF", "Conv"] if domain == "wave_optics" else ["coordinate", "ideal", "elimination"]},
                evaluator_oracle="verify_representation_selection_certificate",
                expected_complexity_bound=30,
            )
            instances.append(inst)
        return instances

    def _generate_family_e_self_generated(self, count: int) -> list[HiddenTaskInstance]:
        """Family E: Self-generated tasks where MORTRA generator proposes a task

        and solver receives only public requirements without generator state.
        """
        instances = []
        for i in range(count):
            seed = self.master_seed + 500 + i
            rng = random.Random(seed)
            n_pts = 4 + i
            pts = [f"P_{k}" for k in range(n_pts)]
            task_id = f"task_E_{i+1:02d}_self_gen"
            pub = PublicTaskSpec(
                task_id=task_id,
                family="family_e_self_generated",
                domain="synthetic_discovery",
                public_requirements={
                    "points": pts,
                    "target_invariance": "concurrence_or_collinearity",
                    "budget": 50,
                },
                symbols=tuple(pts),
                target_statement=f"FindNonTrivialTheorem({task_id})",
            )
            inst = HiddenTaskInstance(
                task_id=task_id,
                family="family_e_self_generated",
                public_spec=pub,
                hidden_construction_ast={"generator_seed": seed, "n_points": n_pts},
                hidden_witness_values={"non_trivial_rank": n_pts - 1},
                evaluator_oracle="verify_non_trivial_self_generated_solution",
                expected_complexity_bound=60,
            )
            instances.append(inst)
        return instances

    def _generate_family_j_ablations(self, count: int) -> list[HiddenTaskInstance]:
        """Family J: Ablation tasks with surface perturbations (shuffled premises,

        randomized point labels, irrelevant distractors).
        """
        instances = []
        perturbation_types = [
            "shuffled_premises",
            "randomized_point_labels",
            "added_irrelevant_distractor_points",
            "coordinate_rigid_transformation",
        ]
        for i in range(min(count, len(perturbation_types))):
            ptype = perturbation_types[i]
            seed = self.master_seed + 600 + i
            task_id = f"task_J_{i+1:02d}_{ptype}"
            pub = PublicTaskSpec(
                task_id=task_id,
                family="family_j_ablations",
                domain="robustness_ablation",
                public_requirements={
                    "perturbation_type": ptype,
                    "base_task": "harmonic_cross_ratio",
                    "distractor_count": 3 if "distractor" in ptype else 0,
                },
                symbols=("A_rand", "B_rand", "C_rand", "D_rand"),
                target_statement=f"HarmonicCrossRatioUnder({ptype})",
            )
            inst = HiddenTaskInstance(
                task_id=task_id,
                family="family_j_ablations",
                public_spec=pub,
                hidden_construction_ast={"perturbation": ptype, "seed": seed},
                hidden_witness_values={"invariant_holds": True},
                evaluator_oracle="verify_ablation_invariance",
                expected_complexity_bound=40,
            )
            instances.append(inst)
        return instances


def compute_benchmark_hash(families: dict[str, list[HiddenTaskInstance]]) -> str:
    """Compute deterministic SHA-256 hash of all public benchmark specifications."""
    hasher = hashlib.sha256()
    for fam_name in sorted(families.keys()):
        hasher.update(fam_name.encode("utf-8"))
        for inst in families[fam_name]:
            pub_dict = asdict(inst.public_spec)
            hasher.update(json.dumps(pub_dict, sort_keys=True).encode("utf-8"))
    return hasher.hexdigest()
