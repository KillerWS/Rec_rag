import React from 'react'
import { Popover } from 'antd'

interface PopularityExplainerProps {
  scope: 'area' | 'city'
  areaName?: string
  sampleSize?: number
  confidence?: 'Low' | 'Medium' | 'High'
  areaPopularity?: number | null
  cityPopularityAvg?: number | null
  indexValue?: number | null
}

const Badge: React.FC<{ text: string; color: string }> = ({ text, color }) => (
  <span
    style={{
      display: 'inline-block',
      padding: '2px 6px',
      borderRadius: 6,
      fontSize: 11,
      fontWeight: 600,
      color: color,
      background: `${color}18`,
      border: `1px solid ${color}44`,
    }}
  >
    {text}
  </span>
)

const PopularityExplainer: React.FC<PopularityExplainerProps> = ({
  scope,
  areaName,
  sampleSize,
  confidence,
  areaPopularity,
  cityPopularityAvg,
  indexValue,
}) => {
  const content = (
    <div style={{ maxWidth: 340 }}>
      <div style={{ fontWeight: 700, marginBottom: 6 }}>Popularity · How it works</div>
      <div style={{ marginBottom: 8, fontSize: 12 }}>
        <div>
          <strong style={{ color: '#0ea5e9' }}>Purpose:</strong>
          <span style={{ color: '#374151' }}> Gauge whether this area is <span style={{ color: '#16a34a', fontWeight: 600 }}>more popular</span> than city baseline. Helps assess demand and reputation.</span>
        </div>
      </div>
      <div style={{ marginBottom: 8, fontSize: 12 }}>
        <div style={{ fontWeight: 600 }}>Index definition</div>
        <div>
          Popularity Index = <em>area popularity_score</em> / <em>city average popularity_score</em> × 100
        </div>
      </div>
      <div style={{ marginBottom: 8, fontSize: 12 }}>
        <div style={{ fontWeight: 600 }}>What contributes</div>
        <ul style={{ paddingLeft: 18, margin: 0 }}>
          <li><span style={{ color: '#f59e0b', fontWeight: 600 }}>Review activity</span> (share of listings with reviews)</li>
          <li><span style={{ color: '#8b5cf6', fontWeight: 600 }}>Median review count</span> (robust to outliers)</li>
        </ul>
      </div>
      <div style={{ marginBottom: 8, fontSize: 12, color: '#374151' }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          {scope === 'area' && areaName && <Badge text={areaName} color="#2563eb" />}
          {typeof sampleSize === 'number' && <Badge text={`n = ${sampleSize}`} color="#6b7280" />}
          {confidence && <Badge text={`${confidence} confidence`} color={confidence === 'High' ? '#16a34a' : confidence === 'Medium' ? '#f59e0b' : '#ef4444'} />}
        </div>
        <div style={{ marginTop: 6 }}>
          Area: <strong>{areaPopularity != null ? `${areaPopularity}%` : '—'}</strong>
          , City: <strong>{cityPopularityAvg != null ? `${cityPopularityAvg}%` : '—'}</strong>
          , Index: <strong>{indexValue != null ? `${indexValue}` : '—'}</strong>
        </div>
      </div>
      <div style={{ fontSize: 11, color: '#6b7280' }}>
        Note: If some stats are missing, data is not available or sample is small.
      </div>
    </div>
  )

  return (
    <Popover content={content} trigger={["hover", "click"]} overlayStyle={{ maxWidth: 360, zIndex: 20000 }}>
      <span
        role="img"
        aria-label="explain popularity"
        title="Explain popularity"
        style={{ cursor: 'pointer', marginLeft: 6, fontSize: 14 }}
      >
        ℹ️
      </span>
    </Popover>
  )
}

export default PopularityExplainer 