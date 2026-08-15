import { useEffect, useRef, useState } from 'react'

import { getAccounts, sendShare, shareMailUrl } from '../api/client'
import type { Account } from '../api/types'
import { lastFrom, rememberFrom } from '../lib/owner'
import { Alert, Caret, GoogleMark, Mail, Open, Tick } from './Icons'

interface Props {
  token: string
  /** The subject the API will actually send, quoted rather than guessed. */
  subject: string
  ownerKey: string
  onSent: (to: string, from: string) => void
  onCancel: () => void
}

/** One address to fill, nothing else, and the actual mail underneath it.
 *
 *  No note field: an optional message box is a decision every sender then has
 *  to make, and the draft already says everything the recipient needs. The
 *  preview is the same document the API sends, in an iframe, so what the
 *  sender approves and what the recipient opens cannot diverge.
 */
export function Composer({ token, subject, ownerKey, onSent, onCancel }: Props) {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [from, setFrom] = useState<string | null>(null)
  const [menu, setMenu] = useState(false)

  const [to, setTo] = useState('')
  const [invalid, setInvalid] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const [failed, setFailed] = useState<string | null>(null)

  useEffect(() => {
    void getAccounts()
      .then((found) => {
        setAccounts(found)
        // The mailbox this browser last sent from, so the choice is asked once
        // rather than every time; the first connected one otherwise.
        const remembered = lastFrom()
        setFrom(found.find((a) => a.id === remembered)?.id ?? found[0]?.id ?? null)
      })
      .catch(() => setAccounts([]))
  }, [])

  const current = accounts.find((account) => account.id === from)
  const ready = to.trim() !== '' && invalid === null

  const check = (value: string) => {
    const address = value.trim()
    if (!address) return setInvalid(null)
    if (!/^[^@\s]+@[^@\s]+$/.test(address)) {
      return setInvalid('That does not look like an email address.')
    }
    // The commonest typo by far, and the one worth naming: a domain with no
    // dot in it. Saying which half is wrong beats "invalid email".
    if (!address.split('@')[1].includes('.')) {
      return setInvalid('That address is missing its domain.')
    }
    setInvalid(null)
  }

  const send = async () => {
    if (!ready || !from) return
    setSending(true)
    setFailed(null)
    try {
      await sendShare(token, to.trim(), from, ownerKey)
      rememberFrom(from)
      onSent(to.trim(), current?.email ?? '')
    } catch (exc) {
      setFailed(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="composer">
      <h2>Send this link by email</h2>
      <p className="composer-lede">
        The subject and the body are already written. The only thing missing is who it goes to.
      </p>

      <div className="field">
        {/* A span, not a <label for>: there is no control here to point at,
            and promising a screen reader one that does not exist is worse
            than the missing association. */}
        <span className="field-label">From</span>
        <FromRow
          accounts={accounts}
          current={current}
          open={menu}
          onToggle={() => setMenu((was) => !was)}
          onPick={(id) => {
            setFrom(id)
            setMenu(false)
          }}
        />
        <span className="field-note">Replies come back here</span>
      </div>

      <div className="field">
        <label htmlFor="to">To</label>
        <input
          id="to"
          name="to"
          type="email"
          required
          autoComplete="email"
          placeholder="accountant@firm.com"
          value={to}
          onChange={(event) => {
            setTo(event.target.value)
            if (invalid) check(event.target.value)
          }}
          onBlur={(event) => check(event.target.value)}
          aria-invalid={invalid ? true : undefined}
          aria-describedby={invalid ? 'to-error' : undefined}
        />
      </div>
      {invalid && (
        <p className="field-error" id="to-error">
          {invalid}
        </p>
      )}

      <div className="composer-foot">
        {ready && !sending ? (
          <button className="btn btn-primary" onClick={() => void send()}>
            <Mail />
            Send
          </button>
        ) : (
          <button className="btn btn-primary" aria-disabled="true">
            <Mail />
            {sending ? 'Sending…' : 'Send'}
          </button>
        )}
        <button className="btn-quiet" onClick={onCancel}>
          Cancel
        </button>
        <span className="hint">
          Subject: <b>{subject}</b>. The link is sent, not the files.
        </span>
      </div>

      {/* The Unipile detail verbatim: "something went wrong" is not something
          anyone can act on, and the link is live either way. */}
      {failed && (
        <p className="mail-error">
          <Alert />
          <span>
            <b>Could not send.</b> <code>{failed}</code> Your address is still here, and the link is
            live either way: copy it and send it yourself, or reconnect the mailbox and try again.
          </span>
        </p>
      )}

      <div className="mail-preview">
        <div className="mail-preview-head">
          Preview: what {to.trim() || 'your recipient'} opens
          <a href={shareMailUrl(token)} target="_blank" rel="noopener">
            Full size <Open />
          </a>
        </div>
        <iframe
          src={shareMailUrl(token)}
          title="Preview of the email that will be sent"
          loading="lazy"
        />
      </div>
    </div>
  )
}

/** The sending mailbox: an address, and a caret only when there is a choice.
 *
 *  Not a <select>. A form control frames a settled fact as a question, and the
 *  resting state should say *this goes out as martin@kirov.dev*, not *choose a
 *  sender*.
 */
function FromRow({
  accounts,
  current,
  open,
  onToggle,
  onPick,
}: {
  accounts: Account[]
  current?: Account
  open: boolean
  onToggle: () => void
  onPick: (id: string) => void
}) {
  const anchor = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    if (!open) return
    const away = (event: MouseEvent) => {
      if (!anchor.current?.contains(event.target as Node)) onToggle()
    }
    document.addEventListener('mousedown', away)
    return () => document.removeEventListener('mousedown', away)
  }, [open, onToggle])

  const label = (
    <span className="from-current">
      <GoogleMark />
      {current?.email ?? 'No mailbox connected'}
    </span>
  )

  // A control that leads nowhere is worse than no control.
  if (accounts.length < 2) return label

  return (
    <span className="from-anchor" ref={anchor}>
      {label}
      <button
        className={`icon-btn${open ? ' is-active' : ''}`}
        aria-label="Send from a different mailbox"
        aria-expanded={open}
        onClick={onToggle}
      >
        <Caret />
      </button>
      {open && (
        <div className="from-menu" role="menu">
          {accounts.map((account) => (
            <button
              key={account.id}
              className={`from-opt${account.id === current?.id ? ' is-current' : ''}`}
              role="menuitem"
              onClick={() => onPick(account.id)}
            >
              <GoogleMark />
              {account.email}
              {account.id === current?.id && (
                <span className="tick">
                  <Tick />
                </span>
              )}
            </button>
          ))}
        </div>
      )}
    </span>
  )
}
