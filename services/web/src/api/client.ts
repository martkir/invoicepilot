// The only place fetch() is called. Base URL, error shape and JSON decoding
// live here so components deal in data and never in transport.

import type { Account, InvoicePage, ScanJob, ShareCreated, ShareManifest } from './types'

const BASE = '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** The `detail` as it arrived, when it is not a plain string. An expired
     *  share answers 410 with the owner and the two dates in there, which is
     *  what lets that page name a person rather than say "gone". */
    readonly detail?: unknown,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'content-type': 'application/json', ...init?.headers },
  })

  if (!response.ok) {
    // FastAPI reports failures as {detail}; fall back to the status text when
    // the body is not JSON at all (a proxy error, say). `detail` is a string
    // on every route but the expired share, which answers with an object.
    let message = response.statusText
    let detail: unknown
    try {
      detail = (await response.json())?.detail
      if (typeof detail === 'string') message = detail
    } catch {
      /* keep statusText */
    }
    throw new ApiError(message, response.status, detail)
  }
  // DELETE answers 204 with no body; asking for JSON there would throw.
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const getAccounts = () => call<Account[]>('/accounts')
export const connectAccount = () => call<{ url: string }>('/accounts/connect', { method: 'POST' })
export const disconnectAccount = (id: string) =>
  call<void>(`/accounts/${encodeURIComponent(id)}`, { method: 'DELETE' })
export const getInvoices = () => call<InvoicePage>('/invoices')

/** Where the browser can load an invoice's document from. Not fetched through
 *  `call` — it is a PDF for an <iframe>, not JSON. */
export const documentUrl = (id: string) => `${BASE}/invoices/${encodeURIComponent(id)}/document`

/** No body: how much mail a scan covers is whatever has arrived since the
 *  mailbox was last scanned through, which only the server knows. */
export const startScan = () => call<ScanJob>('/scan', { method: 'POST' })

export const getScan = (id: string) => call<ScanJob>(`/scan/${id}`)

// ------------------------------------------------------------------ shares --
// Everything under /s/{token} is reachable by anyone holding the link. The two
// routes that are not — renaming and sending — carry the owner key from
// localStorage in their body.

/** Mint a link. No ids shares everything, which is what the table's own
 *  download does when nothing is ticked. */
export const createShare = (invoiceIds?: string[], ownerName?: string) =>
  call<ShareCreated>('/shares', {
    method: 'POST',
    body: JSON.stringify({ invoice_ids: invoiceIds?.length ? invoiceIds : null, owner_name: ownerName }),
  })

export const getShare = (token: string) => call<ShareManifest>(`/s/${encodeURIComponent(token)}`)

export const renameShare = (token: string, ownerName: string, ownerKey: string) =>
  call<void>(`/s/${encodeURIComponent(token)}`, {
    method: 'PATCH',
    body: JSON.stringify({ owner_name: ownerName, owner_key: ownerKey }),
  })

export const sendShare = (token: string, to: string, fromAccountId: string, ownerKey: string) =>
  call<void>(`/s/${encodeURIComponent(token)}/email`, {
    method: 'POST',
    body: JSON.stringify({ to, from_account_id: fromAccountId, owner_key: ownerKey }),
  })

/** URLs the browser loads directly rather than through `call`: a zip it saves,
 *  an image it renders, and the mail document the composer frames. */
export const shareZipUrl = (token: string) => `${BASE}/s/${encodeURIComponent(token)}/zip`
export const shareThumbUrl = (token: string, invoiceId: string) =>
  `${BASE}/s/${encodeURIComponent(token)}/thumb/${encodeURIComponent(invoiceId)}`
export const shareMailUrl = (token: string) => `${BASE}/s/${encodeURIComponent(token)}/email/preview`
