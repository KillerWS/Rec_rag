import React, { useEffect, useMemo, useRef, useState } from 'react';
import * as echarts from 'echarts';
import { Card, Slider, Button } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { fetchTestChartOption } from '../../api/api';

interface PriceCoverageDeltaProps {
  // 初始化自后端 echarts_option（可选）
  echartsOption?: any;
  // 可选：初始预算下限/上限（用于 slider 初值）
  initialMin?: number;
  initialMax?: number;
  // 可选：说明文字
  subtitle?: string;
}

const PriceCoverageDelta: React.FC<PriceCoverageDeltaProps> = ({ echartsOption, initialMin = 50, initialMax = 150, subtitle }) => {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [priceMin, setPriceMin] = useState<number>(initialMin);
  const [priceMax, setPriceMax] = useState<number>(initialMax);
  const [xo, setXo] = useState<any>(echartsOption || null);
  const [narrative, setNarrative] = useState<string | null>(null);
  const [step, setStep] = useState<number | null>(null);

  

  const categories: string[] = useMemo(() => {
    const xs = xo?.xAxis?.data || xo?.xAxis?.[0]?.data;
    return Array.isArray(xs) ? xs.map((v: any) => String(v)) : [];
  }, [xo]);

  // 尝试从 echarts_option 提取覆盖率与增量，约定：
  // - 覆盖率曲线 series: type=line 或 name 包含 'coverage'
  // - 增量条形 series: type=bar 或 name 包含 'delta'
  const coverageSeriesObj = useMemo(() => {
    if (!xo?.series) return null as any;
    return (xo.series as any[]).find((it: any) => String(it?.type || '').includes('line') || String(it?.name || '').toLowerCase().includes('coverage'));
  }, [xo]);

  const isPairs = useMemo(() => {
    const arr = coverageSeriesObj?.data;
    return Array.isArray(arr) && Array.isArray(arr[0]) && arr[0].length >= 2;
  }, [coverageSeriesObj]);

  const coverageData: number[] = useMemo(() => {
    if (!coverageSeriesObj) return [];
    const arr = coverageSeriesObj.data as any[];
    if (isPairs) return []; // handled in series as [x,y]
    const raw = Array.isArray(arr) ? arr.map((n) => Number(n) || 0) : [];
    const maxVal = raw.reduce((m, v) => Math.max(m, v), 0);
    const asPercent = maxVal <= 1.1; // treat as ratio -> percentage
    return asPercent ? raw.map((v) => v * 100) : raw;
  }, [coverageSeriesObj, isPairs]);

  const deltaData: number[] = useMemo(() => {
    if (!xo?.series) return [];
    const s = (xo.series as any[]).find((it: any) => String(it?.type || '').includes('bar') || String(it?.name || '').toLowerCase().includes('delta'));
    const arr = s?.data as any[];
    return Array.isArray(arr) ? arr.map((n) => Number(n) || 0) : [];
  }, [xo]);

  // Explanatory text: how coverage changes when raising from min to max
  const explanatoryText = useMemo(() => {
    try {
      // pairs mode: x=budget, y=coverage (0-1 possibly, convert to %)
      if (coverageSeriesObj && isPairs) {
        const raw: Array<[number, number]> = Array.isArray(coverageSeriesObj.data)
          ? (coverageSeriesObj.data as any[]).map((p: any) => [Number(p[0]) || 0, Number(p[1]) || 0])
          : [];
        if (!raw.length) return '';
        const maxY = raw.reduce((m, p) => Math.max(m, p[1]), 0);
        const asPercent = maxY <= 1.1;
        const pairsPct: Array<[number, number]> = raw.map(([x, y]) => [x, asPercent ? y * 100 : y]);
        const nearest = (val: number) => pairsPct.reduce((best, cur) => {
          return Math.abs(cur[0] - val) < Math.abs(best[0] - val) ? cur : best;
        }, pairsPct[0]);
        const [_, baseCov] = nearest(priceMin);
        const [__, newCov] = nearest(priceMax);
        const delta = newCov - baseCov;
        const fmt = (n: number) => `${Math.round(n * 10) / 10}%`;
        if (!Number.isFinite(baseCov) || !Number.isFinite(newCov)) return '';
        if (delta > 0.05) {
          return `If you raise the budget from €${priceMin} to €${priceMax}, coverage is expected to increase from ${fmt(baseCov)} to ${fmt(newCov)} (+${fmt(delta)}).`;
        }
        if (delta < -0.05) {
          return `If you lower the budget from €${priceMin} to €${priceMax}, coverage is expected to drop from ${fmt(baseCov)} to ${fmt(newCov)} (${fmt(delta)}).`;
        }
        return `Adjusting the budget from €${priceMin} to €${priceMax} yields little change in coverage (≈ ${fmt(delta)}).`;
      }

      // category mode: categories + coverageData (already 0-100%)
      if (categories.length && coverageData.length) {
        const nums = categories.map((c) => Number(c));
        const allNumeric = nums.every((n) => !Number.isNaN(n));
        const nearIdx = (val: number) => {
          if (!allNumeric) return 0;
          let best = 0;
          let bestDiff = Math.abs(nums[0] - val);
          for (let i = 1; i < nums.length; i++) {
            const d = Math.abs(nums[i] - val);
            if (d < bestDiff) { best = i; bestDiff = d; }
          }
          return best;
        };
        const i0 = nearIdx(priceMin);
        const i1 = nearIdx(priceMax);
        const baseCov = coverageData[i0] ?? NaN;
        const newCov = coverageData[i1] ?? NaN;
        const delta = (newCov ?? 0) - (baseCov ?? 0);
        const fmt = (n: number) => `${Math.round(n * 10) / 10}%`;
        if (!Number.isFinite(baseCov) || !Number.isFinite(newCov)) return '';
        if (delta > 0.05) {
          return `If you raise the budget from €${priceMin} to €${priceMax}, coverage is expected to increase from ${fmt(baseCov)} to ${fmt(newCov)} (+${fmt(delta)}).`;
        }
        if (delta < -0.05) {
          return `If you lower the budget from €${priceMin} to €${priceMax}, coverage is expected to drop from ${fmt(baseCov)} to ${fmt(newCov)} (${fmt(delta)}).`;
        }
        return `Adjusting the budget from €${priceMin} to €${priceMax} yields little change in coverage (≈ ${fmt(delta)}).`;
      }
    } catch {}
    return '';
  }, [coverageSeriesObj, isPairs, categories, coverageData, priceMin, priceMax]);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstanceRef.current) chartInstanceRef.current = echarts.init(chartRef.current);
    const chart = chartInstanceRef.current;

    let option: echarts.EChartsOption;

    if (isPairs) {
      // 后端返回的是 [x,y] 对，保持 value 轴渲染
      const rawPairs: Array<[number, number]> = Array.isArray(coverageSeriesObj?.data)
        ? (coverageSeriesObj.data as any[]).map((p: any) => [Number(p[0]) || 0, Number(p[1]) || 0])
        : [];
      const maxY = rawPairs.reduce((m, p) => Math.max(m, p[1]), 0);
      const asPercent = maxY <= 1.1;
      const pairs: Array<[number, number]> = rawPairs.map(([x, y]) => [x, asPercent ? y * 100 : y]);
      // 计算 Δ coverage（相邻差分），用同样的 x 值绘制柱状
      const deltaPairs: Array<[number, number]> = pairs.map((p, idx) => [p[0], idx === 0 ? 0 : Math.max(0, p[1] - pairs[idx - 1][1])]);
      const xs = pairs.map((p) => p[0]);
      const minX = xs.length ? Math.min(...xs) : priceMin;
      const maxX = xs.length ? Math.max(...xs) : priceMax;

      option = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
        grid: { left: '8%', right: '8%', top: 40, bottom: 50, containLabel: true },
        legend: { data: ['Coverage %', 'Δ Coverage (%)'] },
        xAxis: { type: 'value', name: xo?.xAxis?.name || 'Budget (€)' },
        yAxis: [
          { type: 'value', name: xo?.yAxis?.name || 'Coverage %', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
          { type: 'value', name: 'Δ Coverage (%)', min: 0, axisLabel: { formatter: '{value}%' } }
        ],
        series: [
          {
            type: 'line',
            name: 'Coverage %',
            data: pairs,
            smooth: true,
            yAxisIndex: 0,
            // 区间底色（中间为红色，高亮所选范围）
            markArea: {
              silent: true,
              itemStyle: { color: 'rgba(239,68,68,0.18)' },
              data: [ [ { xAxis: priceMin }, { xAxis: priceMax } ] ]
            }
          },
          {
            type: 'bar',
            name: 'Δ Coverage (%)',
            data: deltaPairs,
            yAxisIndex: 1,
            itemStyle: { color: '#60a5fa' },
            barWidth: '40%',
            tooltip: {
              valueFormatter: (val: any) => `${Number(val).toFixed(1)}%`,
              formatter: (params: any) => {
                const v = Array.isArray(params.value) ? Number(params.value[1]) : Number(params.value);
                const x = Array.isArray(params.value) ? params.value[0] : params.name;
                const sign = v > 0 ? '+' : '';
                return `Δ Coverage: ${sign}${v.toFixed(1)}%<br/>at €${x}`;
              }
            },
            // 左右两侧的淡灰底色
            markArea: {
              silent: true,
              itemStyle: { color: 'rgba(148,163,184,0.10)' },
              data: [
                [ { xAxis: minX }, { xAxis: priceMin } ],
                [ { xAxis: priceMax }, { xAxis: maxX } ]
              ]
            }
          }
        ],
      };
    } else {
      // 分类轴模式（旧格式），使用 categories + 数组
      const normalized = coverageData;
      const deltas = normalized.map((v, idx) => (idx === 0 ? 0 : Math.max(0, v - normalized[idx - 1])));
      // 尝试推断左右边界与区间端点
      const firstCat = categories[0];
      const lastCat = categories[categories.length - 1];
      const numCats = categories.map((c) => Number(c));
      const allNumeric = numCats.every((n) => !Number.isNaN(n));
      const leftEdge = allNumeric ? String(Math.min(...numCats)) : firstCat;
      const rightEdge = allNumeric ? String(Math.max(...numCats)) : lastCat;
      // 将 slider 值映射到最近的分类（若为数值型分类）
      const near = (val: number) => {
        if (!allNumeric) return String(val);
        let best = numCats[0];
        let bestDiff = Math.abs(numCats[0] - val);
        for (let i = 1; i < numCats.length; i++) {
          const d = Math.abs(numCats[i] - val);
          if (d < bestDiff) { best = numCats[i]; bestDiff = d; }
        }
        return String(best);
      };
      const leftSel = near(priceMin);
      const rightSel = near(priceMax);
      option = {
        tooltip: { trigger: 'axis' },
        grid: { left: '8%', right: '8%', top: 40, bottom: 50, containLabel: true },
        legend: { data: ['Coverage %', 'Δ Coverage (%)'] },
        xAxis: { type: 'category', data: categories },
        yAxis: [
          { type: 'value', name: 'Coverage %', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
          { type: 'value', name: 'Δ Coverage (%)', min: 0, axisLabel: { formatter: '{value}%' } }
        ],
        series: [
          {
            type: 'line',
            name: 'Coverage %',
            data: normalized,
            smooth: true,
            yAxisIndex: 0,
            markArea: {
              silent: true,
              itemStyle: { color: 'rgba(239,68,68,0.18)' },
              data: [ [ { xAxis: leftSel }, { xAxis: rightSel } ] ]
            }
          },
          {
            type: 'bar',
            name: 'Δ Coverage (%)',
            data: deltas,
            yAxisIndex: 1,
            itemStyle: { color: '#60a5fa' },
            tooltip: {
              valueFormatter: (val: any) => `${Number(val).toFixed(1)}%`,
              formatter: (params: any) => {
                const v = Number(params.value);
                const sign = v > 0 ? '+' : '';
                return `Δ Coverage: ${sign}${v.toFixed(1)}%\n@ ${params.name}`;
              }
            },
            markArea: {
              silent: true,
              itemStyle: { color: 'rgba(148,163,184,0.10)' },
              data: [
                [ { xAxis: leftEdge }, { xAxis: leftSel } ],
                [ { xAxis: rightSel }, { xAxis: rightEdge } ]
              ]
            }
          }
        ],
      };
    }

    chart.setOption(option as any);

    const handleResize = () => chart.resize();
    const ro = new ResizeObserver(() => handleResize());
    ro.observe(chartRef.current);
    return () => { ro.disconnect(); chart.dispose(); chartInstanceRef.current = null; };
  }, [categories, coverageData, deltaData, isPairs, coverageSeriesObj, xo, priceMin, priceMax]);

  const refetch = async () => {
    try {
      setLoading(true);
      const res: any = await fetchTestChartOption({ type: 'price_coverage_delta', price_min: priceMin, price_max: priceMax });
      const option = res?.echarts_option || res?.option || null;
      if (option) setXo(option);
      // Try to find request_budgets in multiple common locations
      const reqBudgets = (res as any)?.request_budgets
        || (res as any)?.inputs?.request_budgets
        || (res as any)?.meta?.request_budgets
        || (res as any)?.session?.request_budgets;
      const inputs = (res as any)?.inputs;
      // Apply request_budgets first (takes precedence), with string/number coercion
      if (reqBudgets) {
        if (reqBudgets.price_min !== undefined && reqBudgets.price_min !== null) setPriceMin(Number(reqBudgets.price_min));
        if (reqBudgets.price_max !== undefined && reqBudgets.price_max !== null) setPriceMax(Number(reqBudgets.price_max));
      }
      // Then apply inputs-derived values if present (but don't override reqBudgets if already set by backend)
      if (inputs) {
        if (inputs.step !== undefined && inputs.step !== null) setStep(Number(inputs.step));
        if ((reqBudgets?.price_min === undefined || reqBudgets?.price_min === null) && inputs.base_budget !== undefined && inputs.base_budget !== null) {
          setPriceMin(Number(inputs.base_budget));
        }
        if ((reqBudgets?.price_max === undefined || reqBudgets?.price_max === null) && inputs.new_budget !== undefined && inputs.new_budget !== null) {
          setPriceMax(Number(inputs.new_budget));
        }
      }
      if (typeof (res as any)?.narrative === 'string') setNarrative(String((res as any).narrative));
    } catch (e) {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  // fetch once on mount to initialize from request_budgets
  useEffect(() => {
    refetch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Card
      title={<span className="font-semibold text-gray-800">💰 Price Coverage Delta</span>}
      extra={<Button size="small" icon={<ReloadOutlined />} onClick={refetch} loading={loading}>Refresh</Button>}
      style={{ width: '100%', borderRadius: 12, background: 'linear-gradient(180deg, #fef2f2 0%, #fff 100%)' }}
    >
      {subtitle && <div className="text-sm text-gray-500 mb-2">{subtitle}</div>}
      <div className="mb-3">
        <div className="text-xs text-gray-600 mb-1">Budget range (€)</div>
        <Slider
          range
          min={10}
          max={300}
          step={step ?? 5}
          value={[priceMin, priceMax]}
          onChange={(vals: any) => {
            const arr = Array.isArray(vals) ? vals : [priceMin, priceMax];
            setPriceMin(Number(arr[0]));
            setPriceMax(Number(arr[1]));
          }}
          onAfterChange={() => refetch()}
        />
        <div className="text-xs text-gray-500">Current range: €{priceMin} – €{priceMax}</div>
      </div>
      <div style={{ width: '100%', height: 260 }}>
        <div ref={chartRef} style={{ width: '100%', height: '100%' }} />
      </div>
      <div className="mt-3 text-sm text-gray-600">
        {narrative && (
          <span dangerouslySetInnerHTML={{
            __html: narrative.replace(/(\d+\.?\d*%?)/g, '<strong class="text-gray-800">$1</strong>')
          }} />
        )}
        {explanatoryText && (
          <div className="mt-1">{explanatoryText}</div>
        )}
        {!narrative && !explanatoryText && (
          categories.length > 0 ? (
            <>Within the current range, coverage increases as the budget ceiling rises. Drag the slider to simulate the marginal gain (Δ Coverage) when raising the budget.</>
          ) : 'No data'
        )}
      </div>
    </Card>
  );
};

export default PriceCoverageDelta;


