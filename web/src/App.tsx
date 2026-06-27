import { useState } from 'react'
import Search from './Search'
import Ingest from './Ingest'
import './App.css'

/**
 * Top-level test UI. Holds the one shared bearer token in state and hands it to
 * both panels; everything else (search, ingest) is same-origin via the Vite proxy.
 */
export default function App() {
  const [token, setToken] = useState('')

  return (
    <main className="app">
      <h1>Condense</h1>
      <label className="token">
        Bearer token
        <input
          type="password"
          value={token}
          placeholder="INGEST_TOKEN"
          autoComplete="off"
          onChange={(e) => setToken(e.target.value)}
        />
      </label>
      <Search token={token} />
      <Ingest token={token} />
    </main>
  )
}
