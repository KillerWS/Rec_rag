import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Modal, Button, Spin, Alert, Divider, InputNumber, Space, message, Tooltip, Slider, Segmented, Tag } from 'antd';
import GenericOptionChart from '../quickModals/GenericOptionChart';
import { fetchTestChartOption } from '../../api/api';

interface CenterPoint {
  lat: number;
  lon: number;
  name?: string;
}

interface DistancePriceTradeoffPreferences {
  granularity?: 'group' | 'neighbourhood';
  alpha?: number; // [0,1]
  center?: CenterPoint;
  min_listings?: number; // only for neighbourhood
  room_type?: string;
  minimum_nights?: number;
  min_reviews?: number;
  price_min?: number;
  price_max?: number;
  top_k?: number;
  sort_by?: 'tradeoff' | 'price_score' | 'dist_score' | 'median_price' | 'distance_km' | 'listing_count';
  sort_order?: 'asc' | 'desc';
  always_include_areas?: string[];
}

interface DistancePriceTradeoffProps {
  visible: boolean;
  onClose: () => void;
  preferences?: DistancePriceTradeoffPreferences;
  width?: number;
}

const DistancePriceTradeoff: React.FC<DistancePriceTradeoffProps> = ({ visible, onClose, preferences, width = 980 }) => {
  const loadedRef = useRef(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [option, setOption] = useState<any | null>(null);
  const [meta, setMeta] = useState<any | null>(null);
  const [chartCfg, setChartCfg] = useState<any | null>(null);
  const [showInfo, setShowInfo] = useState(false);
  const [viewMode, setViewMode] = useState<'combined' | 'split'>('combined');

  // local controls
  const [localMin, setLocalMin] = useState<number | undefined>(preferences?.price_min);
  const [localMax, setLocalMax] = useState<number | undefined>(preferences?.price_max);
  const [localAlpha, setLocalAlpha] = useState<number>(
    typeof preferences?.alpha === 'number' ? Math.max(0, Math.min(1, preferences.alpha)) : 0.6
  );

  useEffect(() => {
    const load = async () => {
      if (!visible || loadedRef.current) return;
      setLoading(true);
      setError(null);
      try {
        const payload: any = {
          type: 'distance_price_tradeoff',
          preferences: preferences || {}
        };
        const res: any = await fetchTestChartOption(payload);
        const opt = res?.echarts_option || res?.option;
        if (!opt) throw new Error('No ECharts option returned');
        setOption(opt);
        setMeta(res?.metadata || null);
        setChartCfg(res?.chart_config || null);
        // sync alpha if backend echoes it
        const echoedAlpha = res?.metadata?.alpha;
        if (typeof echoedAlpha === 'number') {
          setLocalAlpha(Math.max(0, Math.min(1, echoedAlpha)));
        }
        loadedRef.current = true;
      } catch (e: any) {
        setError(e?.message || 'Failed to load distance-price tradeoff');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [visible, preferences]);

  const info = useMemo(() => {
    const appliedBudget = meta?.applied_budget || {};
    const alpha = meta?.alpha;
    const center = meta?.center || preferences?.center;
    const granularity = meta?.granularity || preferences?.granularity || 'group';
    const minListings = meta?.min_listings ?? preferences?.min_listings;
    const corr = meta?.corr_price_distance;
    const scoreExp = meta?.score_explanation || {
      price_advantage: 'Scaled 0-100 (cheapest ~100, most expensive ~0) based on median price.',
      distance_advantage: 'Scaled 0-100 (closest ~100, farthest ~0) based on centroid distance.',
      tradeoff: 'alpha * price_advantage + (1-alpha) * distance_advantage'
    };

    return {
      appliedBudget,
      alpha,
      center,
      granularity,
      minListings,
      corr,
      scoreExp,
      sorting: meta?.sorting,
      highlights: meta?.highlights,
    };
  }, [meta, preferences]);

  const massageOption = (opt: any) => {
    if (!opt || typeof opt !== 'object') return opt;
    const cloned = JSON.parse(JSON.stringify(opt));

    const ensureArray = (v: any) => (Array.isArray(v) ? v : (v ? [v] : []));

    if (cloned.title) {
      const titles = ensureArray(cloned.title);
      titles.forEach((t: any) => {
        t.top = t.top ?? 8;
        t.left = t.left ?? 'center';
        if (!t.subtextStyle) t.subtextStyle = {};
        t.subtextStyle.fontSize = t.subtextStyle.fontSize ?? 11;
        t.subtextStyle.lineHeight = t.subtextStyle.lineHeight ?? 14;
      });
      cloned.title = titles.length === 1 ? titles[0] : titles;
    }

    const legends = ensureArray(cloned.legend);
    if (legends.length > 0) {
      legends.forEach((lg: any) => {
        lg.top = 54;
        lg.left = lg.left ?? 'center';
        lg.orient = lg.orient ?? 'horizontal';
      });
      cloned.legend = legends.length === 1 ? legends[0] : legends;
    }

    const grids = ensureArray(cloned.grid);
    if (grids.length > 0) {
      grids.forEach((g: any) => {
        const currentTop = typeof g.top === 'number' ? g.top : (g.top ?  g.top : 60);
        g.top = Math.max(70, currentTop);
        g.containLabel = g.containLabel ?? true;
      });
      cloned.grid = grids.length === 1 ? grids[0] : grids;
    } else {
      cloned.grid = { left: '3%', right: '4%', bottom: '8%', top: 70, containLabel: true };
    }

    return cloned;
  };

  const tweakedOption = useMemo(() => massageOption(option), [option]);

  const combinedOption = useMemo(() => {
    if (!option || !option.series || !Array.isArray(option.series) || option.series.length < 2) return option;
    const priceSeries = option.series[0];
    const distSeries = option.series[1];
    const categories: string[] = option?.xAxis?.data || [];
    const toNum = (d: any) => (typeof d === 'number' ? d : (d && typeof d.value === 'number' ? d.value : 0));
    const priceData: number[] = Array.isArray(priceSeries?.data) ? priceSeries.data.map(toNum) : [];
    const distData: number[] = Array.isArray(distSeries?.data) ? distSeries.data.map(toNum) : [];
    if (!categories.length || !priceData.length || !distData.length) return option;
    const alpha = Math.max(0, Math.min(1, localAlpha));
    const rows = categories.map((name: string, i: number) => {
      const p = priceData[i] ?? 0;
      const d = distData[i] ?? 0;
      const combined = alpha * p + (1 - alpha) * d;
      return { name, p, d, combined };
    });
    rows.sort((a, b) => b.combined - a.combined);
    const newXAxis = {
      ...(option.xAxis || {}),
      data: rows.map(r => r.name)
    };
    const newSeries = [
      {
        name: 'Overall score',
        type: 'bar',
        itemStyle: { color: '#5470c6' },
        data: rows.map(r => Number(r.combined.toFixed(1)))
      }
    ];
    const newLegend = { show: false };
    const newTitle = {
      ...(option.title || {}),
      subtext: `price=${alpha.toFixed(2)}, distance=${(1 - alpha).toFixed(2)} | combined view`
    };
    return {
      ...option,
      xAxis: newXAxis,
      series: newSeries,
      legend: newLegend,
      title: newTitle
    };
  }, [option, localAlpha]);

  const splitOptionSorted = useMemo(() => {
    if (!option || !option.series || !Array.isArray(option.series) || option.series.length < 2) return tweakedOption;
    const priceSeries = option.series[0];
    const distSeries = option.series[1];
    const categories: string[] = option?.xAxis?.data || [];
    const toNum = (d: any) => (typeof d === 'number' ? d : (d && typeof d.value === 'number' ? d.value : 0));
    const priceData: any[] = Array.isArray(priceSeries?.data) ? priceSeries.data : [];
    const distData: any[] = Array.isArray(distSeries?.data) ? distSeries.data : [];
    if (!categories.length || !priceData.length || !distData.length) return tweakedOption;
    const alpha = Math.max(0, Math.min(1, localAlpha));
    const rows = categories.map((name: string, i: number) => {
      const p = toNum(priceData[i]);
      const d = toNum(distData[i]);
      const combined = alpha * p + (1 - alpha) * d;
      return { name, idx: i, combined };
    });
    rows.sort((a, b) => b.combined - a.combined);
    const orderIdx = rows.map(r => r.idx);
    const reorder = (arr: any[]) => orderIdx.map(i => arr[i]);
    const newXAxis = {
      ...(option.xAxis || {}),
      data: rows.map(r => r.name)
    };
    const newSeries = [
      { ...priceSeries, data: reorder(priceData) },
      { ...distSeries, data: reorder(distData) }
    ];
    const newTitle = {
      ...(option.title || {}),
      subtext: `alpha=${alpha.toFixed(2)}, sorted by tradeoff (desc)`
    };
    return {
      ...option,
      xAxis: newXAxis,
      series: newSeries,
      title: newTitle
    };
  }, [option, tweakedOption, localAlpha]);

  const displayOption = useMemo(() => {
    const base = viewMode === 'combined' ? combinedOption : splitOptionSorted;
    return massageOption(base);
  }, [viewMode, combinedOption, splitOptionSorted]);

  const applyControls = async () => {
    if (localMin != null && localMax != null && localMin > localMax) {
      message.error('Min price cannot be greater than max price');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const payload: any = {
        type: 'distance_price_tradeoff',
        preferences: {
          ...(preferences || {}),
          price_min: localMin,
          price_max: localMax,
          alpha: localAlpha
        }
      };
      const res: any = await fetchTestChartOption(payload);
      const opt = res?.echarts_option || res?.option;
      if (!opt) throw new Error('No ECharts option returned');
      setOption(opt);
      setMeta(res?.metadata || null);
      setChartCfg(res?.chart_config || null);
    } catch (e: any) {
      setError(e?.message || 'Failed to refresh chart');
    } finally {
      setLoading(false);
    }
  };

  // Reset button removed per request

  const subtitleText = displayOption?.title?.subtext || chartCfg?.subtitle || meta?.chart_subtitle_text;

  return (
    <>
      <Modal
        title={chartCfg?.title || 'Distance vs Price Tradeoff'}
        open={visible}
        onCancel={onClose}
        footer={null}
        width={width}
        destroyOnClose={false}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm text-gray-600">
            <Tooltip
              title={(
                <div style={{ maxWidth: 360 }}>
                  <div><strong>alpha</strong>: price weight in the overall score (0 = only distance, 1 = only price)</div>
                  <div><strong>granularity</strong>: districts (group) vs. smaller areas (neighbourhood)</div>
                  {typeof info.minListings === 'number' && (
                    <div><strong>enough data</strong>: we only keep areas with sufficient listings</div>
                  )}
                  {info.center && (
                    <div><strong>center</strong>: {info.center.name || 'Center'}</div>
                  )}
                  {info.sorting && (
                    <div><strong>sorted by</strong>: {info.sorting.by} ({info.sorting.order})</div>
                  )}
                  <div style={{ marginTop: 6, color: '#64748b' }}>Click ℹ️ for details.</div>
                </div>
              )}
            >
              <span>{subtitleText}</span>
            </Tooltip>
          </div>
          <Button size="small" onClick={() => setShowInfo(true)}>ℹ️ Explanation</Button>
        </div>

        {/* Controls row */}
        <div className="mb-3">
          <Space size={16} wrap>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-600">Budget (€)</span>
              <InputNumber placeholder="Min" value={localMin} onChange={(v) => setLocalMin(typeof v === 'number' ? v : undefined)} min={0} step={5} style={{ width: 110 }} />
              <InputNumber placeholder="Max" value={localMax} onChange={(v) => setLocalMax(typeof v === 'number' ? v : undefined)} min={0} step={5} style={{ width: 110 }} />
            </div>
            <Button type="primary" size="small" onClick={applyControls}>Apply</Button>
            <div className="flex items-center gap-3" style={{ minWidth: 520 }}>
              <div className="flex items-center gap-2" style={{ minWidth: 210 }}>
                <span className="text-xs text-gray-600">View</span>
                <Segmented
                  size="small"
                  value={viewMode}
                  onChange={(v) => setViewMode((v as 'combined' | 'split'))}
                  options={[
                    { label: (<Tag color="blue" style={{ margin: 0, pointerEvents: 'none' }}>Combined</Tag>), value: 'combined' },
                    { label: (<Tag color="magenta" style={{ margin: 0, pointerEvents: 'none' }}>Split</Tag>), value: 'split' }
                  ]}
                />
              </div>
              <div className="flex items-center gap-2" style={{ minWidth: 260 }}>
                <span className="text-xs text-gray-600"><strong>Price weight ({localAlpha.toFixed(2)})</strong></span>
                <div style={{ width: 160 }}>
                  <Slider min={0} max={1} step={0.01} value={localAlpha} onChange={(v) => setLocalAlpha(Array.isArray(v) ? v[0] : v)} />
                </div>
              </div>
              <div className="flex items-center gap-2" style={{ minWidth: 280 }}>
                <span className="text-xs text-gray-600"><strong>Distance weight ({(1 - localAlpha).toFixed(2)})</strong></span>
                <div style={{ width: 160 }}>
                  <Slider min={0} max={1} step={0.01} value={1 - localAlpha} onChange={(v) => {
                    const val = Array.isArray(v) ? v[0] : v;
                    setLocalAlpha(1 - (typeof val === 'number' ? val : 0));
                  }} />
                </div>
              </div>
            </div>
          </Space>
        </div>

        {loading && (
          <div className="py-6 text-center">
            <Spin />
          </div>
        )}
        {error && (
          <Alert type="error" message={error} showIcon />
        )}
        {!loading && !error && displayOption && (
          <GenericOptionChart option={displayOption} height={460} />
        )}
      </Modal>

      <Modal
        title="How the score is calculated"
        open={showInfo}
        onCancel={() => setShowInfo(false)}
        footer={<Button onClick={() => setShowInfo(false)}>Close</Button>}
        width={720}
      >
        <div className="space-y-3 text-sm">
          <div>
            <div className="font-medium mb-1">What the scores mean</div>
            <ul className="list-disc ml-5 space-y-1">
              <li><strong>Weights (sum to 1)</strong>: price = {localAlpha.toFixed(2)}, distance = {(1 - localAlpha).toFixed(2)}.</li>
              <li><strong>Price score (0–100)</strong>: cheaper areas get higher values compared with others on the chart.</li>
              <li><strong>Distance score (0–100)</strong>: closer to the center gets higher values.</li>
              <li><strong>Overall score</strong>: priceWeight × price score + distanceWeight × distance score.</li>
            </ul>
          </div>

          <Divider />

          <div>
            <div className="font-medium mb-1">Notes</div>
            <ul className="list-disc ml-5 space-y-1">
              <li>Scores are relative to the areas currently shown.</li>
              <li>We only keep areas with enough listings to stay reliable.</li>
              {info.sorting && (<li>Bars may be ordered by: {info.sorting.by} ({info.sorting.order}).</li>)}
            </ul>
          </div>
        </div>
      </Modal>
    </>
  );
};

export default DistancePriceTradeoff; 