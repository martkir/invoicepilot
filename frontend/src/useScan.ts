import { useCallback, useEffect, useRef, useState } from 'react'

import { getInvoices, getScan, startScan } from './api/client'
import type { Invoice } from './api/types'

// A scan downloads attachments, runs invoice2data over every candidate and may
// fetch linked PDFs from vendors, so it takes far longer than a request can
// wait. The API hands back a job id; this polls it.
const POLL_MS = 1500

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

      const poll = async () => {
        const job = await getScan(started.id)
        if (job.status === 'running') {
          later(() => void poll(), POLL_MS)
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

      later(() => void poll(), POLL_MS)
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
