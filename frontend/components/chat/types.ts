import type { UIMessage } from "ai"

export type Conversation = {
  id: string
  title: string
  messages: UIMessage[]
  createdAt: number
}

export function messageText(m: UIMessage): string {
  return m.parts
    .filter((p): p is { type: "text"; text: string } => p.type === "text")
    .map((p) => p.text)
    .join(" ")
    .trim()
}

export function deriveTitle(messages: UIMessage[]): string | null {
  const firstUser = messages.find((m) => m.role === "user")
  if (!firstUser) return null
  const text = messageText(firstUser)
  if (!text) return null
  return text.length > 42 ? text.slice(0, 42).trimEnd() + "..." : text
}
