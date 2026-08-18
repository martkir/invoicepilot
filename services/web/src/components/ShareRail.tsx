import { useState } from 'react'

import type { ShareManifest } from '../api/types'
import { bytes as formatBytes, longDate } from '../lib/format'
import { Download, Mail, Pen } from './Icons'

interface Props {
  share: ShareManifest
  /** Bytes received so far, or null when no download is running. */
  progress: number | null
  onDownload: () => void
  /** Owner-only, and only when this browser holds the key that made the link. */
  owner: OwnerProps | null
}

export interface OwnerProps {
  onCompose: () => void
  onRename: (name: string) => Promise<void>
}

/** What the batch is, and the one thing to do with it.
 *
 *  The filename is the largest thing on the page because "is this the right
 *  export?" is the only question the page has to settle before anyone clicks.
 *  Sticky, so the answer and the action stay on screen through 37 rows.
 */
export function ShareRail({ share, progress, onDownload, owner }: Props) {
  return (
    <section className="rail" aria-labelledby="batch-name">
      <div>
        <p className="rail-kicker">
          <span className="ftype">zip</span>One download, no account needed
        </p>
        <h1 className="batch-name" id="batch-name">
          {share.filename}
        </h1>
      </div>

      <dl className="facts">
        <div>
          <dt>Invoices</dt>
          <dd>{share.invoices}</dd>
        </div>
        <div>
          <dt>Documents</dt>
          <dd>{share.documents}</dd>
        </div>
        <div>
          <dt>Size</dt>
          <dd>{formatBytes(share.bytes)}</dd>
        </div>
        <div>
          <dt>Period</dt>
          <dd>{share.period || '-'}</dd>
        </div>
      </dl>

      {progress === null ? (
        <div className="get">
          {/* A real link, so the browser's own save still works when this
              handler does not: the click is intercepted only to report
              progress, which a plain navigation cannot. */}
          <a
            className="btn btn-primary btn-lg"
            href={`#download-${share.token}`}
            onClick={(event) => {
              event.preventDefault()
              onDownload()
            }}
          >
            <Download size={18} />
            Download all
          </a>
          <p className="get-note">
            {share.documents} PDFs and <b>invoices.csv</b>, zipped. {formatBytes(share.bytes)}.
          </p>
        </div>
      ) : (
        <Zipping share={share} received={progress} />
      )}

      {owner && <OwnerBlock share={share} {...owner} />}
    </section>
  )
}

/** Determinate, because the page already told the recipient what the batch
 *  weighs: the bar measures what has arrived against that figure. */
function Zipping({ share, received }: { share: ShareManifest; received: number }) {
  const percent = share.bytes ? Math.min(100, Math.round((received / share.bytes) * 100)) : 0
  return (
    <div className="get">
      <div className="zipping" role="status">
        <p className="row">
          Preparing your download
          <span>
            {formatBytes(received)} of {formatBytes(share.bytes)}
          </span>
        </p>
        <div className="bar">
          <div className="bar-fill" style={{ width: `${percent}%` }}></div>
        </div>
        <p className="get-note">
          Zipping {share.documents} documents and building invoices.csv. The file starts saving on
          its own.
        </p>
      </div>
    </div>
  )
}

/** The only difference between the owner's page and everyone else's.
 *
 *  Three things, in the order the owner asks about them: how long the link
 *  lives, whose name is on it, and how to send it. The first replaced Revoke —
 *  a link that ends on a date needs no switch, and the date is worth more on
 *  the page than the switch was.
 */
function OwnerBlock({ share, onCompose, onRename }: { share: ShareManifest } & OwnerProps) {
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(share.owner_name)
  const [saving, setSaving] = useState(false)

  const live = (
    <p className="live">
      <b>This link is live.</b> Anyone with it can download these invoices. It stops working on{' '}
      <b>{longDate(share.expires_at)}</b>.
    </p>
  )

  if (!editing) {
    return (
      <div className="owner-block">
        {live}
        <p className="sent-as">
          Recipients see it from <b>{share.owner_name}</b>
          <button
            className="btn-quiet"
            onClick={() => {
              setName(share.owner_name)
              setEditing(true)
            }}
          >
            <Pen />
            Change
          </button>
        </p>
        <div className="rail-actions">
          <button className="btn btn-secondary" onClick={onCompose}>
            <Mail />
            Send by email
          </button>
        </div>
      </div>
    )
  }

  const save = async () => {
    setSaving(true)
    try {
      await onRename(name.trim())
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="owner-block">
      {live}
      <div className="name-edit">
        <div className="field">
          <label htmlFor="sent-as">Recipients see it from</label>
          <input
            id="sent-as"
            name="sent-as"
            type="text"
            autoComplete="name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-describedby="sent-as-note"
          />
        </div>
        {/* The mailbox is named because it is where the name came from, and
            the local part is exactly the value somebody will want to fix. */}
        <p className="field-note" id="sent-as-note">
          Taken from {share.owner_email}
          {share.owner_name === share.owner_email.split('@')[0] ? ', which carries no name' : ''}.
          Shown on this page and in the email.
        </p>
        <div className="rail-actions">
          <button
            className="btn btn-secondary"
            disabled={saving || !name.trim() || name.trim() === share.owner_name}
            onClick={() => void save()}
          >
            Save
          </button>
          <button className="btn-quiet" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
