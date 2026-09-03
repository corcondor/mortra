import {
  auditPublicationContent,
  type PublicationMathArtifact,
} from './publication-content-audit'

export type EntranceExamPublicationAudit = {
  passed: boolean
  errors: string[]
  audience: 'japanese-upper-secondary'
}

const ADVANCED_PUBLIC_METHODS: Array<readonly [RegExp, string]> = [
  [/\\operatorname\s*\{?Res\}?|終結式|resultant/i, 'resultant elimination'],
  [/Sylvester|シルベスター/i, 'Sylvester determinant'],
  [/Gr[oö]bner|グレブナー/i, 'Groebner basis'],
  [/fiber\s*product|ファイバー積/i, 'fiber product'],
  [/Galois|ガロア|体の自己同型/i, 'Galois theory'],
  [/固有値|eigenvalue/i, 'eigenvalue argument'],
]

/**
 * Publication gate for problems advertised as Japanese entrance-exam style.
 * Internal certificates may use stronger mathematics; the visible statement
 * and proof must remain exact, self-contained, and readable with secondary
 * school algebra and elementary number theory.
 */
export function auditEntranceExamPublication(
  artifact: PublicationMathArtifact,
): EntranceExamPublicationAudit {
  const base = auditPublicationContent(artifact)
  const errors = [...base.errors]
  const visible = `${artifact.statement_tex}\n${artifact.solution_tex}`

  for (const [pattern, label] of ADVANCED_PUBLIC_METHODS) {
    if (pattern.test(visible)) errors.push(`visible proof requires ${label}`)
  }
  if (/\d+\.\d+/.test(artifact.answer_tex)) {
    errors.push('answer contains a decimal approximation instead of an exact value')
  }
  if (artifact.statement_tex.length > 900) {
    errors.push('statement is too long for the entrance-exam publication profile')
  }
  if (artifact.solution_tex.length < 320) {
    errors.push('solution is too short to expose a reproducible argument')
  }
  if (/(^|[^\\A-Za-z])(?:qquad|quad|pmod|equiv|operatorname)(?=[\s{])/m.test(visible)) {
    errors.push('visible mathematics contains a TeX command with a missing backslash')
  }
  if (!/(?:したがって|従って|よって)/.test(artifact.solution_tex)) {
    errors.push('solution does not state a visible logical conclusion')
  }
  const displayedRelations = artifact.solution_tex.match(/\\\[|\\begin\{aligned\}|\\begin\{array\}/g)?.length ?? 0
  if (displayedRelations < 2) {
    errors.push('solution does not show enough intermediate mathematical relations')
  }

  return {
    passed: errors.length === 0,
    errors: [...new Set(errors)],
    audience: 'japanese-upper-secondary',
  }
}
