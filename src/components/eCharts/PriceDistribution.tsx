import React, { useRef, useEffect, useState, useMemo } from 'react';
import * as echarts from 'echarts';
import { Typography, Select, Button, Tooltip, Space, Slider, InputNumber } from 'antd';
import { EnvironmentOutlined } from '@ant-design/icons';

const { Text } = Typography;
const { Option } = Select;

// Removed static Berlin districts data; map selection is handled via the map modal

// Props
interface PriceDistributionProps {
  chartData: {
    title: string;
    data: any; // rich payload per spec (bins, stack_by_room_type, cdf, global_stats, budget, meta, bin_quality)
    echarts_option?: any; // fallback option from backend
    type: string;
  };
  height?: number;
  width?: string;
  modalVisible?: boolean;
  onDistrictSelect?: (district: string, neighborhood?: string) => void;
  onShowMap?: (district: string | any) => void;
  showControls?: boolean;
}

// helpers
const parseBinsFromXAxis = (labels: string[] = []) => {
  return labels.map((rawLabel) => {
    const label = String(rawLabel);
    const normalized = label.replace(/–|—/g, '-');

    // Match range like 100-150€
    const rangeMatch = normalized.match(/(\d+)\s*-\s*(\d+)/);
    if (rangeMatch) {
      const min = parseInt(rangeMatch[1], 10);
      const max = parseInt(rangeMatch[2], 10);
      return { label, min, max };
    }

    // Match open-ended like ≥350€ or >=350€
    const geMatch = normalized.match(/[≥>]=?\s*(\d+)/);
    if (geMatch) {
      const min = parseInt(geMatch[1], 10);
      const max = Number.POSITIVE_INFINITY;
      return { label, min, max };
    }

    // Fallback: extract any number and use as both bounds
    const onlyNum = parseInt(normalized.replace(/[^0-9]/g, ''), 10);
    if (Number.isFinite(onlyNum)) {
      return { label, min: onlyNum, max: onlyNum };
    }
    return { label, min: 0, max: 0 };
  });
};

const sum = (arr: number[]) => arr.reduce((a, b) => a + (Number.isFinite(b) ? b : 0), 0);

const currency = (v?: number) => (typeof v === 'number' && Number.isFinite(v) ? `€${Math.round(v)}` : '–');

// const pct = (v?: number) => (typeof v === 'number' && Number.isFinite(v) ? `${(v).toFixed(0)}%` : '–');

const SAFE_COLORS: Record<string, string> = {
  'Entire home/apt': '#4e79a7',
  'Private room': '#f28e2b',
  'Shared room': '#e15759',
  'Hotel room': '#76b7b2'
};

const PriceDistribution: React.FC<PriceDistributionProps> = ({
  chartData,
  height = 360,
  width = '100%',
  modalVisible,
  onDistrictSelect: _onDistrictSelect,
  onShowMap,
  showControls = true
}) => {
  const [yMode, setYMode] = useState<'count' | 'percentage'>('count');
  const [showCDF] = useState<boolean>(true);
  const [selectedRoomTypes, setSelectedRoomTypes] = useState<string[]>([]);
  const [externalLoading, setExternalLoading] = useState<boolean>(false);

  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  // derive bins and room types
  const { bins, xLabels, allRoomTypes, cdfSeries, globalStats } = useMemo(() => {
    const payload = chartData?.data || {};
    const option = chartData?.echarts_option || {};

    const xAxisLabels: string[] = payload?.bins?.length
      ? payload.bins.map((b: any) => `${b.min}-${b.max}€`)
      : option?.xAxis?.data || [];

    const binsParsed = payload?.bins?.length
      ? payload.bins.map((b: any, i: number) => ({ ...b, label: xAxisLabels[i] }))
      : parseBinsFromXAxis(xAxisLabels);

    // room types
    const roomTypesFromPayload: string[] = payload?.stack_by_room_type
      ? Object.keys(payload.stack_by_room_type)
      : (option?.series || [])
          .filter((s: any) => s.type === 'bar')
          .map((s: any) => s.name);

    // cdf
    const cdf = payload?.cdf || ((option?.series || []).find((s: any) => s.type === 'line')?.data || []);

    return {
      bins: binsParsed,
      xLabels: xAxisLabels,
      allRoomTypes: roomTypesFromPayload,
      cdfSeries: cdf,
      globalStats: payload?.global_stats || {}
    };
  }, [chartData]);

  // initialize room types & bin strategy & budgetRange
  const BUDGET_MIN = 0;
  const BUDGET_MAX = 800;
  const [budgetRange, setBudgetRange] = useState<[number, number]>([BUDGET_MIN, BUDGET_MAX]);

  useEffect(() => {
    if (allRoomTypes && allRoomTypes.length) {
      setSelectedRoomTypes(allRoomTypes);
    }
  }, [allRoomTypes]);
  // listen to global loading events for price_distribution fetches
  useEffect(() => {
    const handler = (e: any) => {
      try {
        const flag = !!(e?.detail?.loading ?? e?.detail);
        setExternalLoading(flag);
      } catch {}
    };
    try { window.addEventListener('price_distribution:loading', handler as EventListener); } catch {}
    return () => { try { window.removeEventListener('price_distribution:loading', handler as EventListener); } catch {} };
  }, []);

  // Removed district/neighbourhood dropdown state updates; map handles area selection

  const totalCountsAcrossBins: number[] = useMemo(() => {
    // prefer structured counts_total, else compute from option bars
    const payload = chartData?.data || {};
    if (payload?.counts_total) return payload.counts_total;

    const option = chartData?.echarts_option || {};
    const barSeries = (option?.series || []).filter((s: any) => s.type === 'bar');
    if (!barSeries.length || !option?.xAxis?.data) return [];
    const len = option.xAxis.data.length;
    const totals = new Array(len).fill(0);
    barSeries.forEach((s: any) => {
      (s.data || []).forEach((v: number, i: number) => {
        totals[i] += Number.isFinite(v) ? v : 0;
      });
    });
    return totals;
  }, [chartData]);

  const grandTotal = useMemo(() => sum(totalCountsAcrossBins), [totalCountsAcrossBins]);

  // chart builder
  const buildOption = (): any => {
    const optionBase = JSON.parse(JSON.stringify(chartData?.echarts_option || {}));

    // labels
    optionBase.xAxis = optionBase.xAxis || {};
    optionBase.xAxis.data = xLabels || [];
    optionBase.xAxis.axisLine = { lineStyle: { color: '#bfbfbf', width: 1 } };
    optionBase.xAxis.axisTick = { alignWithLabel: true, length: 4 };
    optionBase.xAxis.axisLabel = { margin: 6 };

    // y axis config per mode
    optionBase.yAxis = [
      {
        type: 'value',
        name: yMode === 'count' ? 'Listings' : 'Share %',
        nameGap: 8,
        nameTextStyle: { color: '#8c8c8c', fontSize: 11 },
        axisLine: { lineStyle: { color: '#bfbfbf' } },
        axisTick: { show: false },
        axisLabel: yMode === 'count' 
          ? { show: true, color: '#595959' }
          : { show: true, formatter: '{value}%', color: '#595959' },
        splitLine: { lineStyle: { color: '#f0f0f0' } },
        max: yMode === 'count' ? undefined : 100
      },
      {
        type: 'value',
        name: 'Cumulative %',
        min: 0,
        max: 100,
        axisLine: { lineStyle: { color: '#bfbfbf' } },
        axisTick: { show: false },
        axisLabel: { formatter: '{value}%', color: '#8c8c8c' },
        splitLine: { show: false }
      }
    ];

    // compute per room type series
    const payload = chartData?.data || {};
    const stackData: Record<string, number[]> = payload?.stack_by_room_type
      ? payload.stack_by_room_type
      : (() => {
          const map: Record<string, number[]> = {};
          (chartData?.echarts_option?.series || [])
            .filter((s: any) => s.type === 'bar')
            .forEach((s: any) => {
              map[s.name] = s.data || [];
            });
          return map;
        })();

    // normalize room type selection
    const roomTypes = (selectedRoomTypes.length ? selectedRoomTypes : allRoomTypes).filter((t) => !!stackData[t]);

    const dataPerBinTotals = xLabels.map((_: any, i: number) => roomTypes.reduce((acc, t) => acc + (Number(stackData[t]?.[i]) || 0), 0));

    // helper: in-budget by bin index
    const isIndexInBudget = (idx: number) => {
      const b = bins?.[idx];
      if (!b) return false;
      return !(b.max < budgetRange[0] || b.min > budgetRange[1]);
    };

    const seriesBars = roomTypes.map((rt) => {
      const arr = (stackData[rt] || []).slice();
      const data = (yMode === 'count' ? arr : arr.map((v: number, i: number) => (dataPerBinTotals[i] ? Math.round((v / dataPerBinTotals[i]) * 100) : 0)))
        .map((v: number, i: number) => ({
          value: v,
          itemStyle: isIndexInBudget(i)
            ? { color: SAFE_COLORS[rt] || undefined, opacity: 1 }
            : { color: '#d9d9d9', opacity: 0.6 }
        }));
      return {
        type: 'bar',
        name: rt,
        stack: 'total',
        itemStyle: { color: SAFE_COLORS[rt] || undefined },
        barCategoryGap: '5%',
        barGap: '0%',
        data
      };
    });
    
    // CDF series
    const cdfData = (Array.isArray(cdfSeries) ? cdfSeries : []).slice();
    const seriesCDF = showCDF
      ? [
          {
            type: 'line',
            name: 'CDF',
            data: cdfData,
            yAxisIndex: 1,
            smooth: true,
            symbol: 'none',
            lineStyle: { color: '#333', width: 2 }
          }
        ]
      : [];

    optionBase.series = [...seriesBars, ...seriesCDF];

    // Title
    optionBase.title = {
      left: 'center',
      text: chartData?.title || 'Price Distribution (Stacked by Room Type)'
    };

    // Legend scroll
    optionBase.legend = { top: 30, type: 'scroll' };

    // Grid padding (reduced bottom to bring x-axis closer to slider)
    optionBase.grid = { top: 70, left: 64, right: 40, bottom: 40, containLabel: true };

    // Tooltip formatter with enhanced CDF explanation
    const totalsAll = totalCountsAcrossBins;
    optionBase.tooltip = {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        const idx = Array.isArray(params) && params.length ? params[0].dataIndex : 0;
        const b = bins?.[idx];

        const barParams = params.filter((p: any) => p.seriesType === 'bar');
        const cdfParam = params.find((p: any) => p.seriesName === 'CDF');
        const totalBin = barParams.reduce((acc: number, p: any) => acc + (Number(p.data?.value ?? p.data) || 0), 0);
        const share = grandTotal ? ((totalsAll[idx] || 0) / grandTotal) * 100 : 0;
        const cdfVal = typeof cdfParam?.data === 'number' ? cdfParam.data : (Array.isArray(cdfData) ? cdfData[idx] : undefined);

        // Price range title
        const title = b ? `${currency(b.min)} – ${currency(b.max)}` : xLabels[idx];
        const header = `<div style="font-weight:600;margin-bottom:6px;font-size:14px;">${title}</div>`;
        
        // CDF explanation (highlighted)
        let cdfExplanation = '';
        if (typeof cdfVal === 'number' && b) {
          const upperPrice = b.max === Number.POSITIVE_INFINITY ? '∞' : currency(b.max);
          cdfExplanation = `
            <div style="background:#f0f8ff;padding:6px;border-radius:4px;margin-bottom:6px;border-left:3px solid #1890ff;">
              <div style="font-weight:600;color:#1890ff;margin-bottom:2px;">📊 CDF: ${cdfVal.toFixed(1)}%</div>
              <div style="font-size:12px;color:#666;">
                <strong>${cdfVal.toFixed(1)}%</strong> of the listings are below ${upperPrice}
              </div>
            </div>
          `;
        }

        // Bar data summary
        const meta = `<div style="margin-bottom:6px;font-size:12px;">` +
          (yMode === 'count'
            ? `Total: <b>${totalBin}</b> (${share.toFixed(1)}% of all)`
            : `Bin share: <b>${totalBin}%</b> (${share.toFixed(1)}% of all)`) +
          `</div>`;

        // Room type breakdown
        const rows = barParams
          .map((p: any) => {
            const name = p.seriesName;
            const val = Number(p.data?.value ?? p.data) || 0;
            const shareRt = totalBin ? ((val / totalBin) * 100).toFixed(1) : '0.0';
            const marker = p.marker || '<span style="display:inline-block;margin-right:4px;width:8px;height:8px;background:#999;border-radius:50%;"></span>';
            return `<div style="margin-bottom:2px;">${marker}${name}: <b>${val}${yMode === 'percentage' ? '%' : ''}</b> (${shareRt}%)</div>`;
          })
          .join('');

        return header + cdfExplanation + meta + rows;
      }
    };

    // Median line only (no budget markArea/lines; dataZoom represents budget)
    if (typeof globalStats?.median === 'number' && optionBase.series.length) {
      const firstBarSeriesIndex = optionBase.series.findIndex((s: any) => s.type === 'bar');
      const applySeries = firstBarSeriesIndex >= 0 ? optionBase.series[firstBarSeriesIndex] : optionBase.series[0];
        const medianLabel = bins?.find((b: any) => globalStats.median >= b.min && globalStats.median <= b.max)?.label;
        if (medianLabel) {
        applySeries.markLine = {
          data: [
            { xAxis: medianLabel, lineStyle: { color: '#ff6b6b', type: 'dashed' }, label: { formatter: 'Median' } }
          ]
        };
        }
    }

    return optionBase;
  };

  // chart init and updates
  useEffect(() => {
    if (!chartRef.current) return;

    try {
      if (!chartData) {
        setRenderError('Chart data is missing');
        return;
      }
      
      if (!chartInstance.current) {
        chartInstance.current = echarts.init(chartRef.current);
      }
      
      const option = buildOption();
      chartInstance.current.setOption(option, true);
      setRenderError(null);

      const handleResize = () => chartInstance.current?.resize();
      window.addEventListener('resize', handleResize);
      return () => {
        window.removeEventListener('resize', handleResize);
      };
    } catch (err) {
      console.error('Chart rendering error:', err);
      setRenderError(`Error rendering chart: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [chartData, width, height, selectedRoomTypes, yMode, showCDF, budgetRange, bins]);

  // Modal resize handling
  useEffect(() => {
    if (modalVisible !== undefined && chartInstance.current) {
      const timer = setTimeout(() => {
        chartInstance.current?.resize();
        if (chartInstance.current) {
          const currentOption = chartInstance.current.getOption() as any;
          const xAxisData = currentOption?.xAxis?.[0]?.data;
          if (xAxisData && Array.isArray(xAxisData)) {
            const hasLongLabels = xAxisData.some((item: any) => typeof item === 'string' && item.length > 10);
            if (hasLongLabels) {
              chartInstance.current.setOption({ grid: { bottom: '18%' } });
            }
          }
        }
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [modalVisible]);

  // cleanup
  useEffect(() => {
    return () => {
      if (chartInstance.current) {
        chartInstance.current.dispose();
        chartInstance.current = null;
      }
    };
  }, []);

  // handlers
  const handleShowMap = () => {
    if (onShowMap) onShowMap({ context: 'price_distribution', suppressChatOnMapSelect: true });
  };

  // KPI card derived values / fallbacks (commented out unused variables)
  // const availableRoomTypesUI = allRoomTypes || [];
  // const coveragePct = typeof budgetStats?.coverage_pct === 'number' ? budgetStats.coverage_pct : (() => {
  //   if (!bins?.length || !totalCountsAcrossBins.length) return undefined;
  //   let total = 0;
  //   bins.forEach((b: any, i: number) => {
  //     const overlap = !(b.max < budgetRange[0] || b.min > budgetRange[1]);
  //     if (overlap) total += totalCountsAcrossBins[i] || 0;
  //   });
  //   return grandTotal ? (total / grandTotal) * 100 : undefined;
  // })();

  // render error
  if (renderError) {
    return (
      <div 
        style={{ 
          height: `${height}px`, 
          width: width,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f5f5f5',
          borderRadius: '4px',
          padding: '20px',
          textAlign: 'center'
        }} 
      >
        <div>
          <Text type="danger">{renderError}</Text>
          <div className="mt-2">
            <Text type="secondary" className="text-xs">
              {chartData?.title || 'Price chart'} cannot be displayed
            </Text>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ width: width }}>
      {/* Current selected area banner */}
      <div className="mb-1">
        {(() => {
          const area = (chartData as any)?.data?.area || (typeof window !== 'undefined' ? sessionStorage.getItem('selected_area') : null);
          return area ? (
            <div className="inline-flex items-center px-2 py-1 rounded bg-blue-50 border border-blue-200 text-blue-700 text-xs">
              <span style={{ marginRight: 6 }}>📍</span>
              <span>Area: {area}</span>
            </div>
          ) : null;
        })()}
      </div>
      {showControls && (
        <div className="flex flex-col gap-2 mb-2">
          <div className="flex justify-between items-center">
            <Space style={{ width: '100%' }} wrap>
              <Select value={yMode} onChange={(v) => setYMode(v)} style={{ width: 140 }}>
                <Option value="count">Y: Count</Option>
                <Option value="percentage">Y: Percentage</Option>
              </Select>
            </Space>
            <div className="flex items-center gap-2">
              <Tooltip title="Show all Berlin (no location filter)">
                <Button 
                  onClick={() => {
                    setExternalLoading(true);
                    onShowMap && onShowMap({ context: 'price_distribution', citywide: true, suppressChatOnMapSelect: true });
                  }}
                  size="small"
                  disabled={externalLoading}
                >
                  Citywide
                </Button>
              </Tooltip>
              <Tooltip title="Open Area Explorer">
                <Button 
                  icon={<EnvironmentOutlined />} 
                  onClick={() => { setExternalLoading(true); handleShowMap(); }}
                  type="primary"
                  size="small"
                  disabled={externalLoading}
                >
                  Map
                </Button>
              </Tooltip>
              {externalLoading && (
                <div className="flex items-center gap-1 pl-1">
                  <span className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full" />
                  <span className="text-xs text-blue-600 font-medium">Loading…</span>
                </div>
              )}
              <span className="text-xs text-gray-500">Open Area Explorer</span>
            </div>
          </div>
        </div>
      )}
      
      <div>
          <div 
            ref={chartRef} 
            style={{ 
              height: `${height}px`, 
              width: '100%',
              minHeight: '220px'
            }} 
          />
        </div>

      <div style={{ marginTop: 2, paddingLeft: 2, paddingRight: 8 }}>
        <Slider
          range
          min={BUDGET_MIN}
          max={BUDGET_MAX}
          value={budgetRange}
          onChange={(v: any) => {
            const [minV, maxV] = v as [number, number];
            setBudgetRange([
              Math.max(BUDGET_MIN, Math.min(minV, maxV)),
              Math.min(BUDGET_MAX, Math.max(minV, maxV))
            ]);
          }}
          tooltip={{ formatter: (v) => `€${v}` }}
          railStyle={{ height: 4, backgroundColor: '#e6f4ff' }}
          trackStyle={[{ height: 4, backgroundColor: '#69b1ff' }]}
          handleStyle={[
            { width: 16, height: 16, borderColor: '#69b1ff', backgroundColor: '#fff' },
            { width: 16, height: 16, borderColor: '#69b1ff', backgroundColor: '#fff' }
          ]}
        />
        <div className="flex items-center justify-between" style={{ marginTop: 8 }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <Text type="secondary" style={{ fontSize: 12, marginBottom: 4 }}>Minimum</Text>
            <InputNumber
              size="small"
              min={BUDGET_MIN}
              max={budgetRange[1]}
              value={budgetRange[0]}
              onChange={(val) => {
                const v = typeof val === 'number' ? val : BUDGET_MIN;
                setBudgetRange([Math.min(Math.max(BUDGET_MIN, v), budgetRange[1]), budgetRange[1]]);
              }}
              formatter={(value) => `€${value}`}
              parser={(value) => Number(String(value).replace(/€\s?|,/g, ''))}
              style={{ borderRadius: 16, width: 100 }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
            <Text type="secondary" style={{ fontSize: 12, marginBottom: 4 }}>Maximum</Text>
            <InputNumber
              size="small"
              min={budgetRange[0]}
              max={BUDGET_MAX}
              value={budgetRange[1]}
              onChange={(val) => {
                const v = typeof val === 'number' ? val : BUDGET_MAX;
                setBudgetRange([budgetRange[0], Math.max(Math.min(BUDGET_MAX, v), budgetRange[0])]);
              }}
              formatter={(value) => `€${value}${Number(value) >= BUDGET_MAX ? '+' : ''}`}
              parser={(value) => Number(String(value).replace(/€\s?|\+/g, ''))}
              style={{ borderRadius: 16, width: 100 }}
            />
          </div>
        </div>
      </div>

      {showCDF && (
        <div style={{ marginTop: 10 }}>
          <Text strong style={{ fontSize: 13, lineHeight: 1.6, color: '#333' }}>
            CDF (Cumulative Distribution Function) shows the share of the market priced at or below a given price. Read it like this: if the CDF at a price is x%, then x% of all listings are priced at that level or lower. This helps you judge budget coverage and the boundary price at a glance.
          </Text>
        </div>
      )}
    </div>
  );
};

export default PriceDistribution; 