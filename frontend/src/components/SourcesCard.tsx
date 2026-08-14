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
    <section className="card sources">
      <div className="card-label">Email sources</div>

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

      {error ? (
        <div className="accounts-note is-error">{error}</div>
      ) : (
        <div className="accounts-note">
          <span className={`dot${accounts.length === 0 ? ' dot-idle' : ''}`}></span>
          {accounts.length === 0
            ? 'No accounts connected'
            : accounts.length === 1
              ? '1 account connected'
              : `${accounts.length} accounts connected`}
        </div>
      )}
    </section>
  )
}
