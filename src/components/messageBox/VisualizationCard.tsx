import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { Button, Modal, Card, Spin, Tag, Tooltip } from 'antd';
import { 
  ExpandOutlined, 
  CloseOutlined, 
  BarChartOutlined,
  BulbOutlined,
  InfoCircleOutlined,
  DatabaseOutlined,
  FilterOutlined
} from '@ant-design/icons';
import * as echarts from 'echarts';

// Types
interface VisualizationMetadata {
  total_records?: number;
  most_common_range?: string;
  avg_price_overall?: number;
}

interface ChartConfig {
  title?: string;
}

interface VisualizationData {
  visualizations?: Record<string, {
    chart_type?: string;
    data?: {
      categories?: string[];
      values?: (number | { value: number; avgPrice?: number })[];
      additional_metrics?: {
        avg_prices?: number[];
      };
    };
    echarts_option?: any;
    chart_config?: ChartConfig;
    metadata?: VisualizationMetadata;
  }>;
  visualization_filters?: Record<string, any>;
}

interface VizDataType {
  key: string;
  chart_type?: string;
  data?: {
    categories?: string[];
    values?: (number | { value: number; avgPrice?: number })[];
    additional_metrics?: {
      avg_prices?: number[];
    };
  };
  echarts_option?: any;
  chart_config?: ChartConfig;
  metadata?: VisualizationMetadata;
}

interface VisualizationCardProps {
  visualizationData?: VisualizationData;
  isVisible: boolean;
  onToggleVisibility: () => void;
  compact?: boolean;
  showProcess?: boolean;
}

const VisualizationCard: React.FC<VisualizationCardProps> = ({ 
  visualizationData, 
  isVisible, 
  onToggleVisibility,
  compact = false, 
  showProcess = false, 
}) => {
  const [modalVisible, setModalVisible] = useState<boolean>(false);
  const chartRef = useRef<HTMLDivElement>(null);
  const modalChartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);
  const modalChartInstanceRef = useRef<echarts.ECharts | null>(null);
  const [chartReady, setChartReady] = useState<boolean>(false);
  const [modalChartReady, setModalChartReady] = useState<boolean>(false);

  // Parse visualization data
  const vizData = useMemo<VizDataType | null>(() => {
    if (!visualizationData?.visualizations) return null;
    const firstKey = Object.keys(visualizationData.visualizations)[0];
    return firstKey ? { key: firstKey, ...visualizationData.visualizations[firstKey] } : null;
  }, [visualizationData]);

  // Generate smart explanation for visualization
  const generateSmartExplanation = useCallback((data: VizDataType | null, vizData?: VisualizationData) => {
    if (!data) return '';
    
    const base = `I analyzed ${data.metadata?.total_records?.toLocaleString() || 'available'} Airbnb listings`;
    const chartType = data?.chart_type || '';
    const filters = vizData?.visualization_filters || {};
    const hasFilters = Object.keys(filters).length > 0;
    
    const explanations: Record<string, string> = {
      'price_distribution': `${base}${hasFilters ? ' with your preferences applied' : ''} and created a bar chart to show how listings are distributed across different price ranges. The chart reveals that ${data.metadata?.most_common_range || 'a specific range'} has the highest concentration of properties, which I've highlighted in red to draw your attention.`,
      
      'location_distribution': `${base}${hasFilters ? ' matching your criteria' : ''} and mapped them geographically to show where most properties are located. This helps identify the most popular neighborhoods and their pricing patterns.`,
      
      'room_type_distribution': `${base}${hasFilters ? ' within your search parameters' : ''} and broke them down by room type using a pie chart. This gives you a clear view of what types of accommodations are most available.`,
      
      'time_trend': `${base}${hasFilters ? ' based on your filters' : ''} and created a timeline to show how availability and pricing change over time.`
    };
    
    return explanations[chartType] || `${base}${hasFilters ? ' with applied filters' : ''} and created a visualization to help you understand the data patterns. The highlighted elements show the most significant findings.`;
  }, []);

  // Create chart option configuration
  const createChartOption = useCallback((data: VizDataType | null, isModal = false) => {
    if (!data || (!data.echarts_option && !data.data)) return null;

    let baseOption = data.echarts_option ? { ...data.echarts_option } : {
      title: { text: data.chart_config?.title || 'Data Visualization', left: 'center' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: data.data?.categories || [] },
      yAxis: { type: 'value' },
      series: [{ type: 'bar', data: data.data?.values || [], itemStyle: { color: '#5470c6' } }]
    };

    // Adjust styling based on display mode
    if (isModal) {
      baseOption.title = { ...baseOption.title, textStyle: { fontSize: 18 } };
      baseOption.grid = { left: '10%', right: '10%', bottom: '15%', top: '15%' };
    } else {
      baseOption.title = { ...baseOption.title, textStyle: { fontSize: 14 } };
      baseOption.grid = { left: '15%', right: '10%', bottom: '20%', top: '20%' };
      
      if (baseOption.xAxis) {
        baseOption.xAxis.axisLabel = { fontSize: 10, rotate: compact ? 45 : 0 };
      }
      if (baseOption.yAxis) {
        baseOption.yAxis.axisLabel = { fontSize: 10 };
      }
    }

    // Highlight logic for bar charts
    if (baseOption.series && baseOption.series[0] && baseOption.series[0].type === 'bar') {
      const series = baseOption.series[0];
      if (series.data && Array.isArray(series.data)) {
        const maxValue = Math.max(...series.data.map((item: any) => 
          typeof item === 'object' ? item.value || item.avgPrice || 0 : item || 0
        ));
        
        series.data = series.data.map((item: any) => {
          let value, avgPrice;
          if (typeof item === 'object') {
            value = item.value || 0;
            avgPrice = item.avgPrice;
          } else {
            value = item || 0;
          }
          
          const isHighlight = value === maxValue;
          const result: any = {
            value: value,
            itemStyle: {
              color: isHighlight ? '#ff6b6b' : '#5470c6',
              borderColor: isHighlight ? '#ff4757' : 'transparent',
              borderWidth: isHighlight ? 2 : 0
            }
          };
          
          if (avgPrice !== undefined) {
            result.avgPrice = avgPrice;
          }
          
          return result;
        });
        
        // Custom tooltip for additional metrics
        if (data.data?.additional_metrics?.avg_prices) {
          baseOption.tooltip = {
            trigger: 'axis',
            formatter: function(params: any) {
              const p = params[0];
              let content = `${p.name}<br/>`;
              content += `房源数量: ${p.value}<br/>`;
              if (p.data.avgPrice) {
                content += `平均价格: €${p.data.avgPrice.toFixed(2)}`;
              }
              return content;
            }
          };
        }
      }
    }

    return baseOption;
  }, [compact]);

  // Safely dispose chart instances
  const disposeChart = useCallback((chartInstance: echarts.ECharts | null) => {
    if (chartInstance && typeof chartInstance.dispose === 'function' && !chartInstance.isDisposed()) {
      try {
        chartInstance.dispose();
      } catch (error) {
        console.warn('Chart cleanup warning:', error);
      }
    }
  }, []);

  // Initialize chart with unified approach for both main and modal views
  const initializeChart = useCallback((containerRef: React.RefObject<HTMLDivElement | null>, instanceRef: React.MutableRefObject<echarts.ECharts | null>, isModal = false) => {
    if (!containerRef.current || !vizData) {
      return { success: false, cleanup: () => {} };
    }

    try {
      // Clean up existing instance
      if (instanceRef.current) {
        disposeChart(instanceRef.current);
        instanceRef.current = null;
      }

      // Verify container size
      const container = containerRef.current;
      if (container.offsetWidth === 0 || container.offsetHeight === 0) {
        return { success: false, cleanup: () => {} };
      }

      // Create chart option
      const chartOption = createChartOption(vizData, isModal);
      if (!chartOption) {
        return { success: false, cleanup: () => {} };
      }

      // Initialize and set up chart
      const chartInstance = echarts.init(container);
      chartInstance.setOption(chartOption, true);
      instanceRef.current = chartInstance;

      // Add resize handler
      const resizeHandler = () => {
        if (instanceRef.current && !instanceRef.current.isDisposed()) {
          try {
            instanceRef.current.resize();
          } catch (error) {
            console.warn('Chart resize warning:', error);
          }
        }
      };

      window.addEventListener('resize', resizeHandler);

      return { 
        success: true, 
        cleanup: () => {
          window.removeEventListener('resize', resizeHandler);
          if (instanceRef.current) {
            disposeChart(instanceRef.current);
            instanceRef.current = null;
          }
        }
      };
    } catch (error) {
      console.error('Chart initialization error:', error);
      return { success: false, cleanup: () => {} };
    }
  }, [vizData, createChartOption, disposeChart]);

  // Initialize main chart
  useEffect(() => {
    if (!isVisible || !vizData) {
      setChartReady(false);
      return;
    }

    const timer = setTimeout(() => {
      const result = initializeChart(chartRef, chartInstanceRef, false);
      setChartReady(result.success);
      return result.cleanup;
    }, 50);

    return () => {
      clearTimeout(timer);
      setChartReady(false);
    };
  }, [isVisible, vizData, initializeChart]);

  // Initialize modal chart
  useEffect(() => {
    if (!modalVisible || !vizData) {
      setModalChartReady(false);
      return;
    }

    const timer = setTimeout(() => {
      const result = initializeChart(modalChartRef, modalChartInstanceRef, true);
      setModalChartReady(result.success);
      return result.cleanup;
    }, 200);

    return () => {
      clearTimeout(timer);
      setModalChartReady(false);
    };
  }, [modalVisible, vizData, initializeChart]);

  // Clean up on component unmount
  useEffect(() => {
    return () => {
      disposeChart(chartInstanceRef.current);
      disposeChart(modalChartInstanceRef.current);
    };
  }, [disposeChart]);

  // Render process explanation section
  const renderProcessExplanation = () => {
    if (!showProcess || !vizData) return null;
    
    const explanation = generateSmartExplanation(vizData, visualizationData);
    const filters = visualizationData?.visualization_filters || {};
    
    return (
      <div className="mb-3 space-y-2">
        <div className="p-2 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200">
          <div className="flex items-start space-x-2">
            <BulbOutlined className="text-blue-600 mt-0.5 flex-shrink-0" />
            <div className="text-xs text-blue-900 leading-relaxed">
              {explanation}
            </div>
          </div>
        </div>
        
        <div className="flex items-center space-x-2 text-xs">
          <Tooltip title={`Total records analyzed: ${vizData.metadata?.total_records?.toLocaleString()}`}>
            <Tag icon={<DatabaseOutlined />} color="blue">
              {vizData.metadata?.total_records?.toLocaleString()} records
            </Tag>
          </Tooltip>
          
          <Tooltip title="Chart type selected based on data characteristics">
            <Tag icon={<BarChartOutlined />} color="green">
              {vizData.chart_type?.replace('_', ' ')}
            </Tag>
          </Tooltip>
          
          {Object.keys(filters).length > 0 && (
            <Tooltip title={`Applied filters: ${Object.keys(filters).join(', ')}`}>
              <Tag icon={<FilterOutlined />} color="purple">
                {Object.keys(filters).length} filters
              </Tag>
            </Tooltip>
          )}
        </div>
      </div>
    );
  };

  // Loading spinner view
  if (!vizData) {
    return (
      <div className="text-center text-gray-500 py-4">
        <Spin size="small" />
        <p className="mt-2 text-xs">Loading visualization...</p>
      </div>
    );
  }

  const { chart_config, metadata } = vizData;

  return (
    <>
      {/* Main card */}
      <div className="relative p-3 bg-white shadow-md rounded-lg mt-2">
        {/* Control buttons */}
        <div className="absolute top-2 right-2 z-10 flex space-x-1">
          <Tooltip title="View in full screen">
            <Button 
              type="default" 
              size="small"
              icon={<ExpandOutlined />}
              onClick={() => setModalVisible(true)}
              className="w-8 h-8 flex items-center justify-center"
            />
          </Tooltip>
          
          <Button 
            type="default" 
            size="small"
            onClick={onToggleVisibility}
            className="w-8 h-8 flex items-center justify-center"
          >
            {isVisible ? <CloseOutlined /> : <BarChartOutlined />}
          </Button>
        </div>

        {/* Chart content */}
        {isVisible && (
          <>
            {renderProcessExplanation()}
            
            {/* Title and metadata */}
            <div className="mb-2 pr-20">
              <h4 className="text-sm font-medium text-gray-800 mb-1">
                {chart_config?.title || 'Data Visualization'}
              </h4>
              
              {metadata && (
                <div className="text-xs text-gray-500 space-y-1">
                  {metadata.total_records && (
                    <div className="flex items-center space-x-1">
                      <span>📊</span>
                      <span>Total records: {metadata.total_records.toLocaleString()}</span>
                    </div>
                  )}
                  {metadata.most_common_range && (
                    <div className="flex items-center space-x-1">
                      <span>🎯</span>
                      <span>Most common: {metadata.most_common_range}</span>
                    </div>
                  )}
                  {metadata.avg_price_overall && (
                    <div className="flex items-center space-x-1">
                      <span>💰</span>
                      <span>Average: €{metadata.avg_price_overall.toFixed(2)}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Chart area */}
            <div 
              ref={chartRef}
              className={`w-full bg-gray-50 rounded ${compact ? 'h-40' : 'h-64'} relative`}
              style={{ minHeight: compact ? '160px' : '256px' }}
            >
              {!chartReady && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <Spin size="small" />
                    <p className="mt-2 text-xs text-gray-500">Rendering chart...</p>
                  </div>
                </div>
              )}
            </div>
          </>
        )}

        {/* Collapsed preview */}
        {!isVisible && (
          <div className="py-4 text-center text-gray-500 cursor-pointer hover:bg-gray-50" 
               onClick={onToggleVisibility}>
            <BarChartOutlined className="text-lg mb-1" />
            <div className="text-xs">{chart_config?.title || 'Data Visualization'}</div>
            <div className="text-xs text-gray-400 mt-1">
              {metadata?.total_records?.toLocaleString()} records analyzed
            </div>
          </div>
        )}
      </div>

      {/* Fullscreen modal */}
      <Modal
        title={
          <div className="flex items-center space-x-2">
            <BarChartOutlined />
            <span>{chart_config?.title || 'Data Visualization'}</span>
          </div>
        }
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width="80vw"
        style={{ top: 20 }}
        bodyStyle={{ padding: '20px' }}
        destroyOnClose={true}
      >
        {/* Detailed explanation */}
        <div className="mb-4 p-4 bg-blue-50 rounded-lg">
          <div className="flex items-start space-x-2">
            <InfoCircleOutlined className="text-blue-600 mt-0.5" />
            <div className="text-sm text-blue-900">
              {generateSmartExplanation(vizData, visualizationData)}
            </div>
          </div>
        </div>

        {/* Statistics */}
        {metadata && (
          <div className="mb-4">
            <Card size="small" className="bg-blue-50">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                {metadata.total_records && (
                  <div className="text-center">
                    <div className="font-medium text-gray-700">Total Records</div>
                    <div className="text-blue-600 font-semibold">
                      {metadata.total_records.toLocaleString()}
                    </div>
                  </div>
                )}
                
                {metadata.most_common_range && (
                  <div className="text-center">
                    <div className="font-medium text-gray-700">Most Common</div>
                    <div className="text-green-600 font-semibold">
                      {metadata.most_common_range}
                    </div>
                  </div>
                )}
                
                {metadata.avg_price_overall && (
                  <div className="text-center">
                    <div className="font-medium text-gray-700">Average Price</div>
                    <div className="text-purple-600 font-semibold">
                      €{metadata.avg_price_overall.toFixed(2)}
                    </div>
                  </div>
                )}
                
                <div className="text-center">
                  <div className="font-medium text-gray-700">Chart Type</div>
                  <div className="text-orange-600 font-semibold capitalize">
                    {vizData.chart_type?.replace('_', ' ') || 'Unknown'}
                  </div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Modal chart */}
        <div ref={modalChartRef} className="w-full h-96 bg-gray-50 rounded-lg relative">
          {!modalChartReady && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center">
                <Spin size="large" />
                <p className="mt-3 text-sm text-gray-500">Loading full-screen chart...</p>
              </div>
            </div>
          )}
        </div>
        
        {/* Additional information */}
        <div className="mt-4 text-sm text-gray-600">
          <p>💡 The highlighted elements represent the most significant findings in your data.</p>
          <p>📊 Hover over chart elements to see detailed information and interactive insights.</p>
        </div>
      </Modal>
    </>
  );
};

export default VisualizationCard;