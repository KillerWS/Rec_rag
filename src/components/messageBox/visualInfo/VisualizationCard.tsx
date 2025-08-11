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

// 🎯 前端组件使用的数据类型
interface ChartData {
  type: 'bar' | 'pie' | 'line' | 'scatter';
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
  onShowMap?: (district: string) => void;
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
  onShowMap?: (district: string) => void;
  showControls?: boolean;
}> = ({ chartData, height = 300, width = '100%', modalVisible, onDistrictSelect, onShowMap, showControls }) => {
  // 检查是否是价格分布柱状图 - 在任何hooks之前进行检查
  const isPriceDistributionBar = 
    chartData?.options?.title === 'Price Distribution Analysis' && 
    chartData?.options?.type === "histogram";
    
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

  // 只有在不是价格分布图的情况下才定义这些hooks
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
        minHeight: '200px'
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
  onShowMap
}) => {
  console.log("visualizationData", visualizationData);
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedChart, setSelectedChart] = useState<string | null>(null);
  const [loading] = useState(false);
  // const [selectedDistrict, setSelectedDistrict] = useState<string>("All");

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
            <div className="h-24 bg-gray-50 rounded flex items-center justify-center">
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