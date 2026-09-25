import { useState } from 'react'
import { Button, Card } from 'antd'
import { BarChartOutlined } from '@ant-design/icons'
import { AnimatePresence, motion } from 'motion/react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const COLORS = ['#2f7cf6', '#36b37e', '#f5a623', '#a855f7', '#ef4444', '#06b6d4', '#f472b6', '#84cc16']

export interface BillData {
  category_totals?: Record<string, number>
  monthly_series?: { month: string; amount: number }[]
  total_out?: number
  total_in?: number
}

export function BillCharts({ data }: { data: BillData }) {
  const categories = Object.entries(data.category_totals ?? {}).map(([name, value]) => ({ name, value }))
  const monthly = (data.monthly_series ?? []).slice(-12)
  const [open, setOpen] = useState(false)

  return (
    <div style={{ marginTop: 8 }}>
      <Button size="small" icon={<BarChartOutlined />} onClick={() => setOpen(!open)}>
        {open ? '收起可视化图表' : '查看可视化图表'}
      </Button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.35, ease: 'easeInOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
              <Card size="small" className="glass" style={{ flex: '1 1 300px' }} title="消费分类占比">
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart>
                    <Pie data={categories} dataKey="value" nameKey="name" innerRadius={50} outerRadius={85} paddingAngle={2} isAnimationActive>
                      {categories.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} stroke="none" />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: any) => `¥ ${Number(v).toFixed(2)}`} />
                  </PieChart>
                </ResponsiveContainer>
              </Card>
              <Card size="small" className="glass" style={{ flex: '1 1 300px' }} title="月度支出趋势">
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={monthly}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                    <XAxis dataKey="month" tick={{ fill: '#8b949e', fontSize: 11 }} />
                    <YAxis tick={{ fill: '#8b949e', fontSize: 11 }} />
                    <Tooltip formatter={(v: any) => `¥ ${Number(v).toFixed(2)}`} />
                    <Bar dataKey="amount" fill="#2f7cf6" radius={[4, 4, 0, 0]} isAnimationActive />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
