// src/components/OverviewPanel.tsx
import React, { useEffect, useMemo, useState } from 'react'
import { Popover } from 'antd'
import { fetchRoomTypeStats, fetchPriceStats } from '../../../api/api'
import PopularityExplainer from './PopularityExplainer'
import InfoPopover from './InfoPopover'
import RoomTypePie from './RoomTypePie'

interface OverviewPanelProps {
  districtsData: Array<{
    name?: string
    listing_count: number
    avg_price: number
    total_reviews: number
    popularity_score?: number
    min_price?: number
    max_price?: number
    median_price?: number
    p25_price?: number
    p75_price?: number
  }>
  selectedName?: string
  level?: 'district' | 'neighbourhood'
  budgetMin?: number | null
  budgetMax?: number | null
  onDrillDown: (insightKey: string) => void
}

const MetricCard: React.FC<{
  title: React.ReactNode
  value: React.ReactNode
  description?: React.ReactNode
  onDrillDown?: () => void
}> = ({ title, value, description, onDrillDown }) => (
  <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm" data-has-drilldown={!!onDrillDown}>
    <div className="text-sm text-gray-500 flex items-center gap-1">
      {title}
    </div>
    <div className="mt-1 text-2xl font-bold text-gray-800">{value}</div>
    {description && <div className="text-xs text-gray-600 mt-1">{description}</div>}
  </div>
)

const colorForBudget = (ratio: number) => (ratio >= 0.6 ? '#16a34a' : ratio >= 0.3 ? '#f59e0b' : '#ef4444')

const OverviewPanel: React.FC<OverviewPanelProps> = ({
  districtsData,
  selectedName = 'all',
  level = 'district',
  budgetMin = null,
  budgetMax = null,
  onDrillDown
}) => {
  if (!districtsData || districtsData.length === 0) return null

  // 全局（城市）基线：基于现有聚合数据保守计算
  const prices = useMemo(() => districtsData.map(d => d.avg_price).sort((a, b) => a - b), [districtsData])

  const mean = (arr: number[]) => arr.reduce((s, x) => s + x, 0) / (arr.length || 1)
  const quantile = (arr: number[], q: number) => {
    if (arr.length === 0) return 0
    const idx = (arr.length - 1) * q
    const lo = Math.floor(idx), hi = Math.ceil(idx)
    return arr[lo] + (arr[hi] - arr[lo]) * (idx - lo)
  }

  const cityPriceMedian = Math.round(quantile(prices, 0.5))
  const cityPriceQ1 = Math.round(quantile(prices, 0.25))
  const cityPriceQ3 = Math.round(quantile(prices, 0.75))
  const cityPopularityAvg = Math.round(mean(districtsData.map(d => d.popularity_score ?? 0)))
  const totalListingsCity = districtsData.reduce((s, d) => s + (d.listing_count || 0), 0)

  // 选中区域
  const selected = selectedName !== 'all' ? districtsData.find(d => d.name === selectedName) : undefined
  const n = selected?.listing_count || 0
  const confidenceLabel = n >= 300 ? 'High' : n >= 100 ? 'Medium' : 'Low'

  const areaMedian = selected?.median_price ?? selected?.avg_price
  const areaQ1 = selected?.p25_price
  const areaQ3 = selected?.p75_price
  const areaPriceIndex = areaMedian && cityPriceMedian ? Math.round((areaMedian / cityPriceMedian) * 100) : undefined
  const areaSupplyShare = selected && totalListingsCity > 0 ? Math.round((selected.listing_count / totalListingsCity) * 100) : undefined

  // 房型占比（选区 + 全市）
  const [areaRoomTypes, setAreaRoomTypes] = useState<Array<{ label: string; value: number; color: string }> | null>(null)
  const [cityRoomTypes, setCityRoomTypes] = useState<Array<{ label: string; value: number; color: string }> | null>(null)

  // 加载状态
  const [areaRoomLoading, setAreaRoomLoading] = useState<boolean>(false)
  const [budgetLoading, setBudgetLoading] = useState<boolean>(false)
  const overviewLoading = areaRoomLoading || budgetLoading

  const [snapshotCollapsed, setSnapshotCollapsed] = useState<boolean>(false)

  useEffect(() => {
    const colors: Record<string, string> = {
      'Entire home/apt': '#60a5fa',
      'Private room': '#34d399',
      'Shared room': '#f59e0b',
      'Hotel room': '#a78bfa'
    }
    // 全市基线
    fetchRoomTypeStats('district', 'ALL')
      .then((res) => {
        if (res?.data?.categories && res?.data?.values) {
          setCityRoomTypes(
            res.data.categories.map((c: string, i: number) => ({ label: c, value: res.data.values[i], color: colors[c] || '#9ca3af' }))
          )
        }
      })
      .catch(() => setCityRoomTypes(null))
  }, [])

  useEffect(() => {
    if (!selected || !selectedName) {
      setAreaRoomTypes(null)
      return
    }
    const colors: Record<string, string> = {
      'Entire home/apt': '#60a5fa',
      'Private room': '#34d399',
      'Shared room': '#f59e0b',
      'Hotel room': '#a78bfa'
    }
    setAreaRoomLoading(true)
    fetchRoomTypeStats(level, selectedName)
      .then((res) => {
        if (res?.data?.categories && res?.data?.values) {
          setAreaRoomTypes(
            res.data.categories.map((c: string, i: number) => ({ label: c, value: res.data.values[i], color: colors[c] || '#9ca3af' }))
          )
        } else {
          setAreaRoomTypes(null)
        }
      })
      .catch(() => setAreaRoomTypes(null))
      .finally(() => setAreaRoomLoading(false))
  }, [level, selectedName])

  // 预算命中率
  const [budgetHit, setBudgetHit] = useState<number | null>(null)
  useEffect(() => {
    const hasBudget = budgetMin != null || budgetMax != null
    if (!selected || !hasBudget) {
      setBudgetHit(null)
      return
    }
    let cancelled = false
    setBudgetLoading(true)
    ;(async () => {
      try {
        const totalRes = await fetchPriceStats(level, selectedName)
        const inBudgetRes = await fetchPriceStats(
          level,
          selectedName,
          budgetMin == null ? 0 : budgetMin,
          budgetMax == null ? 99999 : budgetMax
        )
        const sum = (arr: number[]) => arr.reduce((s, x) => s + x, 0)
        const total = sum(totalRes?.data?.values || [])
        const within = sum(inBudgetRes?.data?.values || [])
        const ratio = total > 0 ? within / total : 0
        if (!cancelled) setBudgetHit(ratio)
      } catch {
        if (!cancelled) setBudgetHit(null)
      } finally {
        if (!cancelled) setBudgetLoading(false)
      }
    })()
    return () => { cancelled = true }
  }, [selectedName, level, budgetMin, budgetMax, !!selected])

  // 人气指数：用 popularity_score 相对全市均值
  const areaPopularity = selected?.popularity_score
  const popularityIndex = areaPopularity != null && cityPopularityAvg > 0
    ? Math.round((areaPopularity / cityPopularityAvg) * 100)
    : undefined

  // 稳定性：价格波动系数 IQR/Median（没有分位数则退化为 Range/Avg 近似）
  const stabilityCoef = useMemo(() => {
    if (areaMedian && areaQ1 && areaQ3) {
      const iqr = areaQ3 - areaQ1
      return areaMedian > 0 ? Math.round((iqr / areaMedian) * 100) : undefined
    }
    if (selected?.min_price != null && selected?.max_price != null && selected?.avg_price) {
      const range = selected.max_price - selected.min_price
      return selected.avg_price > 0 ? Math.round((range / selected.avg_price) * 100) : undefined
    }
    return undefined
  }, [areaMedian, areaQ1, areaQ3, selected?.min_price, selected?.max_price, selected?.avg_price])

  const activeDistricts = districtsData.filter(d => d.listing_count > 0).length

  return (
    <div className="space-y-4">
      {/* 模块 A：Selected Area Snapshot */}
      {selected && (
        <div className="bg-white p-4 rounded-lg border border-blue-200 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-sm text-blue-700 font-medium flex items-center gap-2">
                <span>Selected Area Snapshot</span>
                {overviewLoading && (
                  <span className="inline-flex items-center" title="Loading area insights...">
                    <span className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full"></span>
                  </span>
                )}
              </div>
              <div className="text-lg font-bold text-gray-800">{selectedName}</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-gray-500">n = {n.toLocaleString()}</div>
              <div className={`text-xs font-medium ${confidenceLabel === 'High' ? 'text-green-600' : confidenceLabel === 'Medium' ? 'text-amber-600' : 'text-red-600'}`}>{confidenceLabel} confidence</div>
              <button
                onClick={() => setSnapshotCollapsed(v => !v)}
                className="ml-2 mt-2 text-xs px-2 py-1 border rounded text-gray-600 hover:bg-gray-50"
                title={snapshotCollapsed ? 'Expand' : 'Collapse'}
              >
                {snapshotCollapsed ? '▼ Expand' : '▲ Collapse'}
              </button>
            </div>
          </div>

          {!snapshotCollapsed && (
          <div className="grid grid-cols-2 gap-3">
            {/* 价格（稳健口径） */}
            <MetricCard
              title={
                <span className="flex items-center gap-1">
                  Price (Median • IQR)
                  <InfoPopover
                    title="Price · How it works"
                    lines={[
                      <span key="p1"><strong style={{ color: '#0ea5e9' }}>Purpose:</strong> Median and IQR provide robust typical prices and range.</span>,
                      <span key="p2"><strong>Median:</strong> middle price (stable vs outliers).</span>,
                      <span key="p3"><strong>IQR (P25–P75):</strong> typical price band.</span>,
                      <span key="p4"><strong>Index:</strong> area median / city median ×100.</span>
                    ]}
                    iconTitle="Explain price metrics"
                  />
                </span>
              }
              value={
                areaMedian ? (
                  <span>
                    €{Math.round(areaMedian)}
                    {areaQ1 != null && areaQ3 != null && (
                      <span className="text-gray-500 text-sm"> {' '}• [{Math.round(areaQ1)}–{Math.round(areaQ3)}]</span>
                    )}
                    {areaPriceIndex && (
                      <span className="ml-2 text-xs text-gray-500">Index {areaPriceIndex}</span>
                    )}
                  </span>
                ) : '—'
              }
              onDrillDown={undefined}
            />

            {/* 预算匹配度 */}
            <MetricCard
              title={<span>Budget Match</span>}
              value={
                budgetHit != null ? (
                  <span className="flex items-center gap-2">
                    <span className="text-lg font-bold" style={{ color: colorForBudget(budgetHit) }}>{Math.round(budgetHit * 100)}%</span>
                    <span className="text-xs text-gray-500">in budget</span>
                  </span>
                ) : '—'
              }
              description={
                budgetMin != null || budgetMax != null
                  ? `Budget: ${budgetMin != null ? '€' + budgetMin : '—'}–${budgetMax != null ? '€' + budgetMax : '—'}`
                  : undefined
              }
            />

            {/* 供给与结构（加入解释与悬浮图表） */}
            <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
              {/* Upper block: City share */}
              {level === 'district' && (
              <div className="mb-3">
                <div className="text-sm text-gray-700 flex items-center gap-1">
                  <span>Supply & Structure</span>
                </div>
                <div className="mt-1 text-sm text-gray-700 flex items-center gap-1">
                  <span>City share</span>
                  <InfoPopover
                    title="City share · How it works"
                    lines={[
                      <span key="l1"><strong>Meaning:</strong> This area's listings as a share of the city's total.</span>,
                      <span key="l2"><strong>Purpose:</strong> Indicates breadth of choice and supply depth (larger share = more options).</span>
                    ]}
                    iconTitle="What is City share?"
                  />
                  <span>:</span>
                  <span className="font-semibold text-blue-700">{areaSupplyShare != null ? `${areaSupplyShare}%` : '—'}</span>
                </div>
              </div>
              )}

              {/* Lower block: Room type mix */}
              <div>
                <div className="text-sm text-gray-700 flex items-center gap-1 mb-2">
                  <span>Room type mix</span>
                  <InfoPopover
                    title="Room type mix · How it works"
                    lines={[
                      <span key="r1"><strong style={{ color: '#0ea5e9' }}>Purpose:</strong> Understand supply structure (Entire vs Private vs Shared vs Hotel).</span>
                    ]}
                  />
                </div>
                {areaRoomTypes ? (
                  <Popover trigger={["hover", "click"]} overlayStyle={{ zIndex: 20000 }} content={<div style={{ width: 360 }}><RoomTypePie items={areaRoomTypes} height={280} title={`${selectedName} · Room type mix`} showLegend /></div>}>
                    <div>
                      <RoomTypePie items={areaRoomTypes} height={120} title={undefined} showLegend={false} />
                    </div>
                  </Popover>
                ) : (
                  <div className="text-xs text-gray-400">Room type mix unavailable</div>
                )}
              </div>
            </div>

            {/* 受欢迎度（人气） */}
            <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
              <div className="text-sm text-gray-500 mb-1 flex items-center">
                <span>Popularity</span>
                <PopularityExplainer
                  scope="area"
                  areaName={selectedName || undefined}
                  sampleSize={n}
                  confidence={confidenceLabel as any}
                  areaPopularity={areaPopularity ?? null}
                  cityPopularityAvg={cityPopularityAvg}
                  indexValue={popularityIndex ?? null}
                />
              </div>
              <div className="text-2xl font-bold text-gray-800">
                {areaPopularity != null ? (
                  <span>
                    {areaPopularity}%
                    {popularityIndex && (
                      <span className="ml-2 text-xs text-gray-500">Index {popularityIndex}</span>
                    )}
                  </span>
                ) : '—'}
              </div>
            </div>

            {/* 可订性 */}
            <MetricCard
              title={
                <span className="flex items-center gap-1">
                  Bookability
                  <InfoPopover
                    title="Bookability · How it works"
                    lines={[
                      <span key="b1"><strong style={{ color: '#0ea5e9' }}>Purpose:</strong> Estimate how easy it is to book.</span>,
                      <span key="b2"><strong>Metrics:</strong> median availability_365; if trip length is set, share of listings with ≥X nights available.</span>
                    ]}
                  />
                </span>
              }
              value={'—'}
              description={<span className="text-gray-400">availability data not available</span>}
            />

            {/* 稳定性/风险 */}
            <MetricCard
              title={
                <span className="flex items-center gap-1">
                  Price Stability (IQR/Median)
                  <InfoPopover
                    title="Price stability"
                    lines={[
                      <span key="s1"><strong style={{ color: '#0ea5e9' }}>Purpose:</strong> Lower variation = more predictable pricing.</span>,
                      <span key="s2"><strong>Metric:</strong> IQR / Median (or Range / Avg fallback).</span>
                    ]}
                  />
                </span>
              }
              value={stabilityCoef != null ? `${stabilityCoef}%` : '—'}
              description={n < 100 ? <span className="text-red-500">⚠️ Low confidence due to small sample</span> : undefined}
            />
          </div>
          )}
        </div>
      )}

      {/* 模块 B：Global Baseline */}
      <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
        <div className="text-sm text-gray-700 font-medium mb-3">Global Baseline</div>
        <div className="grid grid-cols-2 gap-4">
          <MetricCard
            title={
              <span className="flex items-center gap-1">
                City Price Baseline (Median • IQR)
                <InfoPopover
                  title="City price baseline"
                  lines={[
                    <span key="bp1"><strong style={{ color: '#0ea5e9' }}>Purpose:</strong> Reference anchor for all price indices.</span>,
                    <span key="bp2">Median and IQR are robust against extremes.</span>
                  ]}
                />
              </span>
            }
            value={`€${cityPriceMedian} • [€${cityPriceQ1}–€${cityPriceQ3}]`}
            onDrillDown={undefined}
          />

          <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
            <div className="text-sm text-gray-500 mb-2 flex items-center gap-1">
              <span>City Room Type Structure</span>
              <InfoPopover
                title="City room type mix"
                lines={[
                  <span key="cr1"><strong style={{ color: '#0ea5e9' }}>Purpose:</strong> City-wide reference for structure comparison.</span>
                ]}
              />
            </div>
            {cityRoomTypes ? (
              <Popover trigger={["hover", "click"]} overlayStyle={{ zIndex: 20000 }} content={<div style={{ width: 360 }}><RoomTypePie items={cityRoomTypes} height={280} title="City · Room type mix" showLegend /></div>}>
                <div>
                  <RoomTypePie items={cityRoomTypes} height={120} title={undefined} showLegend={false} />
                </div>
              </Popover>
            ) : (
              <div className="text-xs text-gray-400">Room type mix unavailable</div>
            )}
          </div>

          <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
            <div className="text-sm text-gray-500 mb-2 flex items-center">
              <span>City Popularity Baseline</span>
              <PopularityExplainer
                scope="city"
                cityPopularityAvg={cityPopularityAvg}
              />
            </div>
            <div className="text-2xl font-bold text-gray-800">{cityPopularityAvg}%</div>
          </div>

          <MetricCard
            title={<span>Active Districts</span>}
            value={activeDistricts}
            onDrillDown={() => onDrillDown('controls')}
          />
        </div>
      </div>
    </div>
  )
}

export default OverviewPanel
