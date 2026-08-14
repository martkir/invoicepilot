import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
// Self-hosted, not fonts.gstatic.com: a page that stalls waiting on a font CDN
// is a page that stalls. The stack in tokens.css falls back to the system
// fonts, so an offline open still renders.
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import './styles/tokens.css'
import './styles/dashboard.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
