"""Bounded rational nullspace using FLINT, checked against the original matrix."""

from flint import fmpq_mat
import sympy as sp


def nullspace_rows(matrix):
    rows, columns = matrix.shape
    if not 0 <= rows <= 512 or not 0 <= columns <= 176:
        raise ValueError("rational matrix exceeds search budget")
    if any(not value.is_Rational for value in matrix):
        raise ValueError("matrix must have rational entries")
    if columns == 0:
        return sp.zeros(0, 0)
    if rows == 0:
        return sp.eye(columns)
    original = fmpq_mat(rows, columns, [str(value) for value in matrix])
    reduced, rank = original.rref()
    pivots = [next(j for j in range(columns) if reduced[i, j]) for i in range(rank)]
    free = [j for j in range(columns) if j not in pivots]
    basis = fmpq_mat(len(free), columns)
    for i, column in enumerate(free):
        basis[i, column] = 1
        for row, pivot in enumerate(pivots):
            basis[i, pivot] = -reduced[row, column]
    # RREF fixes the free columns to an identity matrix; also check annihilation.
    if original*basis.transpose() != fmpq_mat(rows, len(free)):
        raise ValueError("nullspace residual failed exact verification")
    return sp.Matrix(len(free), columns,
                     [sp.Rational(str(basis[i, j])) for i in range(len(free)) for j in range(columns)])
