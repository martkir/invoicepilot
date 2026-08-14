// The mockup's inline SVGs, unchanged. Kept in one file so the markup that
// matters stays readable in the components that use them.

const stroke = {
  fill: 'none',
  stroke: 'currentColor',
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export const Gear = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6h.09A1.65 1.65 0 0 0 10.6 3.09V3a2 2 0 1 1 4 0v.09A1.65 1.65 0 0 0 16.11 4.6a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 20.43 9v.09A1.65 1.65 0 0 0 21.91 10.6H22a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
)

export const Plus = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" strokeWidth="2.2" {...stroke}>
    <path d="M12 5v14M5 12h14" />
  </svg>
)

export const Refresh = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" strokeWidth="2" {...stroke}>
    <path d="M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6" />
  </svg>
)

export const Download = ({ size = 16 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" strokeWidth="1.8" {...stroke}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
  </svg>
)

export const Expand = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" strokeWidth="1.8" {...stroke}>
    <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
  </svg>
)

export const Eye = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
    <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
)

export const SortAsc = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" strokeWidth="2.4" {...stroke}>
    <path d="M8 9l4-4 4 4M16 15l-4 4-4-4" />
  </svg>
)

export const SortDesc = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" strokeWidth="2.4" {...stroke}>
    <path d="M12 5v14M6 13l6 6 6-6" />
  </svg>
)

export const Unlink = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" strokeWidth="1.8" {...stroke}>
    <path d="M18.4 10.6a4.5 4.5 0 0 0-6.4-6.3l-1.4 1.4M5.6 13.4a4.5 4.5 0 0 0 6.4 6.3l1.4-1.4M2 2l20 20" />
  </svg>
)

export const GoogleMark = ({ dim = false }: { dim?: boolean }) => (
  <svg
    className={`source-mark${dim ? ' is-dim' : ''}`}
    viewBox="0 0 24 24"
    aria-hidden="true"
  >
    <path
      fill="#EA4335"
      d="M12 10.2V14h5.3c-.2 1.2-1.6 3.6-5.3 3.6A5.6 5.6 0 1 1 15.7 8l2.7-2.6A9.3 9.3 0 0 0 12 3a9 9 0 1 0 0 18c5.2 0 8.6-3.6 8.6-8.7 0-.6 0-1-.1-1.5H12z"
    />
  </svg>
)
