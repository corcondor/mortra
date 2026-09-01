export type PublicWorkspaceMode = 'auto' | 'solve' | 'fusion' | 'draw'

export type PublicParentSlot = 'a' | 'b'

export type PublicWorkspaceResolution = {
  taskMode: 'solve' | 'fusion'
  inputSlots: PublicParentSlot[]
  command: '/try' | '/solve' | '/combine' | '/draw'
  error: 'empty' | 'needs_two' | null
}

export function resolvePublicWorkspace(
  mode: PublicWorkspaceMode,
  parentA: string,
  parentB: string,
): PublicWorkspaceResolution {
  const inputSlots: PublicParentSlot[] = []
  if (parentA.trim()) inputSlots.push('a')
  if (parentB.trim()) inputSlots.push('b')

  if (inputSlots.length === 0) {
    return {
      taskMode: 'solve',
      inputSlots,
      command: mode === 'draw'
        ? '/draw'
        : mode === 'fusion'
          ? '/combine'
          : mode === 'solve'
            ? '/solve'
            : '/try',
      error: 'empty',
    }
  }

  if (mode === 'fusion') {
    return {
      taskMode: 'fusion',
      inputSlots,
      command: '/combine',
      error: inputSlots.length < 2 ? 'needs_two' : null,
    }
  }

  if (mode === 'auto' && inputSlots.length === 2) {
    return {
      taskMode: 'fusion',
      inputSlots,
      command: '/combine',
      error: null,
    }
  }

  return {
    taskMode: 'solve',
    inputSlots: [inputSlots[0]],
    command: mode === 'draw' ? '/draw' : '/solve',
    error: null,
  }
}
