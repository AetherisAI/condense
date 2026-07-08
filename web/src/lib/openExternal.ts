import { openUrl } from '@tauri-apps/plugin-opener'
import { isRealTauri } from '../platform'

/**
 * Opens `url` in the OS's default browser — the one helper every external link in this app must
 * route through, instead of `<a target="_blank">`/`window.open` directly.
 *
 * Inside the Tauri desktop shell, the WebView never lets `window.open`/a `target="_blank"` anchor
 * reach the OS: the click is swallowed and nothing happens (this is exactly what an unmodified
 * `<a href=... target="_blank">` does in the packaged app — works fine in a plain browser tab,
 * a no-op in the desktop build). `tauri-plugin-opener`'s `openUrl` is the supported way to hand a
 * URL to the OS's own "open with default app" — so `isRealTauri` (the same single detection point
 * `tauri.ts` uses for every other real-vs-mock command) routes there; everywhere else (an ordinary
 * browser tab, or the `forceTauri` QA seam — see `platform.ts`, which is deliberately NOT real
 * Tauri) falls back to plain `window.open`, preserving today's normal-browser behavior exactly.
 */
export async function openExternal(url: string): Promise<void> {
  if (isRealTauri) {
    await openUrl(url)
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}
