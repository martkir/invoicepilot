// Presentation helpers. The API returns raw values; how they read is the
// frontend's business.

// Intl is deliberately not used here: every locale that renders the symbol as
// a suffix also switches the decimal separator to a comma, and the design uses
// a dot with a trailing symbol ("1.20 €").
const SYMBOLS: Record<string, string> = { EUR: '€', USD: '$', GBP: '£', CHF: 'CHF' }

/** "1.20 €", the amount as the dashboard shows it. A hyphen, not a blank,
 *  when there is no figure: blank reads as "we forgot to render it", a dash
 *  reads as "this invoice does not carry one". A hyphen and not an em dash,
 *  because Section 7.D bans those in visible output, data included. */
export function amount(value?: number, currency?: string): string {
  if (value === undefined || value === null) return '-'
  if (!currency) return value.toFixed(2)
  return `${value.toFixed(2)} ${SYMBOLS[currency.toUpperCase()] ?? currency}`
}

/** "42.10 €" from the strings a share manifest carries. The parser filed these
 *  as text, so they are shown as filed rather than re-rounded here. */
export function money(value: string | null, currency?: string | null): string {
  if (!value) return '-'
  const symbol = currency ? (SYMBOLS[currency.toUpperCase()] ?? currency) : ''
  return symbol ? `${value} ${symbol}` : value
}

/** "05.08.2026" from an ISO date. */
export function issued(value: string | null): string {
  if (!value) return '-'
  const [year, month, day] = value.split('-')
  return day && month && year ? `${day}.${month}.${year}` : value
}

/** "12.01.2026 to 14.08.2026" — the stretch of time the rows on screen cover.
 *  Null when not one of them carries a date, since a range of nothing is not
 *  a fact worth a line.
 *
 *  It answers the question the tally above the table cannot: "Scanned 340
 *  emails" says how much mail was read, not how far back the invoices you have
 *  actually go. Same format as the Issued column it summarises, so the two
 *  ends of the range read as two of the cells above them.
 *
 *  Both ends are taken from the dates the rows carry, not from the scan: an
 *  invoice is filed under the date it was issued, and mail from March can
 *  arrive in August. */
export function period(dates: (string | null | undefined)[]): string | null {
  // ISO dates sort as text, which is the whole reason the API sends them that
  // way rather than as anything friendlier.
  const dated = dates.filter((date): date is string => Boolean(date)).sort()
  if (dated.length === 0) return null
  const [first, last] = [dated[0], dated[dated.length - 1]]
  return first === last ? issued(first) : `${issued(first)} to ${issued(last)}`
}

/** "8 August 2026, 07:22" from an ISO timestamp. */
export function dateTime(value?: string): string {
  if (!value) return '-'
  const at = new Date(value)
  if (Number.isNaN(at.getTime())) return value
  return at.toLocaleString('en-GB', {
    day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/** "5 August 2026" from an ISO date, spelled out for the detail panel. */
export function longDate(value?: string | null): string {
  if (!value) return '-'
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

function plural(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

/** "Scanned 128 of 340 emails · 17 invoices" — a scan's tally while it is
 *  still running. It replaces the clock rather than joining it: a scan in
 *  flight is what the line is for at that moment, and the age of the last one
 *  can wait.
 *
 *  The denominator climbs as each further mailbox is listed, so "128 of 340"
 *  can become "128 of 520" mid-scan. Shown anyway: a count against a total
 *  that moves still reads as progress, where a bare count reads as a number
 *  with no end in sight. */
export function scanned(messages: number, total: number, invoices: number): string {
  const counted = total > 0 ? `${messages} of ${plural(total, 'email')}` : plural(messages, 'email')
  return `Scanned ${counted} · ${plural(invoices, 'invoice')}`
}

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

/** "84 KB" from a byte count. Decimal units, because that is what the file
 *  manager the invoice gets downloaded into will say. */
export function bytes(value: number): string {
  if (value < 1000) return `${value} B`
  const kb = value / 1000
  if (kb < 1000) return `${kb < 10 ? kb.toFixed(1) : Math.round(kb)} KB`
  const mb = kb / 1000
  return `${mb < 10 ? mb.toFixed(1) : Math.round(mb)} MB`
}
