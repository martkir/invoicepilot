import type { Account } from '../api/types'
import type { ConnectPhase } from '../useAccounts'
import { GoogleMark, Plus, Unlink } from './Icons'

interface Props {
  accounts: Account[]
  phase: ConnectPhase
  removing: string | null
  onConnect: () => void
  onCancelConnect: () => void
  onDisconnect: (id: string) => void
  error: string | null
}

export function SourcesCard({
  accounts,
  phase,
  removing,
  onConnect,
  onCancelConnect,
  onDisconnect,
  error,
}: Props) {
  return (
    <section className="card sources" aria-label="Email sources">
      <h2 className="card-label">Email sources</h2>

      {accounts.map((account) => (
        <div
          className={`source${removing === account.id ? ' is-removing' : ''}`}
          key={account.id}
        >
          <GoogleMark />
          <span className="source-mail">{account.email}</span>
          {/* One click disconnects; there is no confirmation step. The button
              only appears on hover, and it cannot be undone — the credentials
              are discarded, so the mailbox has to be authorized again. */}
          <button
            className={`icon-btn${removing === account.id ? ' is-busy' : ''}`}
            aria-label={`Disconnect ${account.email}`}
            onClick={() => onDisconnect(account.id)}
            disabled={removing !== null}
          >
            {removing === account.id ? <span className="spinner" /> : <Unlink />}
          </button>
        </div>
      ))}

      {phase === 'waiting' ? (
        <>
          <div className="source is-pending">
            <GoogleMark dim />
            <span className="source-mail">Authorizing…</span>
            <span className="source-confirm">
              <button className="confirm-no" onClick={onCancelConnect}>
                Cancel
              </button>
            </span>
          </div>
          <div className="pending-hint">
            A Unipile tab is open. Approve there, then this updates by itself.
          </div>
        </>
      ) : (
        <button
          className={`add-source${phase === 'opening' ? ' is-busy' : ''}`}
          onClick={onConnect}
          disabled={phase === 'opening'}
        >
          {phase === 'opening' ? <span className="spinner" /> : <Plus />}
          {phase === 'opening' ? 'Opening authorization…' : 'Add source'}
        </button>
      )}

      {/* No status dot on the count. A dot that is always the same colour
          conveys no state, and the sentence already says whether anything is
          connected. */}
      {error ? (
        <p className="accounts-note is-error">{error}</p>
      ) : (
        <p className="accounts-note">
          {accounts.length === 0
            ? 'No accounts connected'
            : accounts.length === 1
              ? '1 account connected'
              : `${accounts.length} accounts connected`}
        </p>
      )}
    </section>
  )
}
