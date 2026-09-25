import { Badge, Drawer, Empty, Spin, Tag, Timeline, Typography } from 'antd'
import type { AuditLog } from '../types'

const LEVEL_COLOR: Record<string, string> = { green: 'green', yellow: 'gold', red: 'red' }

export function AuditDrawer({ open, onClose, logs, loading }: { open: boolean; onClose: () => void; logs: AuditLog[]; loading: boolean }) {
  return (
    <Drawer title="操作审计日志（实时）" placement="right" width={460} open={open} onClose={onClose} className="glass-strong">
      {loading && !logs.length ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin />
        </div>
      ) : !logs.length ? (
        <Empty description="暂无审计记录" />
      ) : (
        <Timeline
          items={logs.map((l) => ({
            key: l.id,
            color: ['tool_error', 'preflight_reject', 'circuit_block'].includes(l.stage)
              ? 'red'
              : l.stage === 'guard'
                ? 'orange'
                : 'green',
            children: (
              <div>
                <Typography.Text strong>
                  {l.stage.startsWith('tool:') ? `工具调用 ${l.stage.slice(5)}` : l.stage}
                </Typography.Text>
                {l.level && <Tag color={LEVEL_COLOR[l.level]} style={{ marginLeft: 6 }}>{l.level}</Tag>}
                {l.intent && <Tag style={{ marginLeft: 2 }}>{l.intent}</Tag>}
                <div>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {l.ts} · trace {l.trace_id}
                  </Typography.Text>
                </div>
              </div>
            ),
          }))}
        />
      )}
      <div style={{ marginTop: 12 }}>
        <Badge status="processing" text={`共 ${logs.length} 条 · trace_id 全链路贯穿`} />
      </div>
    </Drawer>
  )
}
