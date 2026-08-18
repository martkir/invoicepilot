import { useCallback, useEffect, useRef, useState } from 'react'

import { getInvoices, getScan, startScan } from './api/client'
import type { Invoice } from './api/types'

// A scan downloads attachments, runs invoice2data over every candidate and may
// fetch linked PDFs from vendors, so it takes far longer than a request can
// wait. The API hands back a job id; this polls it.
//
// Polling costs latency twice over: once waiting to ask the first time, and
// again in the gap between the job finishing and the next question. A fixed
// interval pays both at full price — at 1500ms it added up to 3s to a scan
// that took 2s. So the first question goes out immediately and the gap widens
// only as the scan proves itself long. GET /scan/{id} is a dictionary lookup,
// which is what makes the early questions cheap enough to ask.
const FIRST_POLL_MS = 150
const POLL_GROWTH = 1.3
const MAX_POLL_MS = 2000

type Phase = 'idle' | 'scanning' | 'done' | 'uptodate' | 'error'

const LABELS: Record<Phase, string> = {
  idle: 'Update',
  scanning: 'Scanning…',
  done: 'Update',
  uptodate: 'Up to date',
  error: 'Failed',
}

export function useScan() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [loading, setLoading] = useState(true)
  const [phase, setPhase] = useState<Phase>('idle')
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<number | null>(null)

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

  const update = useCallback(async () => {
    setPhase('scanning')
    setError(null)
    try {
      const started = await startScan()

      const poll = async (gap: number) => {
        const job = await getScan(started.id)
        if (job.status === 'running') {
          later(() => void poll(Math.min(gap * POLL_GROWTH, MAX_POLL_MS)), gap)
          return
        }
        if (job.status === 'error') {
          setPhase('error')
          setError(job.detail ?? 'The scan failed.')
          later(() => setPhase('idle'), 4000)
          return
        }

        await refresh()
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

      // Straight away rather than after a wait: the scan has been running since
      // POST returned, and a short one can already be over.
      void poll(FIRST_POLL_MS)
    } catch (exc) {
      setPhase('error')
      setError(exc instanceof Error ? exc.message : String(exc))
      later(() => setPhase('idle'), 4000)
    }
  }, [refresh])

  return {
    invoices,
    loading,
    error,
    scanning: phase === 'scanning',
    scanLabel: LABELS[phase],
    lastUpdate,
    update,
    refresh,
  }
}
