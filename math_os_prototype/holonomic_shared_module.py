"""Exact identities via shared Euler-derivative states of formal ODE germs.

No special-function transformation or target identity is assumed. Each seed
uses its defining Euler equation. A discovered scalar operator is checked by
application in the shared polynomial module, then by exact initial values.
"""

from copy import deepcopy
from hashlib import sha256

import sympy as sp
from sympy.polys.matrices import DomainMatrix

from math_os_prototype.holonomic_route_discovery import X, N, key, rational, validate
from math_os_prototype.holonomic_fast_coefficients import coefficients

FIELD = sp.QQ.frac_field(X)
XX = FIELD.from_sympy(X)
SCHEMA = "mortra.shared-euler-module-equality.v1"
SCOPE = "Q[[x]] at zero; no special-value, continuation, minimality or novelty claim"


class SharedModuleBudget(ValueError):
    pass


def descend_quadratic_connection_pair(plus, minus, observation_plus, observation_minus,
                                     delta, delta_derivative, field):
    """Descend conjugate differential systems to the rational coefficient field.

    Entries are pairs (a,b) representing a+b*rho, rho^2=delta. The new basis is
    U=(F+ + F-)/2, V=(F+ - F-)/(2*rho). The original scalar observation is the
    sum of the two supplied observations. A full gauge identity is replayed.
    """
    if not field.is_Field or not field.is_Exact or field.characteristic()!=0 or not delta:
        raise ValueError("a nonzero quadratic radicand over an exact characteristic-zero field is required")
    size=len(plus)
    if not size or len(minus)!=size or any(len(r)!=size for r in plus+minus):
        raise ValueError("square connection matrices of equal size are required")
    if len(observation_plus)!=size or len(observation_minus)!=size:
        raise ValueError("observation dimensions differ")
    for left,right in list(zip(sum(plus,[]),sum(minus,[])))+list(zip(observation_plus,observation_minus)):
        if len(left)!=2 or len(right)!=2 or left[0]!=right[0] or left[1]!=-right[1]:
            raise ValueError("the systems and observations are not conjugate")
    zero,one=field.zero,field.one
    half=one/field.convert(2)
    rate=half*delta_derivative/delta
    connection=[[zero for _ in range(2*size)] for _ in range(2*size)]
    for i in range(size):
        for j in range(size):
            a,b=plus[i][j]
            connection[i][j]=a
            connection[i][j+size]=delta*b
            connection[i+size][j]=b
            connection[i+size][j+size]=a-(rate if i==j else zero)
    observation=[2*a for a,b in observation_plus]+[2*delta*b for a,b in observation_plus]
    pair_zero=(zero,zero)
    def add(a,b):
        return a[0]+b[0],a[1]+b[1]
    def multiply(a,b):
        return a[0]*b[0]+delta*a[1]*b[1],a[0]*b[1]+a[1]*b[0]
    def total(values):
        out=pair_zero
        for value in values:
            out=add(out,value)
        return out
    gauge=[[pair_zero for _ in range(2*size)] for _ in range(2*size)]
    original=[[pair_zero for _ in range(2*size)] for _ in range(2*size)]
    for i in range(size):
        gauge[i][i]=gauge[i][i+size]=(half,zero)
        gauge[i+size][i]=(zero,half/delta)
        gauge[i+size][i+size]=(zero,-half/delta)
        for j in range(size):
            original[i][j]=tuple(plus[i][j])
            original[i+size][j+size]=tuple(minus[i][j])
    for i in range(2*size):
        for j in range(2*size):
            derivative=multiply((-rate,zero),gauge[i][j]) if i>=size else pair_zero
            left=add(derivative,total(multiply(gauge[i][k],original[k][j]) for k in range(2*size)))
            right=total(multiply((connection[i][k],zero),gauge[k][j]) for k in range(2*size))
            if left!=right:
                raise ArithmeticError("quadratic connection gauge identity failed")
    original_observation=observation_plus+observation_minus
    for j in range(2*size):
        if total(multiply((observation[k],zero),gauge[k][j]) for k in range(2*size))!=tuple(original_observation[j]):
            raise ArithmeticError("quadratic observation descent failed")
    return {"connection":connection,"observation":observation,"module_dimension":2*size,
            "gauge_identity_replayed":True,"observation_identity_replayed":True,
            "basis":"U=(Fplus+Fminus)/2; V=(Fplus-Fminus)/(2*rho)",
            "inverse_basis":"Fplus=U+rho*V; Fminus=U-rho*V",
            "scope":"local differential module; analytic cycles and initial values are not identified"}


def annihilator_from_rational_connection(connection, observation, variable, *, max_order=None):
    """Discover a scalar operator from any exact rational differential system.

    Uses ordinary derivatives, unlike SharedModule's Euler convention. The
    certificate proves a relation in the supplied module, not minimality for
    a particular period cycle or an analytic initial-value specification.
    """
    matrix = sp.Matrix(connection)
    row = list(sp.Matrix([observation]))
    if matrix.rows != matrix.cols or len(row) != matrix.rows or not row:
        raise ValueError("connection and observation dimensions differ")
    symbols = sorted(set().union(variable.free_symbols, matrix.free_symbols,
                                *(x.free_symbols for x in row)), key=str)
    field = sp.QQ.frac_field(*symbols)
    generator = field.gens[symbols.index(variable)]
    def load_rational(expression):
        parts = [sp.Poly(p, *symbols, domain=sp.QQ) for p in sp.fraction(sp.together(expression))]
        numerator, denominator = [field.field.ring.from_dict(p.rep.to_dict()) for p in parts]
        return field.field.new(numerator, denominator)
    a = [[load_rational(matrix[i, j]) for j in range(matrix.cols)] for i in range(matrix.rows)]
    current = [load_rational(v) for v in row]
    rows = []
    limit = matrix.rows if max_order is None else min(max_order, matrix.rows)
    for order in range(limit+1):
        rows.append(current)
        relations = DomainMatrix.from_list(rows, field).transpose().nullspace().to_list()
        if relations:
            relation = relations[0]
            if not relation[-1]:
                raise ArithmeticError("unexpected earlier cyclic dependence")
            relation = [v/relation[-1] for v in relation]
            residual = [sum((relation[k]*rows[k][j] for k in range(order+1)), field.zero)
                        for j in range(matrix.rows)]
            if any(residual):
                raise ArithmeticError("rational connection operator does not replay")
            parts = [(sp.Poly.from_dict(dict(v.numer), *symbols, domain=sp.QQ),
                      sp.Poly.from_dict(dict(v.denom), *symbols, domain=sp.QQ)) for v in relation]
            common = sp.Poly(1, *symbols, domain=sp.QQ)
            for _, denominator in parts:
                common = sp.lcm(common, denominator)
            cleared = [numerator*common.exquo(denominator) for numerator, denominator in parts]
            divisor = cleared[0]
            for poly in cleared[1:]:
                divisor = sp.gcd(divisor, poly)
            primitive = [p.exquo(divisor).as_expr() for p in cleared]
            return {"schema": "mortra.rational-connection-scalar-operator.v1",
                "variable": str(variable), "derivative_convention": "ordinary",
                "operator_coefficients_ascending": [str(sp.factor(v)) for v in primitive],
                "order": order, "module_dimension": matrix.rows,
                "cyclic_basis_rows": [[str(field.to_sympy(v)) for v in r] for r in rows[:-1]],
                "earlier_observation_rows_independent": True,
                "module_residual_zero": True,
                "minimal_for_specific_period_cycle": False,
                "target_operator_supplied": False}
        current = [current[j].diff(generator)+sum((current[i]*a[i][j] for i in range(matrix.rows)), field.zero)
                   for j in range(matrix.cols)]
    return {"status": "outside_operator_order_budget", "target_operator_supplied": False}


def _q(value):
    return FIELD.convert(rational(value))


def _poly(values, argument=XX):
    result = FIELD.zero
    for value in reversed(values):
        result = result*argument+_q(value)
    return result


def encode_q(value):
    def dense(poly):
        degree = max((m[0] for m in poly), default=0)
        return [str(poly.get((i,), sp.QQ.zero)) for i in range(degree+1)]
    return {"numerator": dense(value.numer), "denominator": dense(value.denom)}


def decode_q(record):
    if not isinstance(record, dict) or set(record) != {"numerator", "denominator"}:
        raise ValueError("invalid rational-function record")
    if any(not isinstance(v, list) or not 1 <= len(v) <= 4096 for v in record.values()):
        raise ValueError("rational-function degree budget")
    denominator = _poly(record["denominator"])
    if not denominator:
        raise ValueError("zero rational-function denominator")
    return _poly(record["numerator"])/denominator


def _accumulate(result, monomial, value):
    if value:
        result[monomial] = result.get(monomial, FIELD.zero)+value
        if not result[monomial]:
            del result[monomial]


def add(left, right):
    result = left.copy()
    for monomial, value in right.items():
        _accumulate(result, monomial, value)
    return result


def scale(poly, value):
    return {m: c*value for m, c in poly.items() if c*value}


def multiply(left, right, limit=4096):
    result = {}
    for a, ca in left.items():
        for b, cb in right.items():
            _accumulate(result, tuple(sorted(a+b)), ca*cb)
            if len(result) > limit:
                raise SharedModuleBudget("shared polynomial size budget")
    return result


def encode_poly(poly):
    return [{"monomial": list(m), "coefficient": encode_q(c)} for m, c in sorted(poly.items())]


def seed_theta_coefficients(program, argument=XX):
    validate(program)
    if program["op"] not in ("hyper", "ode"):
        raise ValueError("a defining differential-equation seed is required")
    def product(values):
        result = [FIELD.one]
        for value in values:
            following = [FIELD.zero]*(len(result)+1)
            for i, c in enumerate(result):
                following[i] += value*c
                following[i+1] += c
            result = following
        return result
    if program["op"] == "ode":
        # D^k = x^(-k) theta(theta-1)...(theta-k+1), before pullback.
        result = [FIELD.zero]*len(program["operator"])
        for k, row in enumerate(program["operator"]):
            factor = _poly(row, argument)/argument**k
            for j, coefficient in enumerate(product([-FIELD.convert(i) for i in range(k)])):
                result[j] += factor*coefficient
        return result
    left = product([FIELD.zero]+[_q(b)-1 for b in program["b"]])
    right = product([_q(a) for a in program["a"]])
    return [left[i]-(argument*right[i] if i < len(right) else FIELD.zero) for i in range(len(left))]


class SharedModule:
    def __init__(self, max_states=96):
        if type(max_states) is not int or not 1 <= max_states <= 256:
            raise ValueError("invalid shared-state budget")
        self.max_states = max_states
        self.bases, self.base_index, self.connections = [], {}, []
        self._compiled, self._monomial_derivatives = {}, {}

    def seed(self, program, argument):
        signature = key({"program": program, "argument": encode_q(argument)})
        if signature in self.base_index:
            return {(self.base_index[signature],): FIELD.one}
        operator = seed_theta_coefficients(program, argument)
        order, first = len(operator)-1, len(self.connections)
        if first+order > 256:
            raise SharedModuleBudget("seed state budget")
        if not argument or not operator[-1]:
            raise ValueError("invalid seed state")
        factor = XX*argument.diff(FIELD.gens[0])/argument
        for j in range(order):
            if j+1 < order:
                connection = {first+j+1: factor}
            else:
                connection = {first+i: -factor*operator[i]/operator[-1] for i in range(order) if operator[i]}
            self.connections.append(connection)
        self.base_index[signature] = first
        self.bases.append({"program": deepcopy(program), "argument": encode_q(argument),
                           "first_jet": first, "order": order,
                           "theta_operator": [encode_q(c) for c in operator]})
        return {(first,): FIELD.one}

    def delta_monomial(self, monomial):
        if monomial not in self._monomial_derivatives:
            result = {}
            for position, jet in enumerate(monomial):
                remainder = monomial[:position]+monomial[position+1:]
                for target, c in self.connections[jet].items():
                    _accumulate(result, tuple(sorted(remainder+(target,))), c)
            self._monomial_derivatives[monomial] = result
        return self._monomial_derivatives[monomial]

    def delta(self, poly):
        result = {}
        for monomial, coefficient in poly.items():
            _accumulate(result, monomial, XX*coefficient.diff(FIELD.gens[0]))
            for target, value in self.delta_monomial(monomial).items():
                _accumulate(result, target, coefficient*value)
        return result

    def compile(self, program, argument=XX):
        validate(program)
        signature = (key(program), argument)
        if signature in self._compiled:
            return self._compiled[signature].copy()
        op = program["op"]
        if op in ("hyper", "ode"):
            result = self.seed(program, argument)
        elif op == "poly":
            value = _poly(program["coefficients"], argument)
            result = {(): value} if value else {}
        elif op == "scale":
            result = scale(self.compile(program["child"], argument), _q(program["factor"]))
        elif op in ("add", "mul"):
            left, right = self.compile(program["left"], argument), self.compile(program["right"], argument)
            result = add(left, right) if op == "add" else multiply(left, right)
        elif op == "diff":
            factor = XX*argument.diff(FIELD.gens[0])
            if not factor:
                raise ValueError("constant argument in derivative compilation")
            result = scale(self.delta(self.compile(program["child"], argument)), 1/factor)
        else:
            transformed = _poly(program["numerator"], argument)/_poly(program["denominator"], argument)
            result = self.compile(program["child"], transformed)
        if len(result) > 4096:
            raise SharedModuleBudget("compiled polynomial budget")
        self._compiled[signature] = result
        return result.copy()

    def closure(self, observation):
        seen, pending = set(observation), list(sorted(observation))
        while pending:
            monomial = pending.pop()
            for target in self.delta_monomial(monomial):
                if target not in seen:
                    seen.add(target)
                    pending.append(target)
            if len(seen) > self.max_states:
                raise SharedModuleBudget("shared-state closure budget")
        return sorted(seen)

    def descriptor(self, observation, states):
        return {"bases": self.bases, "states": [list(s) for s in states],
                "observation": encode_poly(observation),
                "connections": [encode_poly(self.delta_monomial(s)) for s in states]}

    def annihilating_operator(self, observation, states):
        if not observation:
            return [FIELD.one]
        rows, current = [], observation
        for order in range(len(states)+1):
            rows.append([current.get(state, FIELD.zero) for state in states])
            matrix = DomainMatrix.from_list(rows, FIELD).transpose()
            relations = matrix.nullspace().to_list()
            if relations:
                relation = relations[0]
                if not relation[-1]:
                    raise ValueError("unexpected earlier differential dependence")
                return normalize_operator(relation)
            current = self.delta(current)
        raise ValueError("finite module failed to produce an operator")

    def verify_operator(self, observation, operator):
        residual, current = {}, observation
        for coefficient in operator:
            residual = add(residual, scale(current, coefficient))
            current = self.delta(current)
        return not residual


def normalize_operator(values):
    while len(values) > 1 and not values[-1]:
        values = values[:-1]
    if not any(values):
        raise ValueError("zero differential operator")
    common = values[0].denom.ring.one
    for value in values:
        common = common.lcm(value.denom)
    polys = [common.exquo(value.denom)*value.numer for value in values]
    divisor = next(p for p in polys if p)
    for poly in polys:
        divisor = divisor.gcd(poly)
    polys = [p.exquo(divisor) for p in polys]
    leading = polys[-1].LC
    return [FIELD.from_sympy(p.quo_ground(leading).as_expr()) for p in polys]


def initial_bound(operator):
    if any(any(m[0] != 0 for m in value.denom) for value in operator):
        raise ValueError("nonzero polynomial Euler operator required")
    terms = [(j, powers[0], sp.Rational(str(c))/sp.Rational(str(value.denom[(0,)])))
             for j, value in enumerate(operator) for powers, c in value.numer.items() if c]
    if not terms:
        raise ValueError("nonzero polynomial Euler operator required")
    valuation = min(k for _, k, _ in terms)
    diagonal = sp.Poly(sum(sp.Rational(str(c))*N**j for j, k, c in terms if k == valuation), N, domain=sp.QQ)
    if diagonal.is_zero:
        raise ValueError("zero recurrence diagonal")
    roots = sorted(int(r) for r in diagonal.ground_roots() if r.is_Integer and r >= 0)
    return {"valuation": valuation, "diagonal_coefficients": list(map(str, reversed(diagonal.all_coeffs()))),
            "nonnegative_integer_roots": roots, "required_initial_coefficients": max([0]+[r+1 for r in roots])}


def certify_equal_shared(left, right, max_states=96, max_initial=128):
    if type(max_initial) is not int or not 0 <= max_initial <= 256:
        raise ValueError("invalid initial coefficient budget")
    module = SharedModule(max_states)
    observation = add(module.compile(left), scale(module.compile(right), -FIELD.one))
    states = module.closure(observation)
    operator = module.annihilating_operator(observation, states)
    if not module.verify_operator(observation, operator):
        raise ValueError("shared differential operator failed its action check")
    bound = initial_bound(operator)
    count = bound["required_initial_coefficients"]
    if count > max_initial:
        return {"status": "initial_coefficient_budget", "bound": bound, "states": len(states)}
    initial_left, initial_right = coefficients(left, count), coefficients(right, count)
    if initial_left != initial_right:
        return {"status": "refuted", "first_mismatch": next(i for i in range(count) if initial_left[i] != initial_right[i]),
                "states": len(states)}
    record = {"schema": SCHEMA, "status": "exact_shared_module_equality", "left": deepcopy(left),
        "right": deepcopy(right), "module": module.descriptor(observation, states),
        "operator": [encode_q(c) for c in operator], "uniqueness": bound,
        "initial_coefficients": list(map(str, initial_left)), "scope": SCOPE,
        "special_value_proved": False, "novelty_established": False}
    record["sha256"] = sha256(key(record).encode()).hexdigest()
    return record


def replay_shared_certificate(record):
    try:
        fields = {"schema", "status", "left", "right", "module", "operator", "uniqueness", "initial_coefficients",
                  "scope", "special_value_proved", "novelty_established", "sha256"}
        if (set(record) != fields or record["schema"] != SCHEMA or record["status"] != "exact_shared_module_equality"
                or record["scope"] != SCOPE or record["special_value_proved"] is not False
                or record["novelty_established"] is not False
                or record["sha256"] != sha256(key({k: v for k, v in record.items() if k != "sha256"}).encode()).hexdigest()):
            return False
        module = SharedModule(256)
        observation = add(module.compile(record["left"]), scale(module.compile(record["right"]), -FIELD.one))
        states = module.closure(observation)
        if module.descriptor(observation, states) != record["module"]:
            return False
        if not isinstance(record["operator"], list) or not 1 <= len(record["operator"]) <= 257:
            return False
        operator = [decode_q(c) for c in record["operator"]]
        if operator != normalize_operator(operator) or not module.verify_operator(observation, operator):
            return False
        bound = initial_bound(operator)
        count = bound["required_initial_coefficients"]
        if bound != record["uniqueness"] or count > 256:
            return False
        # Replay initial data with the independent reference coefficient provider.
        from math_os_prototype.holonomic_route_discovery import coefficients as reference
        actual = reference(record["left"], count)
        return actual == reference(record["right"], count) and list(map(str, actual)) == record["initial_coefficients"]
    except (ValueError, TypeError, KeyError, ZeroDivisionError, sp.PolynomialError):
        return False
