import { useEffect, useState } from 'react'
import Search from './Search'
import Ingest from './Ingest'
import Library from './Library'
import SlashField from './SlashField'
import Logo from './Logo'
import SystemMenu from './SystemMenu'
import AgentMenu from './AgentMenu'
import './App.css'

/**
 * Top-level test UI. Holds the one shared bearer token — entered in the System menu and
 * persisted to localStorage so it survives refreshes — and hands it to every panel.
 */
export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('bearerToken') ?? '')

  // Persist the token so it doesn't have to be re-entered on every page refresh.
  useEffect(() => {
    localStorage.setItem('bearerToken', token)
  }, [token])

  return (
    <>
      <SlashField />
      <SystemMenu token={token} setToken={setToken} />
      <AgentMenu />
      <main className="app">
      <header className="app-header">
        <div className="brand">
          <Logo />
          <h1>Condense</h1>
        </div>
        <p className="tagline">Search across all your knowledge</p>
      </header>

        <Search token={token} />
        <Ingest token={token} />
      </main>
      <Library token={token} />
    </>
  )
}
