import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { ApiError, getShare, renameShare, shareZipUrl } from '../api/client'
import type { ExpiredShare, ShareManifest } from '../api/types'
import { Composer } from '../components/Composer'
import { ExpiredLink, MissingLink } from '../components/DeadEnd'
import { Mark, Tick } from '../components/Icons'
import { Manifest } from '../components/Manifest'
import { ShareRail } from '../components/ShareRail'
import { ownerKey, rememberOwnerName } from '../lib/owner'

/** What a link resolves to: the batch, who shared it, and one way to get it.
 *
 *  The owner and the recipient are on the same page. There is no
 *  what-they-will-see mode to keep in step with what they actually see, and no
 *  doubt in the owner's mind about whether the preview was accurate — the
 *  rail's owner block is the entire difference, and it appears only for the
 *  browser holding the key that made the link.
 */
export function SharePage({ token }: { token: string }) {
  const [share, setShare] = useState<ShareManifest | null>(null)
  const [expired, setExpired] = useState<ExpiredShare | null>(null)
  const [missing, setMissing] = useState(false)
  const [failed, setFailed] = useState<string | null>(null)

  // Arriving from the popover's "Send by email" opens the composer straight
  // away; every other arrival opens the page it is on.
  const [composing, setComposing] = useState(() =>
    new URLSearchParams(window.location.search).has('compose'),
  )
  const [sent, setSent] = useState<{ to: string; from: string } | null>(null)
  const [progress, setProgress] = useState<number | null>(null)

  const key = ownerKey(token)

  // The share page is its own surface, not the dashboard's: two columns, a
  // masthead and no app chrome.
  useEffect(() => {
    document.body.classList.add('share-page')
    return () => document.body.classList.remove('share-page')
  }, [])

  useEffect(() => {
    void getShare(token)
      .then(setShare)
      .catch((exc) => {
        if (exc instanceof ApiError && exc.status === 410) {
          return setExpired(exc.detail as ExpiredShare)
        }
        if (exc instanceof ApiError && exc.status === 404) return setMissing(true)
        setFailed(exc instanceof Error ? exc.message : String(exc))
      })
  }, [token])

  useEffect(() => {
    document.title = share ? `${share.filename} · Invoice Pilot` : 'Invoice Pilot'
  }, [share])

  /** The zip, measured against the size the page already states.
   *
   *  Read as a stream so the bar is honest, which does mean holding the batch
   *  in memory before it is saved; a plain navigation is the fallback, and
   *  gives up the progress rather than the download.
   */
  const download = useCallback(async () => {
    if (!share) return
    setProgress(0)
    try {
      const response = await fetch(shareZipUrl(token))
      if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)

      const reader = response.body.getReader()
      const parts: BlobPart[] = []
      let received = 0
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        parts.push(value)
        received += value.length
        setProgress(received)
      }

      const url = URL.createObjectURL(new Blob(parts, { type: 'application/zip' }))
      const save = document.createElement('a')
      save.href = url
      save.download = share.filename
      save.click()
      URL.revokeObjectURL(url)
    } catch {
      window.location.href = shareZipUrl(token)
    } finally {
      setProgress(null)
    }
  }, [share, token])

  const rename = useCallback(
    async (name: string) => {
      if (!share || !key) return
      await renameShare(token, name, key)
      // Kept for the next link too, so the correction is made once rather than
      // once per share.
      rememberOwnerName(name)
      setShare({ ...share, owner_name: name })
    },
    [share, key, token],
  )

  if (expired) return <Shell>{<ExpiredLink share={expired} />}</Shell>
  if (missing) return <Shell>{<MissingLink />}</Shell>
  if (failed) {
    return (
      <Shell>
        <section className="dead">
          <h1>This link could not be opened</h1>
          <p>{failed}</p>
        </section>
      </Shell>
    )
  }
  if (!share) return <Loading />

  const owner = key !== null
  const undocumented = share.invoices - share.documents

  return (
    <Shell
      who={
        owner ? (
          <p className="shared-by">
            Your link<b>{share.owner_email}</b>
          </p>
        ) : (
          <p className="shared-by">
            Shared with you by<b>{share.owner_name}</b>
            {share.owner_email}
          </p>
        )
      }
      foot={
        <>
          <span>invoices.csv carries all 22 columns per invoice.</span>
          <span className="spacer"></span>
          {undocumented > 0 && (
            <span>
              {undocumented} invoice{undocumented === 1 ? ' has' : 's have'} no document;{' '}
              {undocumented === 1 ? 'it rides' : 'they ride'} along in the CSV.
            </span>
          )}
        </>
      }
    >
      {sent && (
        <p className="banner" role="status">
          <span className="tick">
            <Tick />
          </span>
          <span>
            Sent to <b>{sent.to}</b> from {sent.from}. Replies come back to you.
          </span>
          <button
            className="btn-quiet undo"
            onClick={() => {
              setSent(null)
              setComposing(true)
            }}
          >
            Send to someone else
          </button>
        </p>
      )}

      <div className="share-cols">
        <ShareRail
          share={share}
          progress={progress}
          onDownload={() => void download()}
          owner={
            owner ? { onCompose: () => setComposing(true), onRename: rename } : null
          }
        />
        <div className="stack">
          {composing && key && (
            <Composer
              token={token}
              subject={share.subject}
              ownerKey={key}
              onSent={(to, from) => {
                setComposing(false)
                setSent({ to, from })
              }}
              onCancel={() => setComposing(false)}
            />
          )}
          <Manifest share={share} />
        </div>
      </div>
    </Shell>
  )
}

/** The masthead, the content, and the two links a public page owes anyone. */
function Shell({
  who,
  foot,
  children,
}: {
  who?: ReactNode
  foot?: ReactNode
  children: ReactNode
}) {
  return (
    <>
      <a className="skip" href="#content">
        Skip to the content
      </a>
      <main id="content" className="share-main">
        <header className="masthead">
          <a className="brand" href="/">
            <span className="mark">
              <Mark />
            </span>
            Invoice Pilot
          </a>
          {who}
        </header>
        {children}
        <footer className="share-foot">
          {foot ?? <span className="spacer"></span>}
          <nav aria-label="Legal">
            <a href="#privacy">Privacy</a>
            <a href="#terms">Terms</a>
          </nav>
        </footer>
      </main>
    </>
  )
}

/** Shaped like the page it stands in for, so nothing jumps when the manifest
 *  lands. It does not shimmer: a placeholder that animates for the length of a
 *  request is a perpetual loop, and the shape already reads as "not here yet". */
function Loading() {
  return (
    <Shell>
      <div className="share-cols">
        <section className="rail" aria-busy="true" aria-label="Loading this share">
          <div>
            <p className="rail-kicker">
              <span className="ftype">zip</span>One download, no account needed
            </p>
            <h1 className="batch-name">
              <span className="sr-only">Loading this share</span>
              <span className="skel skel-name"></span>
            </h1>
          </div>
          <dl className="facts" aria-hidden="true">
            {['Invoices', 'Documents', 'Size', 'Period'].map((label) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>
                  <span className="skel skel-fact"></span>
                </dd>
              </div>
            ))}
          </dl>
          <div className="get">
            <div className="skel skel-btn"></div>
          </div>
        </section>
        <div className="stack">
          <div className="doc-card" aria-busy="true">
            <section className="part part-docs">
              <div>
                <h2 className="part-head">
                  <span className="ftype">pdf</span>Documents
                </h2>
                <p className="part-note">Loading the manifest.</p>
              </div>
              <div className="doc-grid">
                {Array.from({ length: 6 }, (_, i) => (
                  <div className="doc-tile" key={i}>
                    <div className="skel skel-thumb"></div>
                    <span className="skel skel-line"></span>
                    <span className="skel skel-line is-short"></span>
                  </div>
                ))}
              </div>
            </section>
            <section className="part part-csv">
              <div className="skel-sheet">
                {Array.from({ length: 7 }, (_, i) => (
                  <div className="skel skel-row" key={i}></div>
                ))}
              </div>
            </section>
          </div>
        </div>
      </div>
    </Shell>
  )
}
