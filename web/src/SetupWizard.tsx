import { useEffect, useRef, useState } from 'react'
import Logo from './Logo'
import SlashField from './SlashField'
import { setApiBase } from './api'
import { detectProvider, type DetectedProvider } from './provider'
import { fmtSize } from './ingestClient'
import {
  appConfigGet,
  appConfigSet,
  backendStart,
  backendStateError,
  backendStateKind,
  listenEvent,
  provisionCancel,
  provisionStart,
  provisioningStatus,
  type AppConfig,
  type BackendStateEvent,
  type ComponentId,
  type ProvisionErrorEvent,
  type ProvisionProgressEvent,
  type ProvisioningStatus,
  type Unlisten,
} from './tauri'

/**
 * Full-screen first-run overlay (D60/T2) — shown only while `isTauri && config.mode === null`.
 * Renders nothing at all once `config.mode` is already set (returning user, or right after this
 * wizard finishes): the caller (`App.tsx`) keeps this mounted whenever `isTauri`, and this
 * component's own render logic is the ONE place that decides whether the overlay is visible, so
 * there is never a flash of the chat behind it while the initial `app_config_get()` is in flight —
 * that gap shows the same busy brand mark the rest of the app uses for "working", not a spinner.
 *
 * Two flows, one seam (`AppConfig.mode`): **Run locally** — pick components → download & start →
 * backend health-walk → done; **Connect to a server** — base URL + token → test → save. Every
 * step surfaces its own errors inline with a Retry — this overlay never dead-ends the user.
 */

type StepId = 'choose' | 'local-setup' | 'provisioning' | 'starting' | 'client-setup'

/** Provider `base_url`/`model` defaults applied when `detectProvider` recognizes the pasted key's
 * shape — a first-run convenience only, not a hard pin: fully editable later once desktop Model
 * settings exist. Kept as ONE map, exactly per the design brief, so there is a single place to
 * update if a provider's default model changes. */
const PROVIDER_DEFAULTS: Record<DetectedProvider, { base_url: string; model: string }> = {
  Anthropic: { base_url: 'https://api.anthropic.com/v1', model: 'claude-sonnet-4-5' },
  OpenAI: { base_url: 'https://api.openai.com/v1', model: 'gpt-4o' },
  'Mistral (likely)': { base_url: 'https://api.mistral.ai/v1', model: 'mistral-large-latest' },
}

const PHASE_LABEL: Record<ProvisionProgressEvent['phase'], string> = {
  downloading: 'Downloading',
  verifying: 'Verifying',
  unpacking: 'Unpacking',
  done: 'Done',
}

function describeError(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function formatMaybeSize(bytes?: number): string {
  return typeof bytes === 'number' ? fmtSize(bytes) : '—'
}

type SetupWizardProps = {
  /** Fired once the resolved config is known — on the initial load (whatever `mode` already is)
   * AND again every time this wizard changes it. Lets `App.tsx` learn `engine_port`/`ingest_token`
   * without re-fetching, so its own local-mode auto-wire effect stays in sync. */
  onConfigResolved: (config: AppConfig) => void
  /** The SAME token setter `App.tsx`/`SystemMenu` already persist to `localStorage.bearerToken` —
   * reused here (client-mode "Save") so the wizard never fights that existing state. */
  onTokenChange: (token: string) => void
}

export default function SetupWizard({ onConfigResolved, onTokenChange }: SetupWizardProps) {
  const [loading, setLoading] = useState(true)
  const [config, setConfig] = useState<AppConfig | null>(null)
  // Set only if `app_config_get` itself rejects — effectively never in practice (it's a local
  // file read/create), but per the "zero infinite spinners anywhere" rule this still needs a
  // real terminal UI state instead of leaving `loading` stuck at `true` forever.
  const [configError, setConfigError] = useState<string | null>(null)
  const [step, setStep] = useState<StepId>('choose')
  const [provisioning, setProvisioning] = useState<ProvisioningStatus | null>(null)
  // Set only if `provisioning_status` itself fails (manifest unreachable, parse error, etc.).
  // Deliberately NEVER gates the choose/loading screens — only the 'local-setup' step (the one
  // that actually needs the component list) reads it, with a Retry that bumps
  // `provisioningStatusAttempt`.
  const [provisioningError, setProvisioningError] = useState<string | null>(null)
  const [provisioningStatusAttempt, setProvisioningStatusAttempt] = useState(0)
  const [selected, setSelected] = useState<Partial<Record<ComponentId, boolean>>>({})
  const [llmKeyDraft, setLlmKeyDraft] = useState('')
  const [provisionIds, setProvisionIds] = useState<ComponentId[]>([])
  const [progress, setProgress] = useState<Partial<Record<ComponentId, ProvisionProgressEvent>>>({})
  const [provisionErrors, setProvisionErrors] = useState<Partial<Record<ComponentId, string>>>({})
  const [provisionAttempt, setProvisionAttempt] = useState(0)
  const [backendAttempt, setBackendAttempt] = useState(0)
  const [backendStates, setBackendStates] = useState<{ engine: string; embedder: string }>({
    engine: 'stopped',
    embedder: 'stopped',
  })
  const [stepError, setStepError] = useState<string | null>(null)
  const [clientBase, setClientBase] = useState('')
  const [clientToken, setClientToken] = useState('')
  const [testState, setTestState] = useState<'idle' | 'testing' | 'up' | 'down'>('idle')
  const [saving, setSaving] = useState(false)

  // The base config + resolved LLM choice are frozen at the moment the user commits to "Download &
  // start" (`handleStartLocal`) rather than re-read live from state — refs, not deps, so the
  // provisioning/starting effects below don't need `config`/`llmKeyDraft` in their dependency
  // arrays (including `config` there would re-fire the effect the instant it calls `setConfig`
  // itself at the end, double-invoking `backend_start`).
  const baseConfigRef = useRef<AppConfig | null>(null)
  const pendingLlmRef = useRef<{ base_url: string; model: string; api_key: string } | null>(null)

  // Initial load: config ONLY. Reports the resolved config up immediately, whatever `mode` turns
  // out to be — a returning user (mode already set) never sees this component render anything
  // beyond this effect. Deliberately does NOT wait on `provisioning_status` (that call fetches a
  // manifest over the network and can fail on a pristine install — e.g. the baked default
  // manifest URL 404ing against a private repo); this bare spinner must clear on the config alone,
  // or every install with no reachable manifest hangs on it forever (see `provisioningError`
  // below for how the manifest fetch's own failure is surfaced instead of swallowed).
  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const cfg = await appConfigGet()
        if (cancelled) return
        setConfig(cfg)
        setLoading(false)
        onConfigResolved(cfg)
      } catch (err) {
        if (!cancelled) {
          setConfigError(describeError(err))
          setLoading(false)
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [onConfigResolved])

  // Provisioning status: fetched independently of config, only once there's a pristine (`mode ===
  // null`) config to act on — a returning user in 'local'/'client' mode never needs the component
  // list, so this skips the manifest fetch entirely for them instead of doing it silently on every
  // launch. Failure surfaces via `provisioningError`; Retry bumps `provisioningStatusAttempt`.
  useEffect(() => {
    if (!config || config.mode !== null) return
    let cancelled = false
    setProvisioningError(null)
    async function load() {
      try {
        const prov = await provisioningStatus()
        if (!cancelled) setProvisioning(prov)
      } catch (err) {
        if (!cancelled) setProvisioningError(describeError(err))
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [config, provisioningStatusAttempt])

  // Default the component checklist to "download what's missing" once provisioning status loads.
  useEffect(() => {
    if (!provisioning) return
    setSelected(Object.fromEntries(provisioning.components.map((c) => [c.id, !c.installed])))
  }, [provisioning])

  // Provisioning step: subscribe to progress/error events, then kick off the download. Advances to
  // 'starting' only once every requested id has actually reached a terminal state; surfaces the
  // error inline (with a Retry that bumps `provisionAttempt`, which is in this effect's deps) on
  // failure.
  useEffect(() => {
    if (step !== 'provisioning') return
    let disposed = false
    const disposers: Unlisten[] = []
    let resolveSettled: (() => void) | null = null
    setStepError(null)
    async function run() {
      const settled = new Set<ComponentId>()
      const errored = new Set<ComponentId>()
      const settledPromise = new Promise<void>((resolve) => {
        resolveSettled = resolve
      })
      function checkSettled() {
        if (provisionIds.every((id) => settled.has(id))) resolveSettled?.()
      }

      const unProgress = await listenEvent<ProvisionProgressEvent>('provision-progress', (e) => {
        setProgress((prev) => ({ ...prev, [e.id]: e }))
        if (e.phase === 'done') {
          settled.add(e.id)
          checkSettled()
        }
      })
      if (disposed) {
        unProgress()
        return
      }
      disposers.push(unProgress)

      const unError = await listenEvent<ProvisionErrorEvent>('provision-error', (e) => {
        setProvisionErrors((prev) => ({ ...prev, [e.id]: e.error }))
        settled.add(e.id)
        errored.add(e.id)
        checkSettled()
      })
      if (disposed) {
        unError()
        return
      }
      disposers.push(unError)

      if (provisionIds.length > 0) {
        try {
          await provisionStart(provisionIds)
        } catch (err) {
          if (!disposed) setStepError(describeError(err))
          return
        }
        // `provision_start` only kicks the download off in a background Tokio task (`provisioning.rs`
        // spawns and returns `Ok(())` immediately) — the invoke above resolves long before any
        // component is actually fetched. Without waiting here, `backend_start` in the 'starting'
        // step below fires right away and can find the embedder/model archive still
        // downloading/unpacking, failing with a spurious "binary not found — provision it first"
        // (a real network download, even a fast one, is never as instant as the promise makes it
        // look — unlike a small file:// copy, which is why this never surfaced against an
        // all-file:// manifest). Wait for every requested id to reach a terminal state (a "done"
        // progress phase or a `provision-error` event) before treating provisioning as finished.
        await settledPromise
      }
      if (disposed) return
      if (errored.size > 0) {
        // Stay on this step — the per-component error + Retry button already rendered from
        // `provisionErrors` is the way forward, not a `backend_start` doomed to fail.
        return
      }
      setBackendStates({ engine: 'stopped', embedder: 'stopped' })
      setStep('starting')
    }
    void run()
    return () => {
      disposed = true
      resolveSettled?.()
      disposers.forEach((fn) => fn())
    }
  }, [step, provisionIds, provisionAttempt])

  // Backend-starting step: subscribe to state events, call backend_start, then persist
  // mode:'local' (+ the frozen LLM choice) once it's up. Retry bumps `backendAttempt`.
  useEffect(() => {
    if (step !== 'starting') return
    let disposed = false
    const disposers: Unlisten[] = []
    setStepError(null)
    async function run() {
      const unState = await listenEvent<BackendStateEvent>('backend-state', (e) => {
        setBackendStates((prev) => ({ ...prev, [e.component]: e.state }))
      })
      if (disposed) {
        unState()
        return
      }
      disposers.push(unState)

      try {
        await backendStart()
      } catch (err) {
        if (!disposed) setStepError(describeError(err))
        return
      }
      if (disposed) return

      const base = baseConfigRef.current
      if (!base) return
      const finalConfig: AppConfig = {
        ...base,
        mode: 'local',
        llm: pendingLlmRef.current ?? base.llm,
      }
      try {
        const saved = await appConfigSet(finalConfig)
        if (disposed) return
        setConfig(saved)
        onConfigResolved(saved)
      } catch (err) {
        if (!disposed) setStepError(describeError(err))
      }
    }
    void run()
    return () => {
      disposed = true
      disposers.forEach((fn) => fn())
    }
  }, [step, backendAttempt, onConfigResolved])

  function handleStartLocal() {
    if (!config) return
    baseConfigRef.current = config
    const draft = llmKeyDraft.trim()
    if (draft) {
      const detected = detectProvider(draft)
      const defaults = detected ? PROVIDER_DEFAULTS[detected] : null
      pendingLlmRef.current = { base_url: defaults?.base_url ?? '', model: defaults?.model ?? '', api_key: draft }
    } else {
      pendingLlmRef.current = null
    }
    const ids = (Object.keys(selected) as ComponentId[]).filter((id) => selected[id])
    setProvisionIds(ids)
    setProgress({})
    setProvisionErrors({})
    setStepError(null)
    setProvisionAttempt(0)
    setBackendAttempt(0)
    setStep('provisioning')
  }

  async function handleTestConnection() {
    setTestState('testing')
    try {
      const headers = new Headers()
      if (clientToken) headers.set('Authorization', `Bearer ${clientToken}`)
      const resp = await fetch(clientBase.replace(/\/+$/, '') + '/healthz', { headers })
      setTestState(resp.ok ? 'up' : 'down')
    } catch {
      setTestState('down')
    }
  }

  async function handleSaveClient() {
    if (!config) return
    setSaving(true)
    setStepError(null)
    try {
      const saved = await appConfigSet({ ...config, mode: 'client' })
      setApiBase(clientBase)
      onTokenChange(clientToken)
      setConfig(saved)
      onConfigResolved(saved)
    } catch (err) {
      setStepError(describeError(err))
    } finally {
      setSaving(false)
    }
  }

  function stateLabel(component: 'engine' | 'embedder'): string {
    const raw = backendStates[component]
    const kind = backendStateKind(raw)
    if (kind === 'error') return `Error — ${backendStateError(raw) || 'unknown error'}`
    if (kind === 'running') return 'Running'
    if (kind === 'starting') return 'Starting…'
    return 'Stopped'
  }

  if (loading) {
    return (
      <div className="wizard-overlay" role="dialog" aria-modal="true" aria-label="Loading Condense">
        {/* The overlay covers the app-level SlashField, so it mounts its own — the signature
            slash-mark canvas stays part of the first-run scene (see .wizard-overlay in App.css). */}
        <SlashField />
        <div className="wizard-loading mark-busy">
          <Logo />
        </div>
      </div>
    )
  }

  // `app_config_get` itself failed — extremely rare (a local file read/create), but still a real
  // terminal state rather than an indefinite spinner. No retry-in-place here: `onConfigResolved`
  // was never called, so a reload is the only path back to a clean init.
  if (configError || !config) {
    return (
      <div className="wizard-overlay" role="dialog" aria-modal="true" aria-label="Condense setup error">
        <SlashField />
        <div className="wizard-card">
          <div className="wizard-head">
            <div className="wizard-head-mark">
              <Logo />
            </div>
            <div>
              <p className="wizard-eyebrow">First-run setup</p>
              <h2 className="wizard-title">Couldn't load your configuration</h2>
            </div>
          </div>
          <p className="sys-error">{configError ?? 'Unknown error.'}</p>
        </div>
      </div>
    )
  }

  if (config.mode !== null) return null

  const detectedProvider = detectProvider(llmKeyDraft)

  return (
    <div className="wizard-overlay" role="dialog" aria-modal="true" aria-label="Condense setup">
      <SlashField />
      <div className="wizard-card">
        <div className="wizard-head">
          <div className="wizard-head-mark">
            <Logo />
          </div>
          <div>
            <p className="wizard-eyebrow">First-run setup</p>
            <h2 className="wizard-title">
              {step === 'choose' && 'How do you want to run Condense?'}
              {step === 'local-setup' && 'Run locally'}
              {(step === 'provisioning' || step === 'starting') && 'Setting up your local backend'}
              {step === 'client-setup' && 'Connect to a server'}
            </h2>
          </div>
        </div>

        {step === 'choose' && (
          <div className="wizard-choices">
            <button type="button" className="wizard-choice" onClick={() => setStep('local-setup')}>
              <span className="wizard-choice-badge">Recommended</span>
              <span className="wizard-choice-title">Run locally</span>
              <span className="wizard-choice-desc">
                Downloads the backend and the bge-m3 embedding model, and runs everything on this
                machine. Your documents never leave it.
              </span>
            </button>
            <button type="button" className="wizard-choice" onClick={() => setStep('client-setup')}>
              <span className="wizard-choice-title">Connect to a server</span>
              <span className="wizard-choice-desc">
                Point this app at an existing Condense API — your own server or a hosted instance.
              </span>
            </button>
          </div>
        )}

        {step === 'local-setup' && (
          <div className="wizard-step-body">
            <button type="button" className="wizard-secondary-btn wizard-back" onClick={() => setStep('choose')}>
              ‹ Back
            </button>

            {provisioning ? (
              <>
                {provisioning.source === 'embedded-fallback' && (
                  <p className="sys-muted">
                    Couldn't reach the latest component list online — showing the version bundled with
                    this app instead.
                  </p>
                )}

                <ul className="wizard-component-list">
                  {provisioning.components.map((c) => (
                    <li className="wizard-component-row" key={c.id}>
                      <input
                        type="checkbox"
                        id={`wizard-comp-${c.id}`}
                        checked={selected[c.id] ?? false}
                        onChange={(e) => setSelected((prev) => ({ ...prev, [c.id]: e.target.checked }))}
                      />
                      <label className="wizard-component-meta" htmlFor={`wizard-comp-${c.id}`}>
                        <span className="wizard-component-name">{c.name}</span>
                        <span className="wizard-component-size">{formatMaybeSize(c.size_bytes)}</span>
                      </label>
                      {c.installed && (
                        <span className="wizard-component-status">
                          Installed{c.version ? ` · ${c.version}` : ''}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>

                <div className="wizard-llm-field">
                  <label className="sys-label" htmlFor="wizard-llm-key">
                    LLM API key (optional)
                  </label>
                  <div className="sys-model-key-row">
                    <input
                      id="wizard-llm-key"
                      className="sys-token-input"
                      type="password"
                      value={llmKeyDraft}
                      placeholder="paste a Mistral, OpenAI, or Anthropic key"
                      autoComplete="off"
                      spellCheck={false}
                      onChange={(e) => setLlmKeyDraft(e.target.value)}
                    />
                    {detectedProvider && <span className="sys-provider-badge">{detectedProvider}</span>}
                  </div>
                  {detectedProvider && (
                    <p className="sys-model-hint">
                      Will use {PROVIDER_DEFAULTS[detectedProvider].base_url} ·{' '}
                      {PROVIDER_DEFAULTS[detectedProvider].model} — editable later in Settings.
                    </p>
                  )}
                  {llmKeyDraft && (
                    <button type="button" className="wizard-skip-link" onClick={() => setLlmKeyDraft('')}>
                      Skip for now
                    </button>
                  )}
                </div>

                {stepError && <p className="sys-error">{stepError}</p>}

                <div className="wizard-actions">
                  <button type="button" className="btn-primary" onClick={handleStartLocal}>
                    Download &amp; start
                  </button>
                </div>
              </>
            ) : provisioningError ? (
              <>
                <p className="sys-error">
                  Couldn't load the component list — {provisioningError}. Check your connection, or set a
                  manifest URL in System ▸ Desktop, then retry.
                </p>
                <div className="wizard-actions">
                  <button
                    type="button"
                    className="wizard-secondary-btn"
                    onClick={() => setProvisioningStatusAttempt((n) => n + 1)}
                  >
                    Retry
                  </button>
                </div>
              </>
            ) : (
              <div className="wizard-loading-inline mark-busy">
                <Logo />
              </div>
            )}
          </div>
        )}

        {(step === 'provisioning' || step === 'starting') && (
          <div className="wizard-step-body">
            <div className="wizard-loading-inline mark-busy">
              <Logo />
            </div>

            {step === 'provisioning' && (
              <ul className="wizard-progress-list">
                {provisionIds.map((id) => {
                  const p = progress[id]
                  const err = provisionErrors[id]
                  const knownTotal = provisioning?.components.find((c) => c.id === id)?.size_bytes ?? 0
                  const total = p?.total ?? knownTotal
                  const downloaded = p?.downloaded ?? 0
                  const pct = total > 0 ? Math.min(100, Math.round((downloaded / total) * 100)) : 0
                  const name = provisioning?.components.find((c) => c.id === id)?.name ?? id
                  return (
                    <li className="wizard-progress-row" key={id}>
                      <div className="wizard-progress-label">
                        <span>{name}</span>
                        <span className="sys-muted">
                          {p ? `${PHASE_LABEL[p.phase]} · ${fmtSize(downloaded)} / ${fmtSize(total)}` : 'Queued…'}
                        </span>
                      </div>
                      <div className="wizard-progress-track">
                        <div className="wizard-progress-fill" style={{ width: `${pct}%` }} />
                      </div>
                      {err && (
                        <p className="sys-error">
                          {err}{' '}
                          <button
                            type="button"
                            className="wizard-retry"
                            onClick={() => setProvisionAttempt((n) => n + 1)}
                          >
                            Retry
                          </button>
                        </p>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}

            {step === 'starting' && (
              <ul className="wizard-progress-list">
                {(['embedder', 'engine'] as const).map((component) => {
                  const kind = backendStateKind(backendStates[component])
                  return (
                    <li className="wizard-status-row" key={component}>
                      <span>{component === 'embedder' ? 'Embedding server' : 'Engine'}</span>
                      <span className={`wizard-state-badge is-${kind}`}>{stateLabel(component)}</span>
                    </li>
                  )
                })}
              </ul>
            )}

            {stepError && (
              <p className="sys-error">
                {stepError}{' '}
                <button
                  type="button"
                  className="wizard-retry"
                  onClick={() =>
                    step === 'provisioning' ? setProvisionAttempt((n) => n + 1) : setBackendAttempt((n) => n + 1)
                  }
                >
                  Retry
                </button>
              </p>
            )}

            {step === 'provisioning' && (
              <div className="wizard-actions">
                <button
                  type="button"
                  className="wizard-secondary-btn"
                  onClick={() => {
                    // Best-effort — we're already navigating away regardless of the outcome, but
                    // an uncaught rejection here would still surface as an unhandled promise
                    // rejection in the console for no user-visible benefit.
                    void provisionCancel().catch(() => {})
                    setStep('local-setup')
                  }}
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        )}

        {step === 'client-setup' && (
          <div className="wizard-step-body">
            <button type="button" className="wizard-secondary-btn wizard-back" onClick={() => setStep('choose')}>
              ‹ Back
            </button>

            <div className="sys-token">
              <label className="sys-label" htmlFor="wizard-client-base">
                API base URL
              </label>
              <input
                id="wizard-client-base"
                className="sys-token-input"
                type="text"
                value={clientBase}
                placeholder="https://condense.example.com"
                autoComplete="off"
                spellCheck={false}
                onChange={(e) => {
                  setClientBase(e.target.value)
                  setTestState('idle')
                }}
              />
            </div>

            <div className="sys-token">
              <label className="sys-label" htmlFor="wizard-client-token">
                Bearer token
              </label>
              <input
                id="wizard-client-token"
                className="sys-token-input"
                type="password"
                value={clientToken}
                placeholder="paste your token"
                autoComplete="off"
                spellCheck={false}
                onChange={(e) => setClientToken(e.target.value)}
              />
            </div>

            <div className="wizard-test-row">
              <button
                type="button"
                className="wizard-secondary-btn"
                onClick={() => void handleTestConnection()}
                disabled={!clientBase || testState === 'testing'}
              >
                Test connection
              </button>
              {testState !== 'idle' && (
                <span className="sys-health-chip">
                  <span
                    className={`sys-dot ${testState === 'up' ? 'sys-dot-up' : testState === 'down' ? 'sys-dot-down' : ''}`}
                    aria-hidden="true"
                  />
                  <span className="sys-health-name">API</span>
                  <span className="sys-health-detail">{testState === 'testing' ? 'testing…' : testState}</span>
                </span>
              )}
            </div>

            {stepError && <p className="sys-error">{stepError}</p>}

            <div className="wizard-actions">
              <button
                type="button"
                className="btn-primary"
                onClick={() => void handleSaveClient()}
                disabled={!clientBase || saving}
              >
                {saving ? 'Saving…' : 'Save & connect'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
