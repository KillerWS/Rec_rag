// MessageBubble.jsx - 移除Modal，添加地图触发逻辑
import { Avatar, Button, Card, Modal, Spin } from "antd";
import { UserOutlined, BarChartOutlined, CloseOutlined, QuestionCircleOutlined } from "@ant-design/icons";
import { useState, useEffect } from "react";
import { fetchPriceOverview, fetchNeighbourhoodAggregation, fetchRoomTypeAggregation  } from "../../api/api";
import { incrementVisualizationTrigger } from "../../metrics/sessionMetrics";
import PriceOverview from "../scriptedCharts/PriceOverview";
import RoomTypePie from "../geoLayer/dataBoard/RoomTypePie";
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
import PriceSummaryCard from "./PriceSummaryCard";
// CommentSearchTooltip moved to AgentChat component
import { fetchAreasByBudget } from "../../api/api";

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
  selectedDimensions?: any[];
  appendMessage?: (m: any) => void;
  onRoomTypeSubmit?: (values: string[]) => void;
  onSendMessage?: (message: string) => void; // 🆕 用于发送新的用户消息
}

// 🎯 数据转换适配器函数
const adaptVisualizationDataForCard = (backendData: any): VisualizationCardData | null => {
  if (!backendData || !backendData.visualizations) {
    return null;
  }

  const adaptedVisualizations: VisualizationCardData['visualizations'] = {};

  Object.entries(backendData.visualizations).forEach(([key, chart]: [string, any]) => {
    // 过滤掉 reviews_time_series
    if (chart?.chart_type === 'reviews_time_series') {
      return; // skip
    }
    let chartType: 'bar' | 'pie' | 'line' | 'scatter' = 'bar';
    switch (chart.chart_type) {
      case 'reviews_analysis':
        // Route to ReviewAnalysis component (new backend key)
        (chart as any).__is_reviews_analysis__ = true;
        break;
      // removed: reviews_time_series
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
      // If backend marks reviews_analysis, set the type accordingly so ChartRenderer picks ReviewAnalysis
      type: (chart as any).__is_reviews_analysis__ ? ("reviews analysis" as any) : chartType,
      title: chart.chart_config?.title || chart.title || '数据分析',
      data: chart.data,
      echarts_option: chart.echarts_option,
      description: chart.budget_context?.description || chart.description || '',
      options: {
        ...(chart.chart_config || {}),
        // Help the detector too (exclude time series)
        type: (chart as any).__is_reviews_analysis__ ? 'reviews_analysis'
          : (chart.chart_config?.type),
      }
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
  messageId = null,
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
  selectedDimensions = [],
  appendMessage: appendMessageProp,
  onRoomTypeSubmit,
  onSendMessage

}: MessageBubbleProps) => {
  // Removed unused budgetSubmitted state

  const isUser = sender === "user";
  const [localChartData, setLocalChartData] = useState<any>({
    priceOverview: null,
    neighbourhood: null,
    roomType: null
  });

  const [recommendedAreas, setRecommendedAreas] = useState<Array<{ type?: 'budget' | 'popular' | 'balanced'; name: string; note: string }>>([]);

  const [loadingChart, setLoadingChart] = useState<boolean>(false);

  const [visibleState, setVisibleState] = useState({
    priceOverview: false,
    neighbourhood: false,
    roomType: false,
    visualization: true
  });

  const [isModalVisible, setIsModalVisible] = useState<boolean>(false);
  const [showCommentsPanel, setShowCommentsPanel] = useState<boolean>(false);
  // Removed unused room type temporary states (commented out)
  // const [roomTypeModalVisible, setRoomTypeModalVisible] = useState<boolean>(false);
  
  // Comment search tooltip functionality moved to AgentChat component

  const [localSelection, setLocalSelection] = useState({ district: "All", neighborhood: "All" });

  const CustomRobotIcon = () => (
    <svg className="w-8 h-8" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" fill="currentColor">
      <path d="M704 960h-298.666667c-12.8 0-21.333333-8.533333-21.333333-21.333333v-149.333334h-106.666667c-12.8 0-21.333333-8.533333-21.333333-21.333333v-151.466667l-85.333333-40.533333c-4.266667-2.133333-8.533333-6.4-10.666667-12.8-2.133333-4.266667-2.133333-10.666667 0-17.066667l53.333333-115.2v-6.4c0-200.533333 149.333333-362.666667 330.666667-362.666666s330.666667 162.133333 330.666667 362.666666c0 121.6-55.466667 236.8-149.333334 302.933334v209.066666c0 14.933333-8.533333 23.466667-21.333333 23.466667z" fill="#3A3E46"></path>
      <path d="M533.333333 426.666667c-46.933333 0-85.333333-38.4-85.333333-85.333334s38.4-85.333333 85.333333-85.333333 85.333334 38.4 85.333334 85.333333-38.4 85.333333-85.333334 85.333334z" fill="#FFB724"></path>
    </svg>
  );

  const fetchPriceOverviewCore = async (openChart: boolean) => {
    if (!priceRange) return;
    try {
      setLoadingChart(true);
      const data = await fetchPriceOverview(priceRange.min, priceRange.max);
      if (data) {
        setLocalChartData((prev: any) => ({ ...prev, priceOverview: data }));
        if (openChart) {
          setVisibleState((prev: any)=>({...prev, priceOverview: true}));
        }
      }
    } catch (error) {
      console.error("🚨 Error fetching price overview:", error);
    } finally {
      setLoadingChart(false);
    }
  };

  const fetchPriceOverviewData = async () => {
    if (localChartData.priceOverview) {
      setVisibleState((prev: any)=>({...prev, priceOverview: !visibleState.priceOverview}));
      // 可视化触发计数 - Price Distribution 图表显示/隐藏
      if (messageId) {
        incrementVisualizationTrigger(messageId, 'price_distribution');
      }
      return;
    }
    await fetchPriceOverviewCore(true);
    // 可视化触发计数 - Price Distribution 图表首次加载
    if (messageId) {
      incrementVisualizationTrigger(messageId, 'price_distribution');
    }
  };

  useEffect(() => {
    if (isPriceStep && priceRange && !localChartData.priceOverview) {
      // 预拉取以便展示文本 Summary，但不自动展开图表
      fetchPriceOverviewCore(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPriceStep, priceRange?.min, priceRange?.max]);

  // 🆕 在价格步骤预拉取邻里聚合用于区域推荐
  useEffect(() => {
    const run = async () => {
      if (!isPriceStep || !priceRange) return;
      try {
        // 🆕 优先使用后端返回的地区 Top 3，直接生成富文本说明
        try {
          const byBudget = await fetchAreasByBudget(priceRange.min, priceRange.max);
          const areas = Array.isArray(byBudget?.areas) ? byBudget.areas : [];
          if (areas.length > 0) {
            const top3 = areas.slice(0, 3);
            const picks = top3.map((a: any) => {
              const avg = a?.avg_price != null ? Math.round(a.avg_price) : null;
              const median = a?.median_price != null ? Math.round(a.median_price) : null;
              const p25 = a?.p25_price != null ? Math.round(a.p25_price) : null;
              const p75 = a?.p75_price != null ? Math.round(a.p75_price) : null;
              const listingsCount = a?.listing_count as number | undefined;
              const listingsStr = listingsCount != null ? `${(listingsCount as number).toLocaleString()} listings` : null;
              const distStr = '';
              const rangeStr = p25 != null && p75 != null ? ` (p25 €${p25}–p75 €${p75})` : '';
              const priceStrParts: string[] = [];
              if (avg != null) priceStrParts.push(`avg €${avg}`);
              if (median != null) priceStrParts.push(`median €${median}`);
              const priceStr = priceStrParts.join(', ');
              const lhs = priceStr ? priceStr + rangeStr : null;
              const rhs = listingsStr ? listingsStr + distStr : null;
              const note = [lhs, rhs].filter(Boolean).join(', ');
              return { name: a.name, note } as { name: string; note: string };
            });
            setRecommendedAreas(picks);
            return; // 如果后端已返回，直接结束
          }
        } catch {}

        // 预期 data 结构：{ xAxis: [area], series: { Listings: number[], 'Avg Price (€)': number[], Reviews?: number[] }, highlight: [area] }
        const data = await fetchNeighbourhoodAggregation(priceRange.min, priceRange.max);
        if (!data || !data.xAxis || !data.series) return;
        const names: string[] = data.xAxis;
        const listings: number[] = data.series?.Listings || [];
        const avgPrices: number[] = data.series?.['Avg Price (€)'] || [];
        const reviews: number[] = data.series?.Reviews || [];

        // Budget-friendly: highest listings within budget-highlight (if backend provided), else sort by listings asc price
        const budgetCandidates = names
          .map((name, idx) => ({ name, listings: listings[idx] ?? 0, price: avgPrices[idx] ?? 0 }))
          .sort((a, b) => (b.listings - a.listings) || (a.price - b.price));

        // Popular: by reviews or listings as fallback
        const popularCandidates = names
          .map((name, idx) => ({ name, reviews: reviews[idx] ?? 0, listings: listings[idx] ?? 0 }))
          .sort((a, b) => (b.reviews - a.reviews) || (b.listings - a.listings));

        // Balanced: closest to global average from price overview if available
        const globalAvg = localChartData.priceOverview?.summary?.avg_price ?? null;
        const balancedCandidates = names
          .map((name, idx) => ({ name, price: avgPrices[idx] ?? 0, listings: listings[idx] ?? 0 }))
          .sort((a, b) => {
            const da = globalAvg != null ? Math.abs(a.price - globalAvg) : Number.MAX_SAFE_INTEGER;
            const db = globalAvg != null ? Math.abs(b.price - globalAvg) : Number.MAX_SAFE_INTEGER;
            return da - db || b.listings - a.listings;
          });

        const picks: Array<{ type?: 'budget' | 'popular' | 'balanced'; name: string; note: string }> = [];
        
        // 🆕 从后端 by_budget 接口获取更贴切的备注
        try {
          const byBudget = await fetchAreasByBudget(priceRange.min, priceRange.max);
          if (byBudget?.areas?.length > 0) {
            // const budgetNames = new Set((byBudget?.areas || []).map((a: any) => a.name));
            if (budgetCandidates[0]) {
              const p = budgetCandidates[0];
              const matched = (byBudget?.areas || []).find((a: any) => a.name === p.name);
              const underText = matched?.p75_price ? `under €${Math.round(matched.p75_price)}` : `in your range`;
              picks.push({ type: 'budget', name: p.name, note: `budget-friendly, many listings ${underText}` });
            }
            if (popularCandidates[0]) {
              const p = popularCandidates[0];
              const matched = (byBudget?.areas || []).find((a: any) => a.name === p.name);
              const centerHint = matched?.distance_to_center != null ? `central location` : `central or highly reviewed`;
              picks.push({ type: 'popular', name: p.name, note: centerHint });
            }
            if (balancedCandidates[0]) {
              const p = balancedCandidates[0];
              const matched = (byBudget?.areas || []).find((a: any) => a.name === p.name);
              const around = matched?.median_price ? `around €${Math.round(matched.median_price)}` : `around average price`;
              picks.push({ type: 'balanced', name: p.name, note: `${around}, lively area` });
            }
          }
        } catch {}

        if (picks.length === 0) {
          // 回退到本地启发
          if (budgetCandidates[0]) picks.push({ type: 'budget', name: budgetCandidates[0].name, note: `budget-friendly, many listings` });
          if (popularCandidates[0]) picks.push({ type: 'popular', name: popularCandidates[0].name, note: `central or highly reviewed` });
          if (balancedCandidates[0]) picks.push({ type: 'balanced', name: balancedCandidates[0].name, note: `around average price, lively area` });
        }

        setRecommendedAreas(picks);
      } catch (e) {
        // fail silently
      }
    };
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPriceStep, priceRange?.min, priceRange?.max, localChartData.priceOverview?.summary?.avg_price]);
  
  // Commented out unused function
  // const fetchNeighbourhoodAggregationData = async () => {
  //   if (localChartData.neighbourhood) {
  //     setVisibleState((prev: any)=>({...prev, neighbourhood:!visibleState.neighbourhood}));
  //     return;
  //   } 
  //   setLoadingChart(true);
  //   try {
  //     if (!priceRange) {
  //       console.error("Price range is not defined");
  //       return;
  //     }
  //     const data = await fetchNeighbourhoodAggregation(priceRange.min, priceRange.max);
  //     if (data) {
  //       setLocalChartData((prev: any) => ({ ...prev, neighbourhood: data }));
  //       setVisibleState((prev: any)=>({...prev, neighbourhood: true}));
  //     }
  //   } catch (error) {
  //     console.error("🚨 Error fetching price overview:", error);
  //   } finally {
  //     setLoadingChart(false);
  //   }
  // }
  
  const fetchRoomTypeStackedData = async () => {
    if (localChartData.roomType) {
      setVisibleState((prev: any)=>({...prev, roomType:!visibleState.roomType}));
      // 可视化触发计数 - Room Type Mix 图表显示/隐藏
      if (messageId) {
        incrementVisualizationTrigger(messageId, 'roomtype_pie');
      }
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
        // 可视化触发计数 - Room Type Mix 图表首次加载
        if (messageId) {
          incrementVisualizationTrigger(messageId, 'roomtype_pie');
        }
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

    // 🆕 在 scripted 位置选择步骤下，禁用可视化卡片的“隐藏”切换
    const isScriptedLocationStep = (mode === 'scripted') && shouldShowHeatmapButton();

    return (
      <VisualizationCard
        visualizationData={adaptedVisualizationData as any}
        isVisible={visibleState.visualization}
        onToggleVisibility={isScriptedLocationStep ? undefined : () => 
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
          selectedDimensions={selectedDimensions}
          onSendMessage={onSendMessage}
      />
    );
  };

  return (
    <div className={`
      flex ${isUser ? "justify-end" : "justify-start"} items-center my-2
    `}>
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
              <div className="text-center mb-2 font-bold text-blue-700">🎯 Ready for Review Insights</div>
              <div className="text-sm">
                You can turn on <span className="font-bold text-blue-700">Review Q&A Mode</span> to query insights from user reviews for more precise suggestions and assistance.
              </div>
            </div>
          )}

          { // 🆕 价格步骤：显示文本 Summary 卡片（自动拉取，但不自动展开图表）
            !isUser && isPriceStep && localChartData.priceOverview?.summary && (
              <PriceSummaryCard
                totalListings={localChartData.priceOverview.summary.total_listings}
                avgPrice={localChartData.priceOverview.summary.avg_price}
                medianPrice={localChartData.priceOverview.summary.median_price}
                minPrice={localChartData.priceOverview.summary.min_price}
                maxPrice={localChartData.priceOverview.summary.max_price}
                budgetMin={priceRange?.min}
                budgetMax={priceRange?.max}
                coveragePct={localChartData.priceOverview.summary.coverage_pct ?? null}
                city={localChartData.priceOverview.summary.city || 'Berlin'}
                recommendedAreas={recommendedAreas}
              />
            )
          }

          { !isUser && shouldShowHeatmapButton() && (
            <div className="flex justify-center mt-3">
              <Button 
                type={mode === 'scripted' ? "primary" : "primary"} 
                size={mode === 'scripted' ? "middle" : "small"}
                onClick={handleOpenHeatmap}
                className={mode === 'scripted' 
                  ? "w-full text-white font-semibold bg-amber-500 hover:bg-amber-600 border-amber-500 ring-2 ring-amber-300" 
                  : "bg-green-500 hover:bg-green-600 border-green-500"}
                style={mode === 'scripted' ? { backgroundColor: '#fa8c16', borderColor: '#fa8c16' } : undefined}
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

          {/*
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
                    budgetMin={priceRange?.min}
                    budgetMax={priceRange?.max}
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
          */}

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
                  budgetMin={priceRange?.min}
                  budgetMax={priceRange?.max}
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

              {visibleState.roomType && localChartData.roomType && (() => {
                // Expect localChartData.roomType to contain counts by room type and total
                const colors: Record<string, string> = {
                  'Entire home/apt': '#60a5fa', // blue
                  'Private room': '#f59e0b',     // orange/amber
                  'Shared room': '#9ca3af',      // gray
                  'Hotel room': '#34d399'        // green
                };
                const raw = localChartData.roomType;
                const series = raw?.series || [];
                const total = Array.isArray(series)
                  ? series.reduce((s: number, sItem: any) => s + (Array.isArray(sItem.data) ? sItem.data.reduce((a: number, b: number) => a + (Number(b)||0), 0) : 0), 0)
                  : Number(raw?.total) || 0;
                const byType: Record<string, number> = {};
                if (Array.isArray(series)) {
                  series.forEach((sItem: any) => {
                    const key = String(sItem.name || '').trim();
                    const sum = Array.isArray(sItem.data) ? sItem.data.reduce((a: number, b: number) => a + (Number(b)||0), 0) : 0;
                    if (sum > 0) byType[key] = sum;
                  });
                }
                const entries = Object.entries(byType).filter(([k]) => ['Entire home/apt','Private room','Shared room','Hotel room'].includes(k));
                const totalSum = entries.reduce((s, [,v]) => s + v, 0);
                const items = entries.map(([label, value]) => ({ label, value, color: colors[label] || '#9ca3af' }));

                // Build summary: dominant >50% in bold, rare <5% collapsed
                const parts = entries
                  .map(([label, value]) => {
                    const pct = totalSum > 0 ? Math.round(value / totalSum * 100) : 0;
                    return { label, pct };
                  })
                  .sort((a, b) => b.pct - a.pct);
                const rares = parts.filter(p => p.pct < 5).map(p => p.label);
                const mains = parts.filter(p => p.pct >= 5);
                const top = mains[0];
                const second = mains[1];
                const bold = (s: string) => <span className="font-semibold">{s}</span>;

                const summary = (
                  <div className="text-sm text-gray-700">
                    {top ? (
                      <>
                        In this area, most listings are {top.pct >= 50 ? bold(`${top.label} (${top.pct}%)`) : `${top.label} (${top.pct}%)`}
                        {second ? `, followed by ${second.label} (${second.pct}%).` : '.'}
                      </>
                    ) : 'Room types unavailable.'}
                    {' '}
                    {rares.length > 0 && <span className="text-gray-500">{`Rare: ${rares.length >= 2 ? 'shared and hotel rooms' : rares.join(', ')} (<5%).`}</span>}
                  </div>
                );

                return (
                  <div className="w-full">
                    <Card
                      size="small"
                      title={"🏠 Room Type Mix"}
                    >
                      {summary}
                      <div className="mt-2">
                        <RoomTypePie items={items} height={180} showLegend={false} centerText={`n = ${total.toLocaleString ? total.toLocaleString() : total}`}/>
                      </div>
                      {total < 50 && (
                        <div className="text-xs text-gray-400 mt-1">Low data coverage</div>
                      )}
                    </Card>
                  </div>
                );
              })()}
            </div>
          )}

          {type === "social_prompt" && (
            <div className="w-full mt-2 space-y-2">
              <Typography.Paragraph strong>
                ✅ We’ve collected your preferences. Would you like to explore what other guests say next, or generate recommendations now?
              </Typography.Paragraph>

              <div className="flex justify-center gap-4">
                <Button type="primary" onClick={() => setIsModalVisible(true)}>
                  Show reviews insights
                </Button>
                <Button onClick={() => setConfirm && setConfirm(false)}>Give me recommendations</Button>
              </div>

              <ReviewsPromptModal 
                open={isModalVisible} 
                onClose={() => setIsModalVisible(false)} 
                budgetMin={priceRange?.min ?? null}
                budgetMax={priceRange?.max ?? null}
                areaName={selectedDimensions.find((d: any) => d.key === 'Location')?.value ?? null}
                selectedDimensions={selectedDimensions}
              />
            </div>
          )}

          {loadingChart && <div className="text-center text-gray-500 mt-2">Loading Data...</div>}
        </div>
        </RagSourceTooltip>

        {/* 已移除悬浮按钮，减少界面干扰 */}
      </div>

      {isUser && <Avatar size={36} icon={<UserOutlined />} className="ml-2" />}
      
      {/* Comment Search Tooltip moved to AgentChat component */}
    </div>
  );
};

export default MessageBubble;