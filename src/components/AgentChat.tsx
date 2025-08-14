// AgentChat.tsx - 在原有基础上添加完整地图功能
import { useState, useRef, useEffect } from "react";
import { Switch } from "antd";
import MessageBubble from "./messageBox/MessageBubble";
import { fetchRAGAnswer } from "../api/api";
import { 
  handleBackendResponse
} from "../utils/preferenceUtils";
import RoomTypeMixModal from './quickModals/RoomTypeMixModal';
import ValueForMoneyModal from './quickModals/ValueForMoneyModal';
import ReviewInsightsModal from './quickModals/ReviewInsightsModal';
// import CompareDistrictsModal from './quickModals/CompareDistrictsModal';

interface AgentChatProps {
  indexId: string | null;
  selectedDimensions: any[];
  setSelectedDimensions: (updater: any) => void;
  // onConfirm?: () => void;
  messages: any[];
  // setMessages: (updater: any) => void;
  appendMessage: (msg: any) => void;
  setRecommendations: (recs: any) => void;
  onShowMap?: (data: any) => void;
  mode: string;
  subMode: string;
  onModeSwitch: (checked?: any) => void;
}

const AgentChat: React.FC<AgentChatProps> = ({
  indexId,
  selectedDimensions,
  setSelectedDimensions,
  // onConfirm,
  messages,
  // setMessages,
  appendMessage,
  setRecommendations,
  onShowMap, // 🗺️ 新增：接收地图回调
  mode,
  subMode,
  onModeSwitch
}) => {
  const [inputValue, setInputValue] = useState("");
  const [, setLoading] = useState(false);
  const [showGlobalHint, setShowGlobalHint] = useState(false);
  const [globalSearchEnabled, setGlobalSearchEnabled] = useState(false);
  const [isPreferenceStage, setIsPreferenceStage] = useState(true);
  
  const [regeneratingMessageId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const textAreaRef = useRef<HTMLTextAreaElement | null>(null);

  // Removed showPriceModal; we now open the map directly from the quick button
  const [showRoomTypeModal, setShowRoomTypeModal] = useState(false);
  const [showValueModal, setShowValueModal] = useState(false);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [showCompareModal, setShowCompareModal] = useState(false);

  useEffect(() => {
    const timeout = setTimeout(() => {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
    return () => clearTimeout(timeout);
  }, [messages]);

  useEffect(() => {
    // 首次显示引导气泡（v2，避免之前的本地记录影响）
    const seen = localStorage.getItem('global_hint_seen_v2');
    if (!seen) {
      setShowGlobalHint(true);
    }
  }, []);

  useEffect(() => {
    if (showGlobalHint === false) {
      localStorage.setItem('global_hint_seen_v2', '1');
    }
  }, [showGlobalHint]);

  const autoResizeTextarea = () => {
    const ta = textAreaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    const max = 120; // px, max grow height
    ta.style.height = Math.min(ta.scrollHeight, max) + 'px';
  };

  useEffect(() => {
    autoResizeTextarea();
  }, [inputValue]);

  // 🔄 修改：handleOpenHeatmap 函数，完善数据传递
  const handleOpenHeatmap = (messageData: any = null, selectedDistrict: string | null = null) => {
    const mapData = {
      userPreferences: selectedDimensions,
      chatContext: messages.slice(-5),
      triggerData: messageData,
      requestType: (messageData as any)?.test ? 'debug' : 'user_request',
      selectedDistrict: selectedDistrict,
      timestamp: new Date().toISOString()
    };
    if (onShowMap) {
      onShowMap(mapData);
    }
  };

  // const containsMapKeywords = (text: string) => {
  //   const mapKeywords = [
  //     '地图', '区域', '分布', '位置', '地理', 'map', 'district', 'location', 
  //     '柏林', 'berlin', '热力图', 'heatmap', '可视化', 'visualization'
  //   ];
  //   return mapKeywords.some(keyword => 
  //     text.toLowerCase().includes(keyword.toLowerCase())
  //   );
  // };

  const hasVisualizationData = (response: any) => {
    const hasViz = response?.visualizations && 
                  Object.keys(response.visualizations).length > 0;
    return hasViz;
  };

  const appendVisualizationMessage = (messageText: string, visualizationData: any, visualizationFilters: any = null, res: any,) => {
    const level = visualizationFilters.neighbourhood ? 'neighbourhood' : 'district';
    const groupName =
      visualizationFilters.neighbourhood
        || visualizationFilters.neighbourhood_group
        || 'ALL';
    const newMessage = {
      text: messageText,
      sender: "system",
      type: "visualization",
      visualizationData: visualizationData,
      visualizationFilters: visualizationFilters,
      insightsLevel: level,
      insightsGroupName: groupName,
      source_documents: res.source_documents //这里加上source_documents,不然像 visualization、comments_insights、preference_summary 等分支没有带上它
    };
    appendMessage(newMessage);
  };

  const handleTargetDimension = (response: any) => {
    const followupInfo = response?.followup_info;
    const targetDimension =Array.isArray(followupInfo?.followup_question?.target_dimensions) ? followupInfo?.followup_question?.target_dimensions[0] : followupInfo?.followup_question?.target_dimension;
    if (!targetDimension) {
      return false;
    }
    if (targetDimension.toLowerCase() === 'budget') {
      const budgetMsg  = {
        text: response.answer || "What's your budget range per night?",
        sender: "system",
        type: "budget_input",
        targetDimensions: ["budget"]
      };
      appendMessage(budgetMsg );
      return true;
    }
    if (targetDimension.toLowerCase() === 'location') {
      const locMsg = {
        text: response.answer || "Which area of Berlin would you prefer?",
        sender: "system",
        type: "neighbourhood_prompt",
        targetDimensions: [targetDimension]
      };
      appendMessage(locMsg);
      return true;
    }
    if (targetDimension.toLowerCase() === 'room_type') {
      const roomTypeMsg  = {
        text: response.answer || "What's your budget range per night?",
        sender: "system",
        type: "room_type",
        targetDimensions: ["room_type"]
      };
      appendMessage(roomTypeMsg);
      return true;
    }
    return false;
  };

  const handleBudgetSubmit = async (budgetData: any) => {
    const userMessage = `My budget is ${budgetData.range} per night`;
    appendMessage({ text: userMessage, sender: "user" });
    await sendBudgetToBackend(userMessage, budgetData);
  };

  const sendBudgetToBackend = async (userMessage: string, budgetData: any) => {
    setLoading(true);
    const historyForApi = messages.map((msg) => ({
      type: msg.sender,
      data: msg.text
    })).concat({ type: "human", data: userMessage });
    try {
      const res = await fetchRAGAnswer(userMessage, historyForApi, indexId as string, {
        budget_data: budgetData,
        dimension_type: 'budget'
      });
      await processBackendResponse(res);
    } catch (error) {
      appendMessage({ 
        text: "Sorry, I couldn't process your budget. Please try again.", 
        sender: "system" 
      });
    } finally {
      setLoading(false);
    }
  };
  
  // const sendRoomTypeToBackend = async (roomType: string) => { /* unused */ };

  const processBackendResponse = async (res: any) => {
    const hasPreferenceSummary = res?.preference_summary != null;
    // const hasConfirmation = res?.show_confirmation && res?.confirmation_type === "recommendation";
    const hasTargetDimension = handleTargetDimension(res);
    const hasVizData = hasVisualizationData(res);
    const hasComments = res?.comments != null;
    const hasRecommendations = res?.recommendations != null;

    const source_documents = res?.source_documents;
    console.log("source_documents", source_documents);

    if (hasRecommendations) {
      setRecommendations(res.recommendations);
    }

    if (hasPreferenceSummary) {
      appendMessage({
        text: res.preference_summary,
        sender: "system",
        type: "preference_summary"
      });
      if (onModeSwitch) {
        onModeSwitch("review_qa");
      }
      // Leaving preference collection stage – enable retrieval controls
      setIsPreferenceStage(false);
    }

    if (hasTargetDimension) {
      // handled
    } else if(hasComments){
      appendMessage({
        text: res.answer || "Here are some comment insights:",
        sender: "system",
        type: "comments_insights",
        commentData: res.comments,
        insightsLevel: res.visualization_filters?.neighbourhood ? 'neighbourhood' : 'district',
        insightsGroupName: res.visualization_filters?.neighbourhood
                        || res.visualization_filters?.neighbourhood_group
                        || 'ALL',
        source_documents: source_documents // 新增
      });
    } else if (hasVizData) {
      const messageText = res.answer || res.visualization_message || "Here's the data visualization:";
      appendVisualizationMessage(messageText, res, res.visualization_filters, res);
    } else {
      if (res?.answer) {
        appendMessage({
          text: res.answer,
          sender: "system",
          commentData: res.comments ?? null,
          source_documents: source_documents
        });
      }
    }

    const result = handleBackendResponse(res, setSelectedDimensions);
    if (result.updated) {
      // updated
    }
  };

  const handleSendMessage = async (message?: string) => {
    const userMessage = message ? message.trim() : inputValue.trim();
    if (!userMessage) return;
    appendMessage({ text: userMessage, sender: "user" });
    if (!message) {
      setInputValue("");
    }
    setIsLoading(true);

    const historyForApi = messages.map((msg) => ({
      type: msg.sender,
      data: msg.text
    })).concat({ type: "human", data: userMessage });

    try {
      const extraParams = globalSearchEnabled
        ? { sub_mode: 'review_qa', global_search: true}
        : { sub_mode: subMode };

      const res = await fetchRAGAnswer(userMessage, historyForApi, indexId as string, extraParams);
      await processBackendResponse(res);
      setInputValue("");
    } catch (error) {
      appendMessage({ 
        text: "Something went wrong in the agent response.", 
        sender: "system" 
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col w-full max-w-lg bg-white py-3 rounded-3xl shadow-2xl">
      <div className="flex-1 overflow-y-auto max-h-[70vh] px-4 scroll-smooth">
        {messages.map((msg) => {
          return (
            <MessageBubble 
              key={msg.id} 
              text={msg.text} 
              sender={msg.sender}
              type={msg.type}
              isPriceStep={msg.isPriceStep}
              // isLocationStep={msg.isLocationStep}
              priceRange={msg.priceRange}
              setConfirm={msg.setConfirm}
              messageId={msg.id}
              isRegenerating={regeneratingMessageId === msg.id}
              visualizationData={msg.visualizationData}
              targetDimensions={msg.targetDimensions}
              setSelectedDimensions={setSelectedDimensions}
              onBudgetSubmit={handleBudgetSubmit}
              onOpenHeatmap={(msg, district) => handleOpenHeatmap(msg, district)}
              mode = {mode}
              commentData={msg.commentData}
              insightsLevel={msg.insightsLevel}
              insightsGroupName={msg.insightsGroupName}
              source_documents = {msg.source_documents}
              appendMessage={appendMessage}
            />
          );
        })}

        {isLoading && (
          <div className="flex justify-start items-center my-2">
            <div className="flex-shrink-0 mr-2">
              <div className="w-9 h-9 bg-gray-300 rounded-full flex items-center justify-center">
                🤖
              </div>
            </div>
            <div className="bg-gray-200 p-3 rounded-xl">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
              </div>
            </div>
          </div>
        )}
        
        {/* 输入区域 */}
        <div className="p-4 border-t border-gray-200 bg-gray-50 rounded-b-lg">
          {/* moved mode switches below input */}

          <div className="flex space-x-2 items-end">
            <textarea
              ref={textAreaRef}
              value={inputValue}
              onChange={(e) => { setInputValue(e.target.value); autoResizeTextarea(); }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage(inputValue);
                }
              }}
              placeholder="Type your question..."
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              disabled={isLoading}
              rows={1}
              style={{ overflow: 'hidden' }}
            />
            {/* 发送按钮 */}
            <button
              onClick={() => handleSendMessage(inputValue)}
              disabled={isLoading || !inputValue.trim()}
              className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Send
            </button>
          </div>

          {/* Mode controls under the input */}
          <div className="flex flex-col gap-2 mt-2 px-1">
            {/* Filtered (RAG) switch */}
            <div className="flex items-center gap-2">
              <Switch
                checked={subMode === 'review_qa'}
                onChange={(checked) => {
                  onModeSwitch?.(checked);
                  if (!checked) setGlobalSearchEnabled(false);
                }}
                size="small"
                disabled={isPreferenceStage}
              />
              <span className="text-xs text-gray-700">Search from comments</span>
              <span className="text-[10px] px-2 py-[2px] rounded bg-green-50 text-green-600">Search from the currently selected preferences reviews</span>
            </div>
 
            {/* Global search switch – visible only when Filtered is ON */}
            {subMode === 'review_qa' && (
              <div className="flex items-center gap-2">
                <Switch 
                  checked={globalSearchEnabled} 
                  onChange={(checked) => {
                    setGlobalSearchEnabled(checked);
                    if (checked && !localStorage.getItem('global_hint_seen_v2')) {
                      setShowGlobalHint(true);
                    }
                  }} 
                  size="small"
                  disabled={isPreferenceStage}
                />
                <span className="text-xs text-gray-700">Search from Global comments </span>
                <span className="text-[10px] px-2 py-[2px] rounded bg-purple-50 text-purple-600">Search from global reviews data</span>
              </div>
            )}
            {isPreferenceStage && (
              <div className="text-[11px] text-gray-500">Collecting preferences… retrieval controls will be available soon.</div>
            )}
          </div>

          {/* 首次气泡引导 */}
          {showGlobalHint && (
            <div className="mt-2 text-xs text-gray-600 bg-white border border-blue-200 rounded px-2 py-1 inline-flex items-center gap-2">
              Click here to conduct a global search if a more comprehensive answer needed.
              <button
                className="text-blue-500"
                onClick={() => setShowGlobalHint(false)}
              >
                Got it
              </button>
            </div>
          )}
          
          {/* 快捷按钮 */}
          <div className="flex flex-wrap gap-1 mt-2">
            <button
              onClick={() => {
                onShowMap?.({
                  userPreferences: selectedDimensions,
                  triggerData: { source: 'agent_quick_price_distribution' },
                  requestType: 'location_selection',
                  suppressChatOnMapSelect: true,
                  timestamp: new Date().toISOString()
                });
              }}
              className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300"
              disabled={isLoading}
            >
              🗺️ District price distribution
            </button>
            <button
              onClick={() => setShowRoomTypeModal(true)}
              className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300"
              disabled={isLoading}
            >
              💰 Room-type mix
            </button>
            <button
              onClick={() => setShowValueModal(true)}
              className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300"
              disabled={isLoading}
            >
              ⭐ Value-for-money
            </button>
            <button
              onClick={() => setShowReviewModal(true)}
              className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300"
              disabled={isLoading}
            >
              📝 Review insights
            </button>
            {/* <button
              onClick={() => setShowCompareModal(true)}
              className="px-3 py-1 text-xs bg-gray-200 text-gray-700 rounded-full hover:bg-gray-300"
              disabled={isLoading}
            >
              🆚 Compare districts
            </button> */}
          </div>
          {/* Quick modals */}
          {/* Removed <PriceDistributionModal /> since the map is used instead for this quick action */}
          <RoomTypeMixModal visible={showRoomTypeModal} onClose={() => setShowRoomTypeModal(false)} />
          <ValueForMoneyModal visible={showValueModal} onClose={() => setShowValueModal(false)} />
          <ReviewInsightsModal visible={showReviewModal} onClose={() => setShowReviewModal(false)} />
          {/* <CompareDistrictsModal visible={showCompareModal} onClose={() => setShowCompareModal(false)} /> */}
        </div>

        <div ref={chatEndRef} />
      </div>
    </div>
    
  );
};

export default AgentChat;