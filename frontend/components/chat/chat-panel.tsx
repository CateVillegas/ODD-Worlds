"use client"

import { useEffect, useRef, useState } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import { ArrowUp, Orbit, RefreshCw, Sparkles, Square, TriangleAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { MessageContent } from "@/components/chat/message-content"
import { messageText, type Conversation } from "@/components/chat/types"

const suggestions = [
  "Que exoplanetas estan en la zona habitable?",
  "Compara TRAPPIST-1 e con la Tierra",
  "Como funciona el metodo de transito?",
  "Buscame los mundos mas raros",
]

export function ChatPanel({
  conversation,
  onMessagesChange,
}: {
  conversation: Conversation
  onMessagesChange: (id: string, messages: Conversation["messages"]) => void
}) {
  const { messages, sendMessage, status, stop, error, regenerate } = useChat({
    id: conversation.id,
    messages: conversation.messages,
    transport: new DefaultChatTransport({ api: "/api/chat" }),
  })
  const [input, setInput] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)
  const busy = status === "submitted" || status === "streaming"

  // Sync messages back up to the workspace so history + titles stay current.
  useEffect(() => {
    onMessagesChange(conversation.id, messages)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages])

  // Auto-scroll to the newest content.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, status])

  function submit(text: string) {
    const value = text.trim()
    if (!value || busy) return
    sendMessage({ text: value })
    setInput("")
  }

  const empty = messages.length === 0

  return (
    <div className="flex h-full flex-col">
      <div ref={scrollRef} className="scroll-slim flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
          {empty ? (
            <div className="flex flex-col items-center gap-6 py-10 text-center sm:py-16">
              <span className="flex size-16 items-center justify-center rounded-2xl bg-primary/15 ring-1 ring-primary/30">
                <Orbit className="size-8 text-primary" />
              </span>
              <div className="space-y-2">
                <h1 className="text-balance font-display text-2xl font-semibold sm:text-3xl">
                  Habla con <span className="text-primary text-glow">Odd Worlds</span>
                </h1>
                <p className="mx-auto max-w-md text-pretty text-sm leading-relaxed text-muted-foreground">
                  Tu especialista en exoplanetas anomalos. Pregunta sobre mundos confirmados del
                  archivo de la NASA: composicion, descubrimiento, habitabilidad y mas.
                </p>
              </div>
              <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => submit(s)}
                    className="group flex items-center gap-2.5 rounded-xl border border-border/70 bg-card/60 px-3.5 py-3 text-left text-sm text-foreground/85 backdrop-blur-sm transition-colors hover:border-primary/40 hover:bg-card"
                  >
                    <Sparkles className="size-4 shrink-0 text-primary/80" />
                    <span className="text-pretty">{s}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((m) => {
                const text = messageText(m)
                if (m.role === "user") {
                  return (
                    <div key={m.id} className="flex justify-end">
                      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground">
                        {text}
                      </div>
                    </div>
                  )
                }
                return (
                  <div key={m.id} className="flex gap-3">
                    <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/15 ring-1 ring-primary/25">
                      <Orbit className="size-4 text-primary" />
                    </span>
                    <div className="min-w-0 flex-1 pt-0.5">
                      {text ? (
                        <MessageContent text={text} />
                      ) : (
                        <ThinkingDots />
                      )}
                    </div>
                  </div>
                )
              })}
              {status === "submitted" && (
                <div className="flex gap-3">
                  <span className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/15 ring-1 ring-primary/25">
                    <Orbit className="size-4 animate-pulse text-primary" />
                  </span>
                  <div className="pt-2">
                    <ThinkingDots />
                  </div>
                </div>
              )}
              {status === "error" && (
                <div className="flex items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3">
                  <TriangleAlert className="mt-0.5 size-4 shrink-0 text-destructive" />
                  <div className="flex-1 text-sm text-foreground/90">
                    <p className="font-medium">No pude contactar al modelo.</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {error?.message || "Ocurrio un error de conexion con el agente."}
                    </p>
                  </div>
                  <Button size="sm" variant="secondary" onClick={() => regenerate()}>
                    <RefreshCw className="size-3.5" />
                    Reintentar
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-border/60 bg-background/40 px-4 py-3 backdrop-blur-sm sm:px-6">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            submit(input)
          }}
          className="mx-auto flex w-full max-w-3xl items-end gap-2 rounded-2xl border border-border/70 bg-card/70 p-2 pl-4 backdrop-blur-sm focus-within:border-primary/50"
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing &&
                e.keyCode !== 229
              ) {
                e.preventDefault()
                submit(input)
              }
            }}
            rows={1}
            placeholder="Pregunta sobre cualquier exoplaneta..."
            className="scroll-slim max-h-40 min-h-[24px] flex-1 resize-none bg-transparent py-1.5 text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground"
          />
          {busy ? (
            <Button type="button" size="icon-lg" variant="secondary" onClick={() => stop()} aria-label="Detener">
              <Square className="size-4 fill-current" />
            </Button>
          ) : (
            <Button type="submit" size="icon-lg" disabled={!input.trim()} aria-label="Enviar">
              <ArrowUp className="size-4" />
            </Button>
          )}
        </form>
        <p className="mx-auto mt-2 max-w-3xl text-center text-[11px] text-muted-foreground">
          Odd Worlds puede cometer errores. Los datos provienen del NASA Exoplanet Archive.
        </p>
      </div>
    </div>
  )
}

function ThinkingDots() {
  return (
    <div className="flex items-center gap-1" aria-label="Odd Worlds esta pensando">
      {[0, 150, 300].map((d) => (
        <span
          key={d}
          className="size-1.5 animate-bounce rounded-full bg-primary/70"
          style={{ animationDelay: `${d}ms` }}
        />
      ))}
    </div>
  )
}
