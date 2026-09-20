import { Fragment, type ReactNode } from "react"

// Lightweight inline formatter: **bold** and `code`.
function renderInline(text: string): ReactNode[] {
  const nodes: ReactNode[] = []
  const regex = /(\*\*[^*]+\*\*|`[^`]+`)/g
  let last = 0
  let match: RegExpExecArray | null
  let key = 0
  while ((match = regex.exec(text)) !== null) {
    if (match.index > last) nodes.push(<Fragment key={key++}>{text.slice(last, match.index)}</Fragment>)
    const token = match[0]
    if (token.startsWith("**")) {
      nodes.push(
        <strong key={key++} className="font-semibold text-foreground">
          {token.slice(2, -2)}
        </strong>,
      )
    } else {
      nodes.push(
        <code
          key={key++}
          className="rounded bg-background/70 px-1 py-0.5 font-display text-[0.85em] text-data"
        >
          {token.slice(1, -1)}
        </code>,
      )
    }
    last = match.index + token.length
  }
  if (last < text.length) nodes.push(<Fragment key={key++}>{text.slice(last)}</Fragment>)
  return nodes
}

// Group plain text into paragraphs and bullet / numbered lists.
export function MessageContent({ text }: { text: string }) {
  const lines = text.split("\n")
  const blocks: ReactNode[] = []
  let list: { ordered: boolean; items: string[] } | null = null
  let key = 0

  const flush = () => {
    if (!list) return
    const items = list.items
    blocks.push(
      list.ordered ? (
        <ol key={key++} className="ml-4 list-decimal space-y-1">
          {items.map((it, i) => (
            <li key={i}>{renderInline(it)}</li>
          ))}
        </ol>
      ) : (
        <ul key={key++} className="ml-1 space-y-1">
          {items.map((it, i) => (
            <li key={i} className="flex gap-2">
              <span className="mt-2 size-1 shrink-0 rounded-full bg-primary/70" />
              <span>{renderInline(it)}</span>
            </li>
          ))}
        </ul>
      ),
    )
    list = null
  }

  for (const raw of lines) {
    const line = raw.trimEnd()
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/)
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/)
    if (bullet) {
      if (list && list.ordered) flush()
      list = list ?? { ordered: false, items: [] }
      list.items.push(bullet[1])
    } else if (numbered) {
      if (list && !list.ordered) flush()
      list = list ?? { ordered: true, items: [] }
      list.items.push(numbered[1])
    } else if (line.trim() === "") {
      flush()
    } else {
      flush()
      blocks.push(
        <p key={key++} className="leading-relaxed">
          {renderInline(line)}
        </p>,
      )
    }
  }
  flush()

  return <div className="space-y-2.5 text-sm text-foreground/90">{blocks}</div>
}
