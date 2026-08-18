import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import Dashboard from './routes/Dashboard'
import { SharePage } from './routes/SharePage'
// Self-hosted, not fonts.gstatic.com: a page that stalls waiting on a font CDN
// is a page that stalls. The stack in tokens.css falls back to the system
// fonts, so an offline open still renders.
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import './styles/tokens.css'
import './styles/dashboard.css'
import './styles/flow.css'

// Two pages, and no router: the share page never navigates within itself (the
// download is a real file, the composer is state) and the dashboard is one
// screen. A router would be a dependency and a bundle for one `startsWith`.
//
// /s/<token> is served by this same index.html — nginx's catch-all sends every
// unknown path to it — so the token is read off the URL here rather than
// resolved by a server route.
const share = window.location.pathname.match(/^\/s\/([^/]+)\/?$/)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {share ? <SharePage token={decodeURIComponent(share[1])} /> : <Dashboard />}
  </StrictMode>,
)
