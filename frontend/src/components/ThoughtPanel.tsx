import {
  AimOutlined,
  ApartmentOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  InboxOutlined,
  KeyOutlined,
  LockOutlined,
  QuestionCircleOutlined,
  SafetyCertificateOutlined,
  SafetyOutlined,
  StopOutlined,
  ToolOutlined,
} from '@ant-design/icons'
import { ThoughtChain } from '@ant-design/x'
import type { ThoughtChainItemType } from '@ant-design/x/es/thought-chain/interface'
import { Tag } from 'antd'
import type { AuditLog } from '../types'

const ICONS: Record<string, React.ReactNode> = {
  receive: <InboxOutlined />,
  guard: <SafetyOutlined />,
  intent: <AimOutlined />,
  slots: <EditOutlined />,
  plan: <ApartmentOutlined />,
  permission: <LockOutlined />,
  confirm_request: <QuestionCircleOutlined />,
  confirm_approved: <CheckCircleOutlined />,
  confirm_declined: <CloseCircleOutlined />,
  mfa_issue: <SafetyCertificateOutlined />,
  mfa_verify: <KeyOutlined />,
  done: <CheckCircleOutlined />,
  tool_error: <CloseCircleOutlined />,
  preflight_reject: <CloseCircleOutlined />,
  circuit_block: <StopOutlined />,
  abort: <StopOutlined />,
  human_takeover: <QuestionCircleOutlined />,
}

const TITLES: Record<string, string> = {
  receive: '接收消息',
  guard: '注入检测',
  intent: '意图识别',
  slots: '槽位填充',
  plan: 'DAG 规划',
  permission: '权限判定',
  confirm_request: '请求用户确认',
  confirm_approved: '用户已确认',
  confirm_declined: '用户已拒绝',
  mfa_issue: '下发 MFA 挑战',
  mfa_verify: 'MFA 校验',
  done: '执行完成',
  tool_error: '工具执行失败',
  preflight_reject: '前置校验拒绝',
  circuit_block: '熔断拦截',
  abort: '用户中断',
  human_takeover: '人工接管',
}

function briefDetail(log: AuditLog): string | undefined {
  if (!log.detail) return undefined
  try {
    const d = JSON.parse(log.detail)
    if (log.stage === 'intent') return `${d.intent ?? '?'}（置信度 ${d.confidence ?? '-'}）`
    if (log.stage === 'slots') {
      const keys = Object.keys(d)
      return keys.length ? keys.join(' · ') : '（无槽位）'
    }
    if (log.stage === 'plan') return `${(d.nodes ?? []).join(' → ')}`
    if (log.stage === 'permission') return `${d.reason ?? ''}`
    if (log.stage === 'guard') return d.verdict === 'rejected' ? `拒绝：${d.reason}` : '通过'
    if (log.stage.startsWith('tool:')) {
      const out = d.output ?? d.error ?? {}
      return Object.keys(out).slice(0, 6).join(' · ') || '（执行成功）'
    }
    if (log.stage === 'receive') return `「${String(d.message ?? '').slice(0, 24)}」`
    return undefined
  } catch {
    return undefined
  }
}

export function toThoughtItems(logs: AuditLog[]): ThoughtChainItemType[] {
  return [...logs]
    .reverse()
    .filter((l) => TITLES[l.stage] || l.stage.startsWith('tool:'))
    .map((l) => {
      const isTool = l.stage.startsWith('tool:')
      const desc = briefDetail(l)
      const errorStages = ['tool_error', 'preflight_reject', 'circuit_block']
      return {
        key: String(l.id),
        icon: isTool ? <ToolOutlined /> : ICONS[l.stage],
        title: isTool ? `工具调用：${l.stage.slice(5)}` : TITLES[l.stage] ?? l.stage,
        description: desc,
        status: errorStages.includes(l.stage) || (l.stage === 'mfa_verify' && l.detail?.includes('"fail"'))
          ? ('error' as const)
          : ('success' as const),
        footer: l.level ? <Tag color={l.level === 'green' ? 'success' : l.level === 'red' ? 'error' : 'warning'}>{l.level}</Tag> : undefined,
      }
    })
}

export function ThoughtPanel({ logs }: { logs: AuditLog[] }) {
  if (!logs.length) return <div style={{ padding: 24, color: '#888' }}>发送一条消息后，这里将展示 Agent 的完整决策链路。</div>
  return (
    <div style={{ padding: '12px 16px' }}>
      <ThoughtChain items={toThoughtItems(logs)} />
    </div>
  )
}
