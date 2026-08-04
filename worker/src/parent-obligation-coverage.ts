export type ParentObligation = {
  id: string
  label: string
}

const DISTINCTIVE_OBLIGATIONS: ReadonlyArray<{ id: string; label: string; pattern: RegExp }> = [
  { id: 'ParabolaConstraint', label: '放物線の定義・拘束', pattern: /放物線|parabola/i },
  { id: 'NormalIncidenceConstruction', label: '法線と接点の構成', pattern: /法線|normal(?:s| line)?/i },
  { id: 'LineConstraint', label: '直線上という拘束', pattern: /直線|line\s*[ℓl:]?/i },
  { id: 'ExtremumObjective', label: '最大・最小化する問い', pattern: /最大値|最小値|最大とな|最小とな|最大にせ|最小にせ|maximi[sz]e|minimi[sz]e|extrem/i },
  { id: 'MatrixStructure', label: '行列構造', pattern: /行列|matrix|pmatrix|bmatrix/i },
  { id: 'IteratedPower', label: '反復・冪作用', pattern: /\^[{]?n[}]?|\bn\s*乗|matrix power/i },
  { id: 'RecurrenceConstraint', label: '漸化式拘束', pattern: /漸化式|recurrence|recursive/i },
  { id: 'IntegralOperator', label: '積分作用素', pattern: /積分|integral|\\int/i },
  { id: 'LocusQuery', label: '軌跡の問い', pattern: /軌跡|locus/i },
]

export function extractDistinctiveParentObligations(text: string): ParentObligation[] {
  return DISTINCTIVE_OBLIGATIONS
    .filter(item => item.pattern.test(text))
    .map(({ id, label }) => ({ id, label }))
}

export function uncoveredDistinctiveObligations(text: string, consumed: Iterable<string>): ParentObligation[] {
  const consumedSet = new Set(consumed)
  return extractDistinctiveParentObligations(text).filter(item => !consumedSet.has(item.id))
}
