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
