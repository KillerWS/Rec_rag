// MessageBubble.jsx - 移除Modal，添加地图触发逻辑
import { Avatar, Button, Card, Modal, Spin } from "antd";
import { UserOutlined, BarChartOutlined, CloseOutlined, QuestionCircleOutlined } from "@ant-design/icons";
import { useState } from "react";
import { fetchPriceOverview, fetchNeighbourhoodAggregation, fetchRoomTypeAggregation  } from "../../api/api";
import PriceOverview from "./PriceOverview";
import NeighbourhoodOverview from "./NeighbourhoodOverview";
import RoomTypeStackedBar from "../eCharts/RoomTypeStackedBar";
// 修复导入路径问题
// import ReviewInsightPanel from "./ReviewsCard/ReviewInsightPanel";
import { Typography } from "antd";
import ReviewsPromptModal from "./ReviewsPromptModal";
// import ConfirmationButtons from "./ConfirmationButtons";
import VisualizationCard from "./visualInfo/VisualizationCard";
import BudgetRangeInput from "./BudgetInputCard";
import CommentInsightsPanel from "../commentInsights/CommentInsightsPanel";
import RoomTypeSelector from "./prefsInput/RoomTypeSelector";
import RagSourceTooltip from "./ragSource/RagSourceTooltip";

// 🎯 VisualizationCard需要的数据格式（与原组件保持一致）
interface VisualizationCardData {
  visualizations: {
    [key: string]: {
      type: 'bar' | 'pie' | 'line' | 'scatter';
      title: string;
      data: any;
      options?: any;
      description?: string;
      echarts_option?: any;
    };
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

interface MessageBubbleProps {
  text: string;
  sender?: "user" | "system";
  type?: string;
  isPriceStep?: boolean;
  priceRange?: {min: number; max: number} | null;
  setConfirm?: ((confirm: boolean) => void) | null;
  messageId?: string | null;
  isRegenerating?: boolean;
  visualizationData?: any | null;
  targetDimensions?: string[] | string | null;
  setSelectedDimensions?: any;
  onBudgetSubmit?: (d: any) => void;
  onOpenHeatmap?: (msg: any, district?: string | null) => void;
  mode?: string;
  commentData?: any;
  insightsLevel?: string;
  insightsGroupName?: string;
  source_documents?: any[];
  onScriptedLocationSelected?: (district: string) => void;
  locationResolved?: boolean;
  appendMessage?: (m: any) => void;
  onRoomTypeSubmit?: (values: string[]) => void;
}

// 🎯 数据转换适配器函数
const adaptVisualizationDataForCard = (backendData: any): VisualizationCardData | null => {
  if (!backendData || !backendData.visualizations) {
    return null;
  }

  const adaptedVisualizations: VisualizationCardData['visualizations'] = {};

  Object.entries(backendData.visualizations).forEach(([key, chart]: [string, any]) => {
    let chartType: 'bar' | 'pie' | 'line' | 'scatter' = 'bar';
    switch (chart.chart_type) {
      case 'location_popularity':
        chartType = 'bar';
        break;
      case 'price_distribution':
        chartType = 'bar';
        break;
      case 'room_type_comparison':
        chartType = 'bar';
        break;
      default:
        chartType = 'bar';
    }

    adaptedVisualizations[key] = {
      type: chartType,
      title: chart.chart_config?.title || chart.title || '数据分析',
      data: chart.data,
      echarts_option: chart.echarts_option,
      description: chart.budget_context?.description || chart.description || '',
      options: chart.chart_config
    };
  });

  const chartSuggestions = backendData.chart_suggestions?.map((suggestion: any) => {
    if (typeof suggestion === 'string') {
      return suggestion;
    }
    return suggestion.title || suggestion.chart_type || suggestion.description || '';
  }) || [];

  const budgetInfo = backendData.visualization_filters ? {
    min_price: backendData.visualization_filters.price_min,
    max_price: backendData.visualization_filters.price_max,
    currency: '€'
  } : undefined;

  let priority: 'high' | 'medium' | 'low' = 'medium';
  if (backendData.show_visualization_prompt) {
    priority = 'high';
  } else if (backendData.show_visualization_suggestions) {
    priority = 'medium';
  } else {
    priority = 'low';
  }

  return {
    visualizations: adaptedVisualizations,
    chart_suggestions: chartSuggestions,
    visualization_message: backendData.visualization_message || '📊 数据可视化分析',
    user_budget_info: budgetInfo,
    reason: 'backend_generated',
    priority: priority
  };
};

const MessageBubble = ({ 
  text, 
  sender, 
  type = "text", 
  isPriceStep,
  // isLocationStep,
  priceRange = null,
  setConfirm = null,
  isRegenerating = false,
  // showRegenerateButton = false,
  visualizationData = null,
  // visualizationFilters = null,
  targetDimensions = null,
  setSelectedDimensions,
  onBudgetSubmit = undefined,
  onOpenHeatmap = undefined,
  mode = undefined,
  commentData = undefined,
  insightsLevel = undefined,
  insightsGroupName = undefined,
  source_documents = undefined,
  onScriptedLocationSelected,
  locationResolved,
  appendMessage: appendMessageProp,
  onRoomTypeSubmit

}: MessageBubbleProps) => {
  // Removed unused budgetSubmitted state

  const isUser = sender === "user";
  const [localChartData, setLocalChartData] = useState<any>({
    priceOverview: null,
    neighbourhood: null,
    roomType: null
  });

  const [loadingChart, setLoadingChart] = useState<boolean>(false);

  const [visibleState, setVisibleState] = useState({
    priceOverview: false,
    neighbourhood: false,
    roomType: false,
    visualization: true
  });

  const [isModalVisible, setIsModalVisible] = useState<boolean>(false);
  const [showCommentsPanel, setShowCommentsPanel] = useState<boolean>(false);
  // Removed unused room type temporary states
  const [roomTypeModalVisible, setRoomTypeModalVisible] = useState<boolean>(false);

  const [localSelection, setLocalSelection] = useState({ district: "All", neighborhood: "All" });

  const CustomRobotIcon = () => (
    <svg className="w-8 h-8" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
      <path d="M704 960h-298.666667c-12.8 0-21.333333-8.533333-21.333333-21.333333v-149.333334h-106.666667c-12.8 0-21.333333-8.533333-21.333333-21.333333v-151.466667l-85.333333-40.533333c-4.266667-2.133333-8.533333-6.4-10.666667-12.8-2.133333-4.266667-2.133333-10.666667 0-17.066667l53.333333-115.2v-6.4c0-200.533333 149.333333-362.666667 330.666667-362.666666s330.666667 162.133333 330.666667 362.666666c0 121.6-55.466667 236.8-149.333334 302.933334v209.066666c0 14.933333-8.533333 23.466667-21.333333 23.466667z" fill="#3A3E46"></path>
      <path d="M533.333333 426.666667c-46.933333 0-85.333333-38.4-85.333333-85.333334s38.4-85.333333 85.333333-85.333333 85.333334 38.4 85.333334 85.333333-38.4 85.333333-85.333334 85.333334z" fill="#FFB724"></path>
    </svg>
  );

  const fetchPriceOverviewData = async () => {
    if (localChartData.priceOverview) {
      setVisibleState((prev: any)=>({...prev, priceOverview: !visibleState.priceOverview}));
      return;
    }
    setLoadingChart(true);
    try {
      if (!priceRange) {
        console.error("Price range is not defined");
        return;
      }
      const data = await fetchPriceOverview(priceRange.min, priceRange.max);
      if (data) {
        setLocalChartData((prev: any) => ({ ...prev, priceOverview: data }));
        setVisibleState((prev: any)=>({...prev, priceOverview: true}));
      }
    } catch (error) {
      console.error("🚨 Error fetching price overview:", error);
    } finally {
      setLoadingChart(false);
    }
  };

  const fetchNeighbourhoodAggregationData = async () => {
    if (localChartData.neighbourhood) {
      setVisibleState((prev: any)=>({...prev, neighbourhood:!visibleState.neighbourhood}));
      return;
    } 
    setLoadingChart(true);
    try {
      if (!priceRange) {
        console.error("Price range is not defined");
        return;
      }
      const data = await fetchNeighbourhoodAggregation(priceRange.min, priceRange.max);
      if (data) {
        setLocalChartData((prev: any) => ({ ...prev, neighbourhood: data }));
        setVisibleState((prev: any)=>({...prev, neighbourhood: true}));
      }
    } catch (error) {
      console.error("🚨 Error fetching price overview:", error);
    } finally {
      setLoadingChart(false);
    }
  }
  
  const fetchRoomTypeStackedData = async () => {
    if (localChartData.roomType) {
      setVisibleState((prev: any)=>({...prev, roomType:!visibleState.roomType}));
      return;
    }
    setLoadingChart(true);
    if (!priceRange) {
      console.error("Price range is not defined");
      return;
    }
    try {
      const data = await fetchRoomTypeAggregation(priceRange.min, priceRange.max);
      if (data) {
        setLocalChartData((prev: any) => ({...prev, roomType: data }));
        setVisibleState((prev: any)=>({...prev, roomType: true}));  
      } 
    }
    catch (error) {
      console.error("🚨 Error fetching RoomType data:", error); 
    }finally {
      setLoadingChart(false);
    }
  }

  // 🎯 简化：检查是否显示预算输入组件
  const shouldShowBudgetInput = (): boolean => {
    let hasBudgetTarget = false;
    if (Array.isArray(targetDimensions)) {
      hasBudgetTarget = targetDimensions.some((dim: string) => dim.toLowerCase() === 'budget');
    } else if (typeof targetDimensions === 'string') {
      hasBudgetTarget = (targetDimensions as string).toLowerCase() === 'budget';
    }
    const isBudgetInputType = type === "budget_input";
    return (hasBudgetTarget || isBudgetInputType);
  };

  const shouldShowRoomTypeInput = (): boolean => {
    let hasRoomTypeTarget = false;
    if (Array.isArray(targetDimensions)) {
      hasRoomTypeTarget = targetDimensions.some((dim: string) => dim.toLowerCase() === "room_type");
    } else if (typeof targetDimensions === "string") {
      hasRoomTypeTarget = (targetDimensions as string).toLowerCase() === "room_type";
    }
    const isRoomTypeInputType = type === "roomtype_input";
    return (hasRoomTypeTarget || isRoomTypeInputType);
  };

  const shouldShowCommentsButton = (): boolean => {
    return !isUser && !!commentData?.summary;
  };

  const shouldShowHeatmapButton = (): boolean => {
    const isLocationFollowup = 
      Array.isArray(targetDimensions)
        ? (targetDimensions as string[]).includes("location")
        : targetDimensions === "location";
    // 在 scripted 模式下，如果已经做出了区划选择（本地或全局），则不再显示按钮
    const hasLocalPick = !!(localSelection?.district && localSelection.district !== 'All');
    const isScripted = mode === 'scripted';
    const isResolved = !!locationResolved;
    return !isUser && isLocationFollowup && !(isScripted && (hasLocalPick || isResolved));
  };

  const handleLocalBudgetSubmit = (budgetData: any) => {
    if (onBudgetSubmit) {
      onBudgetSubmit(budgetData);
    }
  };

  const handleOpenHeatmap = () => {
    if (setSelectedDimensions) {
      setSelectedDimensions((prev: any[]) => {
        const withoutLocation = prev.filter((item: any) => item.key !== "Location");
        const chosen = localSelection?.district && localSelection.district !== "All"
          ? localSelection.district
          : "Explore on Map";
        return [...withoutLocation, { key: "Location", value: chosen }];
      });
    }
    if (onOpenHeatmap) {
      onOpenHeatmap?.(null, null);
    }
  };

  // const handleRoomTypeSubmit = (selected: string[]) => {
  //   setSelectedRoomTypes(selected);
  //   setRoomTypeSubmitted(true);
  //   setShowRoomTypeInput(false);
  //   if (setSelectedDimensions) {
  //     setSelectedDimensions((prev: any[]) => [
  //       ...prev.filter((item: any) => item.key !== "Room Type"),
  //       ...selected.map((value: string) => ({ key: "Room Type", value }))
  //     ]);
  //   }
  // };

  // 🎯 关键：在这里进行数据转换
  const adaptedVisualizationData = visualizationData 
    ? adaptVisualizationDataForCard(visualizationData)
    : null;

  const shouldShowVisualization = (): boolean => {
    if (!adaptedVisualizationData) return false;
    const hasVisualizations = 
      adaptedVisualizationData?.visualizations && 
      typeof adaptedVisualizationData.visualizations === 'object' &&
      Object.keys(adaptedVisualizationData.visualizations).length > 0;
    const shouldShow = (visualizationData as any)?.show_visualization_prompt || 
                      (visualizationData as any)?.show_visualization_suggestions ||
                      type === "visualization";
    return hasVisualizations && shouldShow;
  };

  const renderVisualizationComponent = () => {
    if (!shouldShowVisualization() || !adaptedVisualizationData) {
      return null;
    }
    if (!adaptedVisualizationData.visualizations) {
      return null;
    }
    return (
      <VisualizationCard
        visualizationData={adaptedVisualizationData as any}
        isVisible={visibleState.visualization}
        onToggleVisibility={() => 
          setVisibleState((prev: any) => ({
            ...prev, 
            visualization: !prev.visualization
          }))
        }
        onDistrictSelect={(district, neighborhood) => {
          setLocalSelection({ district, neighborhood: neighborhood || "All" });
          if (mode === 'scripted' && onScriptedLocationSelected && district && district !== 'All') {
            onScriptedLocationSelected(district);
          }
        }}
        onShowMap={(district) => {
          if (onOpenHeatmap) {
            onOpenHeatmap(null, district);
          }
        }}
      />
    );
  };

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} items-center my-2`}>
      {!isUser && (
        <div className="flex-shrink-0 mr-2">
          <Avatar size={36} style={{ backgroundColor: "transparent" }} icon={<CustomRobotIcon />} />
        </div>
      )}

      <div className="relative group">
        <RagSourceTooltip sourceDocuments={source_documents || []}>
        <div
          className={`p-3 rounded-xl text-sm leading-snug 
            ${isUser ? "bg-blue-500 text-white" : "bg-gray-200"} 
            shadow-md transition-all duration-200 ease-in-out 
            max-w-md w-fit min-w-[80px] break-words`}
        > 
          {isRegenerating && (
            <div className="absolute inset-0 bg-white bg-opacity-80 rounded-xl flex items-center justify-center z-10">
              <div className="flex flex-col items-center space-y-2">
                <Spin size="small" />
                <span className="text-xs text-gray-500">Regenerating...</span>
              </div>
            </div>
          )}

          {text}
          {renderVisualizationComponent()}

          {!isUser && type === "preference_summary" && (
            <div className="mt-3 p-3 border-2 border-blue-400 bg-blue-50 rounded-lg">
              <div className="text-center mb-2 font-bold text-blue-700">🌟 Preference Summary 🌟</div>
              <div className="mb-3 text-sm">
                Based on your preferences, we've automatically switched to <span className="font-bold text-blue-700">Review Q&A Mode</span>.
                In this mode, the system will retrieve relevant user reviews to provide you with more precise suggestions and assistance.
              </div>
              <div className="flex justify-center">
                <Button 
                  type="primary"
                  size="small"
                  className="bg-blue-600 hover:bg-blue-700 border-blue-600"
                  onClick={() => setShowCommentsPanel(true)}
                >
                  View Review Insights
                </Button>
              </div>
            </div>
          )}

          { !isUser && shouldShowHeatmapButton() && (
            <div className="flex justify-center mt-3">
              <Button 
                type="primary" 
                size="small"
                onClick={handleOpenHeatmap}
                className="bg-green-500 hover:bg-green-600 border-green-500"
              >
                {mode === 'scripted' ? '🗺️ Select your location on the map' : '🗺️ Explore Geographic dimension visualization info'}
              </Button>
            </div>
          )}
          
          {shouldShowBudgetInput() && (
            <BudgetRangeInput
              onBudgetSubmit={handleLocalBudgetSubmit}
              setSelectedDimensions={setSelectedDimensions}
              className="mt-2"
            />
          )}

          {shouldShowCommentsButton() && (
            <div className="flex justify-center mt-3">
              <Button
                type="dashed"
                size="small"
                onClick={() => setShowCommentsPanel(true)}
                icon={<QuestionCircleOutlined />}
              >
                💬 查看评论洞察
              </Button>
            </div>
          )}

          {shouldShowRoomTypeInput() && (
            <RoomTypeSelector
              setSelectedDimensions={setSelectedDimensions}
              mode={mode as 'scripted' | 'agent' | 'none'}
              appendMessage={(msg) => appendMessageProp?.(msg)}
              onSubmit={(values) => onRoomTypeSubmit?.(values)}
            />
          )}

          <Modal
            visible={showCommentsPanel}
            title="Reviews Insights"
            footer={null}
            onCancel={() => setShowCommentsPanel(false)}
            width={600}
            bodyStyle={{ maxHeight: '60vh', overflowY: 'auto' }}
          >
            { insightsLevel && insightsGroupName 
              ? <CommentInsightsPanel       
                  level={insightsLevel as 'neighbourhood' | 'district'}
                  groupName={insightsGroupName as string} />
              : <div className="text-center text-gray-500">No Social Analysis Data</div>
            }
          </Modal>

          {isPriceStep && (
            <div className="flex justify-center mt-2">
              <Button type="primary" size="small" icon={<BarChartOutlined />} onClick={fetchPriceOverviewData}>
                Price Distribution
              </Button>
            </div>
          )}

          {mode === 'scripted' && type === "neighbourhood_prompt" && (
            <div className="flex flex-col items-center mt-2 w-full">
              <Button
                type="primary"
                icon={<BarChartOutlined />}
                onClick={fetchNeighbourhoodAggregationData}
                className="mb-2"
              >
                {visibleState.neighbourhood ? "Hide Neighbourhood Chart" : "Show Neighbourhood Chart"}
              </Button>

              {visibleState.neighbourhood && localChartData.neighbourhood && (
                <div className="w-full">
                  <NeighbourhoodOverview
                    chartData={{
                      xAxis: localChartData.neighbourhood.xAxis,
                      series: localChartData.neighbourhood.series,
                      highlight: localChartData.neighbourhood.highlight,
                      title: localChartData.neighbourhood.title || "Top Neighbourhoods (Listings vs Price)"
                    }}
                    onAreaSelect={(area) => {
                      if (onScriptedLocationSelected) {
                        onScriptedLocationSelected(area);
                      }
                    }}
                  />
                </div>
              )}
            </div>
          )}

          {localChartData.priceOverview && (
            <div className="relative p-2 bg-white shadow-md rounded-lg mt-2">
              <Button 
                type="default" 
                size="small"
                className="absolute top-1 right-1 z-10" 
                onClick={() => setVisibleState((prev: any)=>({...prev, priceOverview: !visibleState.priceOverview}))}
              >
                {visibleState.priceOverview ? <>collapse <CloseOutlined /></> : "Expand"}
              </Button>
              
              {visibleState.priceOverview && 
                <div className="w-full mt-2">
                  <PriceOverview
                  summary={localChartData.priceOverview.summary}
                  pieChart={localChartData.priceOverview.pieChart}
                  barChart={localChartData.priceOverview.barChart}
                  />
                </div>
              }
            </div>
          )}

          {type === "roomtype_prompt" && (
            <div className="flex flex-col items-center mt-2 w-full">
              <Button
                type="primary"
                icon={<BarChartOutlined />}
                onClick={fetchRoomTypeStackedData}
                className="mb-2"
              >
                {visibleState.roomType ? "Hide Room Type Chart" : "Show Room Type Chart"}
              </Button>

              {visibleState.roomType && localChartData.roomType && (
                <div className="w-full">
                  <Card
                    size="small"
                    hoverable
                    title={localChartData.roomType.title || "Room Type Distribution by Price Range"}
                    style={{ cursor: "pointer" }}
                    onClick={() => setRoomTypeModalVisible(true)}
                  >
                    <RoomTypeStackedBar
                      title={
                        localChartData.roomType.title ||
                        "Room Type Distribution by Price Range"
                      }
                      chartData={{
                        xAxis: localChartData.roomType.xAxis,
                        series: localChartData.roomType.series,
                        highlight: localChartData.roomType.highlight,
                        title: localChartData.roomType.title,
                      }}
                      height={300}
                    />
                  </Card>

                  <Modal
                    title={(localChartData.roomType.title || "Room Type Distribution by Price Range") + " (Full View)"}
                    open={roomTypeModalVisible}
                    footer={null}
                    onCancel={() => setRoomTypeModalVisible(false)}
                    width={700}
                  >
                    <RoomTypeStackedBar
                      title={
                        localChartData.roomType.title ||
                        "Room Type Distribution by Price Range"
                      }
                      chartData={{
                        xAxis: localChartData.roomType.xAxis,
                        series: localChartData.roomType.series,
                        highlight: localChartData.roomType.highlight,
                        title: localChartData.roomType.title,
                      }}
                      height={420}
                      modalVisible={roomTypeModalVisible}
                    />
                  </Modal>
                </div>
              )}
            </div>
          )}

          {type === "social_prompt" && (
            <div className="w-full mt-2 space-y-2">
              <Typography.Paragraph strong>
                💬 Would you like to see what previous guests said about different listings?
              </Typography.Paragraph>

              <div className="flex justify-center gap-4">
                <Button type="primary" onClick={() => setIsModalVisible(true)}>
                  Yes, show insights
                </Button>
                <Button onClick={() => setConfirm && setConfirm(false)}>No, give me recommendations</Button>
              </div>

              <ReviewsPromptModal open={isModalVisible} onClose={() => setIsModalVisible(false)} />
            </div>
          )}

          {loadingChart && <div className="text-center text-gray-500 mt-2">Loading chart...</div>}
        </div>
        </RagSourceTooltip>

        {/* 已移除悬浮按钮，减少界面干扰 */}
      </div>

      {isUser && <Avatar size={36} icon={<UserOutlined />} className="ml-2" />}
    </div>
  );
};

export default MessageBubble;