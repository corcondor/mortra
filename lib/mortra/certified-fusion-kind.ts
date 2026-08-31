export type CertifiedFusionKind = 'structural' | 'proof_composition'

const PROOF_COMPOSITION_FAMILIES = new Set([
  'certified.answer_pair_companion_recurrence',
])

export function certifiedFusionKind(familyId?: string | null): CertifiedFusionKind | null {
  if (!familyId?.startsWith('certified.')) return null
  return PROOF_COMPOSITION_FAMILIES.has(familyId) ? 'proof_composition' : 'structural'
}
