import { useEffect, useId, useRef, useState } from 'react'
import CodeBlock from './CodeBlock'

type RenderState =
  | { status: 'loading' }
  | { status: 'done'; svg: string }
  | { status: 'error' }

/**
 * A ```mermaid fence (D47). `mermaid` is never in the main bundle — it's pulled in via a
 * `import('mermaid')` the FIRST time a mermaid block is actually encountered, so chat threads
 * with no diagrams never pay for it. Renders the diagram's own SVG (light theme, matching the
 * app's light-only design); on a parse error, falls back to the raw fence as a normal
 * (unhighlighted) code block rather than showing a broken diagram or throwing.
 */
export default function MermaidBlock({ code }: { code: string }) {
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const [state, setState] = useState<RenderState>({ status: 'loading' })
  const generation = useRef(0)

  useEffect(() => {
    const myGeneration = ++generation.current
    let cancelled = false
    setState({ status: 'loading' })

    import('mermaid')
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'strict' })
        const { svg } = await mermaid.render(`mermaid-${id}-${myGeneration}`, code)
        if (cancelled || generation.current !== myGeneration) return
        setState({ status: 'done', svg })
      })
      .catch(() => {
        if (cancelled || generation.current !== myGeneration) return
        setState({ status: 'error' })
      })

    return () => {
      cancelled = true
    }
  }, [code, id])

  if (state.status === 'error') {
    return <CodeBlock language="mermaid" code={code} />
  }

  if (state.status === 'loading') {
    return <div className="mermaid-block mermaid-loading">Rendering diagram…</div>
  }

  return (
    <div className="mermaid-block" dangerouslySetInnerHTML={{ __html: state.svg }} />
  )
}
