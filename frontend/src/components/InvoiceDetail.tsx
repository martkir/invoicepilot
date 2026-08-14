import { documentUrl } from '../api/client'
import type { Invoice } from '../api/types'
import { amount, dateTime, longDate } from '../lib/format'

/** A label/value pair, dropped entirely when the parser found nothing.
 *  Templates differ per issuer, so a fixed list of rows would be mostly
 *  dashes for anyone but Bolt. */
function pairs(entries: [string, string | null | undefined][]) {
  return entries
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => (
      <div className="pair" key={key}>
        <div className="k">{key}</div>
        <div className="v">{value}</div>
      </div>
    ))
}

export function InvoiceDetail({ item }: { item: Invoice }) {
  const f = item.invoice
  const email = item.email
  const from = email?.from
  const sender = from ? [from.name, from.address && `<${from.address}>`].filter(Boolean).join(' ') : null

  const net =
    f.amount_untaxed !== undefined && f.amount_tax !== undefined
      ? `${f.amount_untaxed.toFixed(2)} / ${f.amount_tax.toFixed(2)}`
      : null

  return (
    <div className="exp">
      <div className="exp-doc">
        {item.document ? (
          /* The browser's own PDF viewer. Nothing is rendered client-side —
             the bytes are exactly what the vendor sent. Downloading lives on
             the row's own icon, so there is no second button here. */
          <iframe
            className="doc-frame"
            src={documentUrl(item.id)}
            title={`${f.issuer ?? 'Invoice'} document`}
          />
        ) : (
          <div className="doc-none">
            <b>No document</b>
            <p>
              This invoice was read from the email itself — nothing was attached and no invoice
              link resolved to a file. The fields beside this are what the parser found in the
              message body.
            </p>
          </div>
        )}
      </div>

      <div className="meta">
        <h3>Invoice</h3>
        <div className="pairs">
          {pairs([
            ['Invoice number', f.invoice_number],
            ['Issued', longDate(item.issued_on)],
            ['Amount', amount(f.amount, f.currency)],
            ['Net / VAT', net],
            ['VAT number', f.vat_number],
            ['Company number', f.company_number],
            ['Reference', f.reference],
            ['Service start', f.service_start],
          ])}
        </div>

        {email && (
          <>
            <h3>Email it arrived in</h3>
            <div className="pairs">
              {pairs([
                ['Subject', email.subject],
                ['From', sender],
                ['Received', email.date ? dateTime(email.date) : null],
              ])}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
