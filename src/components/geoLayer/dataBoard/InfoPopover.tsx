import React from 'react'
import { Popover } from 'antd'

interface InfoPopoverProps {
  title: string
  lines: Array<React.ReactNode>
  iconTitle?: string
}

const InfoPopover: React.FC<InfoPopoverProps> = ({ title, lines, iconTitle }) => {
  const content = (
    <div style={{ maxWidth: 320 }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 12, color: '#374151' }}>
        {lines.map((ln, idx) => (
          <div key={idx} style={{ marginBottom: 6 }}>{ln}</div>
        ))}
      </div>
    </div>
  )

  return (
    <Popover content={content} trigger={["hover", "click"]} overlayStyle={{ maxWidth: 360, zIndex: 20000 }}>
      <span
        role="img"
        aria-label="info"
        title={iconTitle || 'More info'}
        style={{ cursor: 'pointer', marginLeft: 6, fontSize: 14 }}
      >
        ℹ️
      </span>
    </Popover>
  )
}

export default InfoPopover 