import type { DiscoveryParent } from './parent-conditioned-discovery'

export type SymbolicPowerRelation = {
  parentId: string
  source: string
  variable: string
  degreeSymbol: string
  rhs: bigint
}

/**
 * Elaborate a symbolic finite power orbit from the current statement.
 *
 * This is evidence for a CyclicGroup input only when the relation itself is
 * present and has a nonzero right-hand side. Merely mentioning roots, an
 * orbit, or a sum is intentionally insufficient.
 */
export function extractSymbolicPowerRelation(
  parent: DiscoveryParent,
): SymbolicPowerRelation | null {
  const statement = parent.statement ?? ''
  const relation = statement.match(
    /([A-Za-z])\s*\^\s*(?:\{\s*)?([A-Za-z])(?:\s*\})?\s*=\s*([+-]?\d+)/,
  )
  if (!relation) return null
  const rhs = BigInt(relation[3])
  if (rhs === 0n) return null
  return {
    parentId: String(parent.id ?? 'power-relation-parent'),
    source: `${relation[1]}^{${relation[2]}}=${rhs}`,
    variable: relation[1],
    degreeSymbol: relation[2],
    rhs,
  }
}
