import { useCallback, useEffect, useRef, useState } from 'react'

import { connectAccount, disconnectAccount, getAccounts } from './api/client'
import type { Account } from './api/types'

// Unipile can only announce a finished connection to a publicly reachable URL,
// which a local run does not have — so the wizard's result is observed by
// polling the account list instead.
const POLL_MS = 3000
const TIMEOUT_MS = 5 * 60 * 1000

/** idle → opening (fetching the link) → waiting (you are in the wizard) → idle */
export type ConnectPhase = 'idle' | 'opening' | 'waiting'

export function useAccounts() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [error, setError] = useState<string | null>(null)
  const [phase, setPhase] = useState<ConnectPhase>('idle')
  const [removing, setRemoving] = useState<string | null>(null)

  // The wizard tab, and the poll watching for its result. Both are torn down
  // together — by Cancel, by success, by timeout, or by unmount.
  const tab = useRef<Window | null>(null)
  const poll = useRef<number | null>(null)

  const stopPolling = useCallback(() => {
    if (poll.current !== null) {
      clearInterval(poll.current)
      poll.current = null
    }
  }, [])

  useEffect(() => stopPolling, [stopPolling])

  const refresh = useCallback(async () => {
    try {
      const current = await getAccounts()
      setAccounts(current)
      setError(null)
      return current
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc))
      return null
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const cancelConnect = useCallback(() => {
    stopPolling()
    tab.current?.close()
    tab.current = null
    setPhase('idle')
  }, [stopPolling])

  const connect = useCallback(() => {
    // Opened synchronously, inside the click, BEFORE any await. Opening it
    // after the request resolves loses the user gesture and gets popup-blocked.
    tab.current = window.open('', '_blank')
    setPhase('opening')
    setError(null)

    void (async () => {
      let url: string
      try {
        url = (await connectAccount()).url
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc))
        tab.current?.close()
        tab.current = null
        setPhase('idle')
        return
      }

      if (tab.current && !tab.current.closed) {
        tab.current.location.href = url
      } else {
        // Popup blocked despite the synchronous open, or closed already.
        window.location.assign(url)
        return
      }

      const before = accounts.length
      const deadline = Date.now() + TIMEOUT_MS
      setPhase('waiting')

      poll.current = window.setInterval(async () => {
        const current = await refresh()
        const connected = current !== null && current.length > before

        if (connected || Date.now() > deadline) {
          stopPolling()
          tab.current?.close()
          tab.current = null
          setPhase('idle')
          return
        }
        // Closing the tab is how someone abandons the wizard. Checked after the
        // refresh so a connection that landed just before the close still counts.
        if (tab.current?.closed) {
          cancelConnect()
        }
      }, POLL_MS)
    })()
  }, [accounts.length, cancelConnect, refresh, stopPolling])

  const disconnect = useCallback(
    async (id: string) => {
      setRemoving(id)
      try {
        await disconnectAccount(id)
        setError(null)
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : String(exc))
      } finally {
        setRemoving(null)
        // Re-read rather than trusting the local list: Unipile is the source of
        // truth, and another tab may have changed it.
        await refresh()
      }
    },
    [refresh],
  )

  return { accounts, error, phase, removing, connect, cancelConnect, disconnect }
}
