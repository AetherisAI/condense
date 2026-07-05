import { useEffect, useState } from 'react'
import Search from './Search'
import Ingest from './Ingest'
import Library from './Library'
import Chat from './Chat'
import SlashField from './SlashField'
import Logo from './Logo'
import SystemMenu from './SystemMenu'
import AgentMenu from './AgentMenu'
import './App.css'

type Tab = 'search' | 'chat'

/**
 * Top-level test UI. Holds the one shared bearer token — entered in the System menu and
 * persisted to localStorage so it survives refreshes — and hands it to every panel. Two tabs
 * share the same header/token: Search (+ Documents ingest) and Chat (the ``/v1/answer``
 * reference agent).
 */
export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem('bearerToken') ?? '')
  const [tab, setTab] = useState<Tab>(() =>
    localStorage.getItem('activeTab') === 'chat' ? 'chat' : 'search',
  )

  // Persist the token so it doesn't have to be re-entered on every page refresh.
  useEffect(() => {
    localStorage.setItem('bearerToken', token)
  }, [token])

  useEffect(() => {
    localStorage.setItem('activeTab', tab)
  }, [tab])

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

        <div className="tabs" role="tablist" aria-label="Panel">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'search'}
            className={`tab-btn${tab === 'search' ? ' active' : ''}`}
            onClick={() => setTab('search')}
          >
            Search
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'chat'}
            className={`tab-btn${tab === 'chat' ? ' active' : ''}`}
            onClick={() => setTab('chat')}
          >
            Chat
          </button>
        </div>

        {tab === 'search' ? (
          <>
            <Search token={token} />
            <Ingest token={token} />
          </>
        ) : (
          <Chat token={token} />
        )}
      </main>
      <Library token={token} />
    </>
  )
}
