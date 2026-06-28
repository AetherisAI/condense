import { useState } from 'react'
import Search from './Search'
import Ingest from './Ingest'
import Library from './Library'
import SlashField from './SlashField'
import Logo from './Logo'
import SystemMenu from './SystemMenu'
import './App.css'

/**
 * Top-level test UI. Holds the one shared bearer token in state and hands it to
 * both panels; everything else (search, ingest) is same-origin via the Vite proxy.
 */
export default function App() {
  const [token, setToken] = useState('')

  return (
    <>
      <SlashField />
      <SystemMenu token={token} />
      <main className="app">
      <header className="app-header">
        <div className="brand">
          <Logo />
          <h1>Condense</h1>
        </div>
        <p className="tagline">Search across all your knowledge</p>
      </header>

      <label className="token">
        Token
        <input
          type="password"
          value={token}
          placeholder="bearer token"
          autoComplete="off"
          onChange={(e) => setToken(e.target.value)}
        />
      </label>

      <Search token={token} />
      <Ingest token={token} />
      </main>
      <Library token={token} />
    </>
  )
}
