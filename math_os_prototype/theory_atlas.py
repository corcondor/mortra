"""Theory atlas and lift certificates for MathOS generalization.

The atlas is not a list of problem templates.  It defines when two different
surface problems count as the same mathematical structure:

    same theory path + same typed morphism chain + same constraint skeleton
    + same query codomain

Numeric constants and local variable names are parameters.  If they change but
the certificate signature is unchanged, the solver is allowed to reuse the same
backend path without treating the problem as memorized.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class TheoryNode:
    name: str
    depends_on: list[str] = field(default_factory=list)
    backend_contract: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MorphismSchema:
    name: str
    theory: str
    domain: list[str]
    codomain: str
    law: str
    backend: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LiftCertificate:
    family_id: str
    theory_path: list[str]
    structure_signature: str
    morphism_chain: list[str]
    constraint_skeleton: list[str]
    query_signature: str
    backend_contract: str
    admissible: bool
    reason: str
    source: str = "theory_atlas"

    def canonical_signature(self) -> str:
        chain = "∘".join(self.morphism_chain)
        constraints = ";".join(sorted(self.constraint_skeleton))
        return "|".join(
            [
                self.family_id,
                ">".join(self.theory_path),
                self.structure_signature,
                chain,
                constraints,
                self.query_signature,
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["canonical_signature"] = self.canonical_signature()
        return data


HIGH_SCHOOL_THEORY_ATLAS: dict[str, TheoryNode] = {
    "Logic": TheoryNode("Logic", backend_contract="well-formed formulas and typed queries"),
    "Set": TheoryNode("Set", depends_on=["Logic"], backend_contract="objects, functions, relations"),
    "AlgebraicStructure": TheoryNode("AlgebraicStructure", depends_on=["Set"]),
    "OrderedField": TheoryNode(
        "OrderedField",
        depends_on=["AlgebraicStructure"],
        backend_contract="linear/quadratic algebra, inequalities, ordered reasoning",
    ),
    "RealClosedField": TheoryNode(
        "RealClosedField",
        depends_on=["OrderedField"],
        backend_contract="polynomial equations, inequalities, quantifier elimination",
    ),
    "VectorSpace": TheoryNode(
        "VectorSpace",
        depends_on=["OrderedField"],
        backend_contract="linear combinations, affine coordinates",
    ),
    "InnerProductSpace": TheoryNode(
        "InnerProductSpace",
        depends_on=["VectorSpace"],
        backend_contract="norm, distance, angle, projection",
    ),
    "EuclideanGeometry": TheoryNode(
        "EuclideanGeometry",
        depends_on=["InnerProductSpace", "GroupAction"],
        backend_contract="incidence, congruence, loci, area",
    ),
    "PolynomialRing": TheoryNode(
        "PolynomialRing",
        depends_on=["AlgebraicStructure"],
        backend_contract="factor, resultant, degree, roots",
    ),
    "QuotientRing": TheoryNode(
        "QuotientRing",
        depends_on=["PolynomialRing"],
        backend_contract="modular arithmetic and residue classes",
    ),
    "ElementaryNumberTheory": TheoryNode(
        "ElementaryNumberTheory",
        depends_on=["QuotientRing"],
        backend_contract="prime predicates, congruence sieves, and certified bounded search",
    ),
    "GroupAction": TheoryNode(
        "GroupAction",
        depends_on=["AlgebraicStructure"],
        backend_contract="symmetry, orbits, invariant reduction",
    ),
    "DiscreteDynamicalSystem": TheoryNode(
        "DiscreteDynamicalSystem",
        depends_on=["Set", "AlgebraicStructure"],
        backend_contract="recurrence and indexed observations",
    ),
    "Probability": TheoryNode(
        "Probability",
        depends_on=["Set", "OrderedField"],
        backend_contract="finite probability algebra and event operations",
    ),
    "Combinatorics": TheoryNode(
        "Combinatorics",
        depends_on=["Set", "AlgebraicStructure"],
        backend_contract="finite counting, binomial coefficients, selections",
    ),
    "ElementaryFunctions": TheoryNode(
        "ElementaryFunctions",
        depends_on=["OrderedField", "GroupAction"],
        backend_contract="logarithms, exponentials, trigonometric identities",
    ),
    "Calculus": TheoryNode(
        "Calculus",
        depends_on=["RealClosedField", "ElementaryFunctions"],
        backend_contract="polynomial differentiation and integration contracts",
    ),
    "RealAnalysis": TheoryNode(
        "RealAnalysis",
        depends_on=["RealClosedField", "ElementaryFunctions"],
        backend_contract="limits, convergence obligations, and asymptotic comparison",
    ),
    "MeasureTheory": TheoryNode(
        "MeasureTheory",
        depends_on=["Set", "OrderedField"],
        backend_contract="area, volume, and expectation as typed measure observations",
    ),
    "Optimization": TheoryNode(
        "Optimization",
        depends_on=["OrderedField", "RealClosedField"],
        backend_contract="extremum witnesses with interior and boundary verification",
    ),
}


MORPHISM_SCHEMAS: dict[str, MorphismSchema] = {
    "ArithmeticProgression": MorphismSchema(
        "ArithmeticProgression",
        theory="DiscreteDynamicalSystem",
        domain=["Sequence"],
        codomain="Prop",
        law="a(n+1)-a(n)=d",
        backend=["affine recurrence solver", "linear equation solver"],
    ),
    "CommonDifference": MorphismSchema(
        "CommonDifference",
        theory="DiscreteDynamicalSystem",
        domain=["Sequence"],
        codomain="Real",
        law="d=a(n+1)-a(n)",
        backend=["linear arithmetic"],
    ),
    "NthTerm": MorphismSchema(
        "NthTerm",
        theory="DiscreteDynamicalSystem",
        domain=["Sequence", "Index"],
        codomain="Real",
        law="a_n=a_1+(n-1)d",
        backend=["affine recurrence solver"],
    ),
    "Distance": MorphismSchema(
        "Distance",
        theory="InnerProductSpace",
        domain=["Point2", "Point2"],
        codomain="Real",
        law="distance(P,Q)=norm(P-Q)",
        backend=["linear algebra", "radical simplifier"],
    ),
    "Midpoint": MorphismSchema(
        "Midpoint",
        theory="VectorSpace",
        domain=["Point2", "Point2"],
        codomain="Point2",
        law="midpoint(P,Q)=(P+Q)/2",
        backend=["affine coordinate algebra"],
    ),
    "CoordinateSum": MorphismSchema(
        "CoordinateSum",
        theory="VectorSpace",
        domain=["Point2"],
        codomain="Real",
        law="CoordinateSum((x,y))=x+y",
        backend=["linear arithmetic"],
    ),
    "ModResidue": MorphismSchema(
        "ModResidue",
        theory="QuotientRing",
        domain=["Integer", "Modulus"],
        codomain="Integer",
        law="a=q*m+r, 0<=r<m",
        backend=["modular arithmetic"],
    ),
    "PowerMod": MorphismSchema(
        "PowerMod",
        theory="QuotientRing",
        domain=["Integer", "Natural", "Modulus"],
        codomain="Integer",
        law="PowerMod(a,n,m)=a^n mod m",
        backend=["modular exponentiation"],
    ),
    "SelfPower": MorphismSchema(
        "SelfPower",
        theory="ElementaryNumberTheory",
        domain=["Integer"],
        codomain="Integer",
        law="SelfPower(x)=x^x",
        backend=["exact integer exponentiation", "modular exponentiation"],
    ),
    "SymmetricPrimePair": MorphismSchema(
        "SymmetricPrimePair",
        theory="ElementaryNumberTheory",
        domain=["Integer", "Integer"],
        codomain="Prop",
        law="Prime(x+d) and Prime(x-d); d->-d exchanges targets",
        backend=["congruence sieve", "primality checker"],
    ),
    "CongruenceSieve": MorphismSchema(
        "CongruenceSieve",
        theory="QuotientRing",
        domain=["Integer", "Modulus"],
        codomain="Bool",
        law="n=0 mod p and 1<p<n certifies that n is composite",
        backend=["modular exponentiation", "small-prime divisor certificate"],
    ),
    "BaseExpansion": MorphismSchema(
        "BaseExpansion",
        theory="PolynomialRing",
        domain=["DigitString", "Base"],
        codomain="Integer",
        law="digits in base b are a polynomial in b",
        backend=["polynomial equation solver", "integer constraints"],
    ),
    "PercentOf": MorphismSchema(
        "PercentOf",
        theory="OrderedField",
        domain=["Real", "Percent"],
        codomain="Real",
        law="PercentOf(x,p)=x*p/100",
        backend=["linear arithmetic"],
    ),
    "ClockAngle": MorphismSchema(
        "ClockAngle",
        theory="GroupAction",
        domain=["TimeOfDay"],
        codomain="Angle",
        law="clock hands are rotations on S^1",
        backend=["modular affine arithmetic"],
    ),
    "ComplementEvent": MorphismSchema(
        "ComplementEvent",
        theory="Probability",
        domain=["Event"],
        codomain="Event",
        law="P(A^c)=1-P(A)",
        backend=["probability algebra"],
    ),
    "AbsoluteValue": MorphismSchema(
        "AbsoluteValue",
        theory="OrderedField",
        domain=["Real"],
        codomain="Real",
        law="|u|=|v| iff u=v or u=-v",
        backend=["piecewise linear equation solver"],
    ),
    "QuadraticPolynomial": MorphismSchema(
        "QuadraticPolynomial",
        theory="RealClosedField",
        domain=["Real"],
        codomain="Real",
        law="quadratic inequalities reduce to root order over real closed fields",
        backend=["polynomial root solver", "ordered field interval solver"],
    ),
    "CompoundGrowth": MorphismSchema(
        "CompoundGrowth",
        theory="OrderedField",
        domain=["Real", "Percent", "Natural"],
        codomain="Real",
        law="final=principal*(1+r/100)^n",
        backend=["one-variable exponential inverse for generated integer-rate cases"],
    ),
    "StateObservation": MorphismSchema(
        "StateObservation",
        theory="DiscreteDynamicalSystem",
        domain=["State"],
        codomain="Real",
        law="observed quantity of an owner/object state at a time",
        backend=["additive state solver"],
    ),
    "AdditiveStateTransition": MorphismSchema(
        "AdditiveStateTransition",
        theory="DiscreteDynamicalSystem",
        domain=["State", "Event"],
        codomain="State",
        law="state_{t+1}=state_t+delta(event)",
        backend=["additive state solver"],
    ),
    "QuadraticEquation": MorphismSchema(
        "QuadraticEquation",
        theory="RealClosedField",
        domain=["Real"],
        codomain="Prop",
        law="a*x^2+b*x+c=0",
        backend=["quadratic formula", "Vieta relations"],
    ),
    "RootObservable": MorphismSchema(
        "RootObservable",
        theory="RealClosedField",
        domain=["Polynomial"],
        codomain="Real",
        law="sum/product of roots are symmetric polynomial invariants",
        backend=["Vieta relations"],
    ),
    "PolynomialRemainder": MorphismSchema(
        "PolynomialRemainder",
        theory="PolynomialRing",
        domain=["Polynomial", "Polynomial"],
        codomain="Polynomial",
        law="remainder of f(x) by x-a is f(a)",
        backend=["polynomial evaluation"],
    ),
    "RepeatedLinearRemainder": MorphismSchema(
        "RepeatedLinearRemainder",
        theory="PolynomialRing",
        domain=["Polynomial", "Polynomial"],
        codomain="Polynomial",
        law="remainder of f(x) by (x-a)^2 is f(a)+f'(a)(x-a)",
        backend=["Taylor jet", "polynomial remainder"],
    ),
    "LinearSystem2": MorphismSchema(
        "LinearSystem2",
        theory="VectorSpace",
        domain=["Real", "Real"],
        codomain="Prop",
        law="2x2 linear system A*v=b",
        backend=["linear algebra"],
    ),
    "Logarithm": MorphismSchema(
        "Logarithm",
        theory="ElementaryFunctions",
        domain=["Real", "Real"],
        codomain="Real",
        law="log_b(x)=y iff x=b^y",
        backend=["exact integer power inverse"],
    ),
    "ExponentialPower": MorphismSchema(
        "ExponentialPower",
        theory="ElementaryFunctions",
        domain=["Real", "Real"],
        codomain="Real",
        law="b^x=y iff x=log_b(y)",
        backend=["exact integer exponent search"],
    ),
    "TrigPythagorean": MorphismSchema(
        "TrigPythagorean",
        theory="ElementaryFunctions",
        domain=["Angle"],
        codomain="Prop",
        law="sin^2(theta)+cos^2(theta)=1",
        backend=["trigonometric identity algebra"],
    ),
    "BinomialCoefficient": MorphismSchema(
        "BinomialCoefficient",
        theory="Combinatorics",
        domain=["Natural", "Natural"],
        codomain="Natural",
        law="C(n,k)=n!/(k!(n-k)!)",
        backend=["finite counting"],
    ),
    "BinomialProbability": MorphismSchema(
        "BinomialProbability",
        theory="Probability",
        domain=["Natural", "Natural", "Probability"],
        codomain="Probability",
        law="P(X=k)=C(n,k)p^k(1-p)^(n-k)",
        backend=["finite probability algebra"],
    ),
    "DotProduct": MorphismSchema(
        "DotProduct",
        theory="InnerProductSpace",
        domain=["Vector2", "Vector2"],
        codomain="Real",
        law="<u,v>=u1*v1+u2*v2",
        backend=["linear algebra"],
    ),
    "LineIntersection": MorphismSchema(
        "LineIntersection",
        theory="EuclideanGeometry",
        domain=["Line2", "Line2"],
        codomain="Point2",
        law="intersection solves two affine line equations",
        backend=["linear algebra"],
    ),
    "CircleRadius": MorphismSchema(
        "CircleRadius",
        theory="EuclideanGeometry",
        domain=["Point2", "Point2"],
        codomain="Real",
        law="radius is distance from center to point on circle",
        backend=["linear algebra", "radical simplifier"],
    ),
    "Derivative": MorphismSchema(
        "Derivative",
        theory="Calculus",
        domain=["Function"],
        codomain="Function",
        law="D(a*x^2+b*x+c)=2*a*x+b",
        backend=["symbolic differentiation"],
    ),
    "DefiniteIntegral": MorphismSchema(
        "DefiniteIntegral",
        theory="Calculus",
        domain=["Function", "Interval"],
        codomain="Real",
        law="integral_0^r (a*x^2+b*x+c) dx",
        backend=["symbolic integration"],
    ),
}


def build_lift_certificates(
    source_text: str,
    sorts: Iterable[Any],
    objects: Iterable[Any],
    morphisms: Iterable[Any],
    constraints: Iterable[Any],
    queries: Iterable[Any],
) -> list[LiftCertificate]:
    morphism_names = {str(getattr(item, "name", "")) for item in morphisms}
    constraints_list = list(constraints)
    queries_list = list(queries)
    certificates: list[LiftCertificate] = []

    if {"ArithmeticProgression", "CommonDifference", "NthTerm"}.issubset(morphism_names):
        certificates.append(
            make_certificate(
                family_id="discrete_affine_sequence.nth_term",
                theory_path=["Logic", "Set", "AlgebraicStructure", "DiscreteDynamicalSystem", "OrderedField"],
                structure_signature="Sequence with constant translation action on an ordered-field value sort",
                morphism_chain=["ArithmeticProgression", "CommonDifference", "NthTerm"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="solve affine recurrence observation a_n = a_1 + (n-1)d; constants are parameters",
                required_query_prefix="NthTerm",
            )
        )

    if "Distance" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="inner_product_geometry.distance",
                theory_path=["Logic", "Set", "OrderedField", "VectorSpace", "InnerProductSpace"],
                structure_signature="Point objects embedded in an inner-product space with metric induced by norm",
                morphism_chain=["Difference", "Norm", "Distance"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="reduce distance query to norm of coordinate difference",
                required_query_prefix="Distance",
            )
        )

    if {"Midpoint", "CoordinateSum"}.issubset(morphism_names):
        certificates.append(
            make_certificate(
                family_id="affine_geometry.midpoint_observable",
                theory_path=["Logic", "Set", "OrderedField", "VectorSpace"],
                structure_signature="Affine point pair with barycentric constructor and linear observable",
                morphism_chain=["Midpoint", "CoordinateSum"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="compose affine constructor with linear observable",
                required_query_prefix="CoordinateSum",
            )
        )

    if "PowerMod" in morphism_names or "ModResidue" in morphism_names:
        chain = ["Power", "ModResidue"] if "PowerMod" in morphism_names else ["ModResidue"]
        certificates.append(
            make_certificate(
                family_id="quotient_ring.residue",
                theory_path=["Logic", "Set", "AlgebraicStructure", "PolynomialRing", "QuotientRing"],
                structure_signature="Integer expression projected to residue class modulo a positive modulus",
                morphism_chain=chain,
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="evaluate expression in Z/mZ; constants are parameters",
                required_query_prefix="ModResidue" if chain == ["ModResidue"] else "PowerMod",
            )
        )

    if {"SelfPower", "SymmetricPrimePair", "CongruenceSieve"}.issubset(morphism_names):
        certificates.append(
            make_certificate(
                family_id="elementary_number_theory.prime_power_symmetric_primality",
                theory_path=[
                    "Logic",
                    "Set",
                    "AlgebraicStructure",
                    "PolynomialRing",
                    "QuotientRing",
                    "ElementaryNumberTheory",
                    "GroupAction",
                ],
                structure_signature="Prime self-powers forming an S2-symmetric pair x+d and x-d",
                morphism_chain=["SelfPower", "SymmetricPrimePair", "CongruenceSieve"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="apply conditions C1-C5, quotient by offset swap, sieve modulo primes, then test survivors",
                required_query_prefix="Existence(SymmetricPrimePair)",
            )
        )

    if "BaseExpansion" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="polynomial_notation.base_expansion",
                theory_path=["Logic", "Set", "AlgebraicStructure", "PolynomialRing"],
                structure_signature="Digit strings interpreted by a polynomial evaluation morphism in an unknown base",
                morphism_chain=["BaseExpansion", "Equality", "IntegerConstraint"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="expand digit strings into a polynomial equation plus base lower-bound constraints",
                required_query_prefix="base",
            )
        )

    if "PercentOf" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="ordered_field.scalar_percent_action",
                theory_path=["Logic", "Set", "AlgebraicStructure", "OrderedField"],
                structure_signature="Percent as scalar action on ordered-field quantities",
                morphism_chain=["PercentOf", "AdditiveState"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="solve one-hole affine equation over ordered quantities",
                required_query_prefix="tip_percent",
            )
        )

    if "ClockAngle" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="circle_group.clock_angle",
                theory_path=["Logic", "Set", "AlgebraicStructure", "GroupAction"],
                structure_signature="Clock hands as affine rotations on the circle group R/360Z",
                morphism_chain=["ClockAngle", "MinimalRepresentative"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="evaluate angular difference modulo 360 and choose minimal representative",
                required_query_prefix="ClockAngle",
            )
        )

    if {"ProbabilityMeasure", "ComplementEvent"}.issubset(morphism_names):
        certificates.append(
            make_certificate(
                family_id="probability.complement_event",
                theory_path=["Logic", "Set", "Probability"],
                structure_signature="Event in a probability space with complement operation",
                morphism_chain=["ComplementEvent", "ProbabilityMeasure"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="compute P(A^c)=1-P(A)",
                required_query_prefix="Complement",
            )
        )

    if {"LinearForm", "AbsoluteValue"}.issubset(morphism_names):
        certificates.append(
            make_certificate(
                family_id="ordered_field.absolute_value_equation",
                theory_path=["Logic", "Set", "AlgebraicStructure", "OrderedField"],
                structure_signature="Absolute values of affine real forms with one unknown",
                morphism_chain=["LinearForm", "AbsoluteValue", "CaseSplit"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="split |u|=|v| into u=v or u=-v and select requested solution",
                required_query_prefix="min_solution",
            )
        )

    if {"QuadraticPolynomial", "PolynomialInequality"}.issubset(morphism_names):
        certificates.append(
            make_certificate(
                family_id="real_closed_field.quadratic_interval",
                theory_path=["Logic", "Set", "AlgebraicStructure", "OrderedField", "RealClosedField"],
                structure_signature="Monic quadratic inequality over the reals",
                morphism_chain=["QuadraticPolynomial", "PolynomialInequality", "RootBoundary"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="solve monic quadratic inequality by real root boundary",
                required_query_prefix="solution_interval",
            )
        )

    if "CompoundGrowth" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="ordered_field.compound_growth_rate",
                theory_path=["Logic", "Set", "AlgebraicStructure", "OrderedField"],
                structure_signature="Finite repeated multiplicative scalar action with unknown percent rate",
                morphism_chain=["CompoundGrowth", "PercentRate"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="solve final=principal*(1+r/100)^n for generated integer percent rates",
                required_query_prefix="rate_percent",
            )
        )

    if {"StateObservation", "AdditiveStateTransition"}.issubset(morphism_names):
        certificates.append(
            make_certificate(
                family_id="state_event.additive_quantity",
                theory_path=["Logic", "Set", "AlgebraicStructure", "DiscreteDynamicalSystem", "OrderedField"],
                structure_signature="Typed owner/object quantity state with additive event transitions",
                morphism_chain=["StateObservation", "AdditiveStateTransition", "StateQuery"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="sum initial state and signed event deltas for one owner/object query",
                required_query_prefix="StateQuery",
            )
        )

    if {"QuadraticEquation", "RootObservable"}.issubset(morphism_names):
        certificates.append(
            make_certificate(
                family_id="real_closed_field.quadratic_root_observable",
                theory_path=["Logic", "Set", "AlgebraicStructure", "OrderedField", "RealClosedField"],
                structure_signature="Quadratic equation with symmetric root observable",
                morphism_chain=["QuadraticEquation", "RootObservable"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="use Vieta/root solving to compute requested symmetric root observable",
                required_query_prefix="RootObservable",
            )
        )

    if "PolynomialRemainder" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="polynomial_ring.remainder_linear_divisor",
                theory_path=["Logic", "Set", "AlgebraicStructure", "PolynomialRing"],
                structure_signature="Polynomial remainder under quotient by a linear polynomial",
                morphism_chain=["PolynomialRemainder", "EvaluationAtRoot"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="evaluate f(a) for divisor x-a",
                required_query_prefix="PolynomialRemainder",
            )
        )

    if "RepeatedLinearRemainder" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="polynomial_ring.remainder_repeated_linear_divisor",
                theory_path=["Logic", "Set", "AlgebraicStructure", "PolynomialRing"],
                structure_signature="Polynomial remainder modulo a repeated linear factor",
                morphism_chain=["RepeatedLinearRemainder", "TaylorJet"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="compute first-order Taylor jet f(a)+f'(a)(x-a) for divisor (x-a)^2",
                required_query_prefix="RepeatedLinearRemainder",
            )
        )

    if "LinearSystem2" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="vector_space.linear_system_2x2",
                theory_path=["Logic", "Set", "AlgebraicStructure", "OrderedField", "VectorSpace"],
                structure_signature="Two affine linear constraints on two real unknowns",
                morphism_chain=["LinearSystem2", "CoordinateProjection"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="solve 2x2 linear system and observe requested coordinate expression",
                required_query_prefix="LinearSystem2",
            )
        )

    if "Logarithm" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="elementary_functions.log_equation",
                theory_path=["Logic", "Set", "AlgebraicStructure", "OrderedField", "ElementaryFunctions"],
                structure_signature="Logarithm equation reduced through inverse exponential",
                morphism_chain=["Logarithm", "InverseExponential"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="solve log_b(x)=k by x=b^k for exact integer cases",
                required_query_prefix="log_unknown",
            )
        )

    if "ExponentialPower" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="elementary_functions.exponential_equation",
                theory_path=["Logic", "Set", "AlgebraicStructure", "OrderedField", "ElementaryFunctions"],
                structure_signature="Exponential equation with exact integer exponent",
                morphism_chain=["ExponentialPower", "Logarithm"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="solve b^x=N by exact integer exponent search",
                required_query_prefix="exponent_unknown",
            )
        )

    if "TrigPythagorean" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="elementary_functions.trig_pythagorean",
                theory_path=["Logic", "Set", "AlgebraicStructure", "OrderedField", "ElementaryFunctions"],
                structure_signature="Point on unit circle with Pythagorean trigonometric invariant",
                morphism_chain=["TrigPythagorean", "ComplementSquare"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="compute cos^2(theta)=1-sin^2(theta) for acute-angle generated cases",
                required_query_prefix="cos_square",
            )
        )

    if "BinomialCoefficient" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="combinatorics.binomial_coefficient",
                theory_path=["Logic", "Set", "AlgebraicStructure", "Combinatorics"],
                structure_signature="Finite subset selection counted by binomial coefficient",
                morphism_chain=["BinomialCoefficient"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="compute C(n,k)",
                required_query_prefix="BinomialCoefficient",
            )
        )

    if "BinomialProbability" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="probability.binomial_exact",
                theory_path=["Logic", "Set", "Probability", "Combinatorics"],
                structure_signature="Independent Bernoulli trials with exact-success event",
                morphism_chain=["BinomialCoefficient", "BinomialProbability"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="compute C(n,k)p^k(1-p)^(n-k)",
                required_query_prefix="BinomialProbability",
            )
        )

    if "DotProduct" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="inner_product_geometry.dot_product",
                theory_path=["Logic", "Set", "OrderedField", "VectorSpace", "InnerProductSpace"],
                structure_signature="Two vectors in an inner-product coordinate chart",
                morphism_chain=["DotProduct"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="compute coordinate dot product",
                required_query_prefix="DotProduct",
            )
        )

    if "LineIntersection" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="affine_geometry.line_intersection",
                theory_path=["Logic", "Set", "OrderedField", "VectorSpace", "EuclideanGeometry"],
                structure_signature="Two affine lines with a unique intersection point",
                morphism_chain=["LineIntersection", "CoordinateSum"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="solve two line equations and compute requested coordinate observable",
                required_query_prefix="LineIntersection",
            )
        )

    if "CircleRadius" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="euclidean_geometry.circle_radius",
                theory_path=["Logic", "Set", "OrderedField", "VectorSpace", "InnerProductSpace", "EuclideanGeometry"],
                structure_signature="Circle determined by center and one point",
                morphism_chain=["CircleRadius", "Distance"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="compute radius as point-center distance",
                required_query_prefix="CircleRadius",
            )
        )

    if "Derivative" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="calculus.polynomial_derivative_value",
                theory_path=["Logic", "Set", "OrderedField", "PolynomialRing", "Calculus"],
                structure_signature="Polynomial function differentiated then evaluated at a point",
                morphism_chain=["PolynomialFunction", "Derivative", "Evaluation"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="differentiate polynomial and evaluate",
                required_query_prefix="DerivativeValue",
            )
        )

    if "DefiniteIntegral" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="calculus.polynomial_definite_integral",
                theory_path=["Logic", "Set", "OrderedField", "PolynomialRing", "Calculus"],
                structure_signature="Polynomial function integrated over a compact interval",
                morphism_chain=["PolynomialFunction", "DefiniteIntegral"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="integrate polynomial exactly over generated interval",
                required_query_prefix="DefiniteIntegral",
            )
        )

    if "Area" in morphism_names:
        constructors = ordered_present(
            morphism_names,
            [
                "Circle",
                "Polygon",
                "RegularPolygon",
                "Intersection",
                "SetComprehension",
                "Locus",
                "Centroid",
            ],
        )
        if "Limit" in morphism_names:
            family_id = "real_analysis.planar_measure_limit"
            chain = [*constructors, "Area", "Limit"]
            theory_path = [
                "Logic",
                "Set",
                "OrderedField",
                "EuclideanGeometry",
                "MeasureTheory",
                "RealAnalysis",
            ]
            structure = "Limit observation of planar measure under typed geometric constraints"
            contract = "construct an area expression, then discharge its convergence/limit obligation"
            query_prefix = "Limit"
        elif "Maximum" in morphism_names or "Minimum" in morphism_names:
            extremum = "Maximum" if "Maximum" in morphism_names else "Minimum"
            family_id = "optimization.planar_area_extremum"
            chain = [*constructors, "Area", extremum]
            theory_path = [
                "Logic",
                "Set",
                "OrderedField",
                "EuclideanGeometry",
                "MeasureTheory",
                "Optimization",
            ]
            structure = "Extremum of a planar measure over a typed feasible family"
            contract = "construct the feasible region and verify interior/boundary area extrema"
            query_prefix = extremum.lower()
        else:
            family_id = (
                "measure_geometry.locus_area"
                if "Locus" in morphism_names
                else "measure_geometry.planar_area"
            )
            chain = [*constructors, "Area"]
            theory_path = [
                "Logic",
                "Set",
                "OrderedField",
                "EuclideanGeometry",
                "MeasureTheory",
            ]
            structure = "Planar measure observation of a typed geometric region"
            contract = "construct or eliminate the region, prove boundedness, and integrate its measure"
            query_prefix = "Area"
        certificates.append(
            make_certificate(
                family_id=family_id,
                theory_path=theory_path,
                structure_signature=structure,
                morphism_chain=chain,
                constraints=constraints_list,
                queries=queries_list,
                backend_contract=contract,
                required_query_prefix=query_prefix,
            )
        )

    if "Volume" in morphism_names:
        chain = [*ordered_present(morphism_names, ["SetComprehension", "Locus"]), "Volume"]
        query_prefix = "Volume"
        family_id = "measure_geometry.solid_volume"
        theory_path = ["Logic", "Set", "OrderedField", "MeasureTheory"]
        structure = "Three-dimensional measure observation of a typed solid"
        contract = "construct the solid, prove measurability/boundedness, and integrate volume"
        if "Limit" in morphism_names:
            chain.append("Limit")
            query_prefix = "Limit"
            family_id = "real_analysis.solid_volume_limit"
            theory_path.append("RealAnalysis")
            structure = "Limit observation of a three-dimensional measure"
            contract = "construct the volume expression and discharge its limit obligation"
        certificates.append(
            make_certificate(
                family_id=family_id,
                theory_path=theory_path,
                structure_signature=structure,
                morphism_chain=chain,
                constraints=constraints_list,
                queries=queries_list,
                backend_contract=contract,
                required_query_prefix=query_prefix,
            )
        )

    if "FrobeniusInnerProduct" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="linear_algebra.frobenius_pairing",
                theory_path=[
                    "Logic",
                    "Set",
                    "OrderedField",
                    "VectorSpace",
                    "InnerProductSpace",
                ],
                structure_signature=(
                    "Matrix space equipped with the trace-induced Frobenius inner product"
                ),
                morphism_chain=ordered_present(
                    morphism_names,
                    ["InnerProduct", "Norm", "FrobeniusInnerProduct"],
                ),
                constraints=constraints_list,
                queries=queries_list,
                backend_contract=(
                    "check matrix shapes, compute Trace(Transpose(A)B), and verify bilinearity"
                ),
                required_query_prefix="FrobeniusInnerProduct",
            )
        )

    if "Projection" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="linear_algebra.orthogonal_projection",
                theory_path=[
                    "Logic",
                    "Set",
                    "OrderedField",
                    "VectorSpace",
                    "InnerProductSpace",
                ],
                structure_signature=(
                    "Orthogonal projection characterized by an inner-product residual"
                ),
                morphism_chain=ordered_present(
                    morphism_names,
                    ["InnerProduct", "Norm", "Projection"],
                ),
                constraints=constraints_list,
                queries=queries_list,
                backend_contract=(
                    "solve the Gram system and verify that the residual is orthogonal "
                    "to the target subspace"
                ),
                required_query_prefix="Projection",
            )
        )

    if "QuadraticForm" in morphism_names and "Minimum" in morphism_names:
        certificates.append(
            make_certificate(
                family_id="optimization.positive_definite_quadratic",
                theory_path=[
                    "Logic",
                    "Set",
                    "OrderedField",
                    "VectorSpace",
                    "InnerProductSpace",
                    "Optimization",
                ],
                structure_signature=(
                    "Global minimization of a positive-definite quadratic form"
                ),
                morphism_chain=ordered_present(
                    morphism_names,
                    ["InnerProduct", "QuadraticForm", "PositiveDefinite", "Minimum"],
                ),
                constraints=constraints_list,
                queries=queries_list,
                backend_contract=(
                    "certify positive definiteness, solve the linear stationarity "
                    "system, and verify the global quadratic lower bound"
                ),
                required_query_prefix="minimum",
            )
        )

    if (
        "InnerProduct" in morphism_names
        and ({"Maximum", "Minimum"} & morphism_names)
        and "QuadraticForm" not in morphism_names
        and "Area" not in morphism_names
    ):
        extremum = "Maximum" if "Maximum" in morphism_names else "Minimum"
        certificates.append(
            make_certificate(
                family_id="optimization.inner_product_extremum",
                theory_path=[
                    "Logic",
                    "Set",
                    "OrderedField",
                    "VectorSpace",
                    "InnerProductSpace",
                    "Optimization",
                ],
                structure_signature=(
                    "Extremum of an inner-product observable over a norm-constrained set"
                ),
                morphism_chain=ordered_present(
                    morphism_names,
                    ["InnerProduct", "Norm", extremum],
                ),
                constraints=constraints_list,
                queries=queries_list,
                backend_contract=(
                    "apply the Gram/Cauchy-Schwarz bound and verify an attainable "
                    "equality witness"
                ),
                required_query_prefix=extremum.lower(),
            )
        )

    if (
        "NormalizedInnerProduct" in morphism_names
        and "Limit" in morphism_names
        and "Correlation" not in morphism_names
    ):
        certificates.append(
            make_certificate(
                family_id="real_analysis.normalized_inner_product_limit",
                theory_path=[
                    "Logic",
                    "Set",
                    "OrderedField",
                    "VectorSpace",
                    "InnerProductSpace",
                    "RealAnalysis",
                ],
                structure_signature=(
                    "Limit of a normalized inner-product observable in a Hilbert geometry"
                ),
                morphism_chain=ordered_present(
                    morphism_names,
                    ["InnerProduct", "Norm", "NormalizedInnerProduct", "Limit"],
                ),
                constraints=constraints_list,
                queries=queries_list,
                backend_contract=(
                    "construct the Gram data, prove nonzero norms, normalize the "
                    "pairing, and discharge the scalar limit"
                ),
                required_query_prefix="Limit",
            )
        )

    if "CorrelationFunction" in morphism_names:
        has_limit = "Limit" in morphism_names
        certificates.append(
            make_certificate(
                family_id=(
                    "real_analysis.correlation_function_limit"
                    if has_limit
                    else "probability.autocorrelation_function"
                ),
                theory_path=[
                    "Logic",
                    "Set",
                    "Probability",
                    "MeasureTheory",
                    *(["RealAnalysis"] if has_limit else []),
                ],
                structure_signature=(
                    "Lag-indexed normalized inner products of a stationary process"
                ),
                morphism_chain=[
                    *ordered_present(
                        morphism_names,
                        [
                            "Center",
                            "Covariance",
                            "InnerProduct",
                            "Norm",
                            "NormalizedInnerProduct",
                            "CorrelationFunction",
                        ],
                    ),
                    *(["Limit"] if has_limit else []),
                ],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract=(
                    "derive the lag covariance from stationarity, normalize by the "
                    "zero-lag variance, and verify positive semidefiniteness"
                ),
                required_query_prefix=(
                    "Limit" if has_limit else "CorrelationFunction"
                ),
            )
        )

    if "Correlation" in morphism_names:
        chain = ordered_present(
            morphism_names,
            [
                "ProbabilitySpace",
                "Expectation",
                "Center",
                "Covariance",
                "InnerProduct",
                "Norm",
                "NormalizedInnerProduct",
                "Correlation",
            ],
        )
        family_id = "probability.correlation_observable"
        theory_path = ["Logic", "Set", "Probability", "MeasureTheory"]
        structure = (
            "Correlation as a normalized inner product of centered random variables"
        )
        contract = (
            "center in L2(P), construct the covariance inner product, verify "
            "positive norms, and normalize"
        )
        query_prefix = "Correlation"
        if "Limit" in morphism_names:
            chain.append("Limit")
            family_id = "real_analysis.correlation_limit"
            theory_path.append("RealAnalysis")
            structure = "Limit of a correlation observable"
            contract = "derive finite-index moments and discharge the normalized limit"
            query_prefix = "Limit"
        certificates.append(
            make_certificate(
                family_id=family_id,
                theory_path=theory_path,
                structure_signature=structure,
                morphism_chain=chain,
                constraints=constraints_list,
                queries=queries_list,
                backend_contract=contract,
                required_query_prefix=query_prefix,
            )
        )

    if "Expectation" in morphism_names and "Correlation" not in morphism_names:
        certificates.append(
            make_certificate(
                family_id="probability.expectation_observable",
                theory_path=["Logic", "Set", "Probability", "MeasureTheory"],
                structure_signature="Expectation observation on a typed probability space",
                morphism_chain=ordered_present(
                    morphism_names, ["ProbabilitySpace", "Expectation", "Limit"]
                ),
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="construct the probability law and evaluate or bound its expectation",
                required_query_prefix="Limit" if "Limit" in morphism_names else "Expectation",
            )
        )

    if "Limit" in morphism_names and not ({"Area", "Volume", "Correlation", "Expectation"} & morphism_names):
        certificates.append(
            make_certificate(
                family_id="real_analysis.limit_observable",
                theory_path=["Logic", "Set", "OrderedField", "RealAnalysis"],
                structure_signature="Limit query on a typed function or sequence",
                morphism_chain=["Limit"],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="identify the directed limit and verify convergence by symbolic bounds or epsilon obligations",
                required_query_prefix="Limit",
            )
        )

    if "Prime" in morphism_names and "SelfPower" not in morphism_names:
        certificates.append(
            make_certificate(
                family_id="elementary_number_theory.prime_constraint_query",
                theory_path=[
                    "Logic",
                    "Set",
                    "AlgebraicStructure",
                    "PolynomialRing",
                    "QuotientRing",
                    "ElementaryNumberTheory",
                ],
                structure_signature="Query over integer variables constrained by the prime predicate",
                morphism_chain=ordered_present(
                    morphism_names,
                    ["Forall", "Exists", "Divides", "GCD", "LCM", "Factorial", "Prime"],
                ),
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="normalize prime/divisibility constraints, then dispatch modular and certified search obligations",
                required_query_prefix=None,
            )
        )

    for extremum in ("Maximum", "Minimum"):
        if extremum not in morphism_names or "Area" in morphism_names:
            continue
        certificates.append(
            make_certificate(
                family_id=f"optimization.scalar_{extremum.lower()}",
                theory_path=["Logic", "Set", "OrderedField", "RealClosedField", "Optimization"],
                structure_signature=f"Typed feasible-set query for a scalar {extremum.lower()}",
                morphism_chain=[extremum],
                constraints=constraints_list,
                queries=queries_list,
                backend_contract="enumerate stationary and boundary candidates and verify global optimality",
                required_query_prefix=extremum.lower(),
            )
        )

    return certificates


def ordered_present(names: set[str], order: list[str]) -> list[str]:
    return [name for name in order if name in names]


def make_certificate(
    *,
    family_id: str,
    theory_path: list[str],
    structure_signature: str,
    morphism_chain: list[str],
    constraints: list[Any],
    queries: list[Any],
    backend_contract: str,
    required_query_prefix: str | None,
) -> LiftCertificate:
    relevant_constraints = [
        item
        for item in constraints
        if is_relevant_constraint(item, morphism_chain)
    ]
    constraint_skeleton = [
        canonicalize_expression_skeleton(str(getattr(item, "expression", "")))
        for item in relevant_constraints
        if str(getattr(item, "expression", "")).strip()
    ]
    query_signature = canonical_query_signature(queries, required_query_prefix)
    admissible = query_signature != "query:none"
    reason = (
        "same typed morphism chain can be reused after replacing constants by parameters"
        if admissible
        else "structure lifted, but no compatible query was identified"
    )
    return LiftCertificate(
        family_id=family_id,
        theory_path=theory_path,
        structure_signature=structure_signature,
        morphism_chain=morphism_chain,
        constraint_skeleton=constraint_skeleton,
        query_signature=query_signature,
        backend_contract=backend_contract,
        admissible=admissible,
        reason=reason,
    )


def is_relevant_constraint(constraint: Any, morphism_chain: list[str]) -> bool:
    source = str(getattr(constraint, "source", ""))
    if source.startswith("math_morphism_library"):
        return True
    mentioned = {str(item) for item in getattr(constraint, "morphisms", [])}
    if mentioned & set(morphism_chain):
        return True
    if source.startswith("typed_definition_ir"):
        expression = str(getattr(constraint, "expression", ""))
        return any(name in expression for name in morphism_chain)
    return False


def canonical_query_signature(queries: list[Any], required_prefix: str | None) -> str:
    candidates = []
    for query in queries:
        target = str(getattr(query, "target", ""))
        expression = str(getattr(query, "expression", ""))
        kind = str(getattr(query, "kind", "compute"))
        sort = str(getattr(query, "sort", "Unknown"))
        haystack = f"{target} {expression}"
        if required_prefix and required_prefix not in haystack:
            continue
        candidates.append(f"{kind}:{sort}:{canonicalize_expression_skeleton(target or expression)}")
    if candidates:
        return sorted(candidates)[0]
    if queries and required_prefix is None:
        query = queries[0]
        return f"{getattr(query, 'kind', 'compute')}:{getattr(query, 'sort', 'Unknown')}:{canonicalize_expression_skeleton(str(getattr(query, 'target', 'answer')))}"
    return "query:none"


def canonicalize_expression_skeleton(expression: str) -> str:
    value = expression.strip()
    value = re.sub(r"-?\d+(?:\.\d+)?", "N", value)
    value = re.sub(r"[+-]?N", "N", value)
    value = re.sub(r"\b[A-Z]\b", "P", value)
    value = re.sub(r"\b[a-z]\b", "v", value)
    value = re.sub(r"\s+", "", value)
    return value or "empty"


def canonical_graph_signature(certificates: Iterable[Any]) -> list[str]:
    signatures = []
    for certificate in certificates:
        if hasattr(certificate, "canonical_signature"):
            signatures.append(certificate.canonical_signature())
        elif isinstance(certificate, dict):
            signatures.append(str(certificate.get("canonical_signature") or ""))
    return sorted(item for item in signatures if item)


def compare_lift_structures(left: Iterable[Any], right: Iterable[Any]) -> dict[str, Any]:
    left_signatures = set(canonical_graph_signature(left))
    right_signatures = set(canonical_graph_signature(right))
    shared = sorted(left_signatures & right_signatures)
    return {
        "same_structure": bool(shared),
        "shared_signatures": shared,
        "left_only": sorted(left_signatures - right_signatures),
        "right_only": sorted(right_signatures - left_signatures),
    }
