import { type ReactNode, isValidElement, memo, useMemo, useRef } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { PluggableList } from 'unified'
import CodeBlock from './CodeBlock'
import MermaidBlock from './MermaidBlock'
import { CITATION_HREF_PREFIX, remarkCitations, parseCitationGroup, type CitationEntry } from '../citations'

/** Recursively flattens a markdown AST's rendered children back to plain text — used to pull
 * the raw code string out of the `<code>` element react-markdown hands `pre` (its `children`
 * prop is itself already-rendered React nodes, not the source string). */
function textOf(node: ReactNode): string {
  if (node == null || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textOf).join('')
  if (isValidElement<{ children?: ReactNode }>(node)) return textOf(node.props.children)
  return ''
}

/** `pre`'s single child is always the fenced/indented code's own `<code className="language-x">`
 * element — inline code (`` `x` ``) is never wrapped in a `<pre>` by the markdown spec, so
 * overriding `pre` alone cleanly separates "this is a code block" from "this is inline code"
 * with no fragile inline-vs-block heuristic. */
function PreBlock({ children }: { children?: ReactNode }) {
  const codeChild = Array.isArray(children) ? children[0] : children
  const codeClassName =
    isValidElement<{ className?: string }>(codeChild) && typeof codeChild.props.className === 'string'
      ? codeChild.props.className
      : ''
  const match = /language-(\w+)/.exec(codeClassName)
  const language = match ? match[1] : 'text'
  const code = textOf(children).replace(/\n$/, '')

  if (language === 'mermaid') return <MermaidBlock code={code} />
  return <CodeBlock language={language} code={code} />
}

const staticComponents: Components = {
  pre: PreBlock,
  // Table rows/cells render as usual (GFM); only the `<table>` itself gets its own horizontal
  // scroll box, so a wide table scrolls within itself and never the whole chat column.
  table: ({ children }) => (
    <div className="md-table-wrap">
      <table>{children}</table>
    </div>
  ),
}

type ChatMarkdownProps = {
  text: string
  // Inline citations (front-end task: clickable citations + deep links) — the `remarkCitations`
  // plugin (`citations.ts`) rewrites every "(filename.ext, p.N)" run into a `#cite-<n>` link node
  // as part of the markdown parse itself; the `a` override below turns that link into a
  // `.citation-link` when `resolveCitation` finds a matching source card, or into a visibly
  // "unverified" span when it doesn't (a citation with no matching card must never render as a
  // dead link — transparency: the LLM wrote it, retrieval did not back it). Both callbacks are
  // OPTIONAL (a caller that never wires cards gets plain text for every citation, never a broken
  // button) and MUST stay referentially stable (`useCallback` at the call site) across a turn's
  // own re-renders — see the `memo` note below: an unstable prop here would defeat the whole
  // point of memoizing every prior turn's markdown parse on every streamed token of the live one.
  resolveCitation?: (entries: CitationEntry[]) => number | null
  onCitationClick?: (index: number) => void
}

/** The chat answer body's markdown renderer (D47): GFM tables/lists/bold/links as before, plus
 * real fenced code blocks (syntax-highlighted, own scroll box, copy button), lazy Mermaid
 * diagrams, and clickable inline citations. No raw-HTML passthrough — `rehype-raw` is
 * deliberately never added, so any HTML the model emits renders as inert escaped text, never live
 * markup (the citation link is built as a real mdast `link` node by the `remarkCitations` plugin
 * in `citations.ts`, never from a markdown-string rewrite or `dangerouslySetInnerHTML`, so this
 * guarantee is untouched).
 *
 * Wrapped in `React.memo`: react-markdown re-parses its whole input on every render, and the
 * chat thread re-renders on every streamed token, so an un-memoized instance would re-parse the
 * markdown of *every* prior turn once per token (O(turns × tokens)). The default shallow prop
 * compare lets an unchanged turn skip the re-parse — only the actively streaming turn (whose
 * `text` grows) or one whose citation callbacks just changed identity re-renders. */
function ChatMarkdown({ text, resolveCitation, onCitationClick }: ChatMarkdownProps) {
  // Populated synchronously by `remarkCitations` (`citations.ts`) during THIS render's parse pass
  // — index `n` -> the raw matched citation text (e.g. `"(report.pdf, p.3)"`) for every `#cite-n`
  // link node the plugin just produced. A plain ref, not state: writing it is a pure side effect
  // of react-markdown's own (fully synchronous, see `citations.ts`'s module comment) parse call a
  // few lines below, and it only ever needs to be read later in that exact same synchronous call
  // stack (by the `a` override, as react-markdown turns the freshly-built tree into elements) —
  // never across renders, so there's no staleness to worry about.
  const citationsRef = useRef<string[]>([])
  const remarkPlugins = useMemo<PluggableList>(
    () => [remarkGfm, [remarkCitations, (list: string[]) => (citationsRef.current = list)]],
    [],
  )
  const components = useMemo<Components>(
    () => ({
      ...staticComponents,
      a: ({ href, title, children }) => {
        if (typeof href === 'string' && href.startsWith(CITATION_HREF_PREFIX)) {
          // A caller that never wired citations up (`resolveCitation` omitted) gets plain text
          // for every citation, never a broken button.
          if (!resolveCitation) return <>{children}</>
          const raw = citationsRef.current[Number(href.slice(CITATION_HREF_PREFIX.length))]
          const entries = raw ? parseCitationGroup(raw) : []
          const target = entries.length > 0 ? resolveCitation(entries) : null
          // No matching source card — a visibly "unverified" span, not a dead link/button: the
          // LLM wrote this citation but retrieval didn't back it, and that should stay visible
          // rather than silently reading as plain prose.
          if (target == null) {
            return (
              <span className="citation-unverified" title="No retrieved source matches this citation">
                {children}
              </span>
            )
          }
          return (
            <a
              href={href}
              className="citation-link"
              onClick={(event) => {
                event.preventDefault()
                onCitationClick?.(target)
              }}
            >
              {children}
            </a>
          )
        }
        return (
          <a href={href} title={title}>
            {children}
          </a>
        )
      },
    }),
    [resolveCitation, onCitationClick],
  )
  return (
    <ReactMarkdown remarkPlugins={remarkPlugins} components={components}>
      {text}
    </ReactMarkdown>
  )
}

export default memo(ChatMarkdown)
