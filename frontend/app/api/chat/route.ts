import { type NextRequest, NextResponse } from 'next/server'

export const maxDuration = 30

export async function POST(req: NextRequest) {
  const { messages } = await req.json()
  const last = messages[messages.length - 1]
  const question = typeof last === 'string' ? last : last?.content ?? last?.text ?? ''

  const backendUrl = process.env.BACKEND_URL ?? 'http://127.0.0.1:8000'

  const res = await fetch(`${backendUrl}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })

  if (!res.ok) {
    return NextResponse.json(
      { error: 'Error conectando con el agente' },
      { status: 502 },
    )
  }

  const data = await res.json()
  return NextResponse.json(data)
}
