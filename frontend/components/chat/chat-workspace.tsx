"use client"

import { useCallback, useState } from "react"
import { History, Orbit, Plus, Trash2, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ChatPanel } from "@/components/chat/chat-panel"
import { deriveTitle, messageText, type Conversation } from "@/components/chat/types"

function newConversation(): Conversation {
  return {
    id: crypto.randomUUID(),
    title: "Nueva conversacion",
    messages: [],
    createdAt: Date.now(),
  }
}

export function ChatWorkspace() {
  const [conversations, setConversations] = useState<Conversation[]>(() => [newConversation()])
  const [activeId, setActiveId] = useState(() => conversations[0].id)
  const [historyOpen, setHistoryOpen] = useState(false)

  const active = conversations.find((c) => c.id === activeId) ?? conversations[0]

  const handleMessagesChange = useCallback(
    (id: string, messages: Conversation["messages"]) => {
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== id) return c
          const title = deriveTitle(messages) ?? "Nueva conversacion"
          return { ...c, messages, title }
        }),
      )
    },
    [],
  )

  function startNew() {
    const conv = newConversation()
    setConversations((prev) => [conv, ...prev])
    setActiveId(conv.id)
    setHistoryOpen(false)
  }

  function select(id: string) {
    setActiveId(id)
    setHistoryOpen(false)
  }

  function remove(id: string) {
    setConversations((prev) => {
      const next = prev.filter((c) => c.id !== id)
      if (next.length === 0) {
        const conv = newConversation()
        setActiveId(conv.id)
        return [conv]
      }
      if (id === activeId) setActiveId(next[0].id)
      return next
    })
  }

  return (
    <div className="flex h-dvh">
      {/* History sidebar */}
      <HistoryList
        className="hidden w-72 shrink-0 md:flex"
        conversations={conversations}
        activeId={activeId}
        onNew={startNew}
        onSelect={select}
        onDelete={remove}
      />

      {/* Mobile history overlay */}
      {historyOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button
            aria-label="Cerrar historial"
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setHistoryOpen(false)}
          />
          <HistoryList
            className="absolute inset-y-0 left-0 flex w-72 max-w-[85%] shadow-2xl"
            conversations={conversations}
            activeId={activeId}
            onNew={startNew}
            onSelect={select}
            onDelete={remove}
            onClose={() => setHistoryOpen(false)}
          />
        </div>
      )}

      {/* Chat column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center gap-3 border-b border-border/60 bg-background/40 px-4 backdrop-blur-sm">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setHistoryOpen(true)}
            aria-label="Abrir historial"
          >
            <History className="size-5" />
          </Button>
          <div className="min-w-0">
            <h2 className="truncate font-display text-sm font-semibold">{active.title}</h2>
            <p className="text-[11px] text-muted-foreground">Especialista en exoplanetas anomalos</p>
          </div>
          <span className="ml-auto flex items-center gap-1.5 rounded-full bg-data/10 px-2.5 py-1 text-[11px] font-medium text-data ring-1 ring-data/20">
            <span className="size-1.5 animate-pulse rounded-full bg-data" />
            gemini-3.6-flash
          </span>
        </header>

        <div className="min-h-0 flex-1">
          <ChatPanel key={active.id} conversation={active} onMessagesChange={handleMessagesChange} />
        </div>
      </div>
    </div>
  )
}

function HistoryList({
  conversations,
  activeId,
  onNew,
  onSelect,
  onDelete,
  onClose,
  className,
}: {
  conversations: Conversation[]
  activeId: string
  onNew: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
  onClose?: () => void
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex-col border-r border-border/60 bg-sidebar/60 backdrop-blur-xl",
        className,
      )}
    >
      <div className="flex items-center gap-2 px-4 pb-3 pt-4">
        <h1 className="flex items-center gap-2 font-display text-sm font-semibold tracking-wide">
          <History className="size-4 text-primary" />
          Historial
        </h1>
        {onClose && (
          <Button variant="ghost" size="icon-sm" className="ml-auto" onClick={onClose} aria-label="Cerrar">
            <X className="size-4" />
          </Button>
        )}
      </div>

      <div className="px-3">
        <Button onClick={onNew} className="w-full justify-start gap-2" size="lg">
          <Plus className="size-4" />
          Nueva conversacion
        </Button>
      </div>

      <nav className="scroll-slim mt-3 flex-1 space-y-1 overflow-y-auto px-2 pb-4">
        {conversations.map((c) => {
          const last = c.messages.length ? messageText(c.messages[c.messages.length - 1]) : "Sin mensajes todavia"
          const active = c.id === activeId
          return (
            <div
              key={c.id}
              className={cn(
                "group relative flex cursor-pointer flex-col gap-0.5 rounded-lg px-3 py-2.5 transition-colors",
                active ? "bg-primary/12 ring-1 ring-primary/25" : "hover:bg-accent",
              )}
              onClick={() => onSelect(c.id)}
            >
              <div className="flex items-center gap-2">
                <Orbit className={cn("size-3.5 shrink-0", active ? "text-primary" : "text-muted-foreground")} />
                <span
                  className={cn(
                    "truncate text-sm font-medium",
                    active ? "text-foreground" : "text-foreground/80",
                  )}
                >
                  {c.title}
                </span>
              </div>
              <span className="truncate pl-[22px] text-xs text-muted-foreground">{last}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete(c.id)
                }}
                aria-label="Eliminar conversacion"
                className="absolute right-2 top-2 rounded-md p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/15 hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100"
              >
                <Trash2 className="size-3.5" />
              </button>
            </div>
          )
        })}
      </nav>
    </div>
  )
}
