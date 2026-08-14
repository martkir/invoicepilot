// The only place fetch() is called. Base URL, error shape and JSON decoding
// live here so components deal in data and never in transport.

import type { Account, InvoicePage, ScanJob } from './types'

const BASE = '/api'

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
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
    // the body is not JSON at all (a proxy error, say).
    let detail = response.statusText
    try {
      detail = (await response.json())?.detail ?? detail
    } catch {
      /* keep statusText */
    }
    throw new ApiError(detail, response.status)
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

export const startScan = () =>
  call<ScanJob>('/scan', { method: 'POST', body: JSON.stringify({ limit: 20 }) })

export const getScan = (id: string) => call<ScanJob>(`/scan/${id}`)
