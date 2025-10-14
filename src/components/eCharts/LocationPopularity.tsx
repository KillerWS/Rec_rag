import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as echarts from 'echarts';
import { createPortal } from 'react-dom';

interface ChartDataLike {
  type: 'bar' | 'pie' | 'line' | 'scatter' | string;
  title: string;
  data: any;
  options?: any;
  description?: string;
  echarts_option?: any;
}

interface LocationPopularityProps {
  chartData: ChartDataLike;
  height?: number;
  width?: string;
  modalVisible?: boolean;
  onRefreshRequest?: () => void; // 🆕 回调：请求刷新全局数据
}

const LocationPopularity: React.FC<LocationPopularityProps> = ({ chartData, height = 300, width = '100%', modalVisible, onRefreshRequest }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{
    key: string;
    x: number;
    y: number;
    title: string;
    desc: string;
  } | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Adjustable weights (raw -> normalized)
  const defaultWeightRaw = useMemo(() => ({ rpm: 30, rating: 25, ltm: 20, occ: 15, sh: 10 }), []);
  const [weightRaw, setWeightRaw] = useState<{ rpm: number; rating: number; ltm: number; occ: number; sh: number }>(
    defaultWeightRaw
  );
  const weightsNormalized = useMemo(() => {
    const sum = weightRaw.rpm + weightRaw.rating + weightRaw.ltm + weightRaw.occ + weightRaw.sh || 1;
    return {
      rpm: weightRaw.rpm / sum,
      rating: weightRaw.rating / sum,
      ltm: weightRaw.ltm / sum,
      occ: weightRaw.occ / sum,
      sh: weightRaw.sh / sum
    };
  }, [weightRaw]);

  const option = useMemo(() => {
    // Helpers
    const pickNumber = (obj: any, keys: string[], fallback = 0) => {
      for (const k of keys) {
        const v = obj?.[k];
        if (typeof v === 'number' && !isNaN(v)) return v;
      }
      return fallback;
    };
    const pickName = (obj: any) => obj?.neighbourhood_group_cleansed || obj?.district || obj?.name || obj?.neighbourhood || obj?.area || '';
    const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);
    const interp = (a: number, b: number, t: number) => a + (b - a) * t;
    const hexToRgb = (hex: string) => {
      const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
      return m ? { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) } : { r: 0, g: 0, b: 0 };
    };
    const rgbToHex = (r: number, g: number, b: number) => {
      const toHex = (n: number) => Math.round(n).toString(16).padStart(2, '0');
      return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
    };
    const lerpColor = (c1: string, c2: string, t: number) => {
      const a = hexToRgb(c1); const b = hexToRgb(c2);
      return rgbToHex(interp(a.r, b.r, t), interp(a.g, b.g, t), interp(a.b, b.b, t));
    };

    const tryGetSourceRows = () => {
      const opt = chartData?.echarts_option;
      if (opt?.dataset?.source && Array.isArray(opt.dataset.source)) return opt.dataset.source as any[];
      const d = chartData?.data;
      if (Array.isArray(d)) return d as any[];
      if (Array.isArray(d?.rows)) return d.rows as any[];
      if (Array.isArray(d?.source)) return d.source as any[];
      return [] as any[];
    };

    const buildPopularityOption = () => {
      const rows = tryGetSourceRows();
      if (!rows || rows.length === 0) return null;

      // Prepare aggregated records
      const prepared = rows.map((r) => {
        const name = pickName(r);
        const reviewsPerMonth = pickNumber(r, ['avg_reviews_per_month', 'reviews_per_month']);
        const avgRatingRaw = pickNumber(r, ['avg_rating', 'review_scores_rating']);
        const reviewsLtm = pickNumber(r, ['total_reviews_ltm', 'number_of_reviews_ltm']);
        const superhostRatioRaw = pickNumber(r, ['superhost_ratio', 'superhost_ratio_percent']);
        const availabilityAvg = pickNumber(r, ['avg_availability_365', 'availability_365']);
        const occupancyProxy = r?.occupancy_proxy != null
          ? Number(r.occupancy_proxy)
          : clamp01(1 - (availabilityAvg > 0 ? availabilityAvg / 365 : 0));
        const listingCount = pickNumber(r, ['listing_count']);

        // Normalize rating domain (support 0-5 or 0-100)
        const avgRating = avgRatingRaw > 5 ? avgRatingRaw / 20 : avgRatingRaw;
        // Normalize superhost ratio domain (support 0-1 or 0-100)
        const superhostRatio = superhostRatioRaw > 1 ? superhostRatioRaw / 100 : superhostRatioRaw;

        return { name, reviewsPerMonth, avgRating, reviewsLtm, occupancyProxy, superhostRatio, listingCount };
      }).filter(r => r.name);

      if (prepared.length === 0) return null;

      // Compute min-max for each dimension
      const dims = {
        rpm: prepared.map(r => r.reviewsPerMonth),
        rating: prepared.map(r => r.avgRating),
        ltm: prepared.map(r => r.reviewsLtm),
        occ: prepared.map(r => r.occupancyProxy),
        sh: prepared.map(r => r.superhostRatio)
      };
      const min = (arr: number[]) => Math.min(...arr);
      const max = (arr: number[]) => Math.max(...arr);
      const mm = {
        rpm: { min: min(dims.rpm), max: max(dims.rpm) },
        rating: { min: min(dims.rating), max: max(dims.rating) },
        ltm: { min: min(dims.ltm), max: max(dims.ltm) },
        occ: { min: min(dims.occ), max: max(dims.occ) },
        sh: { min: min(dims.sh), max: max(dims.sh) }
      };
      const norm = (v: number, m: { min: number; max: number }) => (m.max > m.min ? (v - m.min) / (m.max - m.min) : 0);

      // Weights (normalized from sliders)
      const weights = weightsNormalized;

      const scored = prepared.map(r => {
        const nRpm = norm(r.reviewsPerMonth, mm.rpm);
        const nRating = norm(r.avgRating, mm.rating);
        const nLtm = norm(r.reviewsLtm, mm.ltm);
        const nOcc = norm(r.occupancyProxy, mm.occ);
        const nSh = norm(r.superhostRatio, mm.sh);
        const score01 = weights.rpm * nRpm + weights.rating * nRating + weights.ltm * nLtm + weights.occ * nOcc + weights.sh * nSh;
        const score100 = score01 * 100;
        return { ...r, nRpm, nRating, nLtm, nOcc, nSh, popularity_score: score100 };
      }).sort((a, b) => b.popularity_score - a.popularity_score);

      const names = scored.map(r => r.name);

      const lowColor = '#f39c12'; // orange
      const highColor = '#2ecc71'; // green

      return {
        title: { text: 'Location Popularity Score', left: 'center' },
        grid: { left: '8%', right: '8%', bottom: '8%', top: '16%', containLabel: true },
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' },
          formatter: (params: any) => {
            const p = Array.isArray(params) ? params[0] : params;
            const d = p?.data || {};
            const rating = d.avgRating != null ? Number(d.avgRating).toFixed(2) : '-';
            const rpm = d.reviewsPerMonth != null ? Number(d.reviewsPerMonth).toFixed(2) : '-';
            const ltm = d.reviewsLtm != null ? d.reviewsLtm : '-';
            const sh = d.superhostRatio != null ? `${Math.round(d.superhostRatio * 100)}%` : '-';
            const occ = d.occupancyProxy != null ? (Number(d.occupancyProxy) * 100).toFixed(0) + '%' : '-';
            const score = d.popularity_score != null ? Math.round(d.popularity_score) : '-';
            return `${d.name || p?.axisValue}<br/>🔥 Popularity Score: ${score}` +
              `<br/>⭐ Avg Rating: ${rating}` +
              `<br/>💬 Avg Reviews per Month: ${rpm}` +
              `<br/>📈 Reviews (12m): ${ltm}` +
              `<br/>🏠 Superhost Ratio: ${sh}` +
              `<br/>📅 Occupancy Proxy: ${occ}`;
          }
        },
        xAxis: { type: 'value', name: 'Popularity Score', max: 100 },
        yAxis: { type: 'category', data: names },
        series: [{
          type: 'bar',
          name: 'Popularity Score',
          encode: undefined,
          label: { show: true, position: 'right', fontWeight: 'bold', fontSize: 12, color: '#333', formatter: (p: any) => `${Math.round(p.data.popularity_score)}` },
          itemStyle: {
            color: (p: any) => {
              const t = clamp01(p?.data?.nRating ?? 0);
              return lerpColor(lowColor, highColor, t);
            }
          },
          data: scored.map((r) => ({ ...r, value: r.popularity_score }))
        }],
        __popExplainer: {
          weights,
          ranges: {
            reviews_per_month: mm.rpm,
            review_scores_rating: mm.rating,
            number_of_reviews_ltm: mm.ltm,
            occupancy_proxy: mm.occ,
            superhost_ratio: mm.sh
          }
        }
      } as any;
    };

    // Try to build new popularity view first
    const popularityOption = buildPopularityOption();
    if (popularityOption) return popularityOption;

    // Prefer backend-provided option (normalized)
    const opt = chartData?.echarts_option;
    if (opt) {
      const normalized: any = {
        ...opt,
        xAxis: Array.isArray((opt as any).xAxis)
          ? (opt as any).xAxis.map((ax: any) => ({ ...ax }))
          : { ...(opt as any).xAxis },
        tooltip: { ...(opt as any).tooltip },
        dataset: { ...(opt as any).dataset }
      };

      // If using dataset+encode, avoid conflicting manual category list
      if (normalized.dataset?.source && normalized.xAxis) {
        if (Array.isArray(normalized.xAxis)) {
          normalized.xAxis = normalized.xAxis.map((ax: any) => {
            if (ax && 'data' in ax) {
              const { data, ...rest } = ax;
              return rest;
            }
            return ax;
          });
        } else if ('data' in normalized.xAxis) {
          delete normalized.xAxis.data;
        }
      }

      // Improve tooltip for axis trigger to reliably show dataset fields
      if (normalized.tooltip?.trigger === 'axis') {
        normalized.tooltip.formatter = (params: any) => {
          const list = Array.isArray(params) ? params : [params];
          const first = list[0];
          const index = first?.dataIndex ?? 0;
          const source = normalized.dataset?.source ?? [];
          const row = source[index];

          if (row && typeof row === 'object') {
            const name = row.neighbourhood_group_cleansed ?? first?.axisValue ?? '';
            const listing = row.listing_count ?? first?.value ?? '';
            const price = row.avg_price ?? '';
            const reviews = row.avg_reviews ?? '';
            const hosts = row.unique_hosts ?? '';
            const pop = row.popularity_percent ?? '';
            return `${name}<br/>🏠 Listings: ${listing}<br/>💰 Avg Price: €${price}<br/>⭐ Reviews: ${reviews}<br/>👤 Hosts: ${hosts}<br/>Popularity: ${pop}%`;
          }

          const axisName = first?.axisValue ?? '';
          const lines = list.map((p: any) => `${p.marker}${p.seriesName}: ${p.value}`);
          return `${axisName}<br/>${lines.join('<br/>')}`;
        };
      }

      return normalized;
    }

    // Fallback: simple bar using data.categories/values
    const categories = chartData?.data?.categories || [];
    const values = chartData?.data?.values || [];
    return {
      title: { text: chartData?.title || 'Neighborhoods Popularity', left: 'center' },
      tooltip: { trigger: 'axis' },
      grid: { left: '8%', right: '8%', bottom: '14%', top: '16%', containLabel: true },
      xAxis: { type: 'category', data: categories, axisLabel: { rotate: 45, interval: 0 } },
      yAxis: { type: 'value', name: 'Popularity' },
      series: [{ type: 'bar', data: values }]
    } as any;
  }, [chartData, weightsNormalized]);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current);
    }
    chartInstance.current.setOption(option, true);

    const handleResize = () => chartInstance.current?.resize();
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chartInstance.current?.dispose();
      chartInstance.current = null;
    };
  }, [option]);

  // Resize when modal visibility changes
  useEffect(() => {
    if (modalVisible !== undefined && chartInstance.current) {
      const timer = setTimeout(() => chartInstance.current?.resize(), 250);
      return () => clearTimeout(timer);
    }
  }, [modalVisible]);

  const explainer = (option as any)?.__popExplainer;
  const isCompact = height <= 120;
  const badgeStyle: React.CSSProperties = {
    display: 'inline-block',
    fontSize: 11,
    fontWeight: 700,
    color: '#2b5bd7',
    background: '#eef5ff',
    border: '1px solid #d0e3ff',
    borderRadius: 6,
    padding: '0px 6px'
  };

  const descriptions: Record<string, string> = {
    reviews_per_month: 'Direct field. Avg reviews per listing per month in the area. Higher indicates stronger demand/booking activity.',
    review_scores_rating: 'Direct field. Average guest rating (often 0–100; normalized internally). Higher indicates greater satisfaction/quality.',
    number_of_reviews_ltm: 'Direct field. Total reviews in the last 12 months across listings. Captures recent engagement and demand recency.',
    occupancy_proxy: 'Derived metric. Tightness proxy = 1 − avg(availability_365)/365. Higher means fewer nights available → higher occupancy/demand.',
    superhost_ratio: "Derived metric. Share of listings by Superhosts: AVG(host_is_superhost). Higher implies stronger host reliability/trust."
  };

  const rangeCards = explainer ? [
    { key: 'reviews_per_month', title: 'reviews_per_month', hint: 'higher = more demand', format: (v: number) => v.toFixed(2) },
    { key: 'review_scores_rating', title: 'review_scores_rating', hint: 'user satisfaction', format: (v: number) => v.toFixed(2) },
    { key: 'number_of_reviews_ltm', title: 'number_of_reviews_ltm', hint: 'recent engagement', format: (v: number) => Math.round(v) },
    { key: 'occupancy_proxy', title: 'occupancy_proxy', hint: 'tightness', format: (v: number) => `${Math.round(v * 100)}%` },
    { key: 'superhost_ratio', title: 'superhost_ratio', hint: 'trust', format: (v: number) => `${Math.round(v * 100)}%` }
  ] : [];

  const renderPortalTooltip = () => {
    if (!tooltip) return null;
    const margin = 8;
    const viewportW = window.innerWidth;
    const viewportH = window.innerHeight;
    // Decide placement: above unless too close to top
    const placeBelow = tooltip.y < 56;
    const left = Math.min(viewportW - margin, Math.max(margin, tooltip.x));
    const top = placeBelow ? Math.min(viewportH - margin, Math.max(margin, tooltip.y + 24)) : Math.max(margin, tooltip.y);

    return createPortal(
      <div style={{
        position: 'fixed',
        left,
        top,
        transform: 'translate(-50%, -100%)',
        background: '#ffffff',
        border: '1px solid #e6f0ff',
        borderRadius: 8,
        padding: '8px 10px',
        boxShadow: '0 10px 28px rgba(30,58,138,0.18)',
        color: '#334155',
        zIndex: 2000,
        whiteSpace: 'nowrap',
        pointerEvents: 'none'
      }}>
        <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 2 }}>{tooltip.title}</div>
        <div style={{ fontSize: 11, color: '#475569' }}>{tooltip.desc}</div>
        <div style={{
          position: 'absolute',
          left: '50%',
          bottom: placeBelow ? 'auto' : -6,
          top: placeBelow ? -6 : 'auto',
          transform: 'translateX(-50%)',
          width: 0,
          height: 0,
          borderLeft: '6px solid transparent',
          borderRight: '6px solid transparent',
          borderTop: placeBelow ? 'none' : '6px solid #ffffff',
          borderBottom: placeBelow ? '6px solid #ffffff' : 'none'
        }} />
      </div>,
      document.body
    );
  };

  return (
    <div>
      <div 
        ref={chartRef}
        style={{ width, height: `${height}px`, minHeight: isCompact ? `${height}px` : '200px' }}
      />
      {explainer && !isCompact && (
        <div style={{ fontSize: 12, color: '#666', marginTop: 8, lineHeight: 1.6 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>How the Popularity Score is computed</div>
          <div>
            {(() => {
              const w = (explainer?.weights || weightsNormalized) as { rpm: number; rating: number; ltm: number; occ: number; sh: number };
              const fmt = (x: number) => (Math.round(x * 100) / 100).toFixed(2);
              return (
                <>
                  Popularity Score = {fmt(w.rpm)} × norm(<span style={badgeStyle} title={descriptions.reviews_per_month}>reviews_per_month</span>)
                  + {fmt(w.rating)} × norm(<span style={badgeStyle} title={descriptions.review_scores_rating}>review_scores_rating</span>)
                  + {fmt(w.ltm)} × norm(<span style={badgeStyle} title={descriptions.number_of_reviews_ltm}>number_of_reviews_ltm</span>)
                  + {fmt(w.occ)} × norm(<span style={badgeStyle} title={descriptions.occupancy_proxy}>occupancy_proxy</span>)
                  + {fmt(w.sh)} × norm(<span style={badgeStyle} title={descriptions.superhost_ratio}>superhost_ratio</span>)
                </>
              );
            })()}
          </div>
          {/* Weights control panel inside explainer to keep context and avoid overflow */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 10 }}>
            <div style={{ fontSize: 12, color: '#334155', fontWeight: 600 }}>Adjust factor weights</div>
            <button
              onClick={() => setWeightRaw(defaultWeightRaw)}
              style={{
                fontSize: 12,
                padding: '4px 8px',
                borderRadius: 6,
                border: '1px solid #d0e3ff',
                background: '#eef5ff',
                color: '#1e40af',
                cursor: 'pointer'
              }}
            >
              Reset
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginTop: 6 }}>
            {[
              { key: 'rpm', title: 'reviews_per_month', pretty: 'Demand' },
              { key: 'rating', title: 'review_scores_rating', pretty: 'Satisfaction' },
              { key: 'ltm', title: 'number_of_reviews_ltm', pretty: 'Engagement' },
              { key: 'occ', title: 'occupancy_proxy', pretty: 'Tightness' },
              { key: 'sh', title: 'superhost_ratio', pretty: 'Trust' }
            ].map((f: any) => {
              const normPct = Math.round((weightsNormalized as any)[f.key] * 100);
              const raw = (weightRaw as any)[f.key] as number;
              return (
                <div key={f.key} style={{ border: '1px solid #eee', borderRadius: 8, padding: 8, background: '#fafafa' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 700 }} title={(descriptions as any)[f.title] || ''}>{f.pretty}</span>
                    <span style={{ fontSize: 12, color: '#0f172a', fontWeight: 700 }}>{normPct}%</span>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={1}
                    value={raw}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setWeightRaw((prev) => ({ ...prev, [f.key]: v } as any));
                    }}
                    style={{ width: '100%' }}
                  />
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 6 }}>
            Ranges observed in this dataset:
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 6 }}>
            {rangeCards.map((c) => {
              const r = explainer.ranges[c.key];
              const min = c.format(r.min);
              const max = c.format(r.max);
              const isHover = hoveredKey === c.key;
              const prettyNames: Record<string, string> = {
                reviews_per_month: 'Demand',
                review_scores_rating: 'Satisfaction',
                number_of_reviews_ltm: 'Engagement',
                occupancy_proxy: 'Tightness',
                superhost_ratio: 'Trust'
              };
              return (
                <div key={c.key} style={{
                  position: 'relative',
                  flex: '1 1 180px',
                  minWidth: 180,
                  border: `1px solid ${isHover ? '#bcd4ff' : '#eee'}`,
                  borderRadius: 6,
                  background: isHover ? '#f6faff' : '#fafafa',
                  padding: '8px 10px',
                  transform: isHover ? 'translateY(-2px) scale(1.02)' : 'none',
                  boxShadow: isHover ? '0 8px 20px rgba(0,0,0,0.10)' : 'none',
                  transition: 'transform 120ms ease, box-shadow 120ms ease, background 120ms ease, border-color 120ms ease',
                  cursor: 'pointer'
                }} onMouseEnter={(e) => {
                  setHoveredKey(c.key);
                  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
                  setTooltip({ key: c.key, x: rect.left + rect.width / 2, y: rect.top - 8, title: prettyNames[c.key] || c.title, desc: descriptions[c.key] });
                }} onMouseLeave={() => { setHoveredKey(null); setTooltip(null); }}>
                  <div style={{ marginBottom: 4 }}>
                    <span style={{
                      display: 'inline-block',
                      fontSize: 11,
                      fontWeight: 700,
                      color: '#2b5bd7',
                      background: '#eef5ff',
                      border: '1px solid #d0e3ff',
                      borderRadius: 6,
                      padding: '2px 6px'
                    }}>{c.title}</span>
                  </div>
                  <div style={{ fontSize: 13, color: '#222' }}>
                    <span style={{ fontWeight: 700 }}>{min}</span>
                    <span style={{ margin: '0 4px' }}>—</span>
                    <span style={{ fontWeight: 700 }}>{max}</span>
                  </div>
                  <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>{c.hint}</div>
                </div>
              );
            })}
          </div>
          {/* 🆕 刷新全局数据按钮 */}
          {onRefreshRequest && (
            <div style={{ marginTop: 16, paddingTop: 12, borderTop: '2px solid #e5e7eb' }}>
              <button
                onClick={async () => {
                  setIsRefreshing(true);
                  try {
                    await onRefreshRequest();
                  } finally {
                    // 延迟 500ms 关闭 loading，确保用户能看到动画
                    setTimeout(() => setIsRefreshing(false), 500);
                  }
                }}
                disabled={isRefreshing}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  width: '100%',
                  padding: '12px 20px',
                  fontSize: 14,
                  fontWeight: 600,
                  color: isRefreshing ? '#94a3b8' : '#ffffff',
                  background: isRefreshing 
                    ? 'linear-gradient(135deg, #cbd5e1 0%, #94a3b8 100%)'
                    : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  border: 'none',
                  borderRadius: 8,
                  cursor: isRefreshing ? 'not-allowed' : 'pointer',
                  boxShadow: isRefreshing 
                    ? 'none'
                    : '0 4px 12px rgba(102, 126, 234, 0.4)',
                  transition: 'all 0.3s ease',
                  transform: isRefreshing ? 'scale(0.98)' : 'scale(1)',
                  opacity: isRefreshing ? 0.7 : 1
                }}
                onMouseEnter={(e) => {
                  if (!isRefreshing) {
                    e.currentTarget.style.transform = 'scale(1.02)';
                    e.currentTarget.style.boxShadow = '0 6px 20px rgba(102, 126, 234, 0.5)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isRefreshing) {
                    e.currentTarget.style.transform = 'scale(1)';
                    e.currentTarget.style.boxShadow = '0 4px 12px rgba(102, 126, 234, 0.4)';
                  }
                }}
              >
                {isRefreshing ? (
                  <>
                    <svg
                      style={{ animation: 'spin 1s linear infinite' }}
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                    </svg>
                    <span>Refreshing...</span>
                  </>
                ) : (
                  <>
                    <svg
                      width="18"
                      height="18"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <polyline points="23 4 23 10 17 10" />
                      <polyline points="1 20 1 14 7 14" />
                      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
                    </svg>
                    <span>🌍 Refresh with All Berlin Data</span>
                  </>
                )}
              </button>
              <style>
                {`
                  @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                  }
                `}
              </style>
            </div>
          )}
        </div>
      )}
      {renderPortalTooltip()}
    </div>
  );
};

export default LocationPopularity; 