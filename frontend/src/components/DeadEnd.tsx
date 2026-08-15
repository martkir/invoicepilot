import type { ExpiredShare } from '../api/types'
import { longDate } from '../lib/format'
import { Back, Expired, Lost, Mail } from './Icons'

/** The two ways a link can be dead, and they are not the same thing.
 *
 *  410: this link worked and its seven days ran out, so the page can name who
 *  shared it and the day it lapsed. 404: no such link ever existed, so the
 *  page says that instead and points at the likeliest cause.
 */
export function ExpiredLink({ share }: { share: ExpiredShare }) {
  const first = share.owner_name.split(' ')[0]
  return (
    <section className="dead" aria-labelledby="expired-title">
      <span className="dead-mark">
        <Expired />
      </span>
      <h1 id="expired-title">This link has expired</h1>
      <p>
        {share.owner_name} shared these invoices on {longDate(share.created_at)}, and share links
        stop working seven days later. It lapsed on {longDate(share.expires_at)}. Nothing was
        deleted; ask for a new link and it takes two clicks.
      </p>
      <p className="quiet">Every link expires on its own, and a new one gets a new address.</p>
      <div className="dead-actions">
        <a className="btn btn-primary" href={`mailto:${share.owner_email}`}>
          <Mail />
          Email {first}
        </a>
        <a className="btn-quiet" href="/">
          <Back />
          Back to Invoice Pilot
        </a>
      </div>
    </section>
  )
}

export function MissingLink() {
  return (
    <section className="dead" aria-labelledby="notfound-title">
      <span className="dead-mark">
        <Lost />
      </span>
      <h1 id="notfound-title">There is nothing at this link</h1>
      <p>
        The address is not one we recognise. Links that break across two lines in an email are the
        usual cause, so check that the whole thing after <code>/s/</code> made it, all 22
        characters.
      </p>
      <p className="quiet">
        A link that has run out of time says so instead, and names the day it did. This one was
        never an address at all.
      </p>
      <div className="dead-actions">
        <button className="btn btn-primary" onClick={() => window.location.reload()}>
          <Back />
          Try the link again
        </button>
        <a className="btn-quiet" href="/">
          Back to Invoice Pilot
        </a>
      </div>
    </section>
  )
}
