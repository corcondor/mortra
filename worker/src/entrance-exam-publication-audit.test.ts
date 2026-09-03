import assert from 'node:assert/strict'
import test from 'node:test'

import { auditEntranceExamPublication } from './entrance-exam-publication-audit'

test('rejects a resultant proof from the entrance-exam publication path', () => {
  const audit = auditEntranceExamPublication({
    statement_tex: String.raw`方程式 \(f(x)=0\), \(g(x)=0\) の根の差を根にもつ多項式を求めよ。`,
    answer_tex: String.raw`\(P(z)=z^4-10z^2+1\)`,
    solution_tex: String.raw`二式から根を消去するため \[R(z)=\operatorname{Res}_x(f(x),g(x-z))\] とおく。終結式を展開して \[P(z)=z^4-10z^2+1\] を得る。したがってこれが答えである。`,
  })

  assert.equal(audit.passed, false)
  assert.ok(audit.errors.some(error => error.includes('resultant')))
})

test('accepts an exact recurrence and congruence proof written in school mathematics', () => {
  const audit = auditEntranceExamPublication({
    statement_tex: String.raw`正の整数 \(n\) に対して数列 \(u_n\) を定める。\(1997\mid u_n\) となる \(n\) を求めよ。`,
    answer_tex: String.raw`\(n=499+998k\quad(k=0,1,2,\ldots)\)`,
    solution_tex: String.raw`二つの共役な数を \(X,Y\) とおくと \(X+Y=10,XY=1\) である。よって
      \[u_{n+2}=10u_{n+1}-u_n,\qquad u_0=2,\quad u_1=10\]
      を得る。法 \(1997\) で \(316^2\equiv6\) だから、\(a=637\) とおくと \(a^{-1}\equiv1370\) である。数列 \(a^n+a^{-n}\) は同じ初期値と漸化式をもつので
      \[u_n\equiv a^n+a^{-n}\pmod{1997}\]
      である。繰り返し二乗法から \(a\) の位数は \(1996\) である。したがって \(u_n\equiv0\) は \(2n\equiv998\pmod{1996}\) と同値であり、よって \(n=499+998k\) を得る。`,
  })

  assert.equal(audit.passed, true, audit.errors.join('; '))
})
