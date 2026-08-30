declare module 'react-katex' {
  import type { ComponentType, ReactNode } from 'react'

  type MathProps = {
    children?: string
    math?: string
    errorColor?: string
    renderError?: (error: Error) => ReactNode
    settings?: Record<string, unknown>
  }

  export const BlockMath: ComponentType<MathProps>
  export const InlineMath: ComponentType<MathProps>
}
