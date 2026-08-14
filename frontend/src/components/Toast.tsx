import { useEffect, useRef } from 'react'
import type { ReactNode } from 'react'

/** A transient message. Deliberately minimal — it exists because some actions
 *  succeed at doing nothing (a download with no file behind it), and silence
 *  would read as a broken button. */
export function Toast({
  message,
  onDismiss,
  after = 4000,
}: {
  /** ReactNode rather than string so a message can emphasise the part that
   *  matters — the reason, not the vendor's name. */
  message: ReactNode
  onDismiss: () => void
  after?: number
}) {
  const timer = useRef<number | null>(null)

  useEffect(() => {
    if (timer.current !== null) clearTimeout(timer.current)
    if (!message) return

    timer.current = window.setTimeout(onDismiss, after)
    return () => {
      if (timer.current !== null) clearTimeout(timer.current)
    }
  }, [message, after, onDismiss])

  return (
    // Always mounted so a screen reader announces changes rather than the
    // arrival of a new region.
    <div className="toast-wrap" role="status" aria-live="polite">
      {message && (
        <div className="toast">
          <span>{message}</span>
          <button className="toast-close" aria-label="Dismiss" onClick={onDismiss}>
            ×
          </button>
        </div>
      )}
    </div>
  )
}
