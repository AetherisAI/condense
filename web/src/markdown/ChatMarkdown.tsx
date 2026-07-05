import { type ReactNode, isValidElement } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CodeBlock from './CodeBlock'
import MermaidBlock from './MermaidBlock'

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

const components: Components = {
  pre: PreBlock,
  // Table rows/cells render as usual (GFM); only the `<table>` itself gets its own horizontal
  // scroll box, so a wide table scrolls within itself and never the whole chat column.
  table: ({ children }) => (
    <div className="md-table-wrap">
      <table>{children}</table>
    </div>
  ),
}

/** The chat answer body's markdown renderer (D47): GFM tables/lists/bold/links as before, plus
 * real fenced code blocks (syntax-highlighted, own scroll box, copy button) and lazy Mermaid
 * diagrams. No raw-HTML passthrough — `rehype-raw` is deliberately never added, so any HTML the
 * model emits renders as inert escaped text, never live markup. */
export default function ChatMarkdown({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {text}
    </ReactMarkdown>
  )
}
