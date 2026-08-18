import { useEffect, useState } from 'react'

import { InvoiceTable } from '../components/InvoiceTable'
import { SourcesCard } from '../components/SourcesCard'
import { relative, scanned } from '../lib/format'
import { useAccounts } from '../useAccounts'
import { useScan } from '../useScan'

export default function Dashboard() {
  const { invoices, loading, error, scanning, scanLabel, progress, lastUpdate, update } = useScan()
  const {
    accounts,
    error: accountError,
    phase,
    removing,
    connect,
    cancelConnect,
    disconnect,
  } = useAccounts()

  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [, setTick] = useState(0)

  // Re-render periodically so "Updated 3 min ago" ages without a state change.
  useEffect(() => {
    const id = window.setInterval(() => setTick((n) => n + 1), 20000)
    return () => clearInterval(id)
  }, [])

  // The one line above the table, in the order it takes precedence: a failure
  // outranks everything, a scan in flight speaks for itself, and the clock is
  // what is left when nothing is happening. A scanning job with no progress
  // yet is one that has not reached its first message.
  const meta = () => {
    if (error) return error
    if (scanning) return progress ? scanned(progress.messages, progress.invoices) : 'Starting scan…'
    return lastUpdate ? `Updated ${relative(lastUpdate)}` : 'Not scanned yet'
  }

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const toggleAll = () =>
    setSelected((current) =>
      current.size === invoices.length ? new Set() : new Set(invoices.map((i) => i.id)),
    )

  return (
    <>
      {/* Keyboard users land on the sources card otherwise, three tab stops
          before the table they came for. */}
      <a className="skip" href="#content">
        Skip to the content
      </a>
      <main id="content">
        <div className="grid">
          <SourcesCard
            accounts={accounts}
            phase={phase}
            removing={removing}
            onConnect={connect}
            onCancelConnect={cancelConnect}
            onDisconnect={(id) => void disconnect(id)}
            error={accountError}
          />
          <InvoiceTable
            invoices={invoices}
            loading={loading}
            scanning={scanning}
            scanLabel={scanLabel}
            meta={meta()}
            onUpdate={() => void update()}
            selected={selected}
            onToggle={toggle}
            onToggleAll={toggleAll}
          />
        </div>
      </main>
    </>
  )
}
