/**
 * Single source of truth for "are we running inside the Tauri desktop shell" (D60/T2). Every
 * desktop-only surface (`SetupWizard`, `SystemMenu`'s "Desktop" section, the folder agent's live
 * controls) gates on `isTauri` — so the ordinary browser bundle stays byte-identical when neither
 * condition holds. `tauri.ts` gates its real-vs-mock command dispatch on `isRealTauri` ALONE, so
 * flipping `forceTauri` inside an actual Tauri window would never shadow the real IPC bridge with
 * mocks — only a real Tauri build can ever be "real".
 *
 * `forceTauri` is a dev/QA seam ONLY: setting `localStorage.forceTauri = '1'` in an ordinary
 * Chrome tab lets the wizard + desktop settings be exercised end-to-end against the deterministic
 * in-memory mocks in `tauri.ts`, without a Tauri build. Clearing the key (or `localStorage.clear()`
 * + reload) restores plain-browser behavior — no new UI, byte-identical to today.
 */

/** True only when the real Tauri v2 IPC bridge is present on `window`. */
export const isRealTauri: boolean = '__TAURI_INTERNALS__' in window

/** `isRealTauri`, OR the `forceTauri` dev/QA seam is set — gates every desktop-only UI surface. */
export const isTauri: boolean = isRealTauri || localStorage.getItem('forceTauri') === '1'
