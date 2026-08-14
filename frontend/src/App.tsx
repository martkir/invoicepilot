import { useEffect, useState } from 'react'

import { InvoiceTable } from './components/InvoiceTable'
import { SourcesCard } from './components/SourcesCard'
import { relative } from './lib/format'
import { useAccounts } from './useAccounts'
import { useScan } from './useScan'

export default function App() {
  const { invoices, loading, error, scanning, scanLabel, lastUpdate, update } = useScan()
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
    <main>
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
            lastUpdate={
              error ? error : lastUpdate ? `Updated ${relative(lastUpdate)}` : 'Not scanned yet'
            }
            onUpdate={() => void update()}
            selected={selected}
            onToggle={toggle}
            onToggleAll={toggleAll}
          />
      </div>
    </main>
  )
}
