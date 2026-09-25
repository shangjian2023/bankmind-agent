import { Alert, Input, Modal, Typography } from 'antd'
import { SafetyCertificateOutlined } from '@ant-design/icons'
import { useState } from 'react'

interface Props {
  open: boolean
  hint: string | null
  busy: boolean
  onVerify: (code: string) => void
  onCancel: () => void
}

export function MfaModal({ open, hint, busy, onVerify, onCancel }: Props) {
  const [code, setCode] = useState('')
  return (
    <Modal
      open={open}
      title={
        <span>
          <SafetyCertificateOutlined style={{ color: '#f5a623', marginRight: 8 }} />
          红色操作 · 短信验证码（模拟）
        </span>
      }
      onCancel={onCancel}
      footer={null}
      centered
      destroyOnHidden
    >
      <Alert
        type="warning"
        showIcon
        message="该操作风险等级为红色，须通过多因子验证"
        description="模拟银行已向您预留手机号发送 6 位验证码（演示环境直接回显）。"
        style={{ marginBottom: 16 }}
      />
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
        <Input.OTP
          length={6}
          autoFocus
          size="large"
          disabled={busy}
          value={code}
          onChange={(v: string) => {
            setCode(v)
            if (v.length === 6) onVerify(v)
          }}
        />
      </div>
      {hint && (
        <Typography.Paragraph type="secondary" style={{ textAlign: 'center' }}>
          {hint}
        </Typography.Paragraph>
      )}
    </Modal>
  )
}
