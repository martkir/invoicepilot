import { Fragment, useCallback, useState } from 'react'
import type { ReactNode } from 'react'

import { createShare, documentUrl } from '../api/client'
import type { Invoice, ShareCreated } from '../api/types'
import { InvoiceDetail } from './InvoiceDetail'
import { SharePop } from './SharePop'
import { Toast } from './Toast'
import { amount, initials, issued, period } from '../lib/format'
import { ownerName, rememberOwnerKey } from '../lib/owner'
import { Download, Eye, Refresh, Share } from './Icons'

interface Props {
  invoices: Invoice[]
  loading: boolean
  scanning: boolean
  scanLabel: string
  /** The line beside the Update button: the scan's own tally while it runs,
   *  the age of the last one otherwise, the reason when one failed. Composed
   *  by the caller — the table shows it and knows nothing about which it is. */
  meta: string
  /** Whether this workspace has a mailbox at all. Only the empty state uses
   *  it, to tell a first visit ("connect something") from a scanned-but-empty
   *  one ("press Update") — two states that used to be indistinguishable
   *  because there was only ever one user with one set of mailboxes. */
  hasSources: boolean
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
  meta,
  hasSources,
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

  // The link this click made, and whether the clipboard took it. One click,
  // one row, one link on the clipboard: there is no dialog in between, so the
  // popover reports rather than asks.
  const [share, setShare] = useState<ShareCreated | null>(null)
  const [copied, setCopied] = useState(false)
  const [sharing, setSharing] = useState(false)

  const copy = useCallback(async (url: string) => {
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
    } catch {
      // Outside https the clipboard is not available at all. The link is on
      // screen either way, so the popover says "created" instead of "copied"
      // rather than claiming something that did not happen.
      setCopied(false)
    }
  }, [])

  const startShare = async () => {
    if (share) {
      setShare(null)
      return
    }
    setSharing(true)
    try {
      // Ticked rows if any are ticked, otherwise the whole view — which is
      // what the table's own download does.
      const made = await createShare([...selected], ownerName() ?? undefined)
      rememberOwnerKey(made.token, made.owner_key)
      await copy(made.url)
      setShare(made)
    } catch (exc) {
      setNotice(
        <>
          <b>Could not create the link.</b> {exc instanceof Error ? exc.message : String(exc)}
        </>,
      )
    } finally {
      setSharing(false)
    }
  }

  const allChecked = invoices.length > 0 && selected.size === invoices.length
  const someChecked = selected.size > 0 && selected.size < invoices.length

  return (
    <section className="card" aria-label="Invoices">
      <div className="table-head">
        <h1 className="table-title">
          Invoices <em id="doc-count">{invoices.length} documents</em>
        </h1>
        <div className="tools">
          <span className="last-update">{meta}</span>
          <div className="tool-divider"></div>
          <button className="update-btn" data-busy={scanning} onClick={onUpdate} disabled={scanning}>
            <Refresh />
            <span>{scanLabel}</span>
          </button>
          <div className="tool-divider"></div>
          {/* The toolbar's download is gone: it was a third path to files the
              row's own arrow already covers, drawn one stroke away from the
              share glyph beside it. Share is labelled and filled because it is
              this screen's primary action, and a bare glyph made the one thing
              the screen exists for its least visible control. */}
          <span className="pop-anchor">
            <button
              className={`share-btn${share ? ' is-active' : ''}`}
              aria-expanded={share !== null}
              disabled={sharing || invoices.length === 0}
              onClick={() => void startShare()}
            >
              <Share />
              <span>Share</span>
            </button>
            {share && (
              <SharePop
                share={share}
                all={selected.size === 0}
                copied={copied}
                onCopy={() => void copy(share.url)}
                onClose={() => setShare(null)}
              />
            )}
          </span>
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
            <th scope="col">Vendor</th>
            {/* No chevron glyphs. The sorted column is a state rather than an
                action, so it is marked by --ink against its neighbours'
                --ink-soft; a direction marker goes back in when sorting is
                actually wired to something. */}
            <th className="col-amount sortable" scope="col">
              <button>Amount</button>
            </th>
            <th className="col-issued sortable sorted" scope="col">
              <button>Issued</button>
            </th>
            <th className="col-actions" scope="col">
              Actions
            </th>
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
          empty database is reachable now — and since the dashboard became
          public it is what every first visit sees, so the line has to say
          which of the two empties this is. Telling someone with no mailbox to
          press Update sends them to a button that can only fail. */}
      {!loading && invoices.length === 0 && (
        <div className="table-foot">
          {hasSources
            ? 'No invoices yet. Press Update to scan your connected mailboxes.'
            : 'No invoices yet. Add a source to connect a mailbox, then press Update.'}
        </div>
      )}

      {invoices.length > 0 && (
        <div className="table-foot">
          <span className="per-page">
            {[
              selected.size
                ? `${selected.size} selected`
                : `${invoices.length} of ${invoices.length} shown`,
              // The count says how many, the range says of when. The stretch
              // is the table's either way: a selection changes what is ticked,
              // not what the rows below cover.
              period(invoices.map((item) => item.issued_on)),
            ]
              .filter(Boolean)
              .join(' · ')}
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
