import { createHash } from 'node:crypto'

import type { DiscoveryParent } from './parent-conditioned-discovery'

export const CAPABILITY_ORIGINS = [
  'synthesized_proof_program',
  'synthesized_linear_program',
  'synthesized_expression_program',
  'registered_parameterized_morphism',
  'primitive_exact_operation',
  'verified_backend_execution',
] as const

export type CapabilityOrigin = typeof CAPABILITY_ORIGINS[number]

type RuntimeCertificateInput = {
  origin: 'synthesized_proof_program' | 'synthesized_linear_program' | 'synthesized_expression_program'
  parents: readonly DiscoveryParent[]
  generatedProgram: unknown
  checks: readonly string[]
  cacheRole?: 'not_consulted' | 'duplicate_exclusion_only'
}

type RegisteredCertificateInput = {
  parents: readonly DiscoveryParent[]
  program: unknown
  checks: readonly string[]
}

function sha256(value: unknown): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex')
}

function parentPayload(parents: readonly DiscoveryParent[]) {
  return parents.map(parent => ({
    id: String(parent.id),
    statement: parent.statement ?? '',
  }))
}

export function certificateValueSha256(value: unknown): string {
  return sha256(value)
}

export function certificateParentSha256(parents: readonly DiscoveryParent[]): string {
  return sha256(parentPayload(parents))
}

export function runtimeSynthesisCertificate(input: RuntimeCertificateInput): Record<string, unknown> {
  return {
    schema: 'mortra.runtime-synthesis.v1',
    verified: true,
    capability_origin: input.origin,
    registered_composite_used: false,
    composite_cache_role: input.cacheRole ?? 'not_consulted',
    input_parent_sha256: certificateParentSha256(input.parents),
    generated_program_sha256: certificateValueSha256(input.generatedProgram),
    generated_program: input.generatedProgram,
    checks: [...input.checks],
  }
}

export function registeredMorphismCertificate(input: RegisteredCertificateInput): Record<string, unknown> {
  return {
    schema: 'mortra.registered-morphism-replay.v1',
    verified: true,
    capability_origin: 'registered_parameterized_morphism',
    registered_composite_used: true,
    composite_cache_role: 'registered_parameterized_schema',
    input_parent_sha256: certificateParentSha256(input.parents),
    instantiated_program_sha256: certificateValueSha256(input.program),
    instantiated_program: input.program,
    checks: [...input.checks],
  }
}

export function capabilityOrigin(certificate: Record<string, unknown> | undefined): CapabilityOrigin | null {
  if (!certificate || certificate.verified !== true) return null
  const origin = certificate.capability_origin
  return typeof origin === 'string' && (CAPABILITY_ORIGINS as readonly string[]).includes(origin)
    ? origin as CapabilityOrigin
    : null
}

export function isRuntimeSynthesisCertificate(certificate: Record<string, unknown> | undefined): boolean {
  const origin = capabilityOrigin(certificate)
  if (origin !== 'synthesized_proof_program' &&
      origin !== 'synthesized_linear_program' &&
      origin !== 'synthesized_expression_program') return false
  return certificate?.registered_composite_used === false &&
    typeof certificate.generated_program_sha256 === 'string'
}
