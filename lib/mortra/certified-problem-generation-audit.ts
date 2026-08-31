import type {
  CertifiedFusionCard,
  CertifiedFusionParent,
  CertifiedProblemGenerationAudit,
  CertifiedProblemGenerationTraceNode,
} from './certified-fusion'

function unique(values: string[]): string[] {
  return [...new Set(values)].sort()
}

function normalizeStatement(value: string): string {
  return value
    .normalize('NFKC')
    .replace(/\\(?:left|right)/g, '')
    .replace(/\\text\s*\{([^{}]*)\}/g, '$1')
    .replace(/[\s{}$。、，,.!?！？；;:：]/g, '')
    .toLowerCase()
}

function buildTrace(card: CertifiedFusionCard): CertifiedProblemGenerationTraceNode[] {
  const nodes: CertifiedProblemGenerationTraceNode[] = []
  const assignmentNodeByPort = new Map<string, string>()

  for (const assignment of card.fusion_derivation.assignments) {
    const id = `premise:${assignment.parentId}:${assignment.portId}`
    assignmentNodeByPort.set(assignment.portId, id)
    nodes.push({
      id,
      kind: 'premise',
      label: `${assignment.parentId} supplies ${assignment.portId}`,
      dependsOn: [],
      parentIds: [assignment.parentId],
    })
  }

  card.fusion_derivation.intermediatePropositions.forEach((proposition, index) => {
    const id = `derived:${proposition.parentId}:${index}`
    const parentAssignments = card.fusion_derivation.assignments
      .filter(assignment => assignment.parentId === proposition.parentId)
    const matchingAssignments = parentAssignments
      .filter(assignment => assignment.witnessSteps.includes(proposition.morphism))
    const dependencies = (matchingAssignments.length ? matchingAssignments : parentAssignments)
      .flatMap(assignment => assignmentNodeByPort.get(assignment.portId) ?? [])
    const parentPremises = unique(dependencies)
    nodes.push({
      id,
      kind: 'derived',
      label: proposition.proposition,
      dependsOn: parentPremises,
      parentIds: [proposition.parentId],
    })
  })

  for (const bridge of card.fusion_derivation.bridges) {
    const dependencies: string[] = []
    const parentIds: string[] = []
    for (const portId of bridge.consumes) {
      const premiseId = assignmentNodeByPort.get(portId)
      if (!premiseId) continue
      const premise = nodes.find(node => node.id === premiseId)
      if (!premise) continue
      parentIds.push(...premise.parentIds)
      const derived = nodes
        .filter(node => node.kind === 'derived' && node.dependsOn.includes(premiseId))
        .map(node => node.id)
      dependencies.push(...(derived.length ? derived : [premiseId]))
    }
    nodes.push({
      id: `bridge:${bridge.id}`,
      kind: 'bridge',
      label: `${bridge.witnessStep}: ${bridge.produces}`,
      dependsOn: unique(dependencies),
      parentIds: unique(parentIds),
    })
  }

  const bridgeNodes = nodes.filter(node => node.kind === 'bridge')
  const fallbackDependencies = nodes.filter(node => node.kind === 'derived').map(node => node.id)
  const goalDependencies = bridgeNodes.length ? bridgeNodes.map(node => node.id) : fallbackDependencies
  const goalParentIds = unique(
    (bridgeNodes.length ? bridgeNodes : nodes.filter(node => node.kind === 'derived'))
      .flatMap(node => node.parentIds),
  )
  const goalId = 'goal:generated-problem'
  nodes.push({
    id: goalId,
    kind: 'goal',
    label: card.structure_blueprint.structuralUniqueness.querySignature,
    dependsOn: unique(goalDependencies),
    parentIds: goalParentIds,
  })

  const obligations = (card.proof_obligations ?? []).length
    ? (card.proof_obligations ?? []).map(obligation => ({
      id: obligation.id,
      label: obligation.claim_ja,
    }))
    : card.structure_blueprint.proofCertificate.map(certificate => ({
      id: certificate.id,
      label: certificate.claim,
    }))
  for (const obligation of obligations) {
    nodes.push({
      id: `verification:${obligation.id}`,
      kind: 'verification',
      label: obligation.label,
      dependsOn: [goalId],
      parentIds: goalParentIds,
    })
  }

  return nodes
}

function tracebackNodeIds(
  trace: CertifiedProblemGenerationTraceNode[],
  startId: string,
): Set<string> {
  const byId = new Map(trace.map(node => [node.id, node]))
  const visited = new Set<string>()
  const pending = [startId]
  while (pending.length > 0) {
    const current = pending.pop()
    if (!current || visited.has(current)) continue
    const node = byId.get(current)
    if (!node) continue
    visited.add(current)
    pending.push(...node.dependsOn)
  }
  return visited
}

/**
 * Trace a generated theorem back to its indispensable parents and reject
 * one-parent playback before the card reaches the public generation path.
 */
export function auditCertifiedGeneratedProblem(
  card: CertifiedFusionCard,
  parents: CertifiedFusionParent[],
): CertifiedProblemGenerationAudit {
  const trace = buildTrace(card)
  const expectedParentIds = unique(card.parent_ids)
  const assignmentParentIds = unique(card.fusion_derivation.assignments.map(item => item.parentId))
  const goalNode = trace.find(node => node.kind === 'goal')
  const tracedNodeIds = tracebackNodeIds(trace, goalNode?.id ?? '')
  const premiseNodes = trace.filter(node => node.kind === 'premise')
  const minimalPremiseIds = premiseNodes
    .filter(node => tracedNodeIds.has(node.id))
    .map(node => node.id)
  const unusedPremiseIds = premiseNodes
    .filter(node => !tracedNodeIds.has(node.id))
    .map(node => node.id)
  const tracedParentIds = unique(
    premiseNodes
      .filter(node => tracedNodeIds.has(node.id))
      .flatMap(node => node.parentIds),
  )
  const parentById = new Map(parents.map(parent => [parent.id, parent]))

  const statedObligations = card.proof_obligations ?? []
  const hasVerifiedCertificate = statedObligations.length > 0
    ? statedObligations.every(obligation => obligation.status === 'verified')
    : card.structure_blueprint.proofCertificate.length > 0
  const exactSolvability = card.verification.exact_backend
    && card.structure_blueprint.executable
    && hasVerifiedCertificate
  const independentVerification = card.verification.independent_check
    && card.structure_blueprint.proofCertificate.length > 0
  const clauseCompleteness = expectedParentIds.every(parentId => {
    const assignments = card.fusion_derivation.assignments.filter(item => item.parentId === parentId)
    return assignments.length > 0
      && assignments.every(item => item.matchedAnchors.length > 0 && item.witnessSteps.length > 0)
      && card.fusion_derivation.intermediatePropositions.some(
        proposition => proposition.parentId === parentId && proposition.proved,
      )
  })
  const premiseMinimality = premiseNodes.length >= expectedParentIds.length
    && unusedPremiseIds.length === 0
  const allParentDependence = expectedParentIds.length >= 2
    && card.fusion_derivation.ablationPassed
    && card.structure_blueprint.structuralUniqueness.conditionAblationPassed
    && expectedParentIds.every(parentId => assignmentParentIds.includes(parentId))
    && expectedParentIds.every(parentId => tracedParentIds.includes(parentId))
  const crossParentComposition = card.fusion_derivation.bridges.some(bridge => {
    const consumedParents = unique(bridge.consumes.flatMap(portId => (
      card.fusion_derivation.assignments
        .filter(assignment => assignment.portId === portId)
        .map(assignment => assignment.parentId)
    )))
    return consumedParents.length >= 2
  })
  const normalizedStatement = normalizeStatement(card.statement_tex)
  const statementDiffersFromParents = expectedParentIds.every(parentId => {
    const parent = parentById.get(parentId)
    return parent ? normalizeStatement(parent.statement) !== normalizedStatement : false
  })
  const bridgeWitnesses = new Set(card.fusion_derivation.bridges.map(bridge => bridge.witnessStep))
  const proofStepCount = card.proof_roadmap?.length ?? card.morphism_chain.length
  const nontrivialProof = proofStepCount >= 3
    && card.morphism_chain.some(morphism => bridgeWitnesses.has(morphism))
    && card.morphism_chain.length >= 3

  const checks = {
    exactSolvability,
    independentVerification,
    clauseCompleteness,
    premiseMinimality,
    allParentDependence,
    crossParentComposition,
    statementDiffersFromParents,
    nontrivialProof,
  }
  const failures = Object.entries(checks)
    .filter(([, passed]) => !passed)
    .map(([name]) => name)
  const reversePlaybackOnly = !crossParentComposition
    || !allParentDependence
    || !premiseMinimality
    || !statementDiffersFromParents

  return {
    schema: 1,
    passed: failures.length === 0 && !reversePlaybackOnly,
    reversePlaybackOnly,
    tracedParentIds,
    minimalPremiseIds,
    unusedPremiseIds,
    proofStepCount,
    checks,
    failures,
    trace,
  }
}

export function attachCertifiedGenerationAudit(
  card: CertifiedFusionCard,
  parents: CertifiedFusionParent[],
): CertifiedFusionCard {
  return {
    ...card,
    generation_audit: auditCertifiedGeneratedProblem(card, parents),
  }
}
