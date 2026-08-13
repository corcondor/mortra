import type { SemanticId } from '../world/world-types'

export type DiagramKnowledgeStatus =
  | 'certified'
  | 'verified-instance'
  | 'conjectured'
  | 'rejected'

export type DiagramCertificate = {
  id: SemanticId
  claim: string
  status: DiagramKnowledgeStatus
  method: string
  consumed: SemanticId[]
  detail?: string
}
export type DiagramAmbiguity = {
  kind: string
  detail: string
  recoverableWith?: string[]
}

export type DiagramProvenance = {
  source: string
  sourceDigest?: string
  constructedBy: string
  constructedFrom: SemanticId[]
}

/**
 * A diagram is a typed representation contract, not a generic node-edge bag.
 * Domain implementations decide what a carrier and a legal rewrite mean.
 */
export type DiagramContract<
  Kind extends string,
  Carrier,
  Structure,
  Rewrite,
  Invariant,
> = {
  id: SemanticId
  kind: Kind
  sourceSemanticIds: SemanticId[]
  encoded: string[]
  forgotten: string[]
  carriers: Carrier[]
  structure: Structure
  legalRewrites: Rewrite[]
  invariants: Invariant[]
  ambiguities: DiagramAmbiguity[]
  certificates: DiagramCertificate[]
  provenance: DiagramProvenance
  parameters?: Record<string, string | number | boolean>
  timeline?: { step: number; semanticId: SemanticId; operation: string }[]
}

export type DiagramContractViolation = {
  kind: string
  detail: string
}

export function auditDiagramContract(
  diagram: DiagramContract<string, unknown, unknown, unknown, unknown>,
): DiagramContractViolation[] {
  const violations: DiagramContractViolation[] = []
  if (!diagram.sourceSemanticIds.length) {
    violations.push({ kind: 'missing_source', detail: '元の数学対象を参照していない' })
  }
  if (!diagram.encoded.length) {
    violations.push({ kind: 'unspecified_encoding', detail: '何を表す図か宣言されていない' })
  }
  if (!diagram.forgotten.length) {
    violations.push({ kind: 'unspecified_loss', detail: '表現で失う情報が宣言されていない' })
  }
  if (!diagram.legalRewrites.length) {
    violations.push({ kind: 'no_legal_rewrite', detail: '図上で許される操作がない' })
  }
  if (!diagram.invariants.length) {
    violations.push({ kind: 'no_invariant', detail: '書換えで保存する量がない' })
  }
  if (!diagram.certificates.some(certificate => certificate.status === 'certified')) {
    violations.push({ kind: 'uncertified_transport', detail: '意味輸送の証明書がない' })
  }
  return violations
}
