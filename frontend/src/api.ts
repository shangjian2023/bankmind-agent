import type { ChatRequest, ChatResponse, AuditLog } from './types'

async function post<T>(path: string, body: any): Promise<T> {
  const r = await fetch(`/api${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json()
}

export const api = {
  users: () => fetch('/api/users').then((r) => r.json()),
  chat: (req: ChatRequest) => post<ChatResponse>('/chat', req),
  confirm: (actionId: string, approve: boolean) => post<ChatResponse>('/confirm', { action_id: actionId, approve }),
  mfa: (actionId: string, code: string) => post<ChatResponse>('/mfa/verify', { action_id: actionId, code }),
  audit: (userId: string, limit = 60, traceId?: string) => {
    const q = new URLSearchParams({ user_id: userId, limit: String(limit) })
    if (traceId) q.set('trace_id', traceId)
    return fetch(`/api/audit?${q}`).then((r) => r.json()) as Promise<{ logs: AuditLog[] }>
  },
}
