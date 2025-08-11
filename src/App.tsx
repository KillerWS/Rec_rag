// App.tsx - 在现有基础上添加地图数据管理
import { useEffect, useRef, useState } from "react";
import ChatContainer from "./components/ChatContainer";
import RecommendationCard from "./components/recommendationCard/RecommendationCard";
import { fetchRecommendations } from "./api/api";
import FreeDecisionCard from "./components/FreeDecisionCard";
import BerlinHeatmapModal from "./components/geoLayer/BerlinHeatmapModal";

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

interface Recommendation {
  id: string;
  name: string;
  price: number;
  room_type: string;
  neighbourhood: string;
  neighbourhood_group: string;
  availability_365: number;
  number_of_reviews: number;
  number_of_reviews_ltm: number;
  reviews_per_month: number;
  last_review: string;
  recommendation_score: number;
  [key: string]: any;
}

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

const App = () => {
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [selectedDimensions, setSelectedDimensions] = useState<Dimension[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setMode] = useState<"none" | "scripted" | "agent">("none");
  
  // 🆕 地图相关状态
  const [isMapVisible, setMapVisible] = useState(false);
  // Removed unused mapData state (modal no longer consumes it)
  const [selectedDistrict, setSelectedDistrict] = useState<DistrictInfo | null>(null); // 🆕 当前选中的区域

  const [subMode, setSubMode] = useState<"default" | "review_qa">("default");

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

  const loadInitialRecommendations = async () => {
    try {
      const res = await fetchRecommendations({ selectedDimensions: [], top_k: 5 });
      if (res && res.recommendations && Array.isArray(res.recommendations)) {
        setRecommendations(res.recommendations || []);
      }
    } catch (error) {
      console.error("Failed to fetch initial recommendations:", error);
    }
  };

  // 🆕 处理地图显示
  const handleShowMap = (data = null) => {
    console.log('🗺️ App - 显示地图，接收数据:', data);
    setMapVisible(true);
  };

  // 🆕 处理区域选择
  const handleDistrictSelect = (districtInfo: DistrictInfo) => {
    console.log('📍 App - 用户选择区域:', districtInfo);

    // 1. 保留一个 selectedDistrict 状态（如果你还在用的话）
    setSelectedDistrict(districtInfo);

    // 2. 更新 selectedDimensions：有 Location 就替换，没有就追加
    setSelectedDimensions(prev => {
      // 把旧的 Location filter 掉
      const others = prev.filter((dim: Dimension) => dim.key !== 'Location');
      // 然后把新的 Location 加进来
      return [
        ...others,
        { key: 'Location', value: districtInfo.name }
      ];
    });

    console.log('📍 自动添加/替换位置偏好:', districtInfo.name);

    // 3. 根据模式分别处理
    const areaLabel = districtInfo.level === 'neighbourhood' ? 'neighbourhood' : 'district';
    const userTip = `I selected the ${areaLabel}: ${districtInfo.name}.`;

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
  
  
  useEffect(() => {
    loadInitialRecommendations();
  }, []);

  return (
    <div className="relative w-screen h-screen from-blue-100 via-white to-blue-50 overflow-hidden">
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
        />
      </div>

      {/* ✅ 决策卡片固定在右侧中上方 */}
      {mode === 'agent' && (
      <div className="absolute top-[15%] right-6 z-20">
        <FreeDecisionCard
          selectedDimensions={selectedDimensions}
          onConfirm={(newRecs: Recommendation[]) => setRecommendations(newRecs)}
          isLoading={isLoading}
          setIsLoading={setIsLoading}
          mode={mode}
          onShowMap={handleShowMap} // 🆕 添加地图显示回调
        />
      </div>
      )}

      {/* ✅ 推荐卡片浮动侧边栏 - 悬浮卡片样式 */}
      {mode === 'agent' && (
      <div
        ref={sidebarRef}
        id="recommendation-panel"
        className="fixed top-8 left-8 w-[380px] max-h-[90vh] bg-gradient-to-b from-white via-blue-50 to-gray-100 rounded-2xl shadow-2xl border border-gray-200 z-40 flex flex-col overflow-hidden"
        style={{ minHeight: '120px' }}
      >
        <div className="p-6 overflow-y-auto flex-1">
          {/* 标题区域 */}
          <div className="mb-6">
            <h2 className="text-xl font-bold text-gray-800 mb-2">🔍 Recommended Listings</h2>
            <div className="h-1 w-12 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"></div>
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
            <div className="text-center py-8">
              <div className="text-gray-400 text-6xl mb-4">🏠</div>
              <div className="text-gray-500 text-sm">No recommended listings</div>
              <div className="text-gray-400 text-xs mt-2">Start a conversation to get personalized recommendations</div>
            </div>
          )}
        </div>
      </div>
      )}

      {/* ✅ 展开/收起按钮 */}
      {/* 已移除切换按钮，不再显示 */}

      {/* 🔄 修改：地图Modal添加数据和回调 */}
      <BerlinHeatmapModal 
        open={isMapVisible} 
        onClose={() => setMapVisible(false)}
        onDistrictSelect={handleDistrictSelect} // 🆕 区域选择回调
      />
    </div>
  );
};

export default App;