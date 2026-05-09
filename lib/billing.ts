export const FREE_GENERATIONS_PER_MONTH = 10
export const ADMIN_EMAIL = 'imtceed@gmail.com'

/** 今月の YYYY-MM 文字列 */
export function currentYearMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}
