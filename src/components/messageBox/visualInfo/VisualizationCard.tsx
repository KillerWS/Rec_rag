import React, { useState, useEffect, useRef } from 'react';
import { Modal, Button, Card, Spin, Tag } from 'antd';
import { 
  BarChartOutlined, 
  PieChartOutlined, 
  AreaChartOutlined,
  ExpandOutlined,
  EyeOutlined,
  CloseOutlined 
} from '@ant-design/icons';
import * as echarts from 'echarts';
import PriceDistributionBar from '../../eCharts/PriceDistribution';
import DistancePriceTradeoff from '../../eCharts/DistancePriceTradeoff';
import LocationPopularity from '../../eCharts/LocationPopularity';
import { WordCloud } from '../../eCharts/wordcloud';
import ReviewAnalysis from '../../eCharts/ReviewAnalysis';
import PriceCoverageDelta from '../../eCharts/PriceCoverageDelta';
import RoomTypeBoxplot from '../../eCharts/RoomTypeBoxplot';
import ValueQualityQuadrant from '../../eCharts/ValueQualityQuadrant';

// 🎯 前端组件使用的数据类型
interface ChartData {
  type: 'bar' | 'pie' | 'line' | 'scatter' | 'wordcloud';
  title: string;
  data: any;
  options?: any;
  description?: string;
  echarts_option?: any;
}

interface VisualizationData {
  visualizations: {
    [key: string]: ChartData;
  };
  chart_suggestions?: string[];
  visualization_message?: string;
  user_budget_info?: {
    min_price?: number;
    max_price?: number;
    currency?: string;
  };
  reason?: string;
  priority?: 'high' | 'medium' | 'low';
}

interface VisualizationCardProps {
  visualizationData: VisualizationData;
  isVisible?: boolean;
  onToggleVisibility?: () => void;
  onDistrictSelect?: (district: string, neighborhood?: string) => void;
  onShowMap?: (payload: any) => void;
  selectedDimensions?: any[];
  onSendMessage?: (message: string) => void; // 🆕 用于发送刷新请求
}

// 🎯 图表类型图标映射
const getChartIcon = (type: string) => {
  switch (type) {
    case 'bar': return <BarChartOutlined />;
    case 'pie': return <PieChartOutlined />;
    case 'line': return <AreaChartOutlined />;
    default: return <BarChartOutlined />;
  }
};

// 🎯 图表类型颜色映射
const getChartColor = (type: string) => {
  switch (type) {
    case 'bar': return '#1890ff';
    case 'pie': return '#52c41a';
    case 'line': return '#faad14';
    default: return '#1890ff';
  }
};

// 🎯 单个图表组件
const ChartRenderer: React.FC<{
  chartData: ChartData;
  height?: number;
  width?: string;
  modalVisible?: boolean; 
  onDistrictSelect?: (district: string, neighborhood?: string) => void;
  onShowMap?: (payload: any) => void;
  showControls?: boolean;
  selectedDimensions?: any[];
  onSendMessage?: (message: string) => void;
}> = ({ chartData, height = 300, width = '100%', modalVisible, onDistrictSelect, onShowMap, showControls, selectedDimensions, onSendMessage }) => {
  // 检查是否是价格分布柱状图 - 在任何hooks之前进行检查
  const isPriceDistributionBar = (
    // 优先：测试接口顶层或常见字段中的 chart_type 标识
    (chartData as any)?.chart_type === 'price_distribution' ||
    chartData?.data?.chart_type === 'price_distribution' ||
    chartData?.options?.chart_type === 'price_distribution' ||
    chartData?.echarts_option?.chart_type === 'price_distribution' ||
    // 兼容：直接使用 type 标识
    chartData?.data?.type === 'price_distribution' ||
    chartData?.options?.type === 'price_distribution' ||
    // 回退：旧版通过标题+类型(histogram)识别
    (chartData?.options?.title === 'Price Distribution Analysis' && 
     chartData?.options?.type === 'histogram')
  );
  
  // 如果是价格分布柱状图，使用专门的组件
  if (isPriceDistributionBar) {
    return (
      <PriceDistributionBar
        chartData={chartData}
        height={height}
        width={width}
        modalVisible={modalVisible}
        onDistrictSelect={onDistrictSelect}
        onShowMap={onShowMap}
        // 缩略图中不显示控件，节省空间
        showControls={showControls !== undefined ? showControls : height > 100}
      />
    );
  }

  // 新增：location_popularity 专用组件（通过标题或类型识别）
  const isLocationPopularity = 
    (chartData?.options?.title || chartData?.title || chartData?.echarts_option?.title?.text || '')
      .toLowerCase().includes('location popularity')
    || chartData?.options?.type === 'location_popularity'
    || chartData?.data?.type === 'location_popularity';

  if (isLocationPopularity) {
    return (
      <LocationPopularity
        chartData={chartData}
        height={height}
        width={width}
        modalVisible={modalVisible}
        onRefreshRequest={onSendMessage ? async () => {
          // 发送请求全局数据的消息
          onSendMessage("Which districts are the most popular for Airbnb stays in all Berlin?");
        } : undefined}
      />
    );
  }

  // 新增：词云组件识别（通过类型或标题关键字）
  const isWordCloud = (
    chartData?.type === 'wordcloud' ||
    chartData?.options?.type === 'wordcloud' ||
    (chartData?.options?.title || chartData?.title || chartData?.echarts_option?.title?.text || '')
      .toLowerCase().includes('word cloud')
  );

  if (isWordCloud) {
    return (
      <WordCloud
        chartData={chartData}
        height={height}
        width={width}
        modalVisible={modalVisible}
        showControls={showControls !== undefined ? showControls : height > 100}
      />
    );
  }

  // 新增：房型比较（room_type_comparison）专用组件（箱线图）
  const isRoomTypeComparison = (
    (chartData?.options?.type === 'room_type_comparison') ||
    (chartData?.data?.type === 'room_type_comparison') ||
    String(chartData?.title || chartData?.options?.title || chartData?.echarts_option?.title?.text || '')
      .toLowerCase()
      .includes('room type comparison')
  );

  if (isRoomTypeComparison) {
    // 适配后端 echarts_option 或 data.items 到 RoomTypeBoxplot 需要的数据结构
    const toNumber = (v: any) => (v != null ? Number(v) : null);
    const rows = (() => {
      // 1) 直接提供的 items
      const items = (chartData as any)?.data?.items;
      if (Array.isArray(items) && items.length > 0) {
        return items.map((it: any) => ({
          room_type: String(it.room_type || it.name || it.label || ''),
          min: Number(it.min ?? (it.stats?.min ?? 0)),
          q1: Number(it.q1 ?? (it.stats?.q1 ?? 0)),
          median: Number(it.median ?? (it.stats?.median ?? 0)),
          q3: Number(it.q3 ?? (it.stats?.q3 ?? 0)),
          max: Number(it.max ?? (it.stats?.max ?? 0)),
          p95: it.p95 != null ? Number(it.p95) : undefined,
          n: it.n != null ? Number(it.n) : undefined,
        }));
      }
      // 2) 从 echarts_option 提取（xAxis.data + series[0].data 形如 [min,q1,median,q3,max]）
      const xo = (chartData as any)?.echarts_option || {};
      // 2a) 优先尝试 dataset.source（对象列表或二维数组）
      if (xo?.dataset && xo.dataset.source) {
        const src = xo.dataset.source;
        // 对象数组形式
        if (Array.isArray(src) && src.length > 0 && typeof src[0] === 'object' && !Array.isArray(src[0])) {
          const out: any[] = [];
          (src as any[]).forEach((row: any) => {
            const rt = row.room_type || row.name || row.label;
            const min = row.min ?? row.p0;
            const q1 = row.q1 ?? row.p25;
            const median = row.median ?? row.p50;
            const q3 = row.q3 ?? row.p75;
            const max = row.max ?? row.p100;
            if (rt != null && [min,q1,median,q3,max].some((v) => v != null)) {
              out.push({
                room_type: String(rt),
                min: Number(min ?? 0),
                q1: Number(q1 ?? min ?? 0),
                median: Number(median ?? q1 ?? min ?? 0),
                q3: Number(q3 ?? median ?? q1 ?? min ?? 0),
                max: Number(max ?? q3 ?? median ?? q1 ?? min ?? 0),
                p95: row.p95 != null ? Number(row.p95) : undefined,
                n: row.n != null ? Number(row.n) : undefined,
              });
            }
          });
          if (out.length > 0) return out;
        }
        // 二维数组形式，首行可能是表头
        if (Array.isArray(src) && Array.isArray(src[0])) {
          const header = (src as any[])[0] as any[];
          const hasHeader = header.some((h: any) => typeof h === 'string');
          if (hasHeader) {
            const idx = (name: string) => header.findIndex((h: any) => String(h).toLowerCase() === name);
            const iRt = idx('room_type') >= 0 ? idx('room_type') : 0;
            const iMin = idx('min');
            const iQ1 = idx('q1');
            const iMed = idx('median');
            const iQ3 = idx('q3');
            const iMax = idx('max');
            const out: any[] = [];
            (src as any[]).slice(1).forEach((row: any[]) => {
              const rt = row[iRt];
              if (rt == null) return;
              const min = iMin >= 0 ? row[iMin] : undefined;
              const q1 = iQ1 >= 0 ? row[iQ1] : undefined;
              const median = iMed >= 0 ? row[iMed] : undefined;
              const q3 = iQ3 >= 0 ? row[iQ3] : undefined;
              const max = iMax >= 0 ? row[iMax] : undefined;
              if ([min,q1,median,q3,max].some((v) => v != null)) {
                out.push({
                  room_type: String(rt),
                  min: Number(min ?? 0),
                  q1: Number(q1 ?? min ?? 0),
                  median: Number(median ?? q1 ?? min ?? 0),
                  q3: Number(q3 ?? median ?? q1 ?? min ?? 0),
                  max: Number(max ?? q3 ?? median ?? q1 ?? min ?? 0),
                });
              }
            });
            if (out.length > 0) return out;
          }
        }
      }
      const categories: any[] = Array.isArray(xo?.xAxis?.data) ? xo.xAxis.data :
        (Array.isArray(xo?.xAxis) && Array.isArray(xo?.xAxis[0]?.data) ? xo.xAxis[0].data : []);
      const seriesArr: any[] = Array.isArray(xo?.series) ? xo.series : [];
      const boxSeries = seriesArr.find((s: any) => String(s?.type).toLowerCase() === 'boxplot') || seriesArr[0];
      const dataArr: any[] = Array.isArray(boxSeries?.data) ? boxSeries.data : [];
      if (categories.length > 0 && dataArr.length > 0) {
        return categories.map((name: any, idx: number) => {
          const raw = dataArr[idx];
          const vals: any[] = Array.isArray(raw?.value) ? raw.value : (Array.isArray(raw) ? raw : []);
          return {
            room_type: String(name),
            min: Number(toNumber(vals[0]) || 0),
            q1: Number(toNumber(vals[1]) || 0),
            median: Number(toNumber(vals[2]) || 0),
            q3: Number(toNumber(vals[3]) || 0),
            max: Number(toNumber(vals[4]) || 0),
          };
        });
      }
      // 2b) 回退：如果是 bar 图（只有一个值，例如 median），构造等值的五数概括
      if (categories.length > 0 && seriesArr.length > 0) {
        const firstSeries = seriesArr[0];
        const vals: any[] = Array.isArray(firstSeries?.data) ? firstSeries.data : [];
        if (vals.length === categories.length) {
          return categories.map((name: any, idx: number) => {
            const v = Number((typeof vals[idx] === 'object' && vals[idx] && 'value' in vals[idx]) ? (vals[idx] as any).value : vals[idx]) || 0;
            return {
              room_type: String(name),
              min: v,
              q1: v,
              median: v,
              q3: v,
              max: v,
            };
          });
        }
      }
      return [] as any[];
    })();

    return (
      <RoomTypeBoxplot
        data={rows}
        onOpenHeatmap={(p: { room_type: string }) => {
          // 复用 onShowMap 回调；此处传入房型名称字符串即可打开地图（上游不会严格使用该值）
          onShowMap?.(p?.room_type as any);
        }}
        height={height}
      />
    );
  }

  // 新增：性价比四象限（value_quality_quadrant）专用组件
  const isValueQualityQuadrant = (
    chartData?.options?.type === 'value_quality_quadrant' ||
    chartData?.data?.type === 'value_quality_quadrant' ||
    (chartData?.title || chartData?.options?.title || chartData?.echarts_option?.title?.text || '')
      .toString().toLowerCase().includes('value quality quadrant')
  );

  if (isValueQualityQuadrant) {
    const model = (chartData as any)?.data?.model || null; // 允许后端直接传模型；否则组件使用内置 mock
    const vqOption = (chartData as any)?.echarts_option || undefined;
    return (
      <ValueQualityQuadrant
        model={model}
        echartsOption={vqOption}
        height={height}
        onRequestMapSelect={(area) => {
          // 打开地图组件，带上上下文，抑制聊天
          try {
            // Signal with rich payload
            (window as any).decisionScope = { area_name: area || null };
          } catch {}
          onShowMap?.({ context: 'value_quality_quadrant', suppressChatOnMapSelect: true, area: area || 'ALL' });
        }}
        onOpenHeatmap={(payload) => onShowMap?.((payload?.listing_id ?? null) as any)}
      />
    );
  }

  // 新增：评论分析复合图（词云 + 情感 + 关键词）
  const isReviewAnalysis = (
    String(chartData?.options?.type || '').toLowerCase() === 'reviews_analysis' ||
    String(chartData?.type || '').toLowerCase() === 'reviews analysis' ||
    ((chartData?.options?.title || chartData?.title || chartData?.echarts_option?.title?.text || '')
      .toLowerCase().includes('reviews analysis'))
  );

  if (isReviewAnalysis) {
    return (
      <ReviewAnalysis
        chartData={chartData}
        height={height}
        width={width}
        modalVisible={modalVisible}
        onShowMap={(payload) => {
          // 特殊入口：Reviews Analysis 打开地图，仅本地选择
          console.log('🟡 [VisualizationCard] ReviewAnalysis 打开地图', { payload });
          const extra = (payload && typeof payload === 'object')
            ? payload
            : (payload ? { area: payload } : {});
          const mapPayload = { context: 'reviews_analysis', suppressChatOnMapSelect: true, suppressDimensionUpdate: true, ...extra };
          console.log('🟡 [VisualizationCard] 调用 onShowMap，payload=', mapPayload);
          onShowMap?.(mapPayload);
        }}
        selectedDimensions={selectedDimensions}
      />
    );
  }

  // 已移除：Reviews Time Series 支持

  // 新增：预算变化的边际收益（price_coverage_delta）
  const isPriceCoverageDelta = (
    chartData?.options?.type === 'price_coverage_delta' ||
    String(chartData?.type) === 'price_coverage_delta' ||
    (chartData?.title || chartData?.options?.title || chartData?.echarts_option?.title?.text || '')
      .toString()
      .toLowerCase()
      .includes('coverage')
  );

  if (isPriceCoverageDelta) {
    return (
      <PriceCoverageDelta
        echartsOption={chartData?.echarts_option}
        initialMin={Number((chartData as any)?.options?.price_min || 60)}
        initialMax={Number((chartData as any)?.options?.price_max || 120)}
        subtitle={(chartData as any)?.description}
      />
    );
  }

  // 只有在不是价格分布/位置热度图/词云的情况下才定义这些hooks
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  // 主要的图表初始化
  useEffect(() => {
    if (!chartRef.current) return;

    try {
      // 数据验证
      if (!chartData || !chartData.type) {
        setRenderError("Chart data is incomplete");
        return;
      }
      
      // 初始化图表
      if (!chartInstance.current) {
        chartInstance.current = echarts.init(chartRef.current);
      }
      
      // 设置图表配置
      const option = createChartOption(chartData);
      chartInstance.current.setOption(option);
      
      // 成功渲染，清除错误
      setRenderError(null);

      // 处理窗口大小变化
      const handleResize = () => {
        chartInstance.current?.resize();
      };
      
      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
      };
    } catch (error) {
      console.error("Chart rendering error:", error);
      setRenderError(`Error rendering chart: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  }, [chartData]);

  // Modal可见性变化时触发resize
  useEffect(() => {
    
    // 当Modal打开/关闭时，强制调整图表大小
    if (modalVisible !== undefined && chartInstance.current) {
      // 使用setTimeout确保在Modal动画完成后调整大小
      const timer = setTimeout(() => {
        chartInstance.current?.resize();
        
        // 特殊处理：增加对长标签的处理，动态调整底部边距
        if (chartInstance.current && chartData.type === 'bar') {
          const currentOption = chartInstance.current.getOption() as any;
          const xAxisData = currentOption?.xAxis?.[0]?.data;
          
          if (xAxisData && Array.isArray(xAxisData)) {
            // 检测是否有长标签
            const hasLongLabels = xAxisData.some(
              (item: any) => typeof item === 'string' && item.length > 10
            );
            
            if (hasLongLabels) {
              // 调整网格底部空间
              chartInstance.current.setOption({
                grid: { 
                  bottom: '18%' // 增加底部空间以适应长标签
                }
              });
            }
          }
        }
      }, 300);
      
      return () => clearTimeout(timer);
    }
  }, [modalVisible, chartData]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      // 只在组件卸载时释放图表实例
      if (chartInstance.current) {
        chartInstance.current.dispose();
        chartInstance.current = null;
      }
    };
  }, []);

  // 🎯 创建图表配置 - 优先使用后端的echarts_option
  const createChartOption = (data: ChartData) => {
    // 如果后端提供了完整的 echarts_option，直接使用
    if (data.echarts_option) {
      return data.echarts_option;
    }

    // 否则使用前端的默认配置
    const baseOption = {
      title: {
        text: data.title,
        left: 'center',
        textStyle: {
          fontSize: 14,
          fontWeight: 'bold'
        }
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        textStyle: {
          color: '#fff'
        }
      },
      grid: {
        left: '10%',
        right: '10%',
        bottom: '15%',
        top: '20%',
        containLabel: true
      }
    };

    switch (data.type) {
      case 'bar':
        return {
          ...baseOption,
          xAxis: {
            type: 'category',
            data: data.data.categories || [],
            axisLabel: {
              rotate: 45,
              fontSize: 10
            }
          },
          yAxis: {
            type: 'value'
          },
          series: [{
            data: data.data.values || [],
            type: 'bar',
            itemStyle: {
              color: '#1890ff'
            }
          }]
        };

      case 'pie':
        return {
          ...baseOption,
          tooltip: {
            trigger: 'item',
            formatter: '{a} <br/>{b} : {c} ({d}%)'
          },
          series: [{
            name: data.title,
            type: 'pie',
            radius: '50%',
            data: data.data.items || [],
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)'
              }
            }
          }]
        };

      case 'line':
        return {
          ...baseOption,
          xAxis: {
            type: 'category',
            data: data.data.categories || []
          },
          yAxis: {
            type: 'value'
          },
          series: [{
            data: data.data.values || [],
            type: 'line',
            smooth: true,
            itemStyle: {
              color: '#faad14'
            }
          }]
        };

      default:
        return baseOption;
    }
  };

  // 显示错误状态
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
          <span style={{ color: '#ff4d4f' }}>{renderError}</span>
          <div className="mt-2">
            <span className="text-xs text-gray-500">
              {chartData?.title || 'Chart'} cannot be displayed
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div 
      ref={chartRef} 
      style={{ 
        height: `${height}px`, 
        width: width,
        minHeight: `${height}px`,
        maxHeight: `${height}px`,
        overflow: 'hidden'
      }} 
    />
  );
};

// 🎯 主组件
const VisualizationCard: React.FC<VisualizationCardProps> = ({
  visualizationData,
  isVisible = true,
  onToggleVisibility,
  onDistrictSelect,
  onShowMap,
  selectedDimensions,
  onSendMessage
}) => {
  console.log("visualizationData", visualizationData);
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedChart, setSelectedChart] = useState<string | null>(null);
  const [loading] = useState(false);
  const [tradeoffVisible, setTradeoffVisible] = useState(false);
  const [tradeoffPrefs, setTradeoffPrefs] = useState<any | undefined>(undefined);
  // const [selectedDistrict, setSelectedDistrict] = useState<string>("All");

  const isDistancePriceTradeoff = (cd?: ChartData) => {
    if (!cd) return false;
    const t = (cd.title || cd.options?.title || cd.echarts_option?.title?.text || '').toLowerCase();
    return t.includes('distance-price tradeoff') || t.includes('distance vs price tradeoff');
  };

  // 处理区域选择
  const handleDistrictSelect = (district: string, neighborhood?: string) => {
    if (onDistrictSelect) {
      onDistrictSelect(district, neighborhood);
    }
  };

  // 处理地图显示
  const handleShowMap = (district: string) => {
    if (onShowMap) {
      onShowMap(district);
    }
  };

  // 🎯 获取图表列表
  const chartEntries = Object.entries(visualizationData.visualizations || {});
  const hasCharts = chartEntries.length > 0;

  // 🎯 处理图表点击
  const handleChartClick = (chartKey: string) => {
    const cd = visualizationData.visualizations[chartKey] as ChartData;
    if (isDistancePriceTradeoff(cd)) {
      // 打开专用的 Distance-Price Tradeoff 组件
      const budget = visualizationData.user_budget_info || {};
      setTradeoffPrefs({
        price_min: budget.min_price,
        price_max: budget.max_price
      });
      setTradeoffVisible(true);
      setSelectedChart(null);
      setModalVisible(false);
      return;
    }
    setSelectedChart(chartKey);
    setModalVisible(true);
  };

  // 🎯 处理Modal关闭
  const handleModalClose = () => {
    setModalVisible(false);
    setSelectedChart(null);
  };

  // 🎯 渲染优先级标签
  const renderPriorityTag = () => {
    if (!visualizationData.priority) return null;

    const colors = {
      high: 'red',
      medium: 'orange',
      low: 'blue'
    };

    return (
      <Tag color={colors[visualizationData.priority]}>
        {visualizationData.priority.toUpperCase()}
      </Tag>
    );
  };

  // 🎯 渲染预算信息
  const renderBudgetInfo = () => {
    const budget = visualizationData.user_budget_info;
    if (!budget || (!budget.min_price && !budget.max_price)) return null;

    return (
      <div className="mb-2 p-2 bg-blue-50 rounded-lg text-xs text-gray-600">
        💰 Budget Range: {budget.currency || '$'}
        {budget.min_price || '0'} - {budget.currency || '$'}
        {budget.max_price || '∞'}
      </div>
    );
  };

  // 🎯 渲染缩略图网格
  const renderThumbnailGrid = () => {
    if (!hasCharts) return null;

    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {chartEntries.map(([key, chartData]) => (
          <Card
            key={key}
            size="small"
            className="cursor-pointer hover:shadow-md transition-shadow duration-200"
            onClick={() => handleChartClick(key)}
            bodyStyle={{ padding: '8px' }}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                {getChartIcon(chartData.type)}
                <span className="text-xs truncate font-semibold" style={{ maxWidth: '150px' }}>
                  {chartData.title}
                </span>
              </div>
              <Button
                type="text"
                size="small"
                icon={<ExpandOutlined />}
                className="text-gray-400 hover:text-blue-500"
              />
            </div>
            
            {/* 缩略图区域 - 修改：确保PriceDistributionBar控件在缩略图中显示 */}
            <div className="h-24 bg-gray-50 rounded flex items-center justify-center" style={{ overflow: 'hidden' }}>
              <ChartRenderer 
                chartData={{
                  ...chartData,
                  // 在缩略图中不显示标题和graphic预算标记
                  echarts_option: chartData.echarts_option ? {
                    ...chartData.echarts_option,
                    title: {
                      ...chartData.echarts_option.title,
                      show: false
                    },
                    // 隐藏预算graphic元素
                    graphic: chartData.echarts_option.graphic ? 
                      chartData.echarts_option.graphic.map((g: any) => ({...g, invisible: true})) : 
                      undefined
                  } : undefined
                }} 
                height={80} 
                width="100%"
                onDistrictSelect={handleDistrictSelect}
                onShowMap={handleShowMap}
                selectedDimensions={selectedDimensions}
                onSendMessage={onSendMessage}
              />
            </div>
            
            {chartData.description && (
              <span className="text-xs mt-1 block truncate text-gray-500">
                {chartData.description}
              </span>
            )}
          </Card>
        ))}
      </div>
    );
  };

  if (!isVisible || !hasCharts) {
    return null;
  }

  return (
    <div className="mt-3 w-full">
      {/* 🎯 可视化消息头部 */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="text-sm font-semibold">
            {visualizationData.visualization_message || '📊 Data Visualization'}
          </span>
          {renderPriorityTag()}
        </div>
        
        {onToggleVisibility && (
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={onToggleVisibility}
            className="text-gray-400 hover:text-blue-500"
          />
        )}
      </div>

      {/* 🎯 预算信息 */}
      {renderBudgetInfo()}

      {/* 🎯 图表建议标签 */}
      {visualizationData.chart_suggestions && (
        <div className="mb-2 flex flex-wrap gap-1">
          {visualizationData.chart_suggestions.map((suggestion, index) => (
            <Tag key={index} color="blue" className="text-xs">
              {suggestion}
            </Tag>
          ))}
        </div>
      )}

      {/* 🎯 缩略图网格 */}
      {renderThumbnailGrid()}

      {/* 🎯 全图Modal */}
      <Modal
        title={null} // 移除默认标题，使用自定义标题
        open={modalVisible}
        onCancel={handleModalClose}
        afterOpenChange={(visible) => {
          // 在Modal打开后，强制更新一次布局以确保图表正确显示
          if (visible && selectedChart) {
            setTimeout(() => {
              window.dispatchEvent(new Event('resize'));
            }, 100);
          }
        }}
        footer={[
          <Button key="close" onClick={handleModalClose}>
            Close
          </Button>
        ]}
        width={800}
        style={{ top: 20 }}
        bodyStyle={{ 
          padding: '0',  // 移除默认padding
          maxHeight: '80vh',
          overflowY: 'auto'
        }}
        closeIcon={<CloseOutlined style={{ color: '#fff' }} />}
        className="visualization-modal"
      >
        {selectedChart && visualizationData.visualizations[selectedChart] && (
          <div style={{ width: '100%' }}>
            {/* 自定义标题区域 */}
            <div className="p-4 border-b flex items-center justify-between" 
                 style={{ background: getChartColor(visualizationData.visualizations[selectedChart].type), color: 'white' }}>
              <div className="flex items-center space-x-2">
                {getChartIcon(visualizationData.visualizations[selectedChart]?.type)}
                <span className="font-medium">
                  {visualizationData.visualizations[selectedChart]?.title}
                </span>
              </div>
              <Button 
                type="text" 
                icon={<CloseOutlined />} 
                onClick={handleModalClose}
                style={{ color: 'white' }}
              />
            </div>
            
            {/* 图表内容区域 */}
            <div className="p-5">
              <ChartRenderer 
                chartData={{
                  ...visualizationData.visualizations[selectedChart],
                  // 修复：当在Modal中显示时，移除图表自身的标题和调整预算标记位置
                  echarts_option: visualizationData.visualizations[selectedChart].echarts_option ? (() => {
                    const original = visualizationData.visualizations[selectedChart].echarts_option;
                    const enhanceAxisLabel = (axis: any) => ({
                      ...(axis?.axisLabel || {}),
                      rotate: 45,
                      fontSize: 11,
                      margin: 10,
                      interval: 0,
                      formatter: (value: any) => {
                        const maxLength = 12;
                        if (value && typeof value === 'string' && value.length > maxLength) {
                          return value.substring(0, maxLength) + '...';
                        }
                        return value;
                      }
                    });
                    const enhancedXAxis = Array.isArray(original.xAxis)
                      ? original.xAxis.map((ax: any) => ({ ...ax, axisLabel: enhanceAxisLabel(ax) }))
                      : (original.xAxis ? { ...original.xAxis, axisLabel: enhanceAxisLabel(original.xAxis) } : original.xAxis);
                    const enhancedGrid = Array.isArray(original.grid)
                      ? original.grid
                      : { ...(original.grid || {}), bottom: '15%', containLabel: true };
                    const enhancedGraphic = original.graphic
                      ? original.graphic.map((g: any) => {
                          if (g.style && typeof g.style.text === 'string' && g.style.text.includes('Your Budget:')) {
                            return { ...g, left: 'center', top: '5%', style: { ...g.style, fontSize: 13 } };
                          }
                          return g;
                        })
                      : undefined;
                    return {
                      ...original,
                      title: { ...(original.title || {}), show: false },
                      xAxis: enhancedXAxis,
                      grid: enhancedGrid,
                      graphic: enhancedGraphic
                    };
                  })() : undefined
                }}
                height={400}
                width="100%"
                modalVisible={modalVisible}
                onDistrictSelect={handleDistrictSelect}
                onShowMap={handleShowMap}
                // 在全尺寸视图中显示控件
                showControls={true}
                selectedDimensions={selectedDimensions}
                onSendMessage={onSendMessage}
              />
              
              {visualizationData.visualizations[selectedChart].description && (
                <div className="mt-4 p-3 bg-gray-50 rounded-lg">
                  <span className="text-gray-600">
                    {visualizationData.visualizations[selectedChart].description}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* 专用 Distance-Price Tradeoff 弹窗 */}
      <DistancePriceTradeoff
        visible={tradeoffVisible}
        onClose={() => setTradeoffVisible(false)}
        preferences={tradeoffPrefs}
      />
      
      {/* 移除jsx global样式，改为使用CSS类 */}
      <style>{`
        /* 全局样式通过类选择器应用 */
        .visualization-modal .ant-modal-close {
          top: 10px;
          right: 10px;
        }
        
        .visualization-modal .ant-modal-footer {
          border-top: none;
          padding: 10px 16px;
        }
      `}</style>

      {/* 🎯 加载状态 */}
      {loading && (
        <div className="text-center py-4 text-xs text-gray-500">
          <Spin size="small" />
          <span className="ml-2">Loading visualization...</span>
        </div>
      )}
    </div>
  );
};

export default VisualizationCard;