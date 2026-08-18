// Mirrors backend/schemas.py. Hand-written rather than generated: the surface
// is three endpoints wide, and a codegen step would cost more than it saves.

export interface Account {
  id: string
  email: string
  /** Unipile's sync status: OK, CREDENTIALS, ERROR, ... */
  status: string
}

export interface ScanError {
  mailbox: string
  subject: string
  detail: string
}

export interface ScanJob {
  id: string
  status: 'running' | 'done' | 'error'
  mailboxes: string[]
  messages_scanned: number
  invoices_found: number
  /** What `messages_scanned` counts towards. Climbs as the scan reaches each
   *  further mailbox, so it is a denominator that grows, not a fixed target. */
  messages_total: number
  invoices_new: number
  errors: ScanError[]
  /** Set only when the scan itself failed, as opposed to individual documents. */
  detail: string | null
}

/** The fields invoice2data extracted. Everything is optional — recognition is
 *  per-issuer, and templates differ in how much they capture, so the detail
 *  panel renders only what is actually present. */
export interface InvoiceFields {
  issuer?: string
  amount?: number
  currency?: string
  date?: string
  invoice_number?: string
  amount_untaxed?: number
  amount_tax?: number
  vat_number?: string
  company_number?: string
  reference?: string
  service_start?: string
}

export interface InvoiceEmail {
  subject?: string
  mailbox?: string
  from?: { name?: string | null; address?: string | null } | null
  date?: string
}

/** The vendor's own file, when the mail carried one. Null when the receipt
 *  only ever existed as an email body. */
export interface InvoiceDocument {
  file: string
  origin: string
  bytes: number
}

/** One stored invoice: the payload as filed, plus its id and sort key. */
export interface Invoice {
  id: string
  issued_on: string | null
  invoice: InvoiceFields
  email?: InvoiceEmail
  document?: InvoiceDocument | null
}

export interface InvoicePage {
  items: Invoice[]
  total: number
}

/** What POST /shares hands back. `owner_key` is returned exactly once and is
 *  what marks this browser as the link's owner; it is kept in localStorage and
 *  never sent anywhere but back to this API. */
export interface ShareCreated {
  token: string
  url: string
  owner_key: string
  owner_name: string
  expires_at: string
  invoices: number
  period: string
}

/** One line of the manifest. Everything is optional because half of it is
 *  empty on a real batch: a receipt read out of an email body carries no
 *  invoice number, no VAT split and no document. */
export interface ShareItem {
  id: string
  vendor: string | null
  invoice_number: string | null
  /** The name this document has inside the zip, or null when there is none. */
  file: string | null
  issued_on: string | null
  currency: string | null
  amount_net: string | null
  amount_vat: string | null
  amount_total: string | null
}

export interface ShareManifest {
  token: string
  owner_name: string
  owner_email: string
  created_at: string
  expires_at: string
  filename: string
  period: string
  invoices: number
  documents: number
  bytes: number
  /** The subject the send will use, quoted by the composer rather than
   *  assembled a second time here. */
  subject: string
  items: ShareItem[]
}

/** The body of the 410. A link that has lapsed is not a link that never
 *  existed, so it can still say who shared it and when it stopped. */
export interface ExpiredShare {
  message: string
  owner_name: string
  owner_email: string
  created_at: string
  expires_at: string
}
