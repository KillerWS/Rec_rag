import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as echarts from 'echarts';
import { fetchTestChartOption } from '../../api/api';
import { EnvironmentOutlined } from '@ant-design/icons';

export interface VqPoint {
  id: string | number;
  title: string;
  price_eur: number;
  review_count: number;
  room_type?: string;
  district?: string;
  neighbourhood?: string;
  lat?: number;
  lng?: number;
  z_price: number;   // x
  z_quality: number; // y (current metric)
  value_score: number; // y - x
}

export interface VqQuadrantSummary {
  count: number;
  top_districts?: string[];
  avg_value_score?: number;
  example_ids?: Array<string | number>;
}

export interface VqModel {
  points: VqPoint[];
  quadrants?: {
    value_picks?: VqQuadrantSummary; // 左上 高评低价
    premium?: VqQuadrantSummary;     // 右上 高评高价
    budget_risk?: VqQuadrantSummary; // 左下 低评低价
    overpriced?: VqQuadrantSummary;  // 右下 低评高价
  };
  trend?: { slope_eur_per_0p1?: number; r?: number; method?: string };
  budget?: { label?: string; z_min?: number; z_max?: number } | null;
  scope?: { level: 'ALL' | 'DISTRICT' | 'NEIGHBOURHOOD'; name?: string | null };
  palette_hint?: { vmin?: number; vmax?: number };
  metric?: 'overall' | 'cleanliness' | 'convenience' | 'accuracy' | 'checkin';
}

export interface ValueQualityQuadrantProps {
  model?: VqModel | null;
  echartsOption?: echarts.EChartsOption | any;
  height?: number;
  onOpenHeatmap?: (payload: any) => void;
  onRequestMapSelect?: (areaName: string | null) => void;
}

const buildMockModel = (): VqModel => {
  const random = (min: number, max: number) => Math.random() * (max - min) + min;
  const points: VqPoint[] = Array.from({ length: 180 }).map((_, i) => {
    const x = random(-2.2, 2.2);
    // introduce slight positive relationship with noise
    const y = x * 0.25 + random(-1.2, 1.2);
    const reviews = Math.max(1, Math.round(Math.abs(random(0, 300))));
    return {
      id: `mock_${i}`,
      title: `Listing #${i + 1}`,
      price_eur: Math.round(random(30, 250)),
      review_count: reviews,
      room_type: ['Entire home/apt', 'Private room', 'Shared room', 'Hotel room'][Math.floor(Math.random() * 4)],
      district: ['Mitte', 'Pankow', 'Neukölln', 'Friedrichshain-Kreuzberg'][Math.floor(Math.random() * 4)],
      neighbourhood: ['Area A', 'Area B', 'Area C', 'Area D'][Math.floor(Math.random() * 4)],
      z_price: x,
      z_quality: y,
      value_score: y - x,
    };
  });
  const summarize = (filter: (p: VqPoint) => boolean): VqQuadrantSummary => {
    const arr = points.filter(filter);
    const avg = arr.length ? arr.reduce((s, p) => s + p.value_score, 0) / arr.length : 0;
    const topDistricts = Array.from(new Map(arr.map(p => [p.district, 1])).keys()).slice(0, 2) as string[];
    return { count: arr.length, avg_value_score: Math.round(avg * 100) / 100, top_districts: topDistricts, example_ids: arr.slice(0, 3).map(p => p.id) };
  };
  return {
    points,
    quadrants: {
      value_picks: summarize(p => p.z_price < 0 && p.z_quality > 0),
      premium: summarize(p => p.z_price >= 0 && p.z_quality > 0),
      budget_risk: summarize(p => p.z_price < 0 && p.z_quality <= 0),
      overpriced: summarize(p => p.z_price >= 0 && p.z_quality <= 0),
    },
    trend: { slope_eur_per_0p1: 18, r: 0.3, method: 'HuberReg' },
    budget: { label: '€80–120', z_min: -0.5, z_max: 0.6 },
    scope: { level: 'ALL', name: null },
    palette_hint: { vmin: -2, vmax: 2 },
    metric: 'overall',
  };
};

const ValueQualityQuadrant: React.FC<ValueQualityQuadrantProps> = ({ model, echartsOption, height = 380, onOpenHeatmap, onRequestMapSelect }) => {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const [dynamicOption, setDynamicOption] = useState<any | null>(echartsOption || null);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [areaName, setAreaName] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem('selected_area') || sessionStorage.getItem('area_name');
    } catch { return null; }
  });
  const [maxPoints, setMaxPoints] = useState<number>(200);
  const [budgetMin, setBudgetMin] = useState<number | null>(null);
  const [budgetMax, setBudgetMax] = useState<number | null>(null);
  const lastAppliedAreaRef = useRef<string | null>(areaName || null);

  const applyFetch = async (override?: { area?: string | null; max_points?: number; price_min?: number | null; price_max?: number | null }) => {
    try {
      setLoadError(null);
      setLoading(true);
      const payload: any = {
        type: 'value_quality_quadrant',
        area: override?.area != null ? override.area : (areaName || undefined),
        max_points: override?.max_points != null ? override.max_points : maxPoints,
      };
      const pmin = override?.price_min != null ? override.price_min : budgetMin;
      const pmax = override?.price_max != null ? override.price_max : budgetMax;
      if (pmin != null) payload.price_min = pmin;
      if (pmax != null) payload.price_max = pmax;
      const res: any = await fetchTestChartOption(payload);
      const opt = res?.echarts_option || res?.option || res;
      if (!opt) throw new Error('No chart option returned');
      // Merge top-level metadata like trend into option for consistent access in tooltips
      try {
        if (res?.trend && typeof opt === 'object') (opt as any).trend = res.trend;
        if (res?.meta && typeof opt === 'object') (opt as any).meta = { ...(opt as any).meta, ...res.meta };
        if (res?.insights && typeof opt === 'object') (opt as any).insights = { ...(opt as any).insights, ...res.insights };
      } catch {}
      setDynamicOption(opt);
    } catch (e: any) {
      setLoadError(e?.message || 'Failed to load chart');
    } finally {
      setLoading(false);
    }
  };

  const dataModel = useMemo<VqModel>(() => {
    if (echartsOption) return {
      points: [],
      metric: 'overall',
    } as VqModel; // placeholder when using raw option
    if (model && Array.isArray(model.points) && model.points.length > 0) return model;
    return buildMockModel();
  }, [model, echartsOption]);

  useEffect(() => {
    setDynamicOption(echartsOption || null);
  }, [echartsOption]);

  // Listen to map/decision events to update areaName
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      try {
        if (!e || (e.key !== 'area_name' && e.key !== 'selected_area' && e.key !== 'district' && e.key !== 'neighbourhood')) return;
        const val = e.newValue || e.oldValue || '';
        const area = val || sessionStorage.getItem('area_name') || sessionStorage.getItem('selected_area') || sessionStorage.getItem('district') || sessionStorage.getItem('neighbourhood');
        if (area) setAreaName(area);
      } catch {}
    };
    const onAreaEvent = (evt: Event) => {
      try {
        const anyEvt: any = evt as any;
        const d = anyEvt?.detail;
        const cand = d?.area || d?.area_name || d?.district || d?.neighbourhood || d;
        if (cand) setAreaName(String(cand));
      } catch {}
    };
    window.addEventListener('storage', onStorage);
    const names = ['map:areaSelected', 'map:selectedArea', 'district:selected', 'neighbourhood:selected', 'area:selected'];
    names.forEach((n) => window.addEventListener(n, onAreaEvent as EventListener));
    return () => {
      window.removeEventListener('storage', onStorage);
      names.forEach((n) => window.removeEventListener(n, onAreaEvent as EventListener));
    };
  }, []);

  // Auto-fetch on area change (from map selection)
  useEffect(() => {
    if (areaName && areaName !== lastAppliedAreaRef.current) {
      lastAppliedAreaRef.current = areaName;
      applyFetch({ area: areaName });
    }
  }, [areaName]);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstanceRef.current) chartInstanceRef.current = echarts.init(chartRef.current);
    const chart = chartInstanceRef.current as echarts.ECharts;

    // If backend provided full echarts option, use it directly
    const activeOption = dynamicOption;
    if (activeOption) {
      try {
        // Enhance backend option: axes styling, equal-value dashed line, trend line, rich tooltip
        const opt = { ...(activeOption as any) };
        // Axis enhancements (names with arrows if absent)
        const defaultXName = '← cheaper | pricier →';
        const defaultYName = '↑ higher rating | lower ↓';
        opt.xAxis = {
          ...(opt.xAxis || {}),
          name: (opt.xAxis && opt.xAxis.name) ? opt.xAxis.name : defaultXName,
          nameTextStyle: { color: '#0ea5e9', fontWeight: 'bold' },
          axisLine: { ...(opt.xAxis?.axisLine || {}), onZero: true, lineStyle: { color: '#94a3b8' } },
        };
        opt.yAxis = {
          ...(opt.yAxis || {}),
          name: (opt.yAxis && opt.yAxis.name) ? opt.yAxis.name : defaultYName,
          nameTextStyle: { color: '#22c55e', fontWeight: 'bold' },
          axisLine: { ...(opt.yAxis?.axisLine || {}), onZero: true, lineStyle: { color: '#94a3b8' } },
        };
        // Prepare ranges centered at origin and series accessor
        const seriesArr: any[] = Array.isArray(opt.series) ? opt.series : [];
        const scatter = seriesArr.find((s: any) => String(s?.type).toLowerCase() === 'scatter');
        const values: number[][] = Array.isArray(scatter?.data)
          ? scatter.data
              .map((d: any) => (Array.isArray(d?.value) ? d.value : (Array.isArray(d) ? d : d?.val || [])))
              .filter((v: any) => Array.isArray(v) && v.length >= 2)
          : [];
        const xs = values.map(v => Number(v[0])).filter((n) => Number.isFinite(n));
        const ys = values.map(v => Number(v[1])).filter((n) => Number.isFinite(n));
        const absMax = (arr: number[], fallback: number) => arr.length ? Math.max(...arr.map(v => Math.abs(v))) : fallback;
        const xAbsMax = absMax(xs, 2.5) * 1.05;
        const yAbsMax = absMax(ys, 2.5) * 1.05;
        const xMin = -xAbsMax, xMax = xAbsMax;
        const yMin = -yAbsMax, yMax = yAbsMax;
        opt.xAxis = { ...(opt.xAxis || {}), min: xMin, max: xMax, splitLine: { ...(opt.xAxis?.splitLine || {}), show: true, lineStyle: { type: 'dashed', color: '#e5e7eb' } } };
        opt.yAxis = { ...(opt.yAxis || {}), min: yMin, max: yMax, splitLine: { ...(opt.yAxis?.splitLine || {}), show: true, lineStyle: { type: 'dashed', color: '#e5e7eb' } } };
        if (scatter) {
          scatter.markLine = {
            symbol: 'none',
            lineStyle: { color: '#9ca3af', type: 'solid' },
            data: [ { xAxis: 0 }, { yAxis: 0 } ]
          };
        }

        // Lines across full width
        const extraSeries: any[] = [];
        const hasLine = (name: string) => Array.isArray(opt.series) && opt.series.some((s: any) => String(s?.name).toLowerCase() === name);
        if (!hasLine('equal_value')) {
          const N = 64; const data: number[][] = [];
          for (let i = 0; i <= N; i++) { const t = i / N; const x = xMin + (xMax - xMin) * t; data.push([x, x]); }
          extraSeries.push({
            type: 'line', name: 'equal_value', data, showSymbol: false,
            lineStyle: { type: 'dashed', color: '#94a3b8' }, z: 2,
            emphasis: { focus: 'series', lineStyle: { width: 3, type: 'dashed' } },
            tooltip: {
              trigger: 'item',
              triggerOn: 'mousemove|click',
              formatter: () => [
                '<div style="font-weight:700">⚖️ Equal-Value Line</div>',
                '<div style="color:#9ca3af">──────────────────────</div>',
                'This grey dashed line shows the <i>ideal balance</i><br/>where price and quality increase equally.',
                '',
                '• Points above-left → Better value (high rating for lower price)',
                '• Points below-right → Overpriced (low rating for higher price)',
                '',
                '💡 The closer to this line, the more “fairly priced” a listing is.'
              ].join('<br/>')
            },
            markPoint: { data: [{ coord: [2.2,2.2], value: 'Equal-Value Line', label: { color: '#64748b', fontWeight: 'bold' } }] }
          });
        }
        if (!hasLine('trend')) {
          const trendMeta = (opt as any)?.trend || {};
          const slope = (typeof trendMeta.slope_z === 'number') ? trendMeta.slope_z : 0.28;
          const intercept = (typeof trendMeta.intercept_z === 'number') ? trendMeta.intercept_z : 0.0;
          const slopeEur = (typeof trendMeta.slope_eur_per_0p1 === 'number') ? trendMeta.slope_eur_per_0p1 : null;
          const rVal = (typeof trendMeta.r === 'number') ? trendMeta.r : 0.31;
          const strength = rVal >= 0.5 ? 'strong' : (rVal >= 0.2 ? 'medium' : 'weak');
          const N = 64; const data: number[][] = [];
          for (let i = 0; i <= N; i++) { const t = i / N; const x = xMin + (xMax - xMin) * t; const y = intercept + slope * x; data.push([x, y]); }
          const compHint = (typeof trendMeta.slope_z === 'number' && trendMeta.slope_z < 1)
            ? 'black line (trend) below → Market slightly overpriced'
            : (typeof trendMeta.slope_z === 'number' && trendMeta.slope_z > 1)
              ? 'black line (trend) above → Better-than-ideal value'
              : 'black line (trend)';
          const slopeSummary = (typeof trendMeta.slope_z === 'number')
            ? (trendMeta.slope_z < 1
                ? 'Price increases slower than quality – good for value seekers.'
                : (trendMeta.slope_z > 1 ? 'Price increases faster than quality – market overpricing.' : ''))
            : '';
          extraSeries.push({
            type: 'line', name: 'trend', data, showSymbol: false,
            lineStyle: { type: 'solid', color: '#111827' }, z: 2,
            emphasis: { focus: 'series', lineStyle: { width: 3 } },
            tooltip: {
              trigger: 'item',
              triggerOn: 'mousemove|click',
              formatter: () => [
                '<div style="font-weight:700">📈 Market Trend Line</div>',
                '<div style="color:#9ca3af">──────────────────────</div>',
                'This black line shows how price <i>actually</i> rises with ratings <br/>based on current listings in this area.',
                '',
                (slopeEur != null ? `• Each 0.1 rating increase → about +€${(Math.round(slopeEur * 10) / 10)} on average` : ''),
                (Number.isFinite(rVal) ? `• Correlation strength: ${strength} (r = ${(Math.round(rVal * 100) / 100)})` : ''),
                '',
                '💬 The market is slightly overpriced compared to the ideal balance.',
                '',
                'grey dashed line ↑',
                compHint,
                slopeSummary ? `<div style="margin-top:6px">${slopeSummary}</div>` : ''
              ].filter(Boolean).join('<br/>')
            },
            markPoint: { data: [{ coord: [1.8,1.8*slope+intercept], value: `Trend: +€${(Math.round(slopeEur))} / 0.1 rating`, label: { color: '#111827' } }] }
          });
        }
        if (extraSeries.length > 0) opt.series = [...(opt.series || []), ...extraSeries];
        // Tooltip rich (category phrasing)
        opt.tooltip = {
          ...(opt.tooltip || {}),
          trigger: 'item', confine: true,
          formatter: (p: any) => {
            const nameRaw = String(p?.seriesName || '');
            const seriesName = nameRaw.toLowerCase();
            const seriesType = String(p?.seriesType || '').toLowerCase();
            const asNum = (v: any) => { const n = Number(v); return Number.isFinite(n) ? n : null; };
            const isEqualByData = () => {
              const v: any = (p?.value ?? (p?.data && (p.data.value || p.data.val)));
              if (!Array.isArray(v) || v.length < 2) return false;
              const x = asNum(v[0]); const y = asNum(v[1]);
              if (x == null || y == null) return false;
              return Math.abs(y - x) < 1e-6; // y≈x → equal-value
            };
            const isEqualSeries = seriesName.includes('equal') || (seriesType === 'line' && isEqualByData());
            const isTrendSeries = seriesName.includes('trend') || (seriesType === 'line' && !isEqualByData());
            if (isEqualSeries) {
              return [
                '<div style="font-weight:700">⚖️ Equal-Value Line</div>',
                '<div style="color:#9ca3af">──────────────────────</div>',
                'This grey dashed line shows the <i>ideal balance</i><br/>where price and quality increase equally.',
                '',
                '• Points above-left → Better value (high rating for lower price)',
                '• Points below-right → Overpriced (low rating for higher price)',
                '',
                '💡 The closer to this line, the more “fairly priced” a listing is.'
              ].join('<br/>');
            }
            if (isTrendSeries) {
              // Resolve trend from multiple sources
              const sArr: any[] = Array.isArray((opt as any)?.series) ? (opt as any).series : [];
              const seriesTrend = (sArr.find((s: any) => String(s?.name || '').toLowerCase().includes('trend')) as any) || {};
              const trendMeta = (opt as any)?.trend
                ?? (opt as any)?.meta?.trend
                ?? (opt as any)?.insights?.trend
                ?? (seriesTrend?.trend)
                ?? {};
              const slopeZ = asNum(trendMeta.slope_z);
              // slope per 0.1 rating
              let slopeEur: number | null = asNum(trendMeta.slope_eur_per_0p1);
              if (slopeEur == null) {
                const per1 = asNum(trendMeta.slope_eur_per_1);
                if (per1 != null) slopeEur = per1 * 0.1;
              }
              if (slopeEur == null) {
                const sz = asNum(trendMeta.slope_z);
                const stdPrice = asNum(trendMeta.std_price_eur);
                const stdRating = asNum(trendMeta.std_rating_metric);
                if (sz != null && stdPrice != null && stdRating != null && stdRating !== 0) {
                  slopeEur = sz * (stdPrice / stdRating) * 0.1;
                }
              }
              const rVal = asNum(trendMeta.r);
              const absR = rVal == null ? null : Math.abs(rVal);
              const strengthLabel = (absR == null) ? null : (
                absR < 0.2 ? 'weak' : (absR < 0.4 ? 'moderate' : (absR < 0.6 ? 'medium–strong' : 'strong'))
              );
              const strengthColor = strengthLabel === 'weak' ? '#6b7280' : (strengthLabel === 'moderate' ? '#f59e0b' : (strengthLabel === 'medium–strong' ? '#2563eb' : '#16a34a'));
              const slopeStrong = (slopeEur != null) ? `<b style="color:#0ea5e9">€${(Math.round(slopeEur * 10) / 10)}</b>` : '';
              const strengthStrong = (strengthLabel && rVal != null)
                ? `<b style="color:${strengthColor}">${strengthLabel}</b> (r = ${(Math.round(rVal * 100) / 100)})`
                : '';
              const slopeSummary = (slopeZ != null)
                ? (slopeZ < 1
                    ? 'Price rises slower than quality — good for value seekers.'
                    : (slopeZ > 1 ? 'Price rises faster than quality — signs of overpricing.' : ''))
                : '';
              const compHint = (slopeZ != null && slopeZ < 1)
                ? 'black line (trend) below → Market slightly overpriced'
                : (slopeZ != null && slopeZ > 1)
                  ? 'black line (trend) above → Better-than-ideal value'
                  : 'black line (trend)';
              return [
                '<div style="font-weight:700">📈 Market Trend Line</div>',
                '<div style="color:#9ca3af">──────────────────────</div>',
                'This black line shows how price <i>actually</i> rises with ratings <br/>based on current listings in this area.',
                '',
                // remove slope bullet per request
                (strengthStrong ? `• Correlation strength: ${strengthStrong}` : ''),
                '',
                '💬 The market is slightly overpriced compared to the ideal balance.',
                '',
                'grey dashed line ↑',
                compHint,
                slopeSummary ? `<div style="margin-top:6px">${slopeSummary}</div>` : ''
              ].filter(Boolean).join('<br/>');
            }
            // scatter point tooltip (unchanged)
            const d = p?.data || {};
            const name = d?.name || p?.name || '';
            const price = d?.price ?? d?.price_eur ?? (Array.isArray(p?.value) ? p.value[2] : undefined);
            const premiumPct = d?.premium_pct;
            const reviews = d?.reviews ?? d?.review_count;
            const rt = d?.room_type;
            const dist = d?.district ?? d?.neighbourhood_group;
            const nb = d?.neighbourhood ?? d?.neighborhood ?? d?.area_name;
            const valArr = d?.value || p?.value || [];
            const vq = { value: asNum(valArr?.[0]) ?? NaN, quality: asNum(valArr?.[1]) ?? NaN };
            // Price text
            let priceHint = '';
            if (typeof premiumPct === 'number') {
              if (premiumPct <= -5) priceHint = ' (below average for similar homes)';
              else if (premiumPct >= 5) priceHint = ' (above average for similar homes)';
              else priceHint = ' (around the average)';
            }
            const ratingStr = Number.isFinite(vq.quality) ? `${Math.round((vq.quality + Number.EPSILON) * 10) / 10} / 5` : '–';
            let ratingHint = '';
            if (Number.isFinite(vq.quality)) {
              if ((vq.quality as number) >= 4.6) ratingHint = ' (higher than most in this area)';
              else if ((vq.quality as number) >= 4.0) ratingHint = ' (typical for this area)';
              else ratingHint = ' (lower than many nearby)';
            }
            const valueCategory = (() => {
              if (typeof premiumPct === 'number' && premiumPct <= -10 && (vq.quality as number) >= 4.4) return { tag: '💎 High Value', color: '#10b981', desc: 'High – great quality for the price' };
              if (typeof premiumPct === 'number' && premiumPct >= 10 && (vq.quality as number) < 4.2) return { tag: '🚫 Low Value', color: '#ef4444', desc: 'Low – quality may not justify the price' };
              return { tag: '⚖️ Average Value', color: '#9ca3af', desc: 'Average – roughly in line with peers' };
            })();
            return [
              `<div style="font-weight:700;font-size:13px">🏠 ${name}</div>`,
              `<div><b>💰 Price:</b> €${price ?? '–'}${priceHint}</div>`,
              `<div><b>⭐ Rating:</b> ${ratingStr}${ratingHint}</div>`,
              `<div><b style="color:${valueCategory.color}">${valueCategory.tag}:</b> ${valueCategory.desc}</div>`,
              `<div><b>🏛️ District:</b> ${dist || '–'}</div>`,
              `<div><b>🏘️ Neighbourhood:</b> ${nb || '–'}</div>`,
              rt ? `<div><b>🛏️ Room type:</b> ${rt}</div>` : '',
              `<div><b>💬 Reviews:</b> ${reviews ?? '–'}</div>`
            ].join('');
          }
        } as any;

        // Color-code points by value category
        seriesArr.forEach((s: any) => {
          if (String(s?.type).toLowerCase() !== 'scatter') return;
          if (!Array.isArray(s.data)) return;
          s.data = s.data.map((d: any) => {
            const premiumPct = d?.premium_pct;
            const valArr = d?.value || d?.val || []; // v[0]=value proxy, v[1]=quality
            const quality = Number(valArr?.[1]);
            let color = '#9ca3af';
            if (typeof premiumPct === 'number' && premiumPct <= -10 && quality >= 4.4) color = '#10b981';
            else if (typeof premiumPct === 'number' && premiumPct >= 10 && quality < 4.2) color = '#ef4444';
            return { ...d, itemStyle: { ...(d?.itemStyle || {}), color } };
          });
        });

        chart.clear();
        chart.setOption(opt as any, true);
        const ro = new ResizeObserver(() => { chart.resize(); });
        ro.observe(chartRef.current!);
        return () => {
          ro.disconnect();
          chart.dispose();
          chartInstanceRef.current = null;
        };
      } catch {}
    }

    const points = dataModel.points || [];
    const palette = dataModel.palette_hint || { vmin: -2, vmax: 2 };

    const scatterData = points.map((p) => ({
      value: [p.z_price, p.z_quality, p.value_score, p.review_count],
      id: p.id,
      name: p.title,
      itemStyle: { opacity: Math.max(0.25, Math.min(0.9, (Math.log10((p.review_count || 1) + 1) / 3))) }
    }));

    // Lines: y=x (equal value) and robust trend line (approximate; use slope r as hint if given)
    const lineX = -2.5, lineX2 = 2.5;
    const equalLine = [[lineX, lineX], [lineX2, lineX2]];
    const slope = (dataModel.trend?.r != null && Math.abs(dataModel.trend.r || 0) > 0.05) ? 0.3 : 0.2;
    const trendLine = [[lineX, lineX * slope], [lineX2, lineX2 * slope]];

    const option: echarts.EChartsOption = {
      title: { text: 'Price × Quality Quadrant', left: 'center' },
      grid: { left: 50, right: 20, top: 50, bottom: 50 },
      tooltip: {
        trigger: 'item',
        confine: true,
        formatter: (p: any) => {
          const d = points.find(pt => String(pt.id) === String(p?.data?.id));
          if (!d) return '';
          const metric = dataModel.metric || 'overall';
          return [
            `<div><strong>${d.title}</strong></div>`,
            `price: €${d.price_eur} · reviews: ${d.review_count}`,
            `${metric} rating (z): ${d.z_quality.toFixed(2)} · price (z): ${d.z_price.toFixed(2)}`,
            `value score: ${(d.value_score).toFixed(2)}`,
            `<div><b>🏛️ District:</b> ${d.district || '–'}</div>`,
            `<div><b>🏘️ Neighbourhood:</b> ${d.neighbourhood || '–'}</div>`
          ].join('<br/>');
        }
      },
      xAxis: {
        type: 'value',
        name: '← cheaper | pricier →',
        nameLocation: 'middle',
        nameGap: 28,
        axisLine: { onZero: true },
        splitLine: { lineStyle: { type: 'dashed' } },
        min: -2.5,
        max: 2.5
      },
      yAxis: {
        type: 'value',
        name: '↑ higher rating | lower ↓',
        nameLocation: 'middle',
        nameGap: 36,
        axisLine: { onZero: true },
        splitLine: { lineStyle: { type: 'dashed' } },
        min: -2.5,
        max: 2.5
      },
      visualMap: {
        show: false,
        min: palette.vmin ?? -2,
        max: palette.vmax ?? 2,
        dimension: 2, // value_score
        inRange: { color: ['#e15759', '#cccccc', '#4e79a7'] }
      },
      series: [
        // Budget band (optional)
        ...(dataModel?.budget?.z_min != null && dataModel?.budget?.z_max != null ? [{
          type: 'custom',
          name: 'budget_band',
          renderItem: (_params: any, api: any) => {
            const x1 = api.coord([dataModel.budget!.z_min, -2.6]);
            const x2 = api.coord([dataModel.budget!.z_max, 2.6]);
            const yTop = api.coord([dataModel.budget!.z_min, 2.6]);
            const size = [x2[0] - x1[0], yTop[1] - x1[1]];
            return {
              type: 'rect', shape: { x: x1[0], y: x1[1], width: size[0], height: size[1] },
              style: { fill: 'rgba(16, 185, 129, 0.10)' }
            } as any;
          },
          silent: true,
          z: 0
        }] : []),
        // Equal value line y=x (with its own tooltip and emphasis)
        { 
          type: 'line', name: 'equal_value', data: equalLine, showSymbol: false, 
          lineStyle: { type: 'dashed', color: '#94a3b8' }, z: 2,
          emphasis: { focus: 'series', lineStyle: { width: 3, type: 'dashed' } },
          tooltip: {
            trigger: 'item',
            triggerOn: 'mousemove|click',
            formatter: () => [
              '<div style="font-weight:700">⚖️ Equal-Value Line</div>',
              '<div style="color:#9ca3af">──────────────────────</div>',
              'This grey dashed line shows the <i>ideal balance</i>',
              'where price and quality increase equally.',
              '',
              '• Points above-left → Better value (high rating for lower price)',
              '• Points below-right → Overpriced (low rating for higher price)',
              '',
              '💡 The closer to this line, the more “fairly priced” a listing is.'
            ].join('<br/>')
          }
        },
        // Trend line with enhanced tooltip & emphasis
        { 
          type: 'line', name: 'trend', data: trendLine, showSymbol: false, 
          lineStyle: { type: 'solid', color: '#111827' }, z: 2,
          emphasis: { focus: 'series', lineStyle: { width: 3 } },
          tooltip: {
            trigger: 'item',
            triggerOn: 'mousemove|click',
            formatter: () => {
              const slopeZ = slope; // approximate in fallback path
              // prefer slope_eur_per_0p1; fallback to slope_eur_per_1*0.1; then slope_z*(std_price/std_rating)*0.1 if available
              const t: any = dataModel?.trend || {};
              let slopeEur: number | null = (typeof t.slope_eur_per_0p1 === 'number') ? t.slope_eur_per_0p1 : null;
              if (slopeEur == null && typeof t.slope_eur_per_1 === 'number') slopeEur = t.slope_eur_per_1 * 0.1;
              if (slopeEur == null && typeof t.slope_z === 'number') {
                const stdPrice = (typeof t.std_price_eur === 'number') ? t.std_price_eur : null;
                const stdRating = (typeof t.std_rating_metric === 'number') ? t.std_rating_metric : null;
                if (stdPrice != null && stdRating != null && stdRating !== 0) slopeEur = t.slope_z * (stdPrice / stdRating) * 0.1;
              }
              const rVal = (typeof t.r === 'number') ? t.r : null;
              const absR = (typeof rVal === 'number') ? Math.abs(rVal) : null;
              const strengthLabel = (absR == null) ? null : (
                absR < 0.2 ? 'weak' : (absR < 0.4 ? 'moderate' : (absR < 0.6 ? 'medium–strong' : 'strong'))
              );
              const strengthColor = strengthLabel === 'weak' ? '#6b7280' : (strengthLabel === 'moderate' ? '#f59e0b' : (strengthLabel === 'medium–strong' ? '#2563eb' : '#16a34a'));
              const strengthStrong = (strengthLabel && typeof rVal === 'number')
                ? `<b style="color:${strengthColor}">${strengthLabel}</b> (r = ${(Math.round(rVal * 100) / 100)})`
                : '';
              const slopeSummary = (typeof slopeZ === 'number')
                ? (slopeZ < 1
                    ? 'Price rises slower than quality — good for value seekers.'
                    : (slopeZ > 1 ? 'Price rises faster than quality — signs of overpricing.' : ''))
                : '';
              const compHint = (typeof slopeZ === 'number' && slopeZ < 1)
                ? 'black line (trend) below → Market slightly overpriced'
                : (typeof slopeZ === 'number' && slopeZ > 1)
                  ? 'black line (trend) above → Better-than-ideal value'
                  : 'black line (trend)';
              return [
                '<div style="font-weight:700">📈 Market Trend Line</div>',
                '<div style="color:#9ca3af">──────────────────────</div>',
                'This black line shows how price <i>actually</i> rises with ratings <br/>based on current listings in this area.',
                '',
                // remove slope bullet per request
                (strengthStrong ? `• Correlation strength: ${strengthStrong}` : ''),
                '',
                '💬 The market is slightly overpriced compared to the ideal balance.',
                '',
                'grey dashed line ↑',
                compHint,
                slopeSummary ? `<div style="margin-top:6px">${slopeSummary}</div>` : ''
              ].filter(Boolean).join('<br/>');
            }
          }
        },
        // Scatter
        {
          type: 'scatter',
          data: scatterData,
          symbolSize: (val: any[]) => {
            const reviews = Number(val?.[3] || 0);
            // size between 4 and 18
            return Math.max(4, Math.min(18, Math.sqrt(reviews) * 0.9));
          },
          emphasis: { focus: 'series' },
          z: 3
        }
      ] as any
    };

    chart.clear();
    chart.setOption(option);

    chart.off('click');
    chart.on('click', (_params: any) => {
      try {
        const lid = (_params as any)?.data?.id;
        if (lid != null && onOpenHeatmap) onOpenHeatmap({ listing_id: lid });
      } catch {}
    });

    const ro = new ResizeObserver(() => { chart.resize(); });
    ro.observe(chartRef.current!);
    return () => {
      ro.disconnect();
      chart.dispose();
      chartInstanceRef.current = null;
    };
  }, [dataModel, onOpenHeatmap, dynamicOption]);

  return (
    <div style={{ width: '100%' }}>
      {/* Inline filter bar (adapted from Reviews scope chips) */}
      <div className="mb-2">
        <div className="w-full bg-gray-50 border border-gray-200 rounded-md p-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-gray-700 font-medium">Scope</span>
          <div className="inline-flex items-center gap-2 bg-gray-100 border border-gray-300 text-gray-700 rounded px-2 py-1">
            <span>{areaName || 'All Berlin'}</span>
            <button
              className="px-2 py-0.5 border rounded bg-white hover:bg-gray-100"
              title="Select on map"
              onClick={() => {
                if (onRequestMapSelect) onRequestMapSelect(areaName || 'ALL');
                else { try { window.dispatchEvent(new CustomEvent('map:open', { detail: { area: areaName || 'ALL' } })); } catch {} }
              }}
            >
              <span className="inline-flex items-center gap-1"><EnvironmentOutlined /> Map</span>
            </button>
          </div>
          <div className="inline-flex items-center gap-1 bg-amber-50 border border-amber-200 text-amber-700 rounded px-2 py-1">
            <span>Budget</span>
            <input
              type="number"
              placeholder="min"
              className="w-20 px-2 py-0.5 border rounded bg-white"
              value={budgetMin ?? ''}
              onChange={(e) => setBudgetMin(e.target.value === '' ? null : Math.max(0, Number(e.target.value)))}
            />
            <span>–</span>
            <input
              type="number"
              placeholder="max"
              className="w-20 px-2 py-0.5 border rounded bg-white"
              value={budgetMax ?? ''}
              onChange={(e) => setBudgetMax(e.target.value === '' ? null : Math.max(0, Number(e.target.value)))}
            />
          </div>
          <div className="inline-flex items-center gap-1 bg-blue-50 border border-blue-200 text-blue-700 rounded px-2 py-1">
            <span>Max points</span>
            <input
              type="number"
              min={50}
              max={2000}
              step={10}
              className="w-20 px-2 py-0.5 border rounded bg-white text-gray-700"
              value={maxPoints}
              onChange={(e) => setMaxPoints(Math.max(50, Math.min(2000, Number(e.target.value) || 200)))}
            />
          </div>
          {/* Use Decision Scope */}
          <button
            className="px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700"
            title="Pull current filters from your Decision Card (Location/Budget)"
            onClick={() => {
              try {
                const w: any = (window as any) || {};
                // Merge props array with window.selectedDimensions (window wins)
                const dims: Array<{ key: string; value: any }> = Array.isArray(w.selectedDimensions) ? w.selectedDimensions : [];
                const mergedByKey = new Map<string, { key: string; value: any }>();
                dims.forEach((d) => mergedByKey.set(String(d?.key || '').toLowerCase(), d));
                const mergedList = Array.from(mergedByKey.values());
                const scope: any = {};
                const roomTypes: string[] = [];
                mergedList.forEach((dim) => {
                  const key = String(dim?.key || '').toLowerCase();
                  const rawVal = dim?.value;
                  const val = rawVal == null ? '' : String(rawVal);
                  if (key === 'location' || key === 'area' || key === 'preferred area') {
                    if (val && val.toLowerCase() !== 'explore on map' && val.toLowerCase() !== 'all') {
                      scope.area_name = val;
                    }
                  } else if (key === 'price' || key === 'budget' || key === 'budget range') {
                    const nums = (val.match(/\d+/g) || []).map((n: string) => Number(n));
                    if (nums.length >= 1) scope.price_min = nums[0];
                    if (nums.length >= 2) scope.price_max = nums[1];
                  } else if (key === 'room type') {
                    if (val.includes(',')) {
                      val.split(',').map((s) => s.trim()).filter(Boolean).forEach((t) => roomTypes.push(t));
                    } else if (val) {
                      roomTypes.push(val);
                    }
                  }
                });
                if (scope.area_name) setAreaName(scope.area_name);
                if (scope.price_min != null) setBudgetMin(scope.price_min);
                if (scope.price_max != null) setBudgetMax(scope.price_max);
              } catch {}
            }}
          >
            Use Decision Scope
          </button>
          {/* Send to Decision Card */}
          <button
            className="px-3 py-1 rounded bg-green-600 text-white hover:bg-green-700"
            title="Push current filters (Location/Budget) to Decision Card"
            onClick={() => {
              try {
                const dims: Array<{ key: string; value: string }> = [];
                if (areaName && areaName.trim()) dims.push({ key: 'Location', value: areaName.trim() });
                if (budgetMin != null || budgetMax != null) {
                  const minLabel = budgetMin != null ? String(budgetMin) : '';
                  const maxLabel = budgetMax != null ? String(budgetMax) : '';
                  dims.push({ key: 'Budget', value: `${minLabel}-${maxLabel}` });
                }
                (window as any).selectedDimensions = dims;
                window.dispatchEvent(new CustomEvent('decisioncard:setDimensions', { detail: { dimensions: dims } }));
              } catch {}
            }}
          >
            Send to Decision Card
          </button>
          <div className="ml-auto">
            <button
              className="px-3 py-1 border rounded bg-blue-50 text-blue-700 hover:bg-blue-100"
              onClick={() => applyFetch()}
            >
              Apply
            </button>
          </div>
        </div>
        {loadError && (
          <div className="mt-2 p-2 rounded bg-red-50 border border-red-200 text-xs text-red-600">{loadError}</div>
        )}
      </div>

      <div style={{ position: 'relative' }}>
        {loading && (
          <div className="absolute inset-0 bg-white/70 flex items-center justify-center z-10">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent"></div>
          </div>
        )}
        <div ref={chartRef} style={{ width: '100%', height }} />
      </div>

      {/* Bottom legend and insight (two lines) */}
      <div className="mt-3 border-t border-gray-200 pt-2 text-xs text-gray-700">
        <div>🧭 Each dot represents a listing. Left = cheaper, up = higher rated.</div>
        <InsightLine dynamicOption={dynamicOption} areaName={areaName} />
      </div>
    </div>
  );
};

export default ValueQualityQuadrant;


// Lightweight insight renderer (extracts backend-provided insights or synthesizes a fallback)
const InsightLine = ({ dynamicOption, areaName }: { dynamicOption: any; areaName: string | null }) => {
  try {
    const opt: any = dynamicOption || {};
    const direct = opt?.insights || opt?.insight || opt?.meta?.insights || opt?.meta?.insight;
    const text = typeof direct === 'string' ? direct.trim() : '';
    if (text) return <div className="text-gray-700 mt-1">💬 {text}</div>;

    const trend = opt?.trend || {};
    const r = typeof trend.r === 'number' ? trend.r : null;
    const slopeEur = typeof trend.slope_eur_per_0p1 === 'number' ? trend.slope_eur_per_0p1 : null;
    const absR = r == null ? null : Math.abs(r);
    const strength = absR == null ? null : (absR < 0.2 ? 'weak' : (absR < 0.4 ? 'moderate' : (absR < 0.6 ? 'medium–strong' : 'strong')));
    const strengthColor = strength === 'weak' ? '#6b7280' : (strength === 'moderate' ? '#f59e0b' : (strength === 'medium–strong' ? '#2563eb' : '#16a34a'));

    if (areaName) {
      if (slopeEur != null && r != null) return (
        <div className="text-gray-700 mt-1">
          💬 In {areaName}, higher ratings come with higher prices (
          <b style={{ color: '#0ea5e9' }}>+€{Math.round(slopeEur)}</b> per 0.1 rating), correlation{' '}
          <b style={{ color: strengthColor }}>{strength}</b> (r = {Math.round(r * 100) / 100}).
        </div>
      );
      if (r != null) return (
        <div className="text-gray-700 mt-1">
          💬 In {areaName}, prices{' '}
          <b style={{ color: strengthColor }}>{strength}</b> (r = {Math.round(r * 100) / 100}).
        </div>
      );
    } else {
      if (r != null) return (
        <div className="text-gray-700 mt-1">
          💬 Citywide, prices{' '}
          <b style={{ color: strengthColor }}>{strength}</b> (r = {Math.round(r * 100) / 100}).
        </div>
      );
    }
  } catch {}
  return <div className="text-gray-500 mt-1">💬 Insight will appear once data loads.</div>;
};

