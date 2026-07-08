import { useState } from 'react'
import { fmtSetting } from './formatSetting'
import { CheckIcon, CopyIcon, RestartIcon } from './SettingsIcons'
import SettingsTooltip from './SettingsTooltip'

/**
 * One settings row: `label [pencil] [restart-chip] [ⓘ]` on the left (deterministic single line —
 * the restart indicator lives HERE, not beside the value, so it never drifts when a long value
 * wraps), and on the right either an inline-editable input or a single-line, ellipsis-truncated,
 * copyable value.
 *
 * Consolidates what used to be two near-duplicate row renderers (the Model section's LLM_MODEL/
 * LLM_API_KEY rows and the Advanced accordion's grouped-settings loop) into one place.
 */
export default function SettingRow({
  label,
  settingKey,
  value,
  editable = false,
  restart = false,
  explanation,
  saved = false,
  onCommit,
}: {
  label: string
  settingKey: string
  value: unknown
  editable?: boolean
  restart?: boolean
  explanation?: string
  saved?: boolean
  onCommit?: (raw: string) => void
}) {
  const [copied, setCopied] = useState(false)
  const formatted = fmtSetting(value)
  const copyable = typeof value === 'string' && value.length > 0

  function copy() {
    void navigator.clipboard.writeText(String(value)).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    })
  }

  return (
    <div className={`sys-row${restart ? ' sys-row-restart' : ''}`}>
      <span className="sys-key">
        {label}
        {editable && (
          <span className="sys-pencil" title="Editable — change and press Enter">
            ✎
          </span>
        )}
        {restart && (
          <span className="sys-restart-dot" title="Requires an engine restart to change">
            <RestartIcon />
          </span>
        )}
        {explanation && <SettingsTooltip text={explanation} />}
      </span>
      <span className="sys-row-right">
        {editable ? (
          <>
            {saved && <span className="sys-saved">Saved ✓</span>}
            <input
              className="sys-edit"
              defaultValue={formatted}
              spellCheck={false}
              aria-label={`Edit ${settingKey}`}
              onKeyDown={(e) => {
                if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
              }}
              onBlur={(e) => {
                if (e.target.value !== formatted) onCommit?.(e.target.value)
              }}
            />
          </>
        ) : (
          <>
            <span className={`sys-val${value === null ? ' sys-null' : ''}`} title={formatted}>
              {formatted}
            </span>
            {copyable && (
              <button
                type="button"
                className="sys-copy-btn"
                onClick={copy}
                aria-label={`Copy ${settingKey}`}
                title="Copy full value"
              >
                {copied ? <CheckIcon /> : <CopyIcon />}
              </button>
            )}
          </>
        )}
      </span>
    </div>
  )
}
