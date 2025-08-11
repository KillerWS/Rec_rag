// src/components/OverviewPanel.tsx
import React from 'react'
import { Button } from 'antd'

interface OverviewPanelProps {
  districtsData: Array<{
    listing_count: number
    avg_price: number
    total_reviews: number
  }>
  onDrillDown: (insightKey: string) => void
}

const MetricCard: React.FC<{
  title: string
  value: React.ReactNode
  description?: React.ReactNode
  onDrillDown: () => void
}> = ({ title, value, description, onDrillDown }) => (
  <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
    <div className="text-sm text-gray-500">{title}</div>
    <div className="mt-1 text-2xl font-bold text-gray-800">{value}</div>
    {description && <div className="text-xs text-gray-600 mt-1">{description}</div>}
    <Button 
      type="link" 
      size="small" 
      style={{ padding: 0, marginTop: 8 }} 
      onClick={onDrillDown}
    >
      Learn more →
    </Button>
  </div>
)

const OverviewPanel: React.FC<OverviewPanelProps> = ({ districtsData, onDrillDown }) => {
  if (!districtsData || districtsData.length === 0) return null

  // 准备 price & review 数组
  const prices = districtsData.map(d => d.avg_price).sort((a, b) => a - b)
  const reviews = districtsData.map(d => d.total_reviews).sort((a, b) => a - b)

  const mean = (arr: number[]) => arr.reduce((s, x) => s + x, 0) / arr.length
  const quantile = (arr: number[], q: number) => {
    const idx = (arr.length - 1) * q
    const lo = Math.floor(idx), hi = Math.ceil(idx)
    return arr[lo] + (arr[hi] - arr[lo]) * (idx - lo)
  }
  const median = (arr: number[]) => quantile(arr, 0.5)
  const q1 = (arr: number[]) => quantile(arr, 0.25)
  const q3 = (arr: number[]) => quantile(arr, 0.75)

  const priceMean = Math.round(mean(prices))
  const priceMedian = Math.round(median(prices))
  const priceQ1 = Math.round(q1(prices))
  const priceQ3 = Math.round(q3(prices))
  const priceMin = Math.round(prices[0])
  const priceMax = Math.round(prices[prices.length - 1])

  const reviewMean = Math.round(mean(reviews))
  const reviewMedian = Math.round(median(reviews))

  // Gini 系数
  const gini = (() => {
    const arr = districtsData.map(d => d.listing_count).sort((a, b) => a - b)
    const n = arr.length
    const cum = arr.reduce((s, x) => s + x, 0)
    let cumWeighted = 0
    arr.forEach((val, idx) => cumWeighted += (idx + 1) * val)
    return ((2 * cumWeighted) / (n * cum) - (n + 1) / n)
  })()

  const activeDistricts = districtsData.filter(d => d.listing_count > 0).length

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <MetricCard
          title="Price Mean vs Median"
          value={`${priceMean}€ / ${priceMedian}€`}
          onDrillDown={() => onDrillDown('price')}
        />
        <MetricCard
          title="Price IQR"
          value={`${priceQ1}€ – ${priceQ3}€`}
          description={`IQR = ${priceQ3 - priceQ1}€`}
          onDrillDown={() => onDrillDown('price')}
        />
        <MetricCard
          title="Price Range"
          value={`${priceMin}€ – ${priceMax}€`}
          onDrillDown={() => onDrillDown('price')}
        />
        <MetricCard
          title="Reviews Dispersion"
          // 这里把 Mean 用蓝色，Median 用绿色
          value={
            <span>
              <span style={{ color: '#1890ff' }}>{reviewMean}</span>
              {' / '}
              <span style={{ color: '#52c41a' }}>{reviewMedian}</span>
            </span>
          }
          onDrillDown={() => onDrillDown('review')}
        />
        <MetricCard
          title="Listing Gini Coefficient"
          value={gini.toFixed(2)}
          onDrillDown={() => onDrillDown('host')}
        />
        <MetricCard
          title="Active Districts"
          value={activeDistricts}
          onDrillDown={() => onDrillDown('controls')}
        />
      </div>
    </div>
  )
}

export default OverviewPanel
