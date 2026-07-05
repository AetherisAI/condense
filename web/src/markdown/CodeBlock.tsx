import { useState } from 'react'
import { Highlight, Prism, themes } from 'prism-react-renderer'
import './prismBash'

/** Fence info strings the model might use for "no real language" content — rendered as a plain
 * (unhighlighted) block rather than guessing. */
const PLAIN_LANGUAGES = new Set(['text', 'plain', 'plaintext', 'txt'])

/** Common aliases mapped to the grammar key Prism actually registers under. */
const LANGUAGE_ALIASES: Record<string, string> = {
  py: 'python',
  ts: 'typescript',
  js: 'javascript',
  sh: 'bash',
  shell: 'bash',
  shellscript: 'bash',
  yml: 'yaml',
  md: 'markdown',
}

function normalizeLanguage(raw: string): string {
  const lower = raw.trim().toLowerCase()
  return LANGUAGE_ALIASES[lower] ?? lower
}

/**
 * One fenced code block from a chat answer (D47): a language label, a copy button (same
 * copy/"Copied ✓" pattern as `Search.tsx`'s machine-mode copy), syntax highlighting via
 * `prism-react-renderer`, and its OWN `overflow-x: auto` scroll box so a wide block (long log
 * lines, a `docker-compose.yml`) scrolls within itself and never widens the chat column.
 */
export default function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false)
  const normalized = normalizeLanguage(language || 'text')
  // Unknown/plain languages fall back to Prism's own no-op "plain" grammar instead of crashing
  // `Highlight` on a missing grammar key.
  const safeLanguage = PLAIN_LANGUAGES.has(normalized) || Prism.languages[normalized] ? normalized : 'text'

  function copy() {
    void navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div className="code-block">
      <div className="code-block-head">
        <span className="code-block-lang">{language || 'text'}</span>
        <button type="button" className="copy-btn" onClick={copy}>
          {copied ? 'Copied ✓' : 'Copy'}
        </button>
      </div>
      <Highlight theme={themes.github} code={code} language={safeLanguage}>
        {({ className, style, tokens, getLineProps, getTokenProps }) => (
          <pre className={`code-block-pre ${className}`} style={{ ...style, backgroundColor: undefined }}>
            <code>
              {tokens.map((line, i) => (
                <div key={i} {...getLineProps({ line })}>
                  {line.map((token, j) => (
                    <span key={j} {...getTokenProps({ token })} />
                  ))}
                </div>
              ))}
            </code>
          </pre>
        )}
      </Highlight>
    </div>
  )
}
