// App.tsx - 在现有基础上添加地图数据管理
import { useEffect, useRef, useState, useCallback } from "react";
import ChatContainer from "./components/ChatContainer";
import RecommendationCard from "./components/recommendationCard/RecommendationCard";
import FreeDecisionCard from "./components/FreeDecisionCard";
import BerlinHeatmapModal from "./components/geoLayer/BerlinHeatmapModal";
import UserStudyAgreementModal from "./components/userStudy/UserStudyAgreementModal";
import LikertSurvey from "./components/userStudy/LikertSurvey";
import { POST_TASK_SECTIONS } from "./components/userStudy/surveyItems";
import { incrementPreferenceAdjust, buildPayload, markCommitted, isCommitted } from "./metrics/sessionMetrics";
import { commitSessionMetrics } from "./api/api";
import VisualizationCard from "./components/messageBox/visualInfo/VisualizationCard";
import { fetchTestChartOption, fetchRecommendations, type Recommendation } from "./api/api";

// 类型定义
interface Dimension {
  key: string;
  value: string;
}

interface DistrictInfo {
  name: string;
  level?: 'neighbourhood_group' | 'neighbourhood' | string;
  parent?: string | null;
  stats?: {
    // 兼容两种字段风格
    count?: number;
    avgPrice?: number;
    listing_count?: number;
    avg_price?: number;
  };
  selectedAt?: string;
  source?: string;
  isConfirmed?: boolean;
}

// Use API Recommendation type

// 新增：动画推荐列表组件
const AnimatedRecommendationList = ({ recommendations }: { recommendations: Recommendation[] }) => {
  // 使用一个更新标记，当推荐列表变化时触发动画
  const [animationKey, setAnimationKey] = useState(0);
  const prevRecommendationsRef = useRef<string[]>([]);
  
  // 当推荐列表变化时，更新标记以触发动画
  useEffect(() => {
    const currentIds = recommendations.map(item => item.id);
    const prevIds = prevRecommendationsRef.current;
    
    // 只有当ID列表真正变化时才触发动画
    if (JSON.stringify(currentIds) !== JSON.stringify(prevIds)) {
      setAnimationKey(prev => prev + 1);
      prevRecommendationsRef.current = currentIds;
    }
  }, [recommendations]);
  
  return (
    <div className="space-y-4">
      {recommendations.map((item, index) => (
        <div 
          key={`${item.id}-${animationKey}`}
          className="transform transition-all duration-300 animate-item"
          style={{ 
            opacity: 0,
            animation: "fadeInUp 0.5s forwards",
            animationDelay: `${index * 100}ms`
          }}
        >
          <RecommendationCard {...item} />
        </div>
      ))}
      
      <style>{`
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-item {
          opacity: 0;
        }
      `}</style>
    </div>
  );
};

// const CONSENT_KEY = 'user_study_consent_v1';

const App = () => {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [selectedDimensions, setSelectedDimensions] = useState<Dimension[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setMode] = useState<"none" | "scripted" | "agent">("none");
  // 🆕 测试图表相关状态
  const [testVisualizationData, setTestVisualizationData] = useState<any | null>(null);
  const [testChartLoading, setTestChartLoading] = useState(false);
  const [testChartError, setTestChartError] = useState<string | null>(null);
  // 🆕 测试图表参数
  const [selectedChartType, setSelectedChartType] = useState<string>('price_distribution');
  const [priceMinInput, setPriceMinInput] = useState<string>('');
  const [priceMaxInput, setPriceMaxInput] = useState<string>('');
 
  
  // 🆕 地图相关状态
  const [isMapVisible, setMapVisible] = useState(false);
  // Removed unused mapData state (modal no longer consumes it)
  const [selectedDistrict, setSelectedDistrict] = useState<DistrictInfo | null>(null); // 🆕 当前选中的区域
  // 🆕 记录地图打开来源（是否来自决策卡片）
  const [mapOpenedFromDecisionCard, setMapOpenedFromDecisionCard] = useState<boolean>(false);
  // 🆕 控制从其他入口打开地图时，是否抑制选择后发送消息（例如快捷按钮）
  const [mapSuppressChatOnSelect, setMapSuppressChatOnSelect] = useState<boolean>(false);

  const [subMode, setSubMode] = useState<"default" | "review_qa">("default");
  const [moreTopK, setMoreTopK] = useState<number>(10);
  // 完成提示 Overlay
  const [showCompletion, setShowCompletion] = useState(false);

  // 仅用于 Scripted 模式：控制“准备初始推荐”占位文案的显示时机
  const [scriptedInitPhase, setScriptedInitPhase] = useState<{
    hasEntered: boolean; // 是否进入过 scripted 模式
    inProgress: boolean; // 是否正在拉取首次推荐
    doneOnce: boolean;   // 是否至少成功或失败结束过一次首次拉取
  }>({ hasEntered: false, inProgress: false, doneOnce: false });

  const sidebarRef = useRef<HTMLDivElement>(null);

  // 🆕 从 ChatContainer 绑定 appendMessage
  const appendMessageRef = useRef<null | ((msg: any) => void)>(null);
  const bindAppendMessage = (fn: (msg: any) => void) => {
    appendMessageRef.current = fn;
  };

  // 🆕 从 ChatContainer 绑定 Agent 发送函数
  const agentSendRef = useRef<null | ((message: string) => void)>(null);
  const bindAgentSend = (fn: (message: string) => void) => {
    agentSendRef.current = fn;
  };

  // 🆕 绑定脚本模式下地图选择后的推进函数
  const scriptedMapAdvanceRef = useRef<null | ((district: string) => void)>(null);
  const bindScriptedMapAdvance = (fn: (district: string) => void) => {
    scriptedMapAdvanceRef.current = fn;
  };

  // 🆕 处理地图显示
  const [mapContext, setMapContext] = useState<string | null>(null);
  const handleShowMap = async (data: any = null) => {
    console.log('🗺️ App - 显示地图，接收数据:', data);
    // Citywide shortcut for Price Distribution: fetch without location filters
    if (data?.context === 'price_distribution' && data?.citywide) {
      try {
        try { window.dispatchEvent(new CustomEvent('price_distribution:loading', { detail: { loading: true } })); } catch {}
        setTestChartLoading(true);
        setTestChartError(null);
        const payload: any = { type: 'price_distribution' }; // no location fields
        console.log('[App] price_distribution citywide payload =>', payload);
        const res: any = await fetchTestChartOption(payload);
        const option = res?.echarts_option || res?.option || res;
        const chartKey = 'test';
        const visData = {
          visualization_message: 'Test Visualization',
          chart_suggestions: ['price_distribution'],
          visualizations: {
            [chartKey]: {
              chart_type: 'price_distribution',
              type: 'bar',
              title: 'Price Distribution Analysis',
              data: { type: 'price_distribution', area: 'Berlin (Citywide)' },
              echarts_option: option
            }
          }
        } as any;
        setTestVisualizationData(visData);
      } catch (e: any) {
        setTestChartError(e?.message || 'Failed to fetch citywide chart');
      } finally {
        try { window.dispatchEvent(new CustomEvent('price_distribution:loading', { detail: { loading: false } })); } catch {}
        setTestChartLoading(false);
        // do not open map in citywide mode
        setMapVisible(false);
        setMapOpenedFromDecisionCard(false);
        setMapSuppressChatOnSelect(false);
        setMapContext(null);
      }
      return;
    }

    // 默认打开地图
    setMapVisible(true);
    setMapSuppressChatOnSelect(!!data?.suppressChatOnMapSelect);
    setMapContext(data?.context || null);
  };

  // 🆕 仅用于性价比四象限入口：本地-only选择（不触发消息/不改决策卡）
  const handleLocalAreaOnly = (districtInfo: any) => {
    try {
      const name = (districtInfo && (districtInfo.name || districtInfo.area || districtInfo.district)) || '';
      if (name) {
        try { sessionStorage.setItem('area_name', name); } catch {}
        try { window.dispatchEvent(new CustomEvent('area:selected', { detail: { area: name } })); } catch {}
      }
    } finally {
      setMapVisible(false);
      setMapOpenedFromDecisionCard(false);
      setMapSuppressChatOnSelect(false);
      setMapContext(null);
    }
  };

  // (removed) handleReviewAnalysisLocalSelect – inlined in handleDistrictSelect

  // 🆕 处理区域选择
  const handleDistrictSelect = async (districtInfo: DistrictInfo) => {
    console.log('📍 App - 用户选择区域:', districtInfo);

    // 🎯 Reviews Analysis 特殊流：仅本地广播，不改变全局、不推送消息
    if (mapContext === 'reviews_analysis') {
      try {
        const name = districtInfo?.name || '';
        console.log('🟣 [App] Reviews Analysis 特殊路径触发', { name, districtInfo, mapContext });
        if (name) {
          console.log('🟣 [App] 准备派发 reviews_analysis:area_selected 事件', { area: name });
          window.dispatchEvent(new CustomEvent('reviews_analysis:area_selected', { detail: { area: name } }));
          console.log('🟣 [App] 事件已派发');
        }
      } finally {
        setMapVisible(false);
        setMapOpenedFromDecisionCard(false);
        setMapSuppressChatOnSelect(false);
        setMapContext(null);
      }
      return;
    }

    // 🎯 当地图来源是 Price Distribution 时，改为请求测试图表并拦截默认行为
    if (mapContext === 'price_distribution') {
      try {
        try { window.dispatchEvent(new CustomEvent('price_distribution:loading', { detail: { loading: true } })); } catch {}
        setTestChartLoading(true);
        setTestChartError(null);
        const payload: any = { type: 'price_distribution' };
        if (districtInfo.level === 'neighbourhood') {
          payload.neighbourhood = districtInfo.name;
        } else {
          payload.neighbourhood_group = districtInfo.name;
        }
        console.log('[App] price_distribution payload =>', payload);
        const res: any = await fetchTestChartOption(payload);
        const option = res?.echarts_option || res?.option || res;
        const chartKey = 'test';
        const visData = {
          visualization_message: 'Test Visualization',
          chart_suggestions: ['price_distribution'],
          visualizations: {
            [chartKey]: {
              chart_type: 'price_distribution',
              type: 'bar',
              title: 'Price Distribution Analysis',
              data: {
                type: 'price_distribution',
                // keep area for UI banner display
                area: districtInfo.name,
                // include backend-compatible filters for downstream consumers
                ...(districtInfo.level === 'neighbourhood'
                  ? { neighbourhood: districtInfo.name }
                  : { neighbourhood_group: districtInfo.name })
              },
              echarts_option: option
            }
          }
        } as any;
        setTestVisualizationData(visData);
      } catch (e: any) {
        setTestChartError(e?.message || 'Failed to fetch chart for selected area');
      } finally {
        try { window.dispatchEvent(new CustomEvent('price_distribution:loading', { detail: { loading: false } })); } catch {}
        setTestChartLoading(false);
        setMapVisible(false);
        setMapOpenedFromDecisionCard(false);
        setMapSuppressChatOnSelect(false);
        setMapContext(null);
      }
      return;
    }

    // 1. 保留一个 selectedDistrict 状态（如果你还在用的话）
    setSelectedDistrict(districtInfo);

    // 2. 更新 selectedDimensions：有 Location 就替换，没有就追加
    setSelectedDimensions(prev => {
      // 把旧的 Location filter 掉
      const others = prev.filter((dim: Dimension) => dim.key !== 'Location');
      // 然后把新的 Location 加进来
      const next = [
        ...others,
        { key: 'Location', value: districtInfo.name }
      ];
      try {
        // Mirror to window for downstream components (e.g., ReviewsPromptModal)
        (window as any).selectedDimensions = next;
        // Also persist simple fields in sessionStorage as fallback
        if (districtInfo?.name) sessionStorage.setItem('selected_area', districtInfo.name);
      } catch {}
      // 偏好调整计数 +1（位置改变） - 使用新的去重接口
      try { incrementPreferenceAdjust('location', districtInfo.name); } catch {}
      return next;
    });

    console.log('📍 自动添加/替换位置偏好:', districtInfo.name);

    // 3. 根据模式分别处理
    const areaLabel = districtInfo.level === 'neighbourhood' ? 'neighbourhood' : 'district';
    const userTip = `I selected the ${areaLabel}: ${districtInfo.name}.`;

    // 🆕 若地图是从决策卡片打开，或者子组件显式要求不发送消息，则仅关闭地图并返回
    const suppressMessage = mapOpenedFromDecisionCard || (districtInfo as any).shouldSendMessage === false || mapSuppressChatOnSelect;
    if (suppressMessage) {
      setMapVisible(false);
      // 重置来源标记与抑制标记
      setMapOpenedFromDecisionCard(false);
      setMapSuppressChatOnSelect(false);
      return;
    }

    if (mode === 'scripted') {
      // 关闭地图，先追加用户选择，然后直接推进脚本到下一步（不再显示可视化按钮）
      setMapVisible(false);
      appendMessageRef.current?.({ text: userTip, sender: 'user' });
      scriptedMapAdvanceRef.current?.(districtInfo.name);
      return;
    }

    // Agent 模式：保持原有行为
    window.setTimeout(() => {
      setMapVisible(false);
      agentSendRef.current?.(userTip);
    }, 1500);
  };
  
  
  // 移除：页面加载时不再自动拉取推荐

  // 当进入 Scripted 模式时，触发一次“首次推荐加载”状态
  useEffect(() => {
    if (mode === 'scripted' && !scriptedInitPhase.hasEntered) {
      setScriptedInitPhase({ hasEntered: true, inProgress: true, doneOnce: false });
    }
  }, [mode, scriptedInitPhase.hasEntered]);

  // 🆕 仅镜像 Room Type 到 sessionStorage（兼容 Reviews Use Decision Scope 解析）
  useEffect(() => {
    try {
      // 保持 window.selectedDimensions 最新，供读取回退
      (window as any).selectedDimensions = selectedDimensions;

      const roomTypeValues = selectedDimensions
        .filter((d: any) => String(d.key).toLowerCase() === 'room type')
        .map((d: any) => String(d.value).trim())
        .filter(Boolean);
      if (roomTypeValues.length > 0) {
        const unique = Array.from(new Set(roomTypeValues));
        sessionStorage.setItem('room_types', JSON.stringify(unique));
        sessionStorage.setItem('room_type', unique.join(','));
        try { console.log('📝 mirrored room_types to sessionStorage', unique); } catch {}
      }
    } catch {}
  }, [selectedDimensions]);

  // 当 ChatContainer 首次拉取推荐完成（或失败）后，标记完成
  useEffect(() => {
    if (!scriptedInitPhase.hasEntered) return;
    // 当推荐产生或明确无数据时，认为首次阶段已结束
    if (recommendations.length > 0 && scriptedInitPhase.inProgress) {
      setScriptedInitPhase({ hasEntered: true, inProgress: false, doneOnce: true });
    }
  }, [recommendations, scriptedInitPhase]);

  // 兜底：超过一定时间（例如8秒）后，不再显示“准备中”占位
  useEffect(() => {
    if (mode !== 'scripted' || !scriptedInitPhase.inProgress || scriptedInitPhase.doneOnce) return;
    const timer = window.setTimeout(() => {
      setScriptedInitPhase((s) => ({ ...s, inProgress: false, doneOnce: true }));
    }, 8000);
    return () => window.clearTimeout(timer);
  }, [mode, scriptedInitPhase.inProgress, scriptedInitPhase.doneOnce]);

  // 🆕 协议与问卷：状态与初次弹出
  const [agreementOpen, setAgreementOpen] = useState(false);
  const [agreementAgreed, setAgreementAgreed] = useState(false);
  const [agreementFirstOpen, setAgreementFirstOpen] = useState(true);
  const [surveyOpen, setSurveyOpen] = useState(false);

  // mock 问卷
  const mockSections = POST_TASK_SECTIONS;

  // 首次进入：纯前端内存控制（每次刷新视为新用户）
  useEffect(() => {
    setAgreementAgreed(false);
    setAgreementFirstOpen(true);
    setAgreementOpen(true);
  }, []);

  // 全局“完成并提交”按钮逻辑
  const submitMetricsOnce = useCallback(async () => {
    if (isCommitted()) return;
    try {
      const payload = buildPayload();
      const res = await fetch('http://localhost:5000/api/metrics/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        markCommitted();
        console.log('✅ 指标提交成功');
        setShowCompletion(true);
      } else {
        console.warn('⚠️ 指标提交失败 (HTTP', res.status, ')');
      }
    } catch (e) {
      console.warn('⚠️ 指标提交失败:', e);
    }
  }, []);

  // beforeunload 兜底提交（挂载一次）
  useEffect(() => {
    const onUnload = () => {
      if (isCommitted()) return;
      try {
        const payload = buildPayload();
        let sent = false;
        if (typeof navigator.sendBeacon === 'function') {
          sent = navigator.sendBeacon(
            'http://localhost:5000/api/metrics/commit',
            new Blob([JSON.stringify(payload)], { type: 'application/json' })
          );
        }
        if (!sent) {
          try { commitSessionMetrics(payload as any); } catch {}
        }
      } catch (_) {}
    };
    window.addEventListener('beforeunload', onUnload);
    return () => window.removeEventListener('beforeunload', onUnload);
  }, []);

  return (
    <div className="relative w-screen h-screen from-blue-100 via-white to-blue-50 overflow-hidden">
      {(mode === 'agent' || mode === 'scripted') && (
        <button
          onClick={submitMetricsOnce}
          className="fixed bottom-6 right-6 z-[70] px-5 py-3 rounded-full shadow-xl bg-gradient-to-r from-blue-600 to-purple-600 text-white hover:opacity-95 transition-opacity cursor-pointer"
        >
          {mode === 'agent' ? 'Finish Agent Session' : 'Finish Scripted Session'}
        </button>
      )}

      {/* 提交完成 Overlay */}
      {showCompletion && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-sm w-[92%] text-center">
            <div className="mx-auto mb-4 w-16 h-16 flex items-center justify-center rounded-full bg-green-100 text-green-600 text-3xl">✅</div>
            <div className="text-xl font-semibold text-gray-800 mb-2">Thank you for your participation</div>
            <div className="text-sm text-gray-600 mb-6">Your {mode === 'agent' ? 'Agent' : 'Scripted'} session is complete, and your data has been submitted successfully.</div>
            <button
              onClick={() => setShowCompletion(false)}
              className="px-4 py-2 rounded-full bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow hover:opacity-95 transition-opacity cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      )}
      {/* ✅ 右上角按钮：协议 + 5-Likert 问卷 */}
      <div className="absolute top-4 right-4 z-[60] flex items-center gap-2">
        {/* 🆕 图表类型选择 */}
        <select
          value={selectedChartType}
          onChange={(e) => setSelectedChartType(e.target.value)}
          className="px-2 py-2 rounded-full bg-white/90 hover:bg-white text-gray-800 shadow-sm border border-gray-200 transition-colors text-sm"
        >
          <option value="price_distribution">Price Distribution</option>
          <option value="location_popularity">Location Popularity</option>
          <option value="room_type_comparison">Room Type Comparison</option>
          <option value="neighbourhood_comparison">Neighbourhood Comparison</option>
          <option value="reviews_analysis">Reviews Analysis</option>
          <option value="price_trend">Price Trend</option>
          <option value="availability_analysis">Availability Analysis</option>
          <option value="host_analysis">Host Analysis</option>
          
          <option value="price_coverage_delta">Price Coverage Delta</option>
          <option value="comments_wordcloud">Comments Word Cloud</option>
          <option value="distance_price_tradeoff">Distance-Price Tradeoff</option>
          <option value="value_quality_quadrant">Value × Quality Quadrant</option>
        </select>
        {/* 🆕 可选预算输入 */}
        <input
          type="number"
          inputMode="numeric"
          placeholder="Min €"
          value={priceMinInput}
          onChange={(e) => setPriceMinInput(e.target.value)}
          className="w-24 px-2 py-2 rounded-full bg-white/90 text-gray-800 shadow-sm border border-gray-200 text-sm"
        />
        <input
          type="number"
          inputMode="numeric"
          placeholder="Max €"
          value={priceMaxInput}
          onChange={(e) => setPriceMaxInput(e.target.value)}
          className="w-24 px-2 py-2 rounded-full bg-white/90 text-gray-800 shadow-sm border border-gray-200 text-sm"
        />
        <button
          onClick={() => setAgreementOpen(true)}
          className="px-3 py-2 rounded-full bg-white/90 hover:bg-white text-gray-800 shadow-sm border border-gray-200 transition-colors text-sm"
        >
          Agreement
        </button>
        <button
          onClick={() => setSurveyOpen(true)}
          className="px-3 py-2 rounded-full bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow-sm hover:opacity-95 transition-opacity text-sm"
        >
          5-Likert Survey
        </button>
        {/* 🆕 测试图表按钮 */}
        <button
          onClick={async () => {
            setTestChartLoading(true);
            setTestChartError(null);
            try {
              const price_min = priceMinInput !== '' ? Number(priceMinInput) : undefined;
              const price_max = priceMaxInput !== '' ? Number(priceMaxInput) : undefined;
              const payload: any = {
                type: selectedChartType,
                ...(price_min !== undefined ? { price_min } : {}),
                ...(price_max !== undefined ? { price_max } : {}),
              };
              if (selectedChartType === 'comments_wordcloud') {
                payload.preferences = {
                  level: 'neighbourhood',
                  group: 'Pankow',
                  name: 'Helmholtzplatz',
                  top_n: 50,
                  measure: 'freq'
                };
              }
              console.log('[App] test payload =>', payload);
              const res: any = await fetchTestChartOption(payload);
              const option = res?.echarts_option || res?.option || res;
              // 构造 VisualizationCard 需要的数据结构
              const mapTypeToChartType = (t: string): 'bar' | 'pie' | 'line' | 'scatter' => {
                if (t.includes('reviews_time_series') || t.includes('trend') || t.includes('time')) return 'line';
                if (t.includes('pie')) return 'pie';
                if (t.includes('scatter') || t.includes('host') || t.includes('distance') || t.includes('tradeoff')) return 'scatter';
                if (t.includes('value_quality_quadrant') || t.includes('value_quality')) return 'scatter';
                return 'bar';
              };
              const titleMap: Record<string, string> = {
                price_distribution: 'Price Distribution Analysis',
                location_popularity: 'Location Popularity',
                room_type_comparison: 'Room Type Comparison',
                neighbourhood_comparison: 'Neighbourhood Comparison',
                reviews_analysis: 'Reviews Analysis',
                price_trend: 'Price Trend',
                availability_analysis: 'Availability Analysis',
                host_analysis: 'Host Analysis',
                
                price_coverage_delta: 'Price Coverage Delta',
                comments_wordcloud: 'Comments Word Cloud',
                distance_price_tradeoff: 'Distance-Price Tradeoff'
                , value_quality_quadrant: 'Value × Quality Quadrant'
              };
              const chartKey = 'test';
              const chartType = mapTypeToChartType(selectedChartType);
              const chartTitle = titleMap[selectedChartType] || 'Test Chart';
              const visData = {
                visualization_message: 'Test Visualization',
                chart_suggestions: [selectedChartType],
                user_budget_info: (price_min || price_max) ? { min_price: price_min, max_price: price_max, currency: '€' } : undefined,
                visualizations: {
                  [chartKey]: {
                    type: chartType,
                    title: chartTitle,
                    data: selectedChartType === 'room_type_comparison' ? { type: 'room_type_comparison' }
                      : (selectedChartType === 'price_distribution' ? { type: 'price_distribution' }
                      : (selectedChartType === 'value_quality_quadrant' ? { type: 'value_quality_quadrant' } : {})),
                    // 避免触发 PriceDistributionBar；交给通用 ECharts 渲染
                    options: selectedChartType === 'room_type_comparison' ? { type: 'room_type_comparison' }
                      : (selectedChartType === 'value_quality_quadrant' ? { type: 'value_quality_quadrant' } : undefined),
                    echarts_option: option
                  }
                }
              };
              setTestVisualizationData(visData);
            } catch (e: any) {
              setTestChartError(e?.message || 'Failed to fetch test chart');
            } finally {
              setTestChartLoading(false);
            }
          }}
          className="px-3 py-2 rounded-full bg-white/90 hover:bg-white text-gray-800 shadow-sm border border-gray-200 transition-colors text-sm"
        >
          Test Chart
        </button>
      </div>

      {/* ✅ 聊天居中固定区域 */}
      <div className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 z-10">
        <ChatContainer
          selectedDimensions={selectedDimensions}
          setRecommendations={setRecommendations}
          setSelectedDimensions={setSelectedDimensions}
          mode={mode}
          setMode={setMode}
          onShowMap={handleShowMap} // 🔄 修改：使用新的处理函数
          subMode={subMode}
          setSubMode={setSubMode}
          // 🆕 绑定 appendMessage，供地图选择后发送消息
          onBindAppendMessage={bindAppendMessage}
          // 🆕 绑定 Agent 发送函数
          onBindAgentSendMessage={bindAgentSend}
          // 🆕 绑定脚本模式地图推进
          onBindScriptedMapAdvance={bindScriptedMapAdvance}
          isMapVisible={isMapVisible}
        />
      </div>

      {/* ✅ 决策卡片固定在右侧中上方 */}
      {(mode === 'agent' || mode === 'scripted') && (
      <div className="absolute top-[15%] right-6 z-20">
        <FreeDecisionCard
          selectedDimensions={selectedDimensions}
          onConfirm={(newRecs: Recommendation[]) => setRecommendations(newRecs)}
          isLoading={isLoading}
          setIsLoading={setIsLoading}
          mode={mode}
          onShowMap={(payload) => { setMapOpenedFromDecisionCard(true); handleShowMap(payload); }} // 🆕 添加地图显示回调，并标记来源为决策卡片
        />
        {/* Scripted 模式下的占位提示：仅在首次进入且首次拉取未完成且当前无推荐时显示 */}
        {mode === 'scripted' && scriptedInitPhase.inProgress && recommendations.length === 0 && (
          <div className="mt-3 px-3 py-2 text-xs text-gray-500 bg-white/70 rounded border border-gray-200">
            Preparing recommendations for scripted mode…
          </div>
        )}
      </div>
      )}

      {/* 🆕 测试可视化卡片：在左下角显示（有数据后） */}
      {testVisualizationData && (
        <div className="fixed left-8 bottom-8 z-30 w-[420px] bg-white/90 rounded-xl shadow-lg border border-gray-200 p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-semibold text-gray-700">Test Visualization</div>
            <div className="flex items-center gap-2">
              {testChartLoading && <span className="text-xs text-gray-400">Loading…</span>}
              {testChartError && <span className="text-xs text-red-500">{testChartError}</span>}
            </div>
          </div>
          <VisualizationCard
            visualizationData={testVisualizationData}
            isVisible={true}
            onDistrictSelect={() => { /* 测试中可不处理 */ }}
            onShowMap={(payload) => handleShowMap(payload || { suppressChatOnMapSelect: true })}
          />
        </div>
      )}

      {/* ✅ 推荐卡片浮动侧边栏 - 悬浮卡片样式 */}
      {(mode === 'agent' || mode === 'scripted') && (
      <div
        ref={sidebarRef}
        id="recommendation-panel"
        className="fixed top-8 left-8 w-[380px] max-h-[90vh] bg-gradient-to-b from-white via-blue-50 to-gray-100 rounded-2xl shadow-2xl border border-gray-200 z-40 flex flex-col overflow-hidden"
        style={{ minHeight: '120px' }}
      >
        <div className="p-6 overflow-y-auto flex-1">
          {/* 标题区域 */}
          <div className="mb-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-gray-800 mb-2">🔍 Recommended Listings</h2>
                <div className="h-1 w-12 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"></div>
              </div>
              {(mode === 'scripted' || mode === 'agent') && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-600">Fetch more</span>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    value={moreTopK}
                    onChange={(e) => setMoreTopK(Math.max(1, Math.min(100, Number(e.target.value) || 1)))}
                    className="w-16 px-2 py-1 border border-gray-300 rounded"
                  />
                  <button
                    className="px-2 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700"
                    onClick={async () => {
                      try {
                        setIsLoading(true);
                        // 合并 Room Type 偏好
                        const nonRoomType = selectedDimensions.filter((d: any) => d.key !== "Room Type");
                        const roomTypes = selectedDimensions
                          .filter((d: any) => d.key === "Room Type")
                          .map((d: any) => String(d.value).trim())
                          .filter(Boolean);
                        const mergedRoomType = roomTypes.length > 0
                          ? [{ key: "Room Type", value: Array.from(new Set(roomTypes)).join(", ") }]
                          : [];
                        const apiDimensions = [
                          ...nonRoomType.map((d: any) => ({ key: d.key, value: String(d.value) })),
                          ...mergedRoomType,
                        ];
                        const res = await fetchRecommendations({ selectedDimensions: apiDimensions as any, top_k: moreTopK });
                        const list = Array.isArray(res) ? (res as any) : ((((res as any)?.recommendations ?? []) as any[]));
                        if (Array.isArray(list) && list.length > 0) {
                          setRecommendations(list as any);
                        } else {
                          console.warn('⚠️ Sidebar Fetch: Backend returned empty recommendations array, keeping current list');
                        }
                      } catch (e) {
                        console.error('Failed to fetch more recommendations (sidebar):', e);
                      } finally {
                        setIsLoading(false);
                      }
                    }}
                  >
                    Fetch
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* 🆕 显示当前选中区域信息 */}
          {selectedDistrict && (
            <div className="mb-6 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-200 shadow-sm">
              <div className="flex items-center mb-2">
                <div className="w-2 h-2 bg-blue-500 rounded-full mr-2"></div>
                <div className="text-sm font-semibold text-blue-800">📍 Selected Area</div>
              </div>
              <div className="text-lg font-bold text-blue-900 mb-1">{selectedDistrict.name}</div>
              <div className="flex items-center justify-between text-xs text-blue-600">
                <span className="flex items-center">
                  <span className="mr-1">🏠</span>
                  Listings: {selectedDistrict.stats?.listing_count ?? selectedDistrict.stats?.count ?? 0}
                </span>
                <span className="flex items-center">
                  <span className="mr-1">💰</span>
                  Avg. Price: €{selectedDistrict.stats?.avg_price ?? selectedDistrict.stats?.avgPrice ?? 0}
                </span>
              </div>
            </div>
          )}
          
          {/* 🔄 修改：用动画组件替换静态列表 */}
          {recommendations.length > 0 ? (
            <AnimatedRecommendationList recommendations={recommendations} />
          ) : (
            mode === 'scripted' ? (
              <div className="text-center py-8">
                <div className="text-gray-500 text-sm">Preparing initial recommendations for scripted mode…</div>
                <div className="text-gray-400 text-xs mt-2">They will appear here shortly based on your scripted flow.</div>
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="text-gray-400 text-6xl mb-4">🏠</div>
                <div className="text-gray-500 text-sm">No recommended listings</div>
                <div className="text-gray-400 text-xs mt-2">Start a conversation to get personalized recommendations</div>
              </div>
            )
          )}
        </div>
      </div>
      )}

      {/* ✅ 展开/收起按钮 */}
      {/* 已移除切换按钮，不再显示 */}

      {/* 🔄 修改：地图Modal添加数据和回调 */}
      <BerlinHeatmapModal 
        open={isMapVisible} 
        onClose={() => { setMapVisible(false); setMapOpenedFromDecisionCard(false); setMapSuppressChatOnSelect(false); }}
        onDistrictSelect={handleDistrictSelect} // 🆕 区域选择回调
        shouldSendMessageOnSelect={!mapOpenedFromDecisionCard && !mapSuppressChatOnSelect}
        requireSelectionBeforeClose={mode === 'scripted'}
        messageId={'map-modal'}
        onLocalAreaSelect={mapContext === 'value_quality_quadrant' ? handleLocalAreaOnly : undefined}
      />

      {/* 测试可视化使用 VisualizationCard 的内置 Modal 展示全图 */}

      {/* 协议弹窗 */}
      <UserStudyAgreementModal
        open={agreementOpen}
        agreed={agreementAgreed}
        isFirstOpen={agreementFirstOpen}
        onAgree={() => { 
          setAgreementAgreed(true); 
          setAgreementFirstOpen(false); 
          setAgreementOpen(false);
        }}
        onClose={() => setAgreementOpen(false)}
        onDisagree={() => {
          // 退出页面
          try { window.location.replace('about:blank'); } catch (_) {}
        }}
      />

      {/* 5-Likert 问卷弹窗 */}
      <LikertSurvey
        open={surveyOpen}
        title="Questionnaire (5-point Likert)"
        sections={mockSections}
        onClose={() => setSurveyOpen(false)}
        onSubmit={(answers) => {
          console.log('Survey answers:', answers);
          setSurveyOpen(false);
        }}
      />
    </div>
  );
};

export default App;