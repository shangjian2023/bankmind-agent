import { Space, Button, Typography } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'

export function ConfirmCard({ onDecision, busy }: { onDecision: (approve: boolean) => void; busy: boolean }) {
  return (
    <Space style={{ marginTop: 8 }} size={8}>
      <Button type="primary" danger={false} icon={<CheckOutlined />} loading={busy} onClick={() => onDecision(true)}>
        确认执行
      </Button>
      <Button icon={<CloseOutlined />} disabled={busy} onClick={() => onDecision(false)}>
        取消
      </Button>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        黄色操作需明确确认
      </Typography.Text>
    </Space>
  )
}
