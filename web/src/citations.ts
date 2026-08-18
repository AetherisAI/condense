import type { Link, Parent, Root, Text } from 'mdast'

/**
 * Inline-citation parsing (front-end only) — detects the strict "(filename.ext, p.N)" shape the
 * answer pipeline instructs the model to use for every citation (the citation-format prompt
 * around `src/sift/pipelines/answer.py:221`), so `ChatMarkdown` can turn each occurrence into a
 * clickable element that jumps to its matching card in `SourcesPanel` (`Chat.tsx`).
 *
 * `remarkCitations` is a real remark/mdast plugin (F1 fix), not a pre-render markdown-string
 * rewrite: react-markdown v10 runs `defaultUrlTransform` on every link's `href` BEFORE
 * `ChatMarkdown`'s `a`-component override ever sees it, and that transform blanks any href whose
 * scheme isn't in a small allowlist (`https?|ircs?|mailto|xmpp`) — the previous approach's
 * made-up `citation:` scheme was silently reduced to `href=""` on every render, so every citation
 * rendered as a dead `<a href="">` (clicking it reloads the SPA). A bare `#fragment` URL has no
 * scheme at all, so `defaultUrlTransform` treats it as relative and passes it through untouched —
 * see its source (`node_modules/react-markdown/lib/index.js`): a `#` before the first `:` reads
 * as "not a protocol". `remarkCitations` walks the mdast tree with its own ~20-line visitor (no
 * runtime dependency: an earlier version imported `mdast-util-find-and-replace`, a phantom
 * transitive of remark-gfm that is not in package.json and, used without its `ignore` option,
 * produced a `link` nested inside a `link` for a citation written inside a markdown link label)
 * and rewrites each citation match into a `link` node with `url: "#cite-<n>"` and the ORIGINAL
 * matched text as its single `text` AST child. The visitor never descends into `link`,
 * `linkReference`, `code`, `inlineCode`, `html` or `definition` nodes, so a citation can never
 * end up nested in another anchor. Two consequences fall out of building real AST nodes instead
 * of a markdown string:
 *   - Fenced code blocks and inline code spans are structurally unreachable: their content lives
 *     in each `code`/`inlineCode` node's own `value` property, never as child `text` nodes, and
 *     `findAndReplace` only ever visits nodes of type `text` — no separate "skip code" logic
 *     needed (the old string-regex approach needed `CODE_SEGMENT_RE` for exactly this).
 *   - The matched text is never re-serialized through markdown syntax, so a filename containing
 *     `[`, `]`, `*`, or a backtick can't leak stray markdown-link syntax into the rendered label
 *     the way `[${match}](citation:...)`-style string interpolation could (F5) — it renders as
 *     inert text, escaped like any other AST text node.
 */

export type CitationEntry = { fileName: string; page: number }

/** The href prefix `remarkCitations` gives every citation link node — `ChatMarkdown`'s `a`
 * override recognizes this prefix and resolves `<n>` back to the raw matched citation text via
 * the per-render list `remarkCitations` reports through its `report` callback. Never a URL
 * anything should navigate to (the override always intercepts + `preventDefault`s it). */
export const CITATION_HREF_PREFIX = '#cite-'

/** Detection is deliberately TWO-STAGE so it runs in linear time (third-pass audit): the
 * one-regex version `\((entry)(;entry)*\)` backtracked catastrophically on an UNCLOSED
 * multi-entry group -- 24 entries without the closing paren cost 559 ms inside the real
 * component and grew ~4x per two entries -- and streaming produces exactly that shape on every
 * intermediate token of a long citation list, freezing the main thread. Stage 1 finds a
 * parenthesised group with no nested parens and a bounded length: `[^()\n]{1,400}` cannot
 * backtrack in more than one way, so an unclosed group is rejected in O(n). Stage 2 validates
 * the small captured group by splitting on `;` and checking each piece with an ANCHORED regex
 * (`^...$`), where the non-greedy filename cannot explode either because the input is at most
 * a few hundred characters and anchored on both ends. */
const GROUP_RE = /\(([^()\n]{1,400})\)/g
/** One entry: a filename with a 1-8 char extension, then `, p.N` (tolerating `p. N`). */
const ENTRY_RE = /^\s*[^,;()]+?\.[A-Za-z0-9]{1,8}\s*,\s*p\.\s*\d+\s*$/

/** True when the text INSIDE a paren group is one or more `;`-separated citation entries. */
function isCitationGroup(inner: string): boolean {
  const pieces = inner.split(';')
  return pieces.length > 0 && pieces.every((piece) => ENTRY_RE.test(piece))
}

/** Parses one already-matched citation group (e.g. `"(report.pdf, p.3; appendix.pdf, p.1)"`)
 * into its entries. Deliberately more lenient than `CITATION_RE` (just `text, p.N` per piece)
 * since the input has already passed the stricter detection regex — this only needs to split it
 * back apart, never re-validate it. */
export function parseCitationGroup(raw: string): CitationEntry[] {
  const inner = raw.trim().replace(/^\(/, '').replace(/\)$/, '')
  const entries: CitationEntry[] = []
  for (const piece of inner.split(';')) {
    const m = /^\s*(.+?)\s*,\s*p\.\s*(\d+)\s*$/.exec(piece)
    if (m) entries.push({ fileName: m[1], page: Number(m[2]) })
  }
  return entries
}

/** Just the file name — the same tiny helper every citation renderer in this app already
 * duplicates locally (`Chat.tsx`, `FindTurn.tsx`) rather than sharing, so a citation's
 * `fileName` can be compared against a source's full `path`. */
function fileName(path: string): string {
  const parts = path.split(/[/\\]/)
  return parts[parts.length - 1] || path
}

/** Called once per `remarkCitations` parse pass with the ordered list of raw matched citation
 * text — index `n` in the list is the same `n` embedded in that citation's `#cite-<n>` href. */
export type ReportCitations = (citations: string[]) => void

/** The remark plugin itself (see the module comment for the full design). `report` is invoked
 * synchronously, once, after the whole tree has been walked — react-markdown's default export
 * (`ChatMarkdown` uses it, not `MarkdownAsync`/`MarkdownHooks`) runs parse → remark plugins → hast
 * → component tree entirely within one synchronous call, so by the time any citation link node
 * reaches `ChatMarkdown`'s `a` override, `report` has already run. */
export function remarkCitations(report: ReportCitations) {
  return (tree: Root) => {
    const citations: string[] = []
    visitTextNodes(tree, (node, parent, index) => {
      const replacement = splitCitations(node.value, citations)
      if (replacement) parent.children.splice(index, 1, ...replacement)
      return replacement ? replacement.length : 1
    })
    report(citations)
  }
}

/** Node types whose subtrees must not be linkified: an anchor inside an anchor is invalid DOM
 * (React really builds it, and click behaviour is undefined), and code/html/definitions are
 * verbatim by contract. */
const SKIP_TYPES = new Set(['link', 'linkReference', 'code', 'inlineCode', 'html', 'definition'])

/** Depth-first walk over `text` nodes. The callback returns how many nodes now sit at `index`
 * (1 when untouched, more after a splice) so the walk continues AFTER the freshly inserted
 * nodes and never revisits a citation link's own text child. */
function visitTextNodes(
  root: Parent,
  visit: (node: Text, parent: Parent, index: number) => number,
): void {
  const stack: Parent[] = [root]
  while (stack.length) {
    const parent = stack.pop() as Parent
    let i = 0
    while (i < parent.children.length) {
      const child = parent.children[i]
      if (child.type === 'text') {
        i += visit(child as Text, parent, i)
        continue
      }
      if (!SKIP_TYPES.has(child.type) && 'children' in child) stack.push(child as Parent)
      i += 1
    }
  }
}

/** Splits one text value into `[text, link, text, link, ...]` mdast nodes, or returns null when
 * it holds no citation (so the caller leaves the node alone). */
function splitCitations(value: string, citations: string[]): Array<Text | Link> | null {
  GROUP_RE.lastIndex = 0
  const out: Array<Text | Link> = []
  let cursor = 0
  let match: RegExpExecArray | null
  while ((match = GROUP_RE.exec(value)) !== null) {
    if (!isCitationGroup(match[1])) continue
    if (match.index > cursor) out.push({ type: 'text', value: value.slice(cursor, match.index) })
    const n = citations.length
    citations.push(match[0])
    out.push({
      type: 'link',
      url: `${CITATION_HREF_PREFIX}${n}`,
      children: [{ type: 'text', value: match[0] }],
    })
    cursor = match.index + match[0].length
  }
  if (!out.length) return null
  if (cursor < value.length) out.push({ type: 'text', value: value.slice(cursor) })
  return out
}

/** Matches one citation entry to its `SourcesPanel` card index. Page 1 is the parser's current
 * everything-flattens-to-one-page placeholder (see `sourceSnippet.tsx`'s `showPageBadge`), not a
 * real citation to a specific page, so it — and a missing/zero page — fall back to matching on
 * filename alone. A real page number (> 1) tries an exact (filename, page) match first, then
 * still falls back to filename-only rather than rendering a dead link over a page mismatch.
 * Returns -1 when nothing matches at all. */
export function findMatchingSourceIndex(
  sources: readonly { path: string; page: number }[],
  entry: CitationEntry,
): number {
  const matchesName = (s: { path: string }) => fileName(s.path) === entry.fileName
  if (entry.page > 1) {
    const exact = sources.findIndex((s) => matchesName(s) && s.page === entry.page)
    if (exact !== -1) return exact
  }
  return sources.findIndex(matchesName)
}

/** Resolves a whole citation GROUP (one or more `;`-separated entries) to the first entry that
 * has a matching card — `null` when none of them do, the render-time signal `ChatMarkdown` uses
 * to fall back to the "unverified" style instead of a clickable element (transparency: the LLM
 * wrote this citation, retrieval did not back it). */
export function resolveCitationTarget(
  sources: readonly { path: string; page: number }[],
  entries: CitationEntry[],
): number | null {
  for (const entry of entries) {
    const index = findMatchingSourceIndex(sources, entry)
    if (index !== -1) return index
  }
  return null
}
