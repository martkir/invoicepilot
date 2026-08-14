// Presentation helpers. The API returns raw values; how they read is the
// frontend's business.

// Intl is deliberately not used here: every locale that renders the symbol as
// a suffix also switches the decimal separator to a comma, and the design uses
// a dot with a trailing symbol ("1.20 €").
const SYMBOLS: Record<string, string> = { EUR: '€', USD: '$', GBP: '£', CHF: 'CHF' }

/** "1.20 €" — the amount as the dashboard shows it. */
export function amount(value?: number, currency?: string): string {
  if (value === undefined || value === null) return '—'
  if (!currency) return value.toFixed(2)
  return `${value.toFixed(2)} ${SYMBOLS[currency.toUpperCase()] ?? currency}`
}

/** "05.08.2026" from an ISO date. */
export function issued(value: string | null): string {
  if (!value) return '—'
  const [year, month, day] = value.split('-')
  return day && month && year ? `${day}.${month}.${year}` : value
}

/** "8 August 2026, 07:22" from an ISO timestamp. */
export function dateTime(value?: string): string {
  if (!value) return '—'
  const at = new Date(value)
  if (Number.isNaN(at.getTime())) return value
  return at.toLocaleString('en-GB', {
    day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/** "5 August 2026" from an ISO date, spelled out for the detail panel. */
export function longDate(value?: string | null): string {
  if (!value) return '—'
  const on = new Date(value)
  if (Number.isNaN(on.getTime())) return value
  return on.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

/** Two-letter mark for the vendor logo: "Bolt Operations OÜ" -> "Bo".
 *  The first two letters of the name, not one letter per word — that is what
 *  the design used ("Am" for Amazon, "Fi" for Figma). */
export function initials(name: string): string {
  const clean = name.trim()
  if (!clean) return '?'
  return clean[0].toUpperCase() + (clean[1] ?? '').toLowerCase()
}

// There is deliberately no per-vendor logo colour. A palette of brand fills is
// a palette of accents, and the design system allows exactly one; the vendor is
// identified by its name, in the cell beside the mark.

/** "just now", "3 min ago" — the age of the last successful scan. */
export function relative(since: number): string {
  const seconds = Math.round((Date.now() - since) / 1000)
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`
  const days = Math.round(hours / 24)
  return `${days} ${days === 1 ? 'day' : 'days'} ago`
}
