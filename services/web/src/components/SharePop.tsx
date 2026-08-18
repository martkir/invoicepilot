import { useEffect, useRef } from 'react'

import type { ShareCreated } from '../api/types'
import { longDate } from '../lib/format'
import { Copy, Mail, Open, Tick } from './Icons'

interface Props {
  share: ShareCreated
  /** Whether the batch was the whole table rather than ticked rows. */
  all: boolean
  /** False when the clipboard refused, which it does outside https. */
  copied: boolean
  onCopy: () => void
  onClose: () => void
}

/** The popover that reports a new link. It does not ask anything.
 *
 *  The click is the share: the row is written and the link is on the clipboard
 *  before this appears, so there is nothing here to confirm or configure.
 *  Opening the link is the button and sending it by email is a text link,
 *  because a matched pair would read as two equal decisions when only one of
 *  them is the point.
 */
export function SharePop({ share, all, copied, onCopy, onClose }: Props) {
  const box = useRef<HTMLDivElement>(null)

  // Click outside or Escape closes it. The link is already live and already
  // copied, so dismissing costs nothing.
  useEffect(() => {
    const away = (event: MouseEvent) => {
      if (!box.current?.parentElement?.contains(event.target as Node)) onClose()
    }
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('mousedown', away)
    document.addEventListener('keydown', key)
    return () => {
      document.removeEventListener('mousedown', away)
      document.removeEventListener('keydown', key)
    }
  }, [onClose])

  const batch = `${all ? 'All ' : ''}${share.invoices} invoice${share.invoices === 1 ? '' : 's'}`

  return (
    <div className="share-pop" role="status" ref={box}>
      <p className="pop-title">
        <span className="ok">
          <Tick />
        </span>
        {copied ? 'Link copied' : 'Link created'}
      </p>
      <p className="pop-sub">
        {batch}
        {share.period ? `, ${share.period}` : ''}. Anyone with this link can view and download
        them. It stops working on <b>{longDate(share.expires_at)}</b>.
      </p>
      <div className="link-row">
        <code>{share.url.replace(/^https?:\/\//, '')}</code>
        <button className="icon-btn" aria-label="Copy the link again" onClick={onCopy}>
          <Copy />
        </button>
      </div>
      <div className="pop-actions">
        <a className="btn btn-primary btn-grow" href={`/s/${share.token}`}>
          <Open />
          Open the link
        </a>
        <a className="btn-quiet" href={`/s/${share.token}?compose`}>
          <Mail />
          Send by email
        </a>
      </div>
    </div>
  )
}
