import { useState } from 'react'

import { shareThumbUrl } from '../api/client'
import type { ShareItem, ShareManifest } from '../api/types'
import { initials, issued, money } from '../lib/format'

// Six cells for six things: five documents and the count of the rest. A
// scrolling strip would mean lazy loading, a scroll affordance and a
// virtualization story for something nobody flicks through, and the sheet
// below lists every invoice by name anyway.
const TILES = 5
const COUNTED = ['no', 'One', 'Two', 'Three', 'Four', 'Five']

// Past this the sheet is longer than anyone reads in a page they visit once.
// The tail is stated rather than rendered; every row is in invoices.csv.
const SHEET_ROWS = 50

// What invoices.csv carries and this sheet does not. The count in the last
// column's ::after is the length of this list, and its title is the list.
const CSV_ONLY =
  'VAT number, company number, currency, payment reference, service date, description, ' +
  'file size, SHA-256, source, mailbox, email subject, received, message id, ' +
  'extracted at, extracted by'

/** What is inside the batch: the documents, then the sheet.
 *
 *  Each half is a named part carrying its own file-type chip, under a page
 *  already chipped `zip`. That is the whole explanation — no sentence says
 *  "the download contains PDFs and a spreadsheet", because the layout does.
 */
export function Manifest({ share }: { share: ShareManifest }) {
  const documents = share.items.filter((item) => item.file)
  const shown = documents.slice(0, TILES)
  const rows = share.items.slice(0, SHEET_ROWS)

  return (
    <div className="doc-card">
      <section className="part part-docs">
        <div>
          <h2 className="part-head">
            <span className="ftype">pdf</span>
            {share.documents} documents
          </h2>
          <p className="part-note">
            The vendors&rsquo; own files, renamed by date so the folder sorts itself.{' '}
            {COUNTED[shown.length] ?? shown.length} of the {share.documents} shown.
          </p>
        </div>
        <figure className="docs-figure">
          <div className="doc-grid">
            {shown.map((item) => (
              <Tile key={item.id} token={share.token} item={item} />
            ))}
            {share.documents > shown.length && (
              <article className="doc-tile is-more">
                <div className="doc-thumb">+{share.documents - shown.length}</div>
                <p className="doc-file">more</p>
              </article>
            )}
          </div>
          <figcaption className="sr-only">
            {COUNTED[shown.length] ?? shown.length} of the {share.documents} documents in this
            download, each with the amount on the invoice.
          </figcaption>
        </figure>
      </section>

      <section className="part part-csv">
        <div>
          <h2 className="part-head">
            <span className="ftype">csv</span>invoices.csv
          </h2>
          <p className="part-note">
            One row per invoice, 22 columns. Everything the extractor read, including where it read
            it from.
          </p>
        </div>
        <div className="sheet-wrap">
          <table className="sheet">
            <caption className="sr-only">
              Every invoice in this download, with the filename it carries inside the zip.
            </caption>
            <thead>
              <tr>
                <th className="c-num" scope="col">
                  #
                </th>
                <th className="c-vendor" scope="col">
                  Vendor
                </th>
                <th className="c-inv" scope="col">
                  Invoice&nbsp;#
                </th>
                <th className="c-doc" scope="col">
                  Document
                </th>
                <th className="c-date" scope="col">
                  Issued
                </th>
                <th className="c-money" scope="col">
                  Net
                </th>
                <th className="c-money" scope="col">
                  VAT
                </th>
                <th className="c-amt" scope="col">
                  Total&nbsp;€
                </th>
                {/* Not a data column: the number of columns the CSV carries and
                    this sheet does not, which drops as columns drop at each
                    breakpoint. Without it the sheet reads as the whole truth. */}
                <th
                  className="c-more"
                  scope="col"
                  data-wide="+15"
                  data-mid="+18"
                  data-narrow="+19"
                  title={`Also in invoices.csv: ${CSV_ONLY}`}
                ></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((item, index) => (
                <Row key={item.id} item={item} n={index + 1} />
              ))}
              {share.items.length > rows.length && (
                <tr className="more">
                  <td className="c-num">…</td>
                  <td colSpan={8}>{share.items.length - rows.length} more rows</td>
                </tr>
              )}
            </tbody>
            <tfoot>
              <tr>
                <td className="c-num"></td>
                <td className="c-vendor">
                  {share.invoices} invoice{share.invoices === 1 ? '' : 's'}
                </td>
                <td className="c-inv"></td>
                <td className="c-doc">
                  {share.documents} document{share.documents === 1 ? '' : 's'}
                </td>
                <td className="c-date"></td>
                <td className="c-money"></td>
                <td className="c-money"></td>
                <td className="c-amt"></td>
                <td className="c-more"></td>
              </tr>
            </tfoot>
          </table>
        </div>
      </section>
    </div>
  )
}

/** One document. The rendered first page, over the initials that stand in for
 *  it while it is missing — a real product state rather than a drawing of a
 *  page. */
function Tile({ token, item }: { token: string; item: ShareItem }) {
  const [rendered, setRendered] = useState(true)
  const vendor = item.vendor ?? 'Unknown vendor'
  return (
    <article className="doc-tile" title={item.file ?? undefined}>
      <div className="doc-thumb" aria-hidden="true">
        {rendered ? (
          <img src={shareThumbUrl(token, item.id)} alt="" onError={() => setRendered(false)} />
        ) : (
          initials(vendor)
        )}
      </div>
      <p className="doc-file">{vendor.split(' ')[0]}</p>
      <p className="doc-amt">{money(item.amount_total, item.currency)}</p>
    </article>
  )
}

function Row({ item, n }: { item: ShareItem; n: number }) {
  // A hyphen, not an empty cell: blank reads as "we forgot to render it", a
  // dash reads as "this invoice does not carry one", which is the truth for
  // every receipt parsed out of a mail body.
  const cell = (value: string | null, className: string) =>
    value ? (
      <td className={className}>{value}</td>
    ) : (
      <td className={`${className} is-none`}>-</td>
    )

  return (
    <tr>
      <td className="c-num">{n}</td>
      <td className="c-vendor">{item.vendor ?? 'Unknown vendor'}</td>
      {cell(item.invoice_number, 'c-inv')}
      {item.file ? (
        <td className="c-doc">{item.file}</td>
      ) : (
        <td className="c-doc is-none" title="Read from an email body, no attachment">
          no document
        </td>
      )}
      <td className="c-date">{issued(item.issued_on)}</td>
      {cell(item.amount_net, 'c-money')}
      {cell(item.amount_vat, 'c-money')}
      <td className="c-amt">{item.amount_total ?? '-'}</td>
      <td className="c-more">…</td>
    </tr>
  )
}
