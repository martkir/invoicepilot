import { useCallback, useEffect, useRef, useState } from 'react'

import { getInvoices, getScan, startScan } from './api/client'
import type { Invoice } from './api/types'

// A scan downloads attachments, runs invoice2data over every candidate and may
// fetch linked PDFs from vendors, so it takes far longer than a request can
// wait. The API hands back a job id; this polls it.
//
// A flat second, not a widening gap. Each answer now carries the counts the
// dashboard puts on screen, so a poll is a frame of an animation rather than
// an impatient "are we there yet" — and one that comes every second reads as
// steady where one that arrives after 150ms and then not for 2s does not.
// GET /scan/{id} is a dictionary lookup, which is what makes that affordable.
const POLL_MS = 1000

type Phase = 'idle' | 'scanning' | 'done' | 'uptodate' | 'error'

const LABELS: Record<Phase, string> = {
  idle: 'Update',
  scanning: 'Scanning…',
  done: 'Update',
  uptodate: 'Up to date',
  error: 'Failed',
}

/** What the running scan has got through. Null when none is running, and
 *  null again the moment one finishes — the new rows are the report then, and
 *  a tally left behind beside them would just be the same news twice. */
export interface ScanProgress {
  messages: number
  invoices: number
}

export function useScan() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<number | null>(null)
  const [progress, setProgress] = useState<ScanProgress | null>(null)

  // Cleared on unmount so a poll or a label reset cannot fire into a gone tree.
  const timers = useRef<number[]>([])
  useEffect(() => () => timers.current.forEach(clearTimeout), [])

  const later = (fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, ms))
  }

  const refresh = useCallback(async () => {
    try {
      const page = await getInvoices()
      setInvoices(page.items)
      setError(null)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const failed = useCallback((detail: string) => {
    setPhase('error')
    setError(detail)
    setProgress(null)
    // The reason clears with the button. Left up, it would still be sitting
    // there an hour later where the clock belongs.
    later(() => {
      setPhase('idle')
      setError(null)
    }, 4000)
  }, [])

  const update = useCallback(async () => {
    setPhase('scanning')
    setError(null)
    // A previous scan's tally must not be what the first frame of this one
    // shows.
    setProgress(null)
    try {
      const started = await startScan()

      const poll = async () => {
        const job = await getScan(started.id)
        if (job.status === 'running') {
          // Zero of everything is not progress — it is the scan still listing
          // the mailbox. Reported as nothing, so the line can say so in words
          // instead of counting up from a pair of noughts.
          if (job.messages_scanned > 0) {
            setProgress({ messages: job.messages_scanned, invoices: job.invoices_found })
          }
          later(() => void poll(), POLL_MS)
          return
        }
        if (job.status === 'error') {
          failed(job.detail ?? 'The scan failed.')
          return
        }

        // Rows first, then the tally comes down: swapping them would blank the
        // line for the length of the fetch, which reads as the scan dropping
        // what it had just told you.
        await refresh()
        setProgress(null)
        setLastUpdate(Date.now())
        // Distinguish "found nothing new" from "found something", the way the
        // original mockup's button did.
        if (job.invoices_new > 0) {
          setPhase('done')
        } else {
          setPhase('uptodate')
          later(() => setPhase('idle'), 2500)
        }
      }

      later(() => void poll(), POLL_MS)
    } catch (exc) {
      failed(exc instanceof Error ? exc.message : String(exc))
    }
  }, [refresh, failed])

  return {
    invoices,
    loading,
    error,
    scanning: phase === 'scanning',
    scanLabel: LABELS[phase],
    progress,
    lastUpdate,
    update,
    refresh,
  }
}
