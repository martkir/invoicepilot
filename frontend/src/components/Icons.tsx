// One set, one grid, one stroke weight (Section 3.C). Every glyph is drawn on
// the same 24x24 viewBox and emitted through the helper below, so the set
// cannot drift the way it did when each icon carried its own stroke width.
//
// These are the paths from docs/flows/share-flow-v3-light/build.py, which is
// where the set was designed; if one changes there it changes here.

interface GlyphProps {
  size?: number
  children: React.ReactNode
}

const Glyph = ({ size = 16, children }: GlyphProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.6"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    {children}
  </svg>
)

export const Plus = () => (
  <Glyph size={14}>
    <path d="M12 5.4v13.2" />
    <path d="M5.4 12h13.2" />
  </Glyph>
)

export const Refresh = () => (
  <Glyph size={15}>
    <path d="M20.4 12a8.4 8.4 0 1 1-2.5-6" />
    <path d="M20.4 4v4.4H16" />
  </Glyph>
)

// The tray is shared with Share below, and only the arrow flips: the two are
// the same gesture in opposite directions, which is what makes them a pair.
export const Download = ({ size = 16 }: { size?: number }) => (
  <Glyph size={size}>
    <path d="M12 3.6v11.9" />
    <path d="m8.2 11.9 3.8 3.6 3.8-3.6" />
    <path d="M5 13v4.9A2.1 2.1 0 0 0 7.1 20h9.8a2.1 2.1 0 0 0 2.1-2.1V13" />
  </Glyph>
)

export const Share = ({ size = 16 }: { size?: number }) => (
  <Glyph size={size}>
    <path d="M12 15.5V3.6" />
    <path d="m8.2 7.2 3.8-3.6 3.8 3.6" />
    <path d="M5 13v4.9A2.1 2.1 0 0 0 7.1 20h9.8a2.1 2.1 0 0 0 2.1-2.1V13" />
  </Glyph>
)

export const Eye = () => (
  <Glyph>
    <path d="M2.8 12S6.9 5.9 12 5.9 21.2 12 21.2 12 17.1 18.1 12 18.1 2.8 12 2.8 12Z" />
    <circle cx="12" cy="12" r="2.9" />
  </Glyph>
)

export const Unlink = () => (
  <Glyph size={15}>
    <path d="M18.1 10.7a4.3 4.3 0 0 0-6.1-6.1l-1.3 1.3" />
    <path d="M5.9 13.3a4.3 4.3 0 0 0 6.1 6.1l1.3-1.3" />
    <path d="m3.6 3.6 16.8 16.8" />
  </Glyph>
)

// Google's own mark, in currentColor rather than in its four brand colours:
// Section 4.9 asks single-colour logos to render in --ink or --ink-soft, and a
// four-colour glyph beside a one-accent palette is a second accent.
export const GoogleMark = ({ dim = false }: { dim?: boolean }) => (
  <svg
    className={`source-mark${dim ? ' is-dim' : ''}`}
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M12 10.2V14h5.3c-.2 1.2-1.6 3.6-5.3 3.6A5.6 5.6 0 1 1 15.7 8l2.7-2.6A9.3 9.3 0 0 0 12 3a9 9 0 1 0 0 18c5.2 0 8.6-3.6 8.6-8.7 0-.6 0-1-.1-1.5H12z" />
  </svg>
)
