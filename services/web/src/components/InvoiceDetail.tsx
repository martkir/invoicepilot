import { documentUrl } from '../api/client'
import type { Invoice } from '../api/types'
import { amount, bytes, dateTime, longDate } from '../lib/format'

/** A label/value pair, dropped entirely when the parser found nothing.
 *  Templates differ per issuer, so a fixed list of rows would be mostly
 *  dashes for anyone but Bolt, and the panel would end up reporting the
 *  template's coverage rather than the invoice.
 *
 *  `id` marks a value that is read a character at a time - an invoice number,
 *  a VAT number, a date - and sets it in mono the way the share page's
 *  manifest does. Prose values stay in the text face. */
function pairs(entries: [string, string | null | undefined, boolean?][]) {
  return entries
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value, id]) => (
      <div className="pair" key={key}>
        <div className="k">{key}</div>
        <div className={id ? 'v is-id' : 'v'}>{value}</div>
      </div>
    ))
}

export function InvoiceDetail({ item }: { item: Invoice }) {
  const f = item.invoice
  const email = item.email
  const from = email?.from
  const sender = from ? [from.name, from.address && `<${from.address}>`].filter(Boolean).join(' ') : null

  return (
    <div className="exp">
      <figure className="exp-doc">
        {item.document ? (
          /* The browser's own PDF viewer. Nothing is rendered client-side -
             the bytes are exactly what the vendor sent. It is sized to be
             recognised rather than read: no width this panel can afford makes
             an A4 page legible, and reading it is what the row's own download
             is for, which is also why there is no second button here. */
          <iframe
            className="doc-frame"
            src={documentUrl(item.id)}
            title={`${f.issuer ?? 'Invoice'} document`}
          />
        ) : (
          <div className="doc-none">
            <b>No document</b>
            <p>
              This invoice was read from the email itself. Nothing was attached and no invoice
              link resolved to a file. The fields beside this are what the parser found in the
              message body.
            </p>
          </div>
        )}

        {item.document && (
          <>
            <figcaption className="doc-cap">
              <span className="file">{item.document.file}</span>
            </figcaption>
            <p className="doc-origin">
              <span className="ftype">{extension(item.document.file)}</span>
              {bytes(item.document.bytes)}, saved from {item.document.origin}.
            </p>
          </>
        )}
      </figure>

      <div className="meta">
        {/* The amount leads: it is the figure the row was opened to check. It
            is deliberately absent from the pairs below, because two copies of
            one number are two answers to one question. */}
        {f.amount !== undefined && (
          <div className="exp-total">
            <span className="big">{amount(f.amount, f.currency)}</span>
            {f.amount_untaxed !== undefined && f.amount_tax !== undefined && (
              <dl className="split">
                <div>
                  <dt>Net</dt>
                  <dd>{f.amount_untaxed.toFixed(2)}</dd>
                </div>
                <div>
                  <dt>VAT</dt>
                  <dd>{f.amount_tax.toFixed(2)}</dd>
                </div>
              </dl>
            )}
          </div>
        )}

        <div className="pair-group">
          <h3>Invoice</h3>
          <div className="pairs">
            {pairs([
              ['Invoice number', f.invoice_number, true],
              ['Issued', item.issued_on ? longDate(item.issued_on) : null, true],
              ['Service start', f.service_start, true],
              ['VAT number', f.vat_number, true],
              ['Company number', f.company_number, true],
              ['Reference', f.reference, true],
            ])}
          </div>
        </div>

        {email && (
          <div className="pair-group">
            <h3>Email it arrived in</h3>
            <div className="pairs">
              {pairs([
                ['Subject', email.subject],
                ['From', sender],
                ['Mailbox', email.mailbox],
                ['Received', email.date ? dateTime(email.date) : null, true],
              ])}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/** "invoice.pdf" -> "pdf". Whatever is after the last dot, lower case, which
 *  is how the extension reads in the file name beside it. */
function extension(file: string): string {
  const dot = file.lastIndexOf('.')
  return dot > 0 ? file.slice(dot + 1).toLowerCase() : 'file'
}
