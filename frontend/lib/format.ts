/** Formats a Decimal-as-string amount from the backend as INR currency. */
export function money(value: string | number): string {
  const amount = typeof value === 'string' ? Number(value) : value
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(amount)
}

/** snake_case backend status/severity values -> "snake case" for display. */
export function pretty(value: string): string {
  return value.replaceAll('_', ' ')
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  return new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}
