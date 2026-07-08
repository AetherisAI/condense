/**
 * Opens a URL in the user's default OS browser/handler — the one helper every "external link"
 * surface in the desktop app should go through (System drawer's API docs link, the Downloads
 * section's release/GitHub links, …) instead of a bare `<a href>`/`window.open`.
 *
 * Inside the real Tauri shell, a plain `<a target="_blank">` navigates the APP'S OWN webview
 * rather than escaping to the OS browser (there is no "new tab" to open one in) — that's the
 * "link does nothing" symptom for anything pointed at an external site. `@tauri-apps/plugin-shell`'s
 * `open()` is the documented escape hatch, scoped by the `shell:allow-open` capability
 * (`capabilities/default.json`) to just the origins this app actually links to.
 *
 * In an ordinary browser tab (dev/QA, or the `forceTauri` mock seam — see `platform.ts`) falls
 * back to `window.open`, i.e. completely normal browser behavior.
 */

import { open as tauriOpenExternal } from '@tauri-apps/plugin-shell'
import { isRealTauri } from '../platform'

export async function openExternal(url: string): Promise<void> {
  if (isRealTauri) {
    await tauriOpenExternal(url)
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}
