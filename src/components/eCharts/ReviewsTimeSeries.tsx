import React, { useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts';
import { Card, Segmented, Collapse, Slider, Select, Button, Space } from 'antd';

export type ReviewsScope = {
  area_level?: 'city'|'neighbourhood_group'|'neighbourhood';
  area_name?: string|null;
  budget_min?: number|null;
  budget_max?: number|null;
  room_type?: string|null;
  min_reviews?: number|null;
};

export type SentimentPoint = {
  period: string;
  pos: number;
  neu: number;
  neg: number;
  total: number;
  pos_ratio: number;
  neg_ratio: number;
};

export type TrendChartType = 'line_ratio' | 'stacked_area';
export type TrendGranularity = 'month' | 'week';
export type TrendRange = '6m' | '12m';

export interface SentimentTrendProps {
  scope: ReviewsScope;
  series: SentimentPoint[];
  chartType: TrendChartType;
  granularity: TrendGranularity;
  range: TrendRange;
  loading?: boolean;
  error?: string|null;

  onScopeToggle: (partial: Partial<ReviewsScope>) => void;
  onConfigChange: (cfg: Partial<{chartType:TrendChartType; granularity:TrendGranularity; range:TrendRange}>) => void;
  onFiltersChange: (f: {room_type?: string|null; budget_min?:number|null; budget_max?:number|null; min_reviews?:number|null}) => void;
  onPointClick: (point: SentimentPoint, scope: ReviewsScope) => void;
  onOpenQnA: (prefill?: string, scope?: ReviewsScope) => void;
}

const Chip = ({ label, onClose }:{label:string; onClose:()=>void}) => (
  <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-gray-100 text-gray-700 text-xs">
    {label}
    <button className="text-gray-500 hover:text-gray-700" onClick={onClose}>×</button>
  </span>
);

const ReviewsTimeSeries: React.FC<SentimentTrendProps> = ({
  scope,
  series,
  chartType,
  granularity,
  range,
  loading,
  error,
  onScopeToggle,
  onConfigChange,
  onFiltersChange,
  onPointClick,
  onOpenQnA
}) => {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  const data = useMemo(() => {
    return Array.isArray(series) ? series.map(d => ({
      ...d,
      pos_ratio_pct: Math.round(((d.total ? (d.pos/d.total) : 0) * 100) * 10) / 10,
      neg_ratio_pct: Math.round(((d.total ? (d.neg/d.total) : 0) * 100) * 10) / 10,
    })) : [] as Array<any>;
  }, [series]);

  useEffect(() => {
    if (!chartRef.current) return;
    if (!chartInstanceRef.current) {
      chartInstanceRef.current = echarts.init(chartRef.current);
    }
    const chart = chartInstanceRef.current;

    const categories = data.map(d => d.period);

    const option: echarts.EChartsOption = chartType === 'line_ratio' ? {
      tooltip: {
        trigger: 'axis',
        valueFormatter: (v: any) => `${v}%`
      },
      legend: { data: ['% Positive', '% Negative'] },
      grid: { left: '8%', right: '4%', top: 40, bottom: 36, containLabel: true },
      xAxis: { type: 'category', data: categories },
      yAxis: { type: 'value', min: 0, max: 100, axisLabel: { formatter: '{value}%' } },
      series: [
        {
          type: 'line',
          name: '% Positive',
          data: data.map(d => d.pos_ratio_pct),
          smooth: true,
          symbolSize: 6
        },
        {
          type: 'line',
          name: '% Negative',
          data: data.map(d => d.neg_ratio_pct),
          smooth: true,
          symbolSize: 6
        }
      ]
    } : {
      tooltip: { trigger: 'axis' },
      legend: { data: ['Positive','Neutral','Negative'] },
      grid: { left: '8%', right: '4%', top: 40, bottom: 36, containLabel: true },
      xAxis: { type: 'category', data: categories },
      yAxis: { type: 'value' },
      series: [
        { type: 'line', name: 'Positive', areaStyle: {}, stack: 'total', data: data.map(d => d.pos), smooth: true },
        { type: 'line', name: 'Neutral',  areaStyle: {}, stack: 'total', data: data.map(d => d.neu), smooth: true },
        { type: 'line', name: 'Negative', areaStyle: {}, stack: 'total', data: data.map(d => d.neg), smooth: true }
      ]
    };

    chart.setOption(option as any);

    chart.off('click');
    chart.on('click', (params: any) => {
      try {
        const idx = params?.dataIndex;
        if (idx != null && data[idx]) {
          onPointClick(data[idx] as any, scope);
        }
      } catch {}
    });

    const handleResize = () => { chart.resize(); };
    const ro = new ResizeObserver(() => handleResize());
    ro.observe(chartRef.current);

    return () => {
      ro.disconnect();
      chart.dispose();
      chartInstanceRef.current = null;
    };
  }, [chartType, JSON.stringify(data), onPointClick, scope]);

  return (
    <Card
      title={(
        <Space>
          <span>📈 Sentiment Trend</span>
          <Segmented
            size="small"
            options={[{ label: '% Positive', value: 'line_ratio' }, { label: 'Stacked Area', value: 'stacked_area' }]}
            value={chartType}
            onChange={(v) => onConfigChange({ chartType: v as TrendChartType })}
          />
        </Space>
      )}
      extra={<Button type="primary" onClick={() => onOpenQnA('', scope)}>Explore with Q&A</Button>}
      style={{ width: '100%', borderRadius: 12 }}
    >
      {/* Scope Chips */}
      <div className="flex flex-wrap gap-2 mb-3">
        {scope.area_name && (
          <Chip label={String(scope.area_name)} onClose={() => onScopeToggle({ area_level: 'city', area_name: null })} />
        )}
        {scope.budget_min != null && scope.budget_max != null && (
          <Chip label={`€${scope.budget_min}–€${scope.budget_max}`} onClose={() => onScopeToggle({ budget_min: null, budget_max: null })} />
        )}
        {scope.room_type && (
          <Chip label={String(scope.room_type)} onClose={() => onScopeToggle({ room_type: null })} />
        )}
        {scope.min_reviews != null && scope.min_reviews > 0 && (
          <Chip label={`min ${scope.min_reviews} reviews`} onClose={() => onScopeToggle({ min_reviews: 0 })} />
        )}
      </div>

      {/* ConfigBar */}
      <div className="flex items-center gap-3 mb-2">
        <Segmented
          options={[{label:'Month', value:'month'}, {label:'Week', value:'week'}]}
          value={granularity}
          onChange={(v)=>onConfigChange({ granularity: v as TrendGranularity })}
          size="small"
        />
        <Segmented
          options={[{label:'6m', value:'6m'}, {label:'12m', value:'12m'}]}
          value={range}
          onChange={(v)=>onConfigChange({ range: v as TrendRange })}
          size="small"
        />
      </div>

      {/* Chart */}
      <div style={{ width: '100%', height: 260 }}>
        <div ref={chartRef} style={{ width: '100%', height: '100%' }} />
      </div>

      {/* Filters */}
      <Collapse ghost items={[{
        key: 'filters',
        label: 'Filters',
        children: (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-12">
            <div>
              <div className="text-xs mb-1">Room Type</div>
              <Select
                allowClear
                placeholder="Any"
                value={scope.room_type ?? undefined}
                onChange={(v)=>onFiltersChange({ room_type: (v ?? null) as any })}
                options={[
                  {label:'Entire home/apt', value:'Entire home/apt'},
                  {label:'Private room', value:'Private room'},
                  {label:'Shared room', value:'Shared room'},
                  {label:'Hotel room', value:'Hotel room'}
                ]}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <div className="text-xs mb-1">Price Range (€)</div>
              <Slider
                range
                min={10}
                max={300}
                value={[
                  (scope.budget_min ?? 50) as number,
                  (scope.budget_max ?? 150) as number
                ]}
                onChange={(vals: any)=>{
                  const arr = Array.isArray(vals) ? vals : [50,150];
                  onFiltersChange({ budget_min: arr[0], budget_max: arr[1] });
                }}
              />
            </div>
            <div>
              <div className="text-xs mb-1">Min Reviews (last 30d)</div>
              <Slider min={0} max={20}
                value={(scope.min_reviews ?? 0) as number}
                onChange={(v: any)=>onFiltersChange({ min_reviews: Number(v) })}
              />
            </div>
          </div>
        )
      }]} />
    </Card>
  );
};

export default ReviewsTimeSeries;


