"""The sign kernel: ordering as an equation, with a witness that can be checked.

The fragment has equalities and non-vanishing, and no order at all. Everything
that has been built on it so far has therefore smuggled order in as a Python
`<=`: whether a pixel is near enough to a stroke, whether a crossing lies on a
segment rather than on its line, whether a point stands between the light and
the shadow. Those comparisons are exact on rationals, and they are still not
statements the fragment can decide.

This module is the smallest thing that fixes that, and it rests on one theorem.

    A rational a is non-negative if and only if there are rationals x, y, z, w
    with a = x^2 + y^2 + z^2 + w^2.

The name for that is not Lagrange -- Lagrange's four-square theorem is about
integers. Write a = p/q in lowest terms with q > 0; then a = (pq)/q^2, and pq is
a non-negative integer, so applying Lagrange to pq and dividing by q gives the
four rational squares. The converse is immediate because a square is
non-negative in every ordering of QQ, and QQ has exactly one. The field-theoretic
way to say it is that **the Pythagoras number of QQ is 4**, and 4 is sharp: 7 is
a sum of four rational squares and not of three. So **an order fact is an
existentially quantified equation**, which is the fragment's own language, and a
certificate for one is four numbers.

It is a theorem about QQ and it fails one step outside. In QQ(sqrt 3), which
`geometry_quadratic` opts into, a sum of squares must be positive under *both*
real embeddings, and 4 sqrt(3) is positive under one and negative under the
other -- so that true ordering fact has no such certificate at all. Everything
here therefore refuses a coordinate that is not rational, rather than pretending
to reach further.

Three consequences, and they are the reason this is worth doing.

**Checking is comparison-free; finding is not.** Verifying a certificate is one
exact equality -- add four squares, compare to `a`, and `==` is not an order
test. Finding the four numbers is a search, and that search is full of
comparisons. This module never pretends otherwise: `sign` is a comparison and
says so, and the certificate is what turns its answer into something the
fragment can be handed.

**The number of squares needed is a dimension.** The least number of rational
squares summing to a non-negative rational a is exactly the least d for which
sqrt(a) is the distance between two points of QQ^d. One means a is a rational
square; two means sqrt(a) is a distance in the rational plane, and the criterion
is arithmetic -- writing a = u/v in lowest terms, every prime congruent to 3 mod
4 must divide uv to an even power; three means it is a distance in rational
space but not in the plane, which is exactly the case of sqrt 3, the diagonal of
the unit cube, and exactly why the plane needed a quadratic extension to build
an equilateral triangle while space does not; four means it is no distance
between rational points of space at all. The kernel reports the count, because
that is the honest answer to "can this fragment see the length you are ordering
by", and the answer names the dimension in which it could.

**The derived relations become constructions.** `P is in the closed disk about O
through A` is not a comparison here: it is `exists U, V: midp(P,U,V) and
cong(O,U,O,A) and cong(O,V,O,A)`, and this module builds U and V, in QQ when the
construction stays rational and in QQ(sqrt s) when it does not, and then asks
`atom_holds` whether the three atoms hold. When no witness exists in either, it
refuses and says which.

Nothing here adds a predicate or a primitive to the fragment.
"""
from __future__ import annotations

from fractions import Fraction
from math import isqrt

import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_semantic_dsl as dsl

#: How large an integer the square-finding search will grind on before refusing.
#: The search is O(sqrt(N)) in the worst case, so this is about a tenth of a
#: second; raising it is a promise to wait.
SEARCH_LIMIT = 10**10


# ---------------------------------------------------------------------------
# The decision, which is a comparison, and says so
# ---------------------------------------------------------------------------

def sign(value):
    """-1, 0 or +1, exactly. This is a comparison; the certificate is separate.

    A non-rational argument is refused rather than converted. The kernel's whole
    content is a theorem about QQ, and in a real quadratic field positivity and
    being a sum of squares part company.
    """
    value = _rational_or_refuse(value)
    return (value > 0)-(value < 0)


def _rational_or_refuse(value):
    if isinstance(value, sp.Expr) and not value.is_Rational:
        raise ValueError(f"{value} is not rational: the sign kernel is a theorem about QQ, and "
                         "in a real quadratic field a positive element need not be a sum of "
                         "squares at all (4*sqrt(3) in QQ(sqrt 3) is the standard example)")
    return Fraction(value)


def two_squares_criterion(value):
    """Whether a non-negative rational is a sum of two rational squares, by arithmetic.

    Writing a = u/v in lowest terms, this holds exactly when every prime
    congruent to 3 modulo 4 divides uv to an even power -- which is the decidable
    form of "sqrt(a) is a distance between two rational points of the plane".
    The search finds the same answer; this states the reason.
    """
    value = _rational_or_refuse(value)
    if value < 0:
        return False
    if value == 0:
        return True
    remaining = value.numerator*value.denominator
    factor = 2
    while factor*factor <= remaining:
        if remaining % factor == 0:
            power = 0
            while remaining % factor == 0:
                remaining //= factor
                power += 1
            if factor % 4 == 3 and power % 2:
                return False
        factor += 1
    return not (remaining % 4 == 3)


def realisable_in_dimension(value):
    """The least d for which sqrt(a) is a distance between two points of QQ^d."""
    witness, refusal = squares_of(value)
    return None if witness is None else len(witness)


# ---------------------------------------------------------------------------
# Sums of squares of integers: the search
# ---------------------------------------------------------------------------

def _is_square(n):
    if n < 0:
        return False
    root = isqrt(n)
    return root*root == n


def _two_squares(n):
    """n = x^2 + y^2 in integers, or None. A bounded search, not a factorisation."""
    if n < 0:
        return None
    for x in range(isqrt(n), -1, -1):
        rest = n-x*x
        if rest > x*x:
            break
        root = isqrt(rest)
        if root*root == rest:
            return (x, root)
    return None


def _three_squares(n):
    """n = x^2 + y^2 + z^2, or None when Legendre forbids it.

    A positive integer is a sum of three squares unless it is 4^a (8b + 7), and
    the search below looks for the representation only when it must exist.
    """
    if n < 0:
        return None
    reduced, power = n, 0
    while reduced and reduced % 4 == 0:
        reduced //= 4
        power += 1
    if reduced % 8 == 7:
        return None
    for x in range(isqrt(n), -1, -1):
        pair = _two_squares(n-x*x)
        if pair is not None:
            return (x,)+pair
    return None


def _four_squares(n):
    """n = x^2 + y^2 + z^2 + w^2 in integers. Lagrange says this always succeeds."""
    for x in range(0, isqrt(n)+1):
        triple = _three_squares(n-x*x)
        if triple is not None:
            return (x,)+triple
    raise ArithmeticError(f"no four squares for {n}, which contradicts Lagrange")


def integer_squares(n):
    """The fewest integer squares summing to a non-negative integer, with them."""
    if n < 0:
        raise ValueError("a negative integer is not a sum of squares")
    if n == 0:
        return ()
    if _is_square(n):
        return (isqrt(n),)
    pair = _two_squares(n)
    if pair is not None:
        return tuple(v for v in pair if v)
    triple = _three_squares(n)
    if triple is not None:
        return tuple(v for v in triple if v)
    return tuple(v for v in _four_squares(n) if v)


# ---------------------------------------------------------------------------
# The certificate
# ---------------------------------------------------------------------------

def squares_of(value, *, limit=SEARCH_LIMIT):
    """The fewest rational squares summing to a non-negative rational.

    `a = p/q` in lowest terms is `(pq)/q^2`, so the integer decomposition of
    `pq` divided by `q` is the rational one, and it is minimal. For one, two or
    three squares that minimality is the Davenport and Cassels lemma, whose
    hypothesis holds because the worst rational point is at distance k/4 < 1 from
    the integer lattice; at four squares the lemma's hypothesis fails with
    equality and nothing is needed, because Lagrange already gives four integer
    squares for pq directly.
    """
    value = _rational_or_refuse(value)
    if value < 0:
        return None, "the value is negative, so it is no sum of squares"
    product = value.numerator*value.denominator
    if product > limit:
        return None, (f"the search was refused: {product} is above the limit {limit}. "
                      "The sign is still decided; only the witness is missing")
    parts = integer_squares(product)
    return tuple(Fraction(v, value.denominator) for v in parts), None


def certify_nonnegative(value, *, limit=SEARCH_LIMIT):
    """`a >= 0` as an equation: the witness, the identity, and the check.

    The check adds the squares and compares the sum to `a` with `==`. No order
    test appears in it, which is the whole point: the comparison is spent in
    finding the witness and never again in using it.
    """
    value = _rational_or_refuse(value)
    witness, refusal = squares_of(value, limit=limit)
    if witness is None:
        return {"holds": value >= 0, "certified": False, "why": refusal,
                "value": str(value)}
    total = sum(w*w for w in witness)
    return {"holds": True, "certified": total == value, "value": str(value),
            "squares": [str(w) for w in witness], "how_many": len(witness),
            "identity": " + ".join(f"({w})^2" for w in witness)+f" = {value}",
            "is_a_planar_length": len(witness) <= 2,
            "least_dimension_holding_the_length": len(witness) if witness else 0,
            "means": "a sum of at most two rational squares is |v|^2 for a rational vector of "
                     "the plane, so its square root is a distance between two rational points; "
                     "three or four squares means the length is not one this fragment can hold"}


def certify_positive(value, *, limit=SEARCH_LIMIT):
    """`a > 0`: non-negative, and not zero. The second half is `diff`, not an order."""
    value = _rational_or_refuse(value)
    report = certify_nonnegative(value, limit=limit)
    report["holds"] = report["holds"] and value != 0
    report["nonzero"] = value != 0
    return report


def certify_leq(left, right, *, limit=SEARCH_LIMIT):
    """`a <= b` is `b - a >= 0`, and nothing else."""
    report = certify_nonnegative(Fraction(right)-Fraction(left), limit=limit)
    report["statement"] = f"{left} <= {right}"
    return report


# ---------------------------------------------------------------------------
# Deciding an atom over a quadratic extension named on the spot
# ---------------------------------------------------------------------------

def _atom_over(predicate, arguments, coordinates):
    """`atom_holds`, with coordinates allowed to live in any QQ(sqrt s).

    `geometry_relational_dsl.atom_holds` coerces every coordinate to a rational,
    which is right for the fragment and wrong for a witness that had to leave it.
    This lowers the predicate by the fragment's own `dsl.lower` and decides the
    vanishing with `simplify`, exactly as `geometry_quadratic` does for its one
    fixed extension.
    """
    elaborator = gc._JGEXElaborator()
    for name in dict.fromkeys(arguments):
        elaborator.coordinates[name] = tuple(sp.sympify(v) for v in coordinates[name])
    value = sp.simplify(sp.expand(dsl.lower(elaborator, predicate, tuple(arguments))))
    if predicate in rdsl.NONZERO_PREDICATES:
        return value != 0
    return value == 0


def _rational(value):
    return sp.sympify(value).is_Rational


# ---------------------------------------------------------------------------
# The geometric relations, as constructions
# ---------------------------------------------------------------------------

def squared_distance(p, q):
    return (Fraction(p[0])-Fraction(q[0]))**2+(Fraction(p[1])-Fraction(q[1]))**2


def cross(a, b, p):
    """Twice the signed area of ABP: positive to the left of AB, and exact."""
    return (Fraction(b[0])-Fraction(a[0]))*(Fraction(p[1])-Fraction(a[1])) - \
        (Fraction(b[1])-Fraction(a[1]))*(Fraction(p[0])-Fraction(a[0]))


def _square_root(value):
    """A rational square root when there is one, else the symbol, else None."""
    value = Fraction(value)
    if value < 0:
        return None, "negative"
    numerator, denominator = isqrt(value.numerator), isqrt(value.denominator)
    if numerator*numerator == value.numerator and denominator*denominator == value.denominator:
        return Fraction(numerator, denominator), "rational"
    return sp.sqrt(sp.Rational(value)), "quadratic"


def witness_in_closed_disk(point, centre, through):
    """Build U and V so that `midp(P,U,V)`, `cong(O,U,O,A)`, `cong(O,V,O,A)` hold.

    P lies in the closed disk about O through A exactly when such a pair exists,
    and the construction is forced: U = P + v and V = P - v with v perpendicular
    to P - O and |v|^2 = |OA|^2 - |OP|^2, because then |U - O|^2 = |OP|^2 + |v|^2
    is |OA|^2 and P is the midpoint by construction.

    Whether v is rational is the question the kernel exists to answer. With
    u = P - O and d = |u|^2, the vector is v = t (-u_y, u_x) with t^2 = r/d, so v
    is rational exactly when r/d is a square in QQ, and otherwise it lives in
    QQ(sqrt(r/d)). When P = O any v of length^2 = r will do, and that one is
    rational exactly when r is a sum of two rational squares -- which is the
    two-square case of the certificate above, and the place where the counting
    of squares is not bookkeeping.
    """
    radius_squared = squared_distance(centre, through)
    distance_squared = squared_distance(point, centre)
    remainder = radius_squared-distance_squared
    decision = certify_nonnegative(remainder) if remainder >= 0 else \
        {"holds": False, "certified": False, "why": "the remainder is negative"}
    report = {"holds": remainder >= 0, "point": [str(v) for v in point],
              "remainder": str(remainder),
              "the_decision": decision,
              "three_layers": "membership MEANS the existential; it is DECIDED by the four-square "
                              "certificate on |OA|^2 - |OP|^2; the pair U, V below ILLUSTRATES it "
                              "and is tagged with the field it needed. The second and third do "
                              "not always agree over QQ: a point can be inside with no rational "
                              "U and V at all"}
    if remainder < 0:
        report.update({"certified": False,
                       "why": "no real U and V exist: the point is outside the circle, and "
                              "that is the content of the relation being false"})
        return report
    if distance_squared == 0:
        length, kind = _square_root(remainder)
        if kind == "rational":
            offset = (length, Fraction(0))
        else:
            pair, _ = squares_of(remainder)
            if pair is not None and len(pair) <= 2:
                filled = list(pair)+[Fraction(0)]*(2-len(pair))
                offset = (filled[0], filled[1])
                kind = "rational"
            else:
                offset = (length, sp.Integer(0))
    else:
        ratio = remainder/distance_squared
        scale, kind = _square_root(ratio)
        direction = (-(Fraction(point[1])-Fraction(centre[1])),
                     Fraction(point[0])-Fraction(centre[0]))
        offset = (scale*direction[0], scale*direction[1])
    first = (sp.sympify(point[0])+offset[0], sp.sympify(point[1])+offset[1])
    second = (sp.sympify(point[0])-offset[0], sp.sympify(point[1])-offset[1])
    coordinates = {"__p": tuple(sp.sympify(v) for v in point),
                   "__o": tuple(sp.sympify(v) for v in centre),
                   "__a": tuple(sp.sympify(v) for v in through),
                   "__u": first, "__v": second}
    atoms = [("midp", ("__p", "__u", "__v")), ("cong", ("__o", "__u", "__o", "__a")),
             ("cong", ("__o", "__v", "__o", "__a"))]
    decided = {f"{name}{args}": _atom_over(name, args, coordinates) for name, args in atoms}
    adjoined = sp.nsimplify(sp.expand(offset[0]**2+offset[1]**2)/distance_squared) \
        if distance_squared else sp.nsimplify(remainder)
    report.update({
        "certified": all(decided.values()),
        "witness_field": "QQ" if kind == "rational" else f"QQ(sqrt({adjoined}))",
        "witness_is_rational": kind == "rational",
        "U": [str(sp.nsimplify(v)) for v in first],
        "V": [str(sp.nsimplify(v)) for v in second],
        "atoms": decided,
        "degenerate": first == second,
        "relation": "exists U V: midp(P,U,V) and cong(O,U,O,A) and cong(O,V,O,A)",
        "soundness": witness_implies_membership()})
    return report


def witness_implies_membership():
    """Why a witness proves membership: `|U - V|^2 = 4(|OA|^2 - |OP|^2)`, identically.

    The existential has to be sound before it is useful, and the soundness is
    not an appeal -- it is a polynomial identity. Given `midp(P,U,V)` and the two
    `cong` atoms, the square of the distance between the two circle points is
    four times the remainder, so the remainder is a square divided by four and
    is non-negative wherever the witness exists. That is the universal layer
    certifying the geometric layer, and it is checked here rather than asserted.
    """
    ox, oy, ux, uy, ax, ay = sp.symbols("ox oy ux uy ax ay", real=True)
    px, py = sp.symbols("px py", real=True)
    vx, vy = 2*px-ux, 2*py-uy                      # midp(P,U,V) solved for V
    radius = (ax-ox)**2+(ay-oy)**2
    on_circle = sp.expand((ux-ox)**2+(uy-oy)**2-radius)
    other = sp.expand((vx-ox)**2+(vy-oy)**2-radius)
    remainder = sp.expand(radius-((px-ox)**2+(py-oy)**2))
    separation = sp.expand((ux-vx)**2+(uy-vy)**2)
    # on both circles, the separation is four times the remainder
    difference = sp.simplify(sp.expand(separation-4*remainder)
                             - sp.expand(2*on_circle+2*other))
    return {"identity": "|U - V|^2 = 4 (|OA|^2 - |OP|^2), given midp(P,U,V) and the two congs",
            "certified": difference == 0,
            "means": "the remainder is a quarter of a square whenever the witness exists, so a "
                     "witness implies membership; the converse is what can fail over QQ"}


def certify_between(a, point, b):
    """`A P B` in that order on a line: `coll`, and two lengths that do not exceed."""
    coordinates = {"__a": tuple(map(Fraction, a)), "__p": tuple(map(Fraction, point)),
                   "__b": tuple(map(Fraction, b))}
    straight = rdsl.atom_holds("coll", ("__a", "__p", "__b"), coordinates)
    whole = squared_distance(a, b)
    first = certify_leq(squared_distance(a, point), whole)
    second = certify_leq(squared_distance(point, b), whole)
    return {"holds": straight and first["holds"] and second["holds"],
            "coll": straight, "AP_at_most_AB": first, "PB_at_most_AB": second,
            "relation": "coll(A,P,B) and |AP|^2 <= |AB|^2 and |PB|^2 <= |AB|^2"}


def certify_same_side(first, second, a, b):
    """Two points on one side of the line AB: the product of the two areas is positive."""
    product = cross(a, b, first)*cross(a, b, second)
    report = certify_positive(product)
    report["relation"] = "cross(A,B,P) * cross(A,B,Q) > 0"
    report["product"] = str(product)
    return report


def certify_on_closed_segment(point, a, b):
    """On the line, and inside the disk on AB as diameter: the segment, not the line."""
    coordinates = {"__a": tuple(map(Fraction, a)), "__p": tuple(map(Fraction, point)),
                   "__b": tuple(map(Fraction, b))}
    straight = rdsl.atom_holds("coll", ("__a", "__p", "__b"), coordinates)
    centre = ((Fraction(a[0])+Fraction(b[0]))/2, (Fraction(a[1])+Fraction(b[1]))/2)
    inside = witness_in_closed_disk(point, centre, a)
    return {"holds": straight and inside["holds"], "coll": straight, "in_the_disk": inside,
            "relation": "coll(A,P,B) and P in the closed disk on AB as diameter"}


def certify_within_of_segment(point, a, b, radius):
    """P is within `radius` of the segment AB -- the relation a drawn stroke is.

    The statement is `exists Q X: on_closed_segment(Q,A,B) and |PX|^2 = r^2 and
    Q in the closed disk about P through X`, and both witnesses are built rather
    than assumed. Q is the fragment's own `foot` of P on the line AB when that
    foot lies on the segment, and an end of the segment otherwise; X is P
    displaced by r along the first axis, which is rational because r is. So the
    membership that decides every inked cell of every letter in this repository
    has a witness in QQ, always, and a certificate that is three atoms.
    """
    a = tuple(Fraction(v) for v in a)
    b = tuple(Fraction(v) for v in b)
    point = tuple(Fraction(v) for v in point)
    radius = Fraction(radius)
    if a == b:
        nearest, how = a, "the segment is a point"
    else:
        coordinates = {"__p": point, "__a": a, "__b": b}
        foot, reason = rdsl.execute_primitive("foot", ["__p", "__a", "__b"], coordinates)
        if foot is None:
            return {"holds": False, "certified": False, "why": f"foot refused: {reason}"}
        foot = (Fraction(str(foot[0])), Fraction(str(foot[1])))
        if certify_on_closed_segment(foot, a, b)["holds"]:
            nearest, how = foot, "the foot of P on the line AB, by the fragment's `foot`"
        else:
            first, second = squared_distance(point, a), squared_distance(point, b)
            nearest = a if first <= second else b
            how = "the nearer end, because the foot falls outside the segment"
    far = (point[0]+radius, point[1])
    on_it = certify_on_closed_segment(nearest, a, b)
    near_enough = witness_in_closed_disk(nearest, point, far)
    return {"holds": on_it["holds"] and near_enough["holds"],
            "certified": on_it["holds"] and near_enough.get("certified", False),
            "Q": [str(v) for v in nearest], "how_Q_was_found": how,
            "X": [str(v) for v in far], "radius": str(radius),
            "Q_on_the_segment": on_it, "Q_within_the_radius": near_enough,
            "relation": "exists Q X: on_closed_segment(Q,A,B) and |PX| = r and Q in the "
                        "closed disk about P through X"}


def certify_the_foot_is_nearest():
    """Why one witness settles an existential over a whole segment, as an identity.

    `P is within r of the segment` is existential, so a witness proves it; the
    *failure* of it needs the other half -- that the witness tried was the best
    one there is. For a line that is exactly the foot, and the reason is an
    identity rather than an argument: with Q running along AB and F the foot,

        |PQ|^2 - |PF|^2  =  |AB|^2 (t - t0)^2,

    a single square. So no point of the line is nearer than the foot, for every
    P and every line, and the certificate is one polynomial identity checked by
    expansion. On a segment the foot may fall outside it, and then the nearest
    point is an end, which is the case the caller separates.
    """
    t, t0, ax, ay, bx, by, px, py = sp.symbols("t t0 ax ay bx by px py", real=True)
    direction = (bx-ax, by-ay)
    squared = direction[0]**2+direction[1]**2
    foot = (ax+t0*direction[0], ay+t0*direction[1])
    q = (ax+t*direction[0], ay+t*direction[1])
    at_the_foot = sp.solve(sp.Eq((px-foot[0])*direction[0]+(py-foot[1])*direction[1], 0), t0)[0]
    difference = sp.expand(((px-q[0])**2+(py-q[1])**2)
                           - ((px-foot[0])**2+(py-foot[1])**2).subs(t0, at_the_foot))
    claimed = sp.expand(squared*(t-at_the_foot)**2)
    return {"certified": sp.simplify(difference-claimed) == 0,
            "identity": "|PQ|^2 - |PF|^2 = |AB|^2 (t - t0)^2",
            "squares": [[str(sp.factor(squared)), str(sp.factor(t-at_the_foot))]],
            "means": "the foot is the nearest point of the line to P, for every P and every "
                     "line, and the reason is one square rather than an appeal to calculus"}


def certify_occluded(x, light, occluder_a, occluder_b):
    """The light does not reach X: some point of AB stands strictly between them.

    The witness is `intersection_ll(L,X,A,B)`, which is a primitive of the
    fragment, and the certificate is that it lies on the occluder's segment and
    strictly between the light and the point. Two lines meet in at most one
    place, so this witness is the only candidate there is.
    """
    coordinates = {"__l": tuple(Fraction(v) for v in light),
                   "__x": tuple(Fraction(v) for v in x),
                   "__a": tuple(Fraction(v) for v in occluder_a),
                   "__b": tuple(Fraction(v) for v in occluder_b)}
    if coordinates["__l"] == coordinates["__x"]:
        return {"holds": False, "certified": False, "why": "the point is the light"}
    meeting, reason = rdsl.execute_primitive("intersection_ll", ["__l", "__x", "__a", "__b"],
                                             coordinates)
    if meeting is None:
        return {"holds": False, "certified": True, "why": reason,
                "means": "the ray runs parallel to the occluder, so it meets it nowhere and "
                         "the existential is false for want of any candidate"}
    meeting = (Fraction(str(meeting[0])), Fraction(str(meeting[1])))
    on_occluder = certify_on_closed_segment(meeting, occluder_a, occluder_b)
    on_ray = certify_between(coordinates["__l"], meeting, coordinates["__x"])
    strict = meeting != coordinates["__l"] and meeting != coordinates["__x"]
    return {"holds": on_occluder["holds"] and on_ray["holds"] and strict,
            "certified": True, "P": [str(v) for v in meeting],
            "P_on_the_occluder": on_occluder, "P_between_light_and_point": on_ray,
            "strict": strict,
            "relation": "exists P: on_closed_segment(P,A,B) and P strictly between L and X"}


# ---------------------------------------------------------------------------
# The universal layer: non-negative for every configuration
# ---------------------------------------------------------------------------

def verify_sum_of_squares(expression, terms, variables):
    """Check a supplied decomposition. This is the comparison-free half.

    `terms` is a list of (coefficient, polynomial) pairs, and the check is one
    expansion and one `==`. Finding such a decomposition is a search; checking
    one is not, and the asymmetry is the same one the four squares have.
    """
    expression = sp.expand(sp.sympify(expression))
    rebuilt = sp.expand(sum(sp.sympify(c)*sp.sympify(q)**2 for c, q in terms))
    negative = [str(c) for c, _ in terms if sp.sympify(c) < 0]
    return {"certified": sp.expand(rebuilt-expression) == 0 and not negative,
            "coefficients_negative": negative,
            "identity": " + ".join(f"({c})*({q})^2" for c, q in terms)+f" = {expression}",
            "means": "the polynomial is a sum of squares with non-negative rational weights, so "
                     "it is non-negative at every configuration, not merely at the ones tried"}


def sum_of_squares(expression, variables, *, degree=None):
    """Write a polynomial as a sum of rational multiples of squares, or refuse.

    A Gram matrix over the monomials of half the degree is solved for, the
    free parameters are set to zero, and an exact LDL decomposition turns it
    into squares. When a pivot comes out negative the attempt fails and is
    reported as a failure rather than as an absence of the property: this
    certifies non-negativity, it does not refute it.
    """
    expression = sp.expand(sp.sympify(expression))
    variables = [sp.sympify(v) for v in variables]
    polynomial = sp.Poly(expression, *variables)
    half = (polynomial.total_degree()+1)//2 if degree is None else degree
    # the monomials whose own square appears in the polynomial come first: for a
    # difference of two squares that basis is the whole of it, and the full
    # basis of half the degree is only tried when the small one fails
    support = {powers for powers, c in zip(polynomial.monoms(), polynomial.coeffs()) if c}
    diagonal = [powers for powers in _exponents(len(variables), half)
                if tuple(2*e for e in powers) in support]
    for basis in ([diagonal] if diagonal else [])+[list(_exponents(len(variables), half))]:
        found = _attempt(expression, variables, basis)
        if found is not None:
            return found
    return {"certified": False,
            "why": "no positive semidefinite Gram matrix was found at this degree, on the "
                   "diagonal basis or the full one. That is a failure to certify, not a "
                   "refutation: the polynomial may still be non-negative"}


def _attempt(expression, variables, basis):
    """One basis, one Gram solve, one exact LDL. None when it does not work out."""
    monomials = [sp.prod([v**e for v, e in zip(variables, powers)]) for powers in basis]
    size = len(monomials)
    entries = {}
    for i in range(size):
        for j in range(i, size):
            entries[(i, j)] = sp.Symbol(f"g_{i}_{j}")
    gram = sp.Matrix(size, size, lambda i, j: entries[(min(i, j), max(i, j))])
    form = sp.expand(sum(gram[i, j]*monomials[i]*monomials[j]
                         for i in range(size) for j in range(size)))
    equations = [sp.Eq(a, b) for a, b in
                 _match_coefficients(form, expression, variables)]
    solution = sp.solve(equations, list(entries.values()), dict=True)
    if not solution:
        return None
    assignment = dict(solution[0])
    for symbol in entries.values():
        assignment.setdefault(symbol, sp.Integer(0))
    assignment = {k: v.subs({s: 0 for s in entries.values()}) if v.free_symbols else v
                  for k, v in assignment.items()}
    numeric = gram.subs(assignment)
    if numeric.free_symbols:
        numeric = numeric.subs({s: 0 for s in numeric.free_symbols})
    pieces = _ldl_squares(numeric, monomials)
    if pieces is None:
        return None
    rebuilt = sp.expand(sum(c*q**2 for c, q in pieces))
    if sp.expand(rebuilt-expression) != 0:
        return None
    return {"certified": True,
            "squares": [[str(c), str(sp.factor(q))] for c, q in pieces],
            "identity": " + ".join(f"({c})*({sp.factor(q)})^2" for c, q in pieces),
            "monomials": [str(m) for m in monomials]}


def _exponents(count, degree):
    if count == 1:
        for e in range(degree+1):
            yield (e,)
        return
    for e in range(degree+1):
        for rest in _exponents(count-1, degree-e):
            yield (e,)+rest


def _match_coefficients(left, right, variables):
    difference = sp.expand(left-right)
    poly = sp.Poly(difference, *variables)
    return [(coefficient, 0) for coefficient in poly.coeffs()]


def _ldl_squares(matrix, monomials):
    """An exact LDL of a symmetric rational matrix, as squares, or None."""
    size = matrix.rows
    work = sp.Matrix(matrix)
    vectors = sp.eye(size)
    pieces = []
    for index in range(size):
        pivot = sp.nsimplify(work[index, index])
        if pivot == 0:
            if any(sp.nsimplify(work[index, j]) != 0 for j in range(index, size)):
                return None
            continue
        if pivot < 0:
            return None
        row = sp.Matrix([[work[index, j]/pivot for j in range(size)]])
        combination = sum(row[0, j]*monomials[j] for j in range(size))
        pieces.append((pivot, sp.expand(combination)))
        # the update has to read the row and the column as they were: modifying
        # them in place while they are still being read is the classic way to
        # get an LDL that almost works
        column = [work[i, index] for i in range(size)]
        across = [work[index, j] for j in range(size)]
        for i in range(size):
            for j in range(size):
                work[i, j] = sp.nsimplify(work[i, j]-column[i]*across[j]/pivot)
    return pieces
