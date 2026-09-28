export interface ChatRequest {
  user_id: string
  message: string
}

export interface ChatResponse {
  status: 'ok' | 'need_confirm' | 'need_mfa' | 'need_slots' | 'rejected' | 'locked'
  reply: string
  trace_id: string | null
  action_id: string | null
  data: Record<string, any>
  mfa_hint: string | null
}

export interface AuditLog {
  id: number
  trace_id: string
  user_id: string
  stage: string
  intent: string | null
  level: string | null
  detail: string | null
  ts: string
}

export interface ChatMessage {
  key: string
  role: 'user' | 'bot'
  text: string
  status?: ChatResponse['status']
  actionId?: string | null
  mfaHint?: string | null
  intent?: string
  billData?: any
  traceId?: string | null
  settled?: boolean
}
