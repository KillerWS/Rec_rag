import React, { useEffect, useMemo, useRef } from "react";
import * as echarts from "echarts";

type Budget = { min: number | null; max: number | null };

// Minimal shape expected from backend StratificationPayload
// Each item should at least carry five-number summary and sample size
interface StratificationPoint {
  room_type: string;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  p95?: number; // optional
  n?: number; // sample size
}

interface StratificationPayload {
  items?: StratificationPoint[];
  data?: StratificationPoint[]; // tolerate alternate field name
}

interface RoomTypeBoxplotProps {
  data: StratificationPayload | StratificationPoint[];
  budget?: Budget;
  onOpenHeatmap: (payload: { room_type: string }) => void;
  height?: number;
}

const ORDER = [
  "Shared room",
  "Private room",
  "Entire home/apt",
  "Hotel room"
];

const RoomTypeBoxplot: React.FC<RoomTypeBoxplotProps> = ({ data, budget, onOpenHeatmap, height = 340 }) => {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  const rows = useMemo<StratificationPoint[]>(() => {
    const arr: StratificationPoint[] = Array.isArray(data)
      ? (data as StratificationPoint[])
      : ((data as StratificationPayload)?.items || (data as StratificationPayload)?.data || []);
    // Normalize and sort by defined order
    const mapByType = new Map<string, StratificationPoint>();
    arr.forEach((it) => {
      if (!it || !it.room_type) return;
      mapByType.set(it.room_type, it);
    });
    const ordered: StratificationPoint[] = [];
    ORDER.forEach((name) => { const r = mapByType.get(name); if (r) ordered.push(r); });
    // append any remaining unknown types
    arr.forEach((it) => { if (!ORDER.includes(it.room_type)) ordered.push(it); });
    return ordered;
  }, [data]);

  const categories = rows.map((r) => r.room_type);
  const lowSampleFlags = rows.map((r) => (r?.n != null && r.n < 20));
  const boxData = rows.map((r) => [r.min, r.q1, r.median, r.q3, r.max]);
  const listings = rows.map((r) => r?.n ?? null);

  const yMax = useMemo(() => {
    // Prefer p95 if present; else fall back to max over 'max'
    const p95s = rows.map((r) => (typeof r.p95 === 'number' ? r.p95 as number : null)).filter((v) => v != null) as number[];
    if (p95s.length > 0) return Math.max(...p95s) * 1.05;
    const maxima = rows.map((r) => r.max).filter((v) => typeof v === 'number');
    return maxima.length ? Math.max(...maxima) * 1.05 : undefined;
  }, [rows]);

  useEffect(() => {
    if (!chartRef.current || rows.length === 0) return;

    if (!chartInstanceRef.current) {
      chartInstanceRef.current = echarts.init(chartRef.current);
    }
    const chart = chartInstanceRef.current as echarts.ECharts;

    const seriesData = boxData.map((vals, idx) => ({
      value: vals,
      itemStyle: lowSampleFlags[idx] ? { opacity: 0.45 } : {},
    }));

    const budgetBand = (budget && (budget.min != null || budget.max != null))
      ? [[{ yAxis: budget.min != null ? budget.min : budget.max }, { yAxis: budget.max != null ? budget.max : budget.min }]]
      : undefined;

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'item',
        confine: true,
        formatter: (p: any) => {
          const idx = p?.dataIndex ?? p?.valueIndex ?? 0;
          const r = rows[idx];
          const n = listings[idx];
          const warn = lowSampleFlags[idx] ? '<br/><span style="color:#f59e0b">Sample size may be low</span>' : '';
          return [
            `<div><strong>${r.room_type}</strong></div>`,
            `min: €${Number(r.min).toFixed(0)}`,
            `q1: €${Number(r.q1).toFixed(0)}`,
            `median: €${Number(r.median).toFixed(0)}`,
            `q3: €${Number(r.q3).toFixed(0)}`,
            `max: €${Number(r.max).toFixed(0)}`,
            (typeof n === 'number' ? `listings: ${n}` : ''),
            warn
          ].filter(Boolean).join('<br/>');
        }
      },
      grid: { top: 30, left: 40, right: 20, bottom: 50 },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: { interval: 0, rotate: 20 },
      },
      yAxis: {
        type: 'value',
        name: '€ / night',
        max: yMax,
        axisLabel: {
          formatter: (v: number) => `€${Math.round(v)}`
        }
      },
      series: [
        {
          name: 'Price distribution',
          type: 'boxplot',
          data: seriesData,
          itemStyle: { color: '#7aa6ff', borderColor: '#3b82f6' },
          markArea: budgetBand ? {
            silent: true,
            itemStyle: { color: 'rgba(16, 185, 129, 0.12)' },
            data: budgetBand
          } : undefined,
        } as any
      ]
    };

    chart.clear();
    chart.setOption(option);

    chart.off('click');
    chart.on('click', (params: any) => {
      try {
        const idx = params?.dataIndex ?? params?.valueIndex ?? 0;
        const rt = categories[idx];
        if (rt) onOpenHeatmap({ room_type: rt });
      } catch {}
    });

    const resizeObserver = new ResizeObserver(() => { chart.resize(); });
    resizeObserver.observe(chartRef.current);
    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartInstanceRef.current = null;
    };
  }, [rows, boxData, categories, listings, lowSampleFlags, yMax, budget, onOpenHeatmap]);

  return (
    <div ref={chartRef} style={{ width: '100%', height }} />
  );
};

export default RoomTypeBoxplot;


