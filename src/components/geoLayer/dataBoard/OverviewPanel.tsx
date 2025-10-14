// src/components/OverviewPanel.tsx
import React, { useEffect, useMemo, useState } from 'react'
import { fetchRoomTypeStats, fetchPriceStats, fetchRecentDemand30d } from '../../../api/api'
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
    // optional fields for scripted cards (may be missing and thus fallback to 'unavailable')
    availability_30?: number
    has_availability?: boolean
    review_scores_rating?: number
    // 🆕 ratings fields (means)
    review_scores_accuracy?: number
    review_scores_cleanliness?: number
    review_scores_checkin?: number
    review_scores_communication?: number
    review_scores_location?: number
    review_scores_value?: number
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

// const colorForBudget = (ratio: number) => (ratio >= 0.6 ? '#16a34a' : ratio >= 0.3 ? '#f59e0b' : '#ef4444')

const OverviewPanel: React.FC<OverviewPanelProps> = ({
  districtsData,
  selectedName = 'all',
  level = 'district',
  budgetMin = null,
  budgetMax = null,
  onDrillDown: _onDrillDown
}) => {
  if (!districtsData || districtsData.length === 0) return null

  // 全局（城市）基线：基于现有聚合数据保守计算
  const prices = useMemo(() => districtsData.map(d => d.avg_price).sort((a, b) => a - b), [districtsData])

  // const mean = (arr: number[]) => arr.reduce((s, x) => s + x, 0) / (arr.length || 1)
  const quantile = (arr: number[], q: number) => {
    if (arr.length === 0) return 0
    const idx = (arr.length - 1) * q
    const lo = Math.floor(idx), hi = Math.ceil(idx)
    return arr[lo] + (arr[hi] - arr[lo]) * (idx - lo)
  }

  const cityPriceMedian = Math.round(quantile(prices, 0.5))
  const cityPriceQ1 = Math.round(quantile(prices, 0.25))
  const cityPriceQ3 = Math.round(quantile(prices, 0.75))
  const totalListingsCity = districtsData.reduce((s, d) => s + (d.listing_count || 0), 0)
  const totalReviewsCity = districtsData.reduce((s, d) => s + (d.total_reviews || 0), 0)
  const cityPopularityBaseline = totalListingsCity > 0 ? Math.round(totalReviewsCity / totalListingsCity) : 0

  // 选中区域
  const selected = selectedName !== 'all' ? districtsData.find(d => d.name === selectedName) : undefined
  const n = selected?.listing_count || 0

  const areaMedian = selected?.median_price ?? selected?.avg_price
  const areaQ1 = selected?.p25_price
  const areaQ3 = selected?.p75_price
  const areaIqr = areaQ1 != null && areaQ3 != null ? Math.max(0, areaQ3 - areaQ1) : undefined
  const stabilityRatio = areaIqr != null && areaMedian ? areaIqr / areaMedian : undefined
  const stabilityLabel = stabilityRatio == null ? undefined
    : (stabilityRatio <= 0.25 ? 'Very stable' : stabilityRatio <= 0.5 ? 'Stable' : 'Variable')

  // 城市房型占比（保留，但移除交互，仅渲染小型环图）
  const [cityRoomTypes, setCityRoomTypes] = useState<Array<{ label: string; value: number; color: string }> | null>(null)
  // 选区房型占比
  const [areaRoomTypes, setAreaRoomTypes] = useState<Array<{ label: string; value: number; color: string }> | null>(null)
  useEffect(() => {
    const colors: Record<string, string> = {
      'Entire home/apt': '#60a5fa',
      'Private room': '#34d399',
      'Shared room': '#f59e0b',
      'Hotel room': '#a78bfa'
    }
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
    if (!selected || !selectedName) { setAreaRoomTypes(null); return }
    const colors: Record<string, string> = {
      'Entire home/apt': '#60a5fa',
      'Private room': '#34d399',
      'Shared room': '#f59e0b',
      'Hotel room': '#a78bfa'
    }
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
  }, [level, selectedName])

  // 预算命中率 + 价格直方图（选区） + 评分均值
  const [budgetHit, setBudgetHit] = useState<number | null>(null)
  const [, setCoverageWithin] = useState<number | null>(null)
  const [, setCoverageTotal] = useState<number | null>(null)
  const [, setCityIqrOverlap] = useState<'High' | 'Med' | 'Low' | null>(null)
  const [areaPriceHist, setAreaPriceHist] = useState<{ categories: string[]; values: number[] } | null>(null)
  const [histExpanded, setHistExpanded] = useState<boolean>(false)
  const [ratingsAvg, setRatingsAvg] = useState<{ rating?: number; accuracy?: number; cleanliness?: number; checkin?: number; communication?: number; location?: number; value?: number } | null>(null)
  // 🆕 近30天需求（Recent Demand 30d）
  const [recentDemand, setRecentDemand] = useState<{ active_share?: number; median_l30d_active?: number | null; l30d_per_100?: number; n?: number; label?: 'Low' | 'Medium' | 'High' | 'Sparse'; sparse?: boolean } | null>(null)
  useEffect(() => {
    if (!selected || !selectedName) {
      setBudgetHit(null)
      setCoverageWithin(null)
      setCoverageTotal(null)
      setCityIqrOverlap(null)
      setAreaPriceHist(null)
      setRatingsAvg(null)
      setRecentDemand(null)
      setHistExpanded(false)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        // 单次直方图请求（统一区间），预算覆盖基于该直方图计算
        const HIST_MIN = 0
        const HIST_MAX = 99999
        const totalRes = await fetchPriceStats(level, selectedName, HIST_MIN, HIST_MAX)
        const sum = (arr: number[]) => arr.reduce((s, x) => s + x, 0)
        const total = sum(totalRes?.data?.values || [])
        if (!cancelled) setCoverageTotal(total)
        if (!cancelled && totalRes?.data?.categories && totalRes?.data?.values) {
          setAreaPriceHist({ categories: totalRes.data.categories, values: totalRes.data.values })
          // 预算覆盖（若设置）
          if (budgetMin != null || budgetMax != null) {
            const blo = budgetMin == null ? -Infinity : budgetMin
            const bhi = budgetMax == null ? Infinity : budgetMax
            const within = totalRes.data.categories.reduce((acc: number, label: string, i: number) => {
              return acc + (binIntersectsRange(label, blo, bhi) ? (totalRes.data.values?.[i] || 0) : 0)
            }, 0)
        const ratio = total > 0 ? within / total : 0
            if (!cancelled) {
              setCoverageWithin(within)
              setBudgetHit(ratio)
            }
          } else {
            if (!cancelled) {
              setCoverageWithin(null)
              setBudgetHit(null)
            }
          }
          // 评分均值（来自后端 review_scores_avg）
          const avg = (totalRes?.data?.review_scores_avg) || null
          if (!cancelled) setRatingsAvg(avg)
        } else if (!cancelled) {
          setAreaPriceHist(null)
          setRatingsAvg(null)
        }
        // 预算与城市 IQR 重叠评估
        if (!cancelled) {
          if (budgetMin == null && budgetMax == null) {
            setCityIqrOverlap(null)
          } else {
            const lo = budgetMin == null ? -Infinity : budgetMin
            const hi = budgetMax == null ? Infinity : budgetMax
            const iqrLo = cityPriceQ1
            const iqrHi = cityPriceQ3
            const overlap = Math.max(0, Math.min(hi, iqrHi) - Math.max(lo, iqrLo))
            const iqrWidth = Math.max(1, iqrHi - iqrLo)
            const frac = overlap / iqrWidth
            setCityIqrOverlap(frac >= 0.66 ? 'High' : frac >= 0.33 ? 'Med' : 'Low')
          }
        }
        // 🆕 拉取近30天需求
        try {
          const rdLevel = level === 'district' ? 'district' : 'neighbourhood'
          const rd = await fetchRecentDemand30d(rdLevel as any, selectedName)
          if (!cancelled) setRecentDemand(rd || null)
        } catch {
          if (!cancelled) setRecentDemand(null)
        }
      } catch {
        if (!cancelled) {
          setBudgetHit(null)
          setCoverageWithin(null)
          setCoverageTotal(null)
          setCityIqrOverlap(null)
          setAreaPriceHist(null)
          setRatingsAvg(null)
          setRecentDemand(null)
        }
      }
    })()
    return () => { cancelled = true }
  }, [selectedName, level, budgetMin, budgetMax, !!selected])

  const parseNums = (s: string) => (s.match(/\d+/g) || []).map(Number)
  const binRange = (label: string): [number, number] => {
    const nums = parseNums(label)
    if (nums.length === 0) return [0, 0]
    if (/\+$/.test(label)) return [nums[0], Infinity]
    if (nums.length === 1) return [nums[0], nums[0]]
    return [nums[0], nums[1]]
  }
  const binIntersectsRange = (label: string, lo: number, hi: number) => {
    const [blo, bhi] = binRange(label)
    return !(bhi < lo || blo > hi)
  }

  // Ratings display + hover tooltip
  const ratings = {
    rating: ratingsAvg?.rating ?? selected?.review_scores_rating,
    accuracy: ratingsAvg?.accuracy ?? selected?.review_scores_accuracy,
    cleanliness: ratingsAvg?.cleanliness ?? selected?.review_scores_cleanliness,
    checkin: ratingsAvg?.checkin ?? selected?.review_scores_checkin,
    communication: ratingsAvg?.communication ?? selected?.review_scores_communication,
    location: ratingsAvg?.location ?? selected?.review_scores_location,
    value: ratingsAvg?.value ?? selected?.review_scores_value
  }
  const [ratingsTip, setRatingsTip] = useState<{ visible: boolean; x: number; y: number }>({ visible: false, x: 0, y: 0 })
  const handleRatingsEnter = () => setRatingsTip(v => ({ ...v, visible: true }))
  const handleRatingsLeave = () => setRatingsTip({ visible: false, x: 0, y: 0 })
  const handleRatingsMove = (e: React.MouseEvent) => setRatingsTip({ visible: true, x: e.clientX, y: e.clientY })
  // 🆕 Tooltip for Recent Demand card
  const [rdTip, setRdTip] = useState<{ visible: boolean; x: number; y: number }>({ visible: false, x: 0, y: 0 })
  const handleRdEnter = () => setRdTip(v => ({ ...v, visible: true }))
  const handleRdLeave = () => setRdTip({ visible: false, x: 0, y: 0 })
  const handleRdMove = (e: React.MouseEvent) => setRdTip({ visible: true, x: e.clientX, y: e.clientY })
  const formatScore = (v: any) => (v == null || isNaN(Number(v)) ? '—' : (Number(v)).toFixed(1))
  // Only show key metrics on card; full definitions remain in hover
  const ratingItems: Array<{ key: keyof typeof ratings; label: string }> = [
    { key: 'rating', label: 'Overall' },
    { key: 'cleanliness', label: 'Cleanliness' },
    { key: 'location', label: 'Location' }
  ]

  // ——— 渲染 ———
  return (
    <div className="space-y-4">
      {/* 未选区：全局（未选区） — 4 张事实卡片 */}
      {(!selected) && (
        <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
          <div className="text-sm text-gray-700 font-medium mb-3">Global (No selection)</div>
          <div className="grid grid-cols-2 gap-4">
            {/* City Price Baseline */}
            <MetricCard
              title={
                <span className="flex items-center gap-1">
                  City Price Baseline (Median • IQR)
                  <InfoPopover
                    title="IQR = 价格稳定性"
                    lines={[
                      <span key="i1"><strong>IQR (P25–P75)</strong> 越大 → 波动越大；越小 → 更稳定。</span>
                    ]}
                    iconTitle="Explain IQR"
                  />
                </span>
              }
              value={`€${cityPriceMedian} • [€${cityPriceQ1}–€${cityPriceQ3}]`}
            />

            {/* Room Type Mix（无交互小环图） */}
            <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
              <div className="text-sm text-gray-500 mb-2">Room Type Mix</div>
              {cityRoomTypes ? (
                <div>
                  <RoomTypePie items={cityRoomTypes} height={120} title={undefined} showLegend={false} />
                </div>
              ) : (
                <div className="text-xs text-gray-400">Room type mix unavailable</div>
              )}
            </div>

            {/* Popularity (Reviews) baseline */}
            <MetricCard
              title={<span>Popularity (Reviews)</span>}
              value={<span>{cityPopularityBaseline}</span>}
              description={<span className="text-gray-500">Estimated by reviews/listing</span>}
            />

            {/* Active Districts */}
            <MetricCard
              title={<span>Active Districts</span>}
              value={districtsData.filter(d => d.listing_count > 0).length}
            />
          </div>
        </div>
      )}

      {/* 已选区：4 卡 + 价格直方图 + 预算结论 */}
      {selected && (
        <div className="bg-white p-4 rounded-lg border border-blue-200 shadow-sm">
          <div className="text-sm text-blue-700 font-medium mb-3 flex items-center gap-2">
            <span>{selectedName} · Snapshot</span>
            <span className="text-xs text-gray-400">•</span>
            <span className="text-xs"><span className="text-rose-600 font-semibold">{n.toLocaleString()}</span> listings</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {/* Price (Median • IQR) + stability badge */}
            <MetricCard
              title={
                <span className="flex items-center gap-1 w-full">
                  Price (Median • IQR)
                  <InfoPopover
                    title="Stability = IQR / Median"
                    lines={[
                      <span key="s1">≤ 0.25 Very stable</span>,
                      <span key="s2">0.25–0.5 Stable</span>,
                      <span key="s3">{'>'} 0.5 Variable</span>
                    ]}
                    iconTitle="Explain stability"
                  />
                  {stabilityRatio != null && (
                    <span className="ml-auto text-[11px] px-2 py-0.5 rounded bg-gray-100 text-gray-700 border">
                      Stability: {stabilityLabel}
                    </span>
                  )}
                </span>
              }
              value={
                areaMedian ? (
                  <span>
                    €{Math.round(areaMedian)}
                    {areaQ1 != null && areaQ3 != null && (
                      <span className="text-gray-500 text-sm"> {' '}• [€{Math.round(areaQ1)}–€{Math.round(areaQ3)}]</span>
                    )}
                  </span>
                ) : '—'
              }
              description={areaMedian != null && areaMedian !== cityPriceMedian ? <span className="text-gray-500">City median: €{cityPriceMedian}</span> : undefined}
            />

            <div
              className="relative"
              onMouseEnter={handleRdEnter}
              onMouseLeave={handleRdLeave}
              onMouseMove={handleRdMove}
            >
              <MetricCard
                title={<span>📈 Recent Demand (30d)</span>}
                value={(() => {
                  if (!recentDemand || recentDemand.active_share == null) return '—'
                  const pct = Math.round((recentDemand.active_share || 0) * 100)
                  const label = recentDemand.label || (pct < 20 ? 'Low' : pct <= 50 ? 'Medium' : 'High')
                  const sparse = recentDemand.sparse
                  return (
                    <div className="flex flex-col gap-1 w-full">
                      <div className="flex items-center justify-between gap-2 w-full">
                        <div className="min-w-0">
                          <div className="leading-tight">
                            <span className="text-3xl font-extrabold text-gray-900" style={{ fontVariantNumeric: 'tabular-nums' }}>{pct}%</span>
                          </div>
                          <div className="text-xs text-gray-600 mt-0.5">of listings had new reviews</div>
                        </div>
                      </div>
                      <div className="pt-0.5">
                        <span className={`text-[10px] px-2 py-0.5 rounded border inline-flex items-center gap-1 ${sparse ? 'bg-gray-100 text-gray-500' : label === 'High' ? 'bg-green-100 text-green-700' : label === 'Medium' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                          <span>{sparse ? '⚪' : label === 'High' ? '🟢' : label === 'Medium' ? '🟠' : '🔴'}</span>
                          <span className="font-medium">{sparse ? 'Sparse' : label}</span>
                        </span>
                      </div>
                    </div>
                  )
                })()}
                description={undefined}
              />
              {rdTip.visible && recentDemand && (
                <div
                  style={{
                    position: 'fixed',
                    left: Math.min(rdTip.x + 12, Math.max(8, window.innerWidth - 320)),
                    top: Math.min(rdTip.y + 12, Math.max(8, window.innerHeight - 220)),
                    zIndex: 20000
                  }}
                  className="w-72 bg-white border border-gray-200 rounded-lg shadow-xl p-3 text-xs text-gray-700"
                >
                  <div className="font-semibold text-gray-800 mb-1">Recent 30-day activity</div>
                  <div className="space-y-1">
                    <div>
                      Median reviews (active): <span className="text-gray-900 font-semibold">{recentDemand.median_l30d_active == null ? '—' : recentDemand.median_l30d_active}</span>
                    </div>
                    <div>
                      Per 100 listings: <span className="text-gray-900 font-semibold">{recentDemand.l30d_per_100 == null ? '—' : (Math.round((recentDemand.l30d_per_100 || 0) * 10) / 10)}</span>
                    </div>
                    <div>
                      n=<span className="text-gray-900 font-semibold">{recentDemand.n ? recentDemand.n.toLocaleString() : '—'}</span>
                    </div>
                  </div>
                  <div className="text-[11px] text-gray-500 mt-2">Shows how many listings were actively reviewed in the last 30 days.</div>
                </div>
              )}
            </div>

            {/* Ratings Overview */}
            <div
              className="bg-white p-3 rounded-lg border border-gray-200 shadow-sm relative overflow-hidden"
              onMouseEnter={handleRatingsEnter}
              onMouseLeave={handleRatingsLeave}
              onMouseMove={handleRatingsMove}
            >
              <div className="text-sm text-gray-500 mb-2 flex items-center gap-1">
                <span>Rating Overview</span>
              </div>
              <div className="space-y-1 text-[11px] leading-4 text-gray-800 w-full">
                {ratingItems.map((it) => (
                  <div key={it.key as string} className="flex items-center justify-between gap-2 w-full">
                    <span className="text-gray-700 flex-1 whitespace-nowrap">{it.label}</span>
                    <span className="font-semibold w-10 text-right" style={{ fontVariantNumeric: 'tabular-nums' }}>{formatScore(ratings[it.key])}</span>
                  </div>
                ))}
              </div>

              {ratingsTip.visible && (
                <div
                  style={{
                    position: 'fixed',
                    left: Math.min(ratingsTip.x + 12, Math.max(8, window.innerWidth - 320)),
                    top: Math.min(ratingsTip.y + 12, Math.max(8, window.innerHeight - 220)),
                    zIndex: 20000
                  }}
                  className="w-72 bg-white border border-gray-200 rounded-lg shadow-xl p-3 text-xs text-gray-700"
                >
                  <div className="font-semibold text-gray-800 mb-2">What these mean</div>
                  <ul className="space-y-1 list-disc pl-4">
                    <li><strong>Overall (1–5)</strong>: post-stay composite score.</li>
                    <li><strong>Cleanliness</strong>: cleanliness level.</li>
                    <li><strong>Location</strong>: convenience and surroundings.</li>
                  </ul>
              </div>
              )}
            </div>

            {/* Room Type Mix (Area) */}
            <div className="bg-white p-4 rounded-lg border border-gray-200 shadow-sm">
              <div className="text-sm text-gray-500 mb-2">Room Type Mix</div>
                {areaRoomTypes ? (
                    <div>
                      <RoomTypePie items={areaRoomTypes} height={120} title={undefined} showLegend={false} />
                  <div className="text-xs text-gray-500 mt-1">
                    {(() => {
                      const entire = areaRoomTypes.find(x => x.label === 'Entire home/apt')
                      const total = areaRoomTypes.reduce((s, it) => s + (Number(it.value) || 0), 0)
                      if (!entire || total <= 0) return null
                      const pct = Math.round(Math.max(0, Math.min(100, (Number(entire.value) || 0) / total * 100)))
                      return <span>Entire homes share: {pct}%</span>
                    })()}
                  </div>
                    </div>
                ) : (
                  <div className="text-xs text-gray-400">Room type mix unavailable</div>
                )}
              </div>
            </div>

          {/* 唯一图：价格直方图（高亮预算区间） */}
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm text-gray-700">Price histogram</div>
              {areaPriceHist && (() => {
                const hasHidden = (() => {
                  const findCutIndex = () => {
                    const TH = 700
                    for (let i = 0; i < areaPriceHist.categories.length; i++) {
                      const c = areaPriceHist.categories[i]
                      const nums = parseNums(c)
                      const lo = nums.length > 0 ? nums[0] : 0
                      if (lo >= TH) return i
                    }
                    return areaPriceHist.categories.length
                  }
                  const cut = findCutIndex()
                  return cut < areaPriceHist.categories.length
                })()
                return hasHidden ? (
                  <button
                    className="text-xs px-2 py-1 border rounded text-gray-600 hover:bg-gray-50"
                    onClick={() => setHistExpanded(v => !v)}
                    title={histExpanded ? 'Collapse ranges above ~€700' : 'Show ranges above ~€700'}
                  >
                    {histExpanded ? '▲ Collapse >€700' : '▼ Show >€700'}
                  </button>
                ) : null
              })()}
            </div>
            {areaPriceHist ? (() => {
              const findCutIndex = () => {
                const TH = 700
                for (let i = 0; i < areaPriceHist.categories.length; i++) {
                  const c = areaPriceHist.categories[i]
                  const nums = parseNums(c)
                  const lo = nums.length > 0 ? nums[0] : 0
                  if (lo >= TH) return i
                }
                return areaPriceHist.categories.length
              }
              const cut = findCutIndex()
              const indices = histExpanded ? [...areaPriceHist.values.keys()] : [...Array(cut).keys()]
              const shownValues = indices.map(i => areaPriceHist.values[i])
              const maxV = Math.max(...shownValues, 1)
              const blo = budgetMin == null ? -Infinity : budgetMin
              const bhi = budgetMax == null ? Infinity : budgetMax
              return (
                <div className="space-y-1">
                  {indices.map((i) => {
                    const v = areaPriceHist.values[i]
                    const widthPct = Math.round((v / maxV) * 100)
                    const label = areaPriceHist.categories[i]
                    const inBudget = (budgetMin != null || budgetMax != null) && binIntersectsRange(label, blo, bhi)
                    return (
                      <div key={i} className="flex items-center gap-2">
                        <div className="w-32 text-xs text-gray-500">{label}</div>
                        <div className={`flex-1 ${inBudget ? 'bg-red-200' : 'bg-red-100'} h-3 rounded`}>
                          <div className={`${inBudget ? 'bg-red-600' : 'bg-red-400'} h-3 rounded`} style={{ width: `${widthPct}%` }}></div>
          </div>
                        <div className="w-10 text-right text-xs text-gray-500">{v}</div>
        </div>
                    )
                  })}
                </div>
              )
            })() : (
              <div className="text-xs text-gray-400">Histogram unavailable</div>
            )}
          </div>

          {/* 预算结论 */}
          <div className="text-xs text-gray-700 mt-2">
            {budgetMin != null || budgetMax != null ? (
              budgetHit != null ? (
                <span>Your range covers {Math.round((budgetHit || 0) * 100)}% of listings in {selectedName}.</span>
              ) : (
                <span className="text-gray-400">Budget coverage unavailable</span>
              )
            ) : (
              <span className="text-gray-400">Set a budget to estimate coverage.</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default OverviewPanel
