import type { HyperMorphismSchema } from './generalization-kernel'

/**
 * Foundation-independent object syntax, following the common OpenMath/MMT
 * shape: references, variables, literals, applications and bindings.
 * Domain operations are declared symbols; they are never new kernel syntax.
 */
export type ObjectConstructor =
  | 'symbol-reference'
  | 'variable-reference'
  | 'literal'
  | 'application'
  | 'binding'

export type StructuralPrimitive =
  | 'theory'
  | 'constant-declaration'
  | 'theory-morphism'
  | 'assignment'

export type JudgmentKind =
  | 'has-type'
  | 'definitionally-equal'
  | 'provable'

export type ExecutionService =
  | 'normalize'
  | 'saturate'
  | 'solve'
  | 'synthesize'
  | 'certify'

export type KernelObject =
  | { constructor: 'symbol-reference'; uri: string }
  | { constructor: 'variable-reference'; name: string }
  | { constructor: 'literal'; value: string | number | boolean }
  | { constructor: 'application'; operator: KernelObject; arguments: KernelObject[] }
  | {
      constructor: 'binding'
      binder: KernelObject
      variables: Array<{ name: string; type: KernelObject }>
      body: KernelObject
    }

export type ApplicationObject = Extract<KernelObject, { constructor: 'application' }>

export type ConstantDeclaration = {
  primitive: 'constant-declaration'
  uri: string
  parameters: Array<{ name: string; type: KernelObject }>
  result: KernelObject
  definiens: KernelObject | null
}

export type KernelJudgment =
  | { kind: 'has-type'; term: KernelObject; type: KernelObject }
  | { kind: 'definitionally-equal'; left: KernelObject; right: KernelObject; type?: KernelObject }
  | { kind: 'provable'; proposition: KernelObject; certificate?: KernelObject }

export type KnowledgeCoreLowering = {
  theory_morphism: string
  declaration: ConstantDeclaration
  application: ApplicationObject
  judgments: KernelJudgment[]
  /** Unproved semantic obligations inherited from the legacy declaration. */
  preservation_obligations: string[]
  /** Candidate implementations, not part of mathematical identity. */
  implementation_hints: string[]
}

function symbol(uri: string): KernelObject {
  return { constructor: 'symbol-reference', uri }
}

function variable(name: string): KernelObject {
  return { constructor: 'variable-reference', name }
}

/**
 * Reifies a legacy named edge as a typed declaration and an application term.
 * This does not claim that two equally typed declarations are equal.
 */
export function lowerMorphismToKnowledgeCore(rule: HyperMorphismSchema): KnowledgeCoreLowering {
  const parameters = rule.sources.map((source, index) => ({
    name: `x${index}`,
    type: symbol(`mathos://sort/${source}`),
  }))
  const application: ApplicationObject = {
    constructor: 'application',
    operator: symbol(`mathos://morphism/${rule.name}`),
    arguments: parameters.map(parameter => variable(parameter.name)),
  }
  const result = symbol(`mathos://sort/${rule.target}`)
  return {
    theory_morphism: rule.name,
    declaration: {
      primitive: 'constant-declaration',
      uri: `mathos://morphism/${rule.name}`,
      parameters,
      result,
      definiens: null,
    },
    application,
    judgments: [{ kind: 'has-type', term: application, type: result }],
    preservation_obligations: [...new Set(rule.preserves)].sort(),
    implementation_hints: [...new Set(rule.backend)].sort(),
  }
}

/** Declared contract for collision auditing only; never an equality proof. */
export function morphismDeclaredContractKey(rule: HyperMorphismSchema): string {
  return JSON.stringify({
    sources: rule.sources,
    target: rule.target,
    preserves: [...new Set(rule.preserves)].sort(),
    backend: [...new Set(rule.backend)].sort(),
    cross_parent: rule.allows_cross_parent_fusion !== false,
  })
}

export function distinctDeclaredContracts(
  rules: readonly HyperMorphismSchema[],
): HyperMorphismSchema[] {
  const byContract = new Map<string, HyperMorphismSchema>()
  for (const rule of rules) {
    const key = morphismDeclaredContractKey(rule)
    if (!byContract.has(key)) byContract.set(key, rule)
  }
  return [...byContract.values()]
}

export const OBJECT_CONSTRUCTORS: readonly ObjectConstructor[] = [
  'symbol-reference', 'variable-reference', 'literal', 'application', 'binding',
]

export const STRUCTURAL_PRIMITIVES: readonly StructuralPrimitive[] = [
  'theory', 'constant-declaration', 'theory-morphism', 'assignment',
]

export const JUDGMENT_KINDS: readonly JudgmentKind[] = [
  'has-type', 'definitionally-equal', 'provable',
]

export const EXECUTION_SERVICES: readonly ExecutionService[] = [
  'normalize', 'saturate', 'solve', 'synthesize', 'certify',
]
