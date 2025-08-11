import React, { useRef, useEffect, useState } from 'react';
import * as echarts from 'echarts';
import { Typography, Select, Button, Tooltip, Space } from 'antd';
import { EnvironmentOutlined } from '@ant-design/icons';

const { Text } = Typography;
const { Option } = Select;

// Berlin districts and neighborhoods data
const berlinDistrictsData: Record<string, string[]> = {
  "All": ["All"],
  "Mitte": ["All", "Mitte", "Moabit", "Hansaviertel", "Tiergarten", "Wedding", "Gesundbrunnen"],
  "Friedrichshain-Kreuzberg": ["All", "Friedrichshain", "Kreuzberg"],
  "Pankow": ["All", "Prenzlauer Berg", "Weißensee", "Blankenburg", "Heinersdorf", "Karow", "Stadtrandsiedlung Malchow", "Pankow", "Blankenfelde", "Buch", "Französisch Buchholz", "Niederschönhausen", "Rosenthal", "Wilhelmsruh"],
  "Charlottenburg-Wilmersdorf": ["All", "Charlottenburg", "Wilmersdorf", "Schmargendorf", "Grunewald", "Westend", "Charlottenburg-Nord", "Halensee"],
  "Spandau": ["All", "Spandau", "Haselhorst", "Siemensstadt", "Staaken", "Gatow", "Kladow", "Hakenfelde", "Falkenhagener Feld", "Wilhelmstadt"],
  "Steglitz-Zehlendorf": ["All", "Steglitz", "Lichterfelde", "Lankwitz", "Zehlendorf", "Dahlem", "Nikolassee", "Wannsee", "Schlachtensee"],
  "Tempelhof-Schöneberg": ["All", "Schöneberg", "Friedenau", "Tempelhof", "Mariendorf", "Marienfelde", "Lichtenrade"],
  "Neukölln": ["All", "Neukölln", "Britz", "Buckow", "Rudow", "Gropiusstadt"],
  "Treptow-Köpenick": ["All", "Alt-Treptow", "Plänterwald", "Baumschulenweg", "Johannisthal", "Niederschöneweide", "Altglienicke", "Adlershof", "Bohnsdorf", "Oberschöneweide", "Köpenick", "Friedrichshagen", "Rahnsdorf", "Grünau", "Müggelheim", "Schmöckwitz"],
  "Marzahn-Hellersdorf": ["All", "Marzahn", "Hellersdorf", "Biesdorf", "Kaulsdorf", "Mahlsdorf"],
  "Lichtenberg": ["All", "Friedrichsfelde", "Karlshorst", "Lichtenberg", "Falkenberg", "Malchow", "Wartenberg", "Neu-Hohenschönhausen", "Alt-Hohenschönhausen", "Fennpfuhl", "Rummelsburg"],
  "Reinickendorf": ["All", "Reinickendorf", "Tegel", "Konradshöhe", "Heiligensee", "Frohnau", "Hermsdorf", "Waidmannslust", "Lübars", "Wittenau", "Märkisches Viertel", "Borsigwalde"]
};

// 价格分布柱状图组件的Props定义
interface PriceDistributionBarProps {
  chartData: {
    title: string;
    data: any;
    echarts_option?: any;
    type: string;
  };
  height?: number;
  width?: string;
  modalVisible?: boolean;
  onDistrictSelect?: (district: string, neighborhood?: string) => void;
  onShowMap?: (district: string) => void;
  districts?: string[];
  showControls?: boolean;
}

const PriceDistributionBar: React.FC<PriceDistributionBarProps> = ({
  chartData,
  height = 300,
  width = '100%',
  modalVisible,
  onDistrictSelect,
  onShowMap,
  districts = Object.keys(berlinDistrictsData),
  showControls = true
}) => {
  const [selectedDistrict, setSelectedDistrict] = useState<string>("All");
  const [selectedNeighborhood, setSelectedNeighborhood] = useState<string>("All");
  const [availableNeighborhoods, setAvailableNeighborhoods] = useState<string[]>(["All"]);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);

  // 更新可用的社区列表
  useEffect(() => {
    if (selectedDistrict === "All") {
      setAvailableNeighborhoods(["All"]);
    } else {
      setAvailableNeighborhoods(berlinDistrictsData[selectedDistrict] || ["All"]);
    }
    setSelectedNeighborhood("All");
  }, [selectedDistrict]);

  // 创建价格分布图配置
  const createPriceDistributionOption = (data: any, district: string = "All", neighborhood: string = "All") => {
    // 如果后端提供了完整的 echarts_option，直接使用作为基础
    if (!data.echarts_option) {
      return null; // 没有基础配置就返回null，让调用方处理
    }

    // 提取价格指标
    if (!data.data?.additional_metrics) {
      return data.echarts_option; // 无法增强，返回原始配置
    }
    
    const metrics = data.data.additional_metrics;
    const minPrice = metrics.min_prices?.[0];
    const maxPrice = metrics.max_prices?.[0];
    const avgPrice = metrics.avg_prices?.[0];
    
    // 如果没有最低和最高价格，则无法增强
    if (!minPrice || !maxPrice) {
      return data.echarts_option;
    }
    
    // 复制原选项以避免修改原对象
    const enhancedOption = JSON.parse(JSON.stringify(data.echarts_option));
    
    // 生成价格区间 - 处理极端情况
    let priceRanges: string[] = [];
    
    if (maxPrice === minPrice) {
      // 如果最大值等于最小值，创建前后各一个区间
      const buffer = Math.max(50, minPrice * 0.1); // 使用至少50€或10%的缓冲区
      priceRanges = [
        `${Math.max(minPrice - buffer, 0)}€-${minPrice}€`,
        `${minPrice}€-${minPrice + buffer}€`,
        `${minPrice + buffer}€-${minPrice + buffer * 2}€`
      ];
    } else {
      // 正常情况，分成约4个区间
      const step = Math.ceil((maxPrice - minPrice) / 4);
      for (let i = minPrice; i < maxPrice; i += step) {
        priceRanges.push(`${i}€-${Math.min(i + step, maxPrice)}€`);
      }
    }
    
    // 修改x轴数据
    enhancedOption.xAxis.data = priceRanges;
    
    // 创建模拟分布数据，以avgPrice为中心，模拟正态分布
    const values = priceRanges.map((range, index) => {
      const rangeParts = range.split('-');
      // 确保正确处理价格格式 (去掉€符号)
      const min = parseInt(rangeParts[0].replace('€', ''));
      const max = parseInt(rangeParts[1].replace('€', ''));
      const rangeMid = (min + max) / 2;
      
      let distanceFromAvg = Math.abs(rangeMid - avgPrice);
      const total = data.data.values[0] || 1; // 避免0
      let value = 0;
      
      // 简单模拟：如果只有一个区间，将所有值放在包含均价的区间
      if (priceRanges.length <= 3) {
        if ((avgPrice >= min && avgPrice <= max) || 
            (index === Math.floor(priceRanges.length / 2))) { // 中间区间
          value = total;
        } else {
          value = Math.max(1, Math.ceil(total * 0.1)); // 保证至少有1个
        }
      } else {
        // 正常分布
        const step = maxPrice !== minPrice ? (maxPrice - minPrice) / 4 : 50;
        // 简单模拟：距离均价越近，数量越多
        if (distanceFromAvg < step) {
          value = Math.ceil(total * 0.5);  // 接近均价
        } else if (distanceFromAvg < step * 2) {
          value = Math.ceil(total * 0.3);  // 中等距离
        } else {
          value = Math.ceil(total * 0.2);  // 远离均价
        }
      }
      
      return value;
    });
    
    // 调整柱状图数据
    enhancedOption.series[0].data = values.map((val, idx) => {
      // 保持原有的样式属性
      const originalItem = typeof enhancedOption.series[0].data[0] === 'object' 
        ? enhancedOption.series[0].data[0] 
        : {};
        
      // 创建新的数据项，保留所有原始属性
      return {
        ...originalItem,
        value: val,
        avgPrice: metrics.avg_prices?.[0],  // 保留均价数据用于tooltip
        // 调整颜色：根据是否在预算范围内来决定
        itemStyle: {
          ...(originalItem.itemStyle || {}),
          color: priceRanges[idx].includes(avgPrice) ? '#ff6b6b' : '#5470c6'
        }
      };
    });
    
    // 保留原有的tooltip格式化函数或创建新的
    if (!enhancedOption.tooltip || !enhancedOption.tooltip.formatter) {
      enhancedOption.tooltip = {
        ...(enhancedOption.tooltip || {}),
        trigger: 'axis',
        formatter: function(params: any) {
          const p = params[0];
          let tooltipText = p.name + '<br/>' +
                'Listings: ' + p.value + '<br/>' +
                'Average price: €' + p.data.avgPrice;
                
          // 添加区域信息到tooltip        
          if (district !== "All") {
            tooltipText += '<br/>District: ' + district;
            
            if (neighborhood !== "All") {
              tooltipText += '<br/>Neighborhood: ' + neighborhood;
            }
          }
          
          return tooltipText;
        }
      };
    }
    
    // 添加均价标记线
    enhancedOption.series[0].markLine = {
      symbol: ['none', 'none'],
      data: [
        {
          name: 'Average Price',
          xAxis: priceRanges.findIndex(range => {
            const [min, max] = range.split('-').map(p => parseInt(p.replace('€', '')));
            return avgPrice >= min && avgPrice <= max;
          }),
          lineStyle: { color: '#ff6b6b', type: 'dashed' },
          label: { formatter: `Avg: €${avgPrice}` }
        }
      ]
    };

    // 如果是特定区域，更新标题
    if (district !== "All") {
      let titleText = `${district} Price Distribution`;
      if (neighborhood !== "All") {
        titleText = `${neighborhood} (${district}) Price Distribution`;
      }
      
      enhancedOption.title = {
        ...enhancedOption.title,
        text: titleText,
        subtext: `Average: €${avgPrice}`
      };
    }
    
    return enhancedOption;
  };

  // 处理区域选择变化
  const handleDistrictChange = (value: string) => {
    setSelectedDistrict(value);
    
    // 如果提供了回调函数，通知父组件
    if (onDistrictSelect) {
      onDistrictSelect(value, selectedNeighborhood);
    }
    
    // 根据选择的区域更新图表
    updateChart(value, "All");
  };
  
  // 处理社区选择变化
  const handleNeighborhoodChange = (value: string) => {
    setSelectedNeighborhood(value);
    
    // 如果提供了回调函数，通知父组件
    if (onDistrictSelect) {
      onDistrictSelect(selectedDistrict, value);
    }
    
    // 根据选择的社区更新图表
    updateChart(selectedDistrict, value);
  };

  // 更新图表数据
  const updateChart = (district: string, neighborhood: string) => {
    if (!chartInstance.current) return;
    
    try {
      const option = createPriceDistributionOption(chartData, district, neighborhood);
      if (option) {
        chartInstance.current.setOption(option, true);
      }
    } catch (error) {
      console.error("Chart update error:", error);
      setRenderError(`Error updating chart: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // 处理打开地图
  const handleShowMap = () => {
    if (onShowMap) {
      onShowMap(selectedDistrict);
    }
  };

  // 图表初始化
  useEffect(() => {
    if (!chartRef.current) return;

    try {
      // 数据验证 - 添加更详细的空值检查
      if (!chartData) {
        setRenderError("Chart data is missing");
        return;
      }

      if (!chartData.type) {
        setRenderError("Invalid chart type");
        return;
      }

      if (!chartData.data) {
        setRenderError("Chart data is incomplete");
        return;
      }
      
      // 初始化图表
      if (!chartInstance.current) {
        chartInstance.current = echarts.init(chartRef.current);
      }
      
      // 判断是否是价格分布图
      const isPriceChart = chartData.title?.toLowerCase().includes('price');
      const hasSingleCategory = chartData.data?.categories?.length === 1;
      const hasMetrics = !!chartData.data?.additional_metrics;
      
      let option;
      
      // 如果是价格分布图，使用特殊处理
      if (isPriceChart && hasSingleCategory && hasMetrics) {
        option = createPriceDistributionOption(chartData, selectedDistrict, selectedNeighborhood);
      }
      
      // 如果没有特殊处理，则使用原始配置
      if (!option && chartData.echarts_option) {
        option = chartData.echarts_option;
      }
      
      // 设置图表配置
      if (option) {
        chartInstance.current.setOption(option);
      } else {
        setRenderError("Could not create chart option");
        return;
      }
      
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
  }, [chartData, height, width, selectedDistrict, selectedNeighborhood]);

  // Modal可见性变化时触发resize
  useEffect(() => {
    if (modalVisible !== undefined && chartInstance.current) {
      // 使用setTimeout确保在Modal动画完成后调整大小
      const timer = setTimeout(() => {
        chartInstance.current?.resize();
        
        // 特殊处理：增加对长标签的处理，动态调整底部边距
        if (chartInstance.current) {
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
  }, [modalVisible]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (chartInstance.current) {
        chartInstance.current.dispose();
        chartInstance.current = null;
      }
    };
  }, []);

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
    <div style={{ width: width, minHeight: '200px' }}>
      {showControls && (
        <div className="flex justify-between items-center mb-2">
          <Space style={{ width: '70%' }}>
            <Select
              value={selectedDistrict}
              onChange={handleDistrictChange}
              style={{ minWidth: '120px' }}
              placeholder="Select a district"
            >
              <Option key="All" value="All">All Districts</Option>
              {districts.filter(d => d !== "All").map(district => (
                <Option key={district} value={district}>{district}</Option>
              ))}
            </Select>
            
            {selectedDistrict !== "All" && (
              <Select
                value={selectedNeighborhood}
                onChange={handleNeighborhoodChange}
                style={{ minWidth: '120px' }}
                placeholder="Select a neighborhood"
              >
                {availableNeighborhoods.map(neighborhood => (
                  <Option key={neighborhood} value={neighborhood}>
                    {neighborhood === "All" ? "All Neighborhoods" : neighborhood}
                  </Option>
                ))}
              </Select>
            )}
          </Space>
          
          <Tooltip title="View on map">
            <Button 
              icon={<EnvironmentOutlined />} 
              onClick={handleShowMap}
              type="primary"
              size="small"
            >
              Map
            </Button>
          </Tooltip>
        </div>
      )}
      
      <div 
        ref={chartRef} 
        style={{ 
          height: `${height}px`, 
          width: '100%',
          minHeight: '200px'
        }} 
      />
    </div>
  );
};

export default PriceDistributionBar; 