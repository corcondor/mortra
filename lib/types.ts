export type Difficulty = 'A' | 'B' | 'C' | 'D'
export type RatingStatus = 'pending' | 'selected' | 'rejected' | 'posted'

export interface Problem {
  id: string
  topic_a: string
  topic_b: string | null
  variation: number
  statement: string
  answer: string | null
  difficulty: Difficulty | null
  solution: string | null
  surprise: number
  minimality: number
  connection: number
  inevitability: number
  diff_cal: number
  total: number
  inspiration: string | null
  meta: string | null
  generation: number
  parent_ids: string[]
  source_file: string | null
  created_at: string
}

export interface Rating {
  problem_id: string
  status: RatingStatus
  x_posted: boolean
  note: string | null
  updated_at: string
}

export interface ProblemWithRating extends Problem {
  rating?: Rating | null
}

export const DIFFICULTY_LABEL: Record<string, string> = {
  A: '超難', B: '難', C: '標準', D: '基礎',
}

export const DIFFICULTY_COLOR: Record<string, string> = {
  A: 'text-apple-gold   border-apple-gold/30   bg-apple-gold/10',
  B: 'text-apple-purple border-apple-purple/30 bg-apple-purple/10',
  C: 'text-apple-blue   border-apple-blue/30   bg-apple-blue/10',
  D: 'text-apple-green  border-apple-green/30  bg-apple-green/10',
}

export const TOPIC_EMOJI: Record<string, string> = {
  analysis:      '∫',
  algebra:       '⊕',
  geometry:      '△',
  number_theory: '#',
  combinatorics: '♦',
  probability:   '◎',
  complex:       'ℂ',
  recurrence:    '↻',
  polynomial:    'χ',
  trigonometry:  '∿',
  inequality:    '≶',
  integral:      '∫',
  limit:         '→',
}
