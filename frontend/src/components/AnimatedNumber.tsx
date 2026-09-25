import { useEffect, useState } from 'react'
import { useMotionValue, useTransform, animate, motion } from 'motion/react'

export function AnimatedNumber({ value }: { value: number }) {
  const mv = useMotionValue(value)
  const text = useTransform(mv, (v) =>
    `¥ ${v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
  )
  const [node, setNode] = useState<HTMLElement | null>(null)
  useEffect(() => {
    if (node) animate(mv, value, { duration: 0.9, ease: 'easeOut' })
  }, [value, node, mv])
  return <motion.span ref={setNode as any}>{text}</motion.span>
}
