import { Fragment, useCallback, useState } from 'react'
import type { ReactNode } from 'react'

import { documentUrl } from '../api/client'
import type { Invoice } from '../api/types'
import { InvoiceDetail } from './InvoiceDetail'
import { Toast } from './Toast'
import { amount, initials, issued } from '../lib/format'
import { Download, Expand, Eye, Refresh, SortAsc, SortDesc } from './Icons'

interface Props {
  invoices: Invoice[]
  loading: boolean
  scanning: boolean
  scanLabel: string
  lastUpdate: string
  onUpdate: () => void
  selected: Set<string>
  onToggle: (id: string) => void
  onToggleAll: () => void
}

export function InvoiceTable({
  invoices,
  loading,
  scanning,
  scanLabel,
  lastUpdate,
  onUpdate,
  selected,
  onToggle,
  onToggleAll,
}: Props) {
  // Which row is open. One at a time: two expanded rows and the list stops
  // being a list. Local state — nothing outside the table cares.
  const [expanded, setExpanded] = useState<string | null>(null)
  const toggleExpanded = (id: string) => setExpanded((current) => (current === id ? null : id))

  // Some invoices have no document to download. The control stays fully
  // enabled and says so when used, rather than being greyed out and leaving
  // you to guess why.
  const [notice, setNotice] = useState<ReactNode>(null)
  const dismiss = useCallback(() => setNotice(null), [])

  const allChecked = invoices.length > 0 && selected.size === invoices.length
  const someChecked = selected.size > 0 && selected.size < invoices.length

  return (
    <section className="card">
      <div className="table-head">
        <div className="table-title">
          Invoices <em id="doc-count">{invoices.length} documents</em>
        </div>
        <div className="tools">
          <span className="last-update">{lastUpdate}</span>
          <div className="tool-divider"></div>
          <button className="update-btn" data-busy={scanning} onClick={onUpdate} disabled={scanning}>
            <Refresh />
            <span>{scanLabel}</span>
          </button>
          <div className="tool-divider"></div>
          <button className="icon-btn" aria-label="Download selected">
            <Download />
          </button>
          <button className="icon-btn" aria-label="Expand table">
            <Expand />
          </button>
        </div>
      </div>

      <table>
        <thead>
          <tr>
            <th className="col-check">
              <input
                type="checkbox"
                aria-label="Select all invoices"
                checked={allChecked}
                ref={(node) => {
                  if (node) node.indeterminate = someChecked
                }}
                onChange={onToggleAll}
              />
            </th>
            <th>Vendor</th>
            <th className="col-amount sortable">
              <button>
                Amount <SortAsc />
              </button>
            </th>
            <th className="col-issued sortable sorted">
              <button>
                Issued <SortDesc />
              </button>
            </th>
            <th className="col-actions">Actions</th>
          </tr>
        </thead>
        <tbody id="rows">
          {invoices.map((item) => {
            const vendor = item.invoice.issuer ?? 'Unknown vendor'
            const isOpen = expanded === item.id
            return (
              <Fragment key={item.id}>
              <tr
                className={[selected.has(item.id) && 'selected', isOpen && 'is-open']
                  .filter(Boolean)
                  .join(' ')}
                onClick={() => toggleExpanded(item.id)}
              >
                {/* Selecting is not viewing, so the checkbox must not open the row. */}
                <td className="col-check" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    aria-label={`Select ${vendor} invoice`}
                    checked={selected.has(item.id)}
                    onChange={() => onToggle(item.id)}
                  />
                </td>
                <td>
                  <div className="vendor">
                    <span className="vendor-logo">{initials(vendor)}</span>
                    <span>
                      <span className="vendor-name">{vendor}</span>
                    </span>
                  </div>
                </td>
                <td className="col-amount">{amount(item.invoice.amount, item.invoice.currency)}</td>
                <td className="col-issued">{issued(item.issued_on)}</td>
                <td className="col-actions">
                  <div className="row-actions">
                    <button
                      className="icon-btn"
                      aria-label={isOpen ? `Hide ${vendor} invoice` : `Preview ${vendor} invoice`}
                      aria-expanded={isOpen}
                    >
                      <Eye />
                    </button>
                    {/* An anchor, not a button: the browser handles the save,
                        so there is no blob to build or revoke. Disabled when the
                        invoice has no document — the endpoint would 404. */}
                    {item.document ? (
                      <a
                        className="icon-btn"
                        href={documentUrl(item.id)}
                        download={item.document.file}
                        aria-label={`Download ${vendor} invoice`}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <Download />
                      </a>
                    ) : (
                      <button
                        className="icon-btn"
                        aria-label={`Download ${vendor} invoice`}
                        onClick={(e) => {
                          e.stopPropagation()
                          setNotice(
                            <>
                              {vendor} has <b>no document to download</b> — it was read from
                              the email body.
                            </>,
                          )
                        }}
                      >
                        <Download />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
              {isOpen && (
                <tr className="expansion">
                  <td colSpan={5}>
                    <InvoiceDetail item={item} />
                  </td>
                </tr>
              )}
              </Fragment>
            )
          })}
        </tbody>
      </table>

      {/* The mockup had no empty state because its rows were hardcoded; an
          empty database is reachable now. */}
      {!loading && invoices.length === 0 && (
        <div className="table-foot">
          No invoices yet. Press Update to scan your connected mailboxes.
        </div>
      )}

      {invoices.length > 0 && (
        <div className="table-foot">
          <span className="per-page">
            {selected.size ? `${selected.size} selected` : `${invoices.length} of ${invoices.length} shown`}
          </span>
          <span className="pager">
            <span className="page-num">1</span>
          </span>
        </div>
      )}
      <Toast message={notice} onDismiss={dismiss} />
    </section>
  )
}
