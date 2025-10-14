// ✅ ChatContainer.tsx — 使用 props 管理维度，移除本地 selectedDimensions 状态
import { useRef, useEffect, useState, Dispatch, SetStateAction } from "react";
import MessageBubble from "./messageBox/MessageBubble";
import { Button, Spin, Modal } from "antd";
import { fetchPrepareRagContext, fetchRecommendations, fetchRAGAnswer } from "../api/api";
import { setConversationMode } from "../api/session";
import ScriptedChat from "./ScriptedChat";
import PreferencePanel from "./PreferencePanel";
import AgentChat from "./AgentChat";
// import RecommendationCard from "./recommendationCard/RecommendationCard";
import type { Recommendation } from "../api/api";
import { incrementRagQuery, incrementUserTurn, initMetrics, noteVisualizationTypes, markTaskCompleted, markTaskStart } from "../metrics/sessionMetrics";

interface ChatContainerProps {
  selectedDimensions: any[];
  setSelectedDimensions: (updater: any) => void;
  setRecommendations: (recs: any) => void;
  mode: "none" | "scripted" | "agent";
  setMode: Dispatch<SetStateAction<"none" | "scripted" | "agent">>;
  subMode: "default" | "review_qa";
  setSubMode: Dispatch<SetStateAction<"default" | "review_qa">>;
  onShowMap?: (data?: any) => void;
  onBindAppendMessage?: (fn: (msg: any) => void) => void;
  onBindAgentSendMessage?: (fn: (message: string) => void) => void;
  onBindScriptedMapAdvance?: (fn: (district: string) => void) => void;
  isMapVisible?: boolean;
}

const ChatContainer: React.FC<ChatContainerProps> = ({
  selectedDimensions,
  setSelectedDimensions,
  setRecommendations,
  mode,
  setMode,
  subMode,
  setSubMode,
  onShowMap,
  onBindAppendMessage,
  onBindAgentSendMessage,
  onBindScriptedMapAdvance,
  isMapVisible = false
}) => {
  const [isPreparingRag, setIsPreparingRag] = useState(false);
  const [showPreferences] = useState(false);
  const [isStarted, setIsStarted] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Welcome to the Airbnb Recommendation System!",
      sender: "system"
    }
  ]);
  // const [scriptedRecs, setScriptedRecs] = useState<Recommendation[]>([]);
  // const [isLoadingScriptedRecs, setIsLoadingScriptedRecs] = useState(false);
  const [hasScriptedConfirmed, setHasScriptedConfirmed] = useState(false);
  
  const [hasLoadedInitialScriptedRecs, setHasLoadedInitialScriptedRecs] = useState(false);

  const chatEndRef = useRef<HTMLDivElement | null>(null);

  // 删除本地提交函数，改为全局 App 统一管理

  // 仅在挂载时初始化指标，避免每次消息变化重置状态
  useEffect(() => {
    initMetrics();
  }, []);

  // 删除页面卸载兜底提交，改为 App 统一管理

  useEffect(() => {
    const timeout = setTimeout(() => {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
    return () => clearTimeout(timeout);
  }, [messages]);

  useEffect(() => {
    const fetchDynamicRecommendations = async () => {
      try {
        const res = await fetchRecommendations({ selectedDimensions, top_k: 5 });
        if (res && Array.isArray(res.recommendations) && res.recommendations.length > 0) {
          setRecommendations(res.recommendations);
          markTaskCompleted();
          // 移除自动提交，改为显式完成按钮触发
        } else {
          console.warn('⚠️ Agent: Backend returned empty recommendations array, keeping current list');
        }
      } catch (error) {
        console.error("Failed to dynamically fetch recommendations:", error);
      }
    };
    if (mode === 'agent' && isStarted && selectedDimensions.length > 0) {
      fetchDynamicRecommendations();
    }
  }, [selectedDimensions, isStarted, mode]);

  // 🆕 Scripted 模式：进入后加载一次初始推荐，用于右侧推荐侧栏
  useEffect(() => {
    const fetchInitialScriptedRecs = async () => {
      try {
        const res = await fetchRecommendations({ selectedDimensions, top_k: 5 });
        const list = Array.isArray(res) ? (res as any as Recommendation[]) : ((((res as any)?.recommendations ?? []) as Recommendation[]));
        console.log('----- SCRIPTED initial recs fetch -----', { req: { selectedDimensions, top_k: 5 }, cnt: Array.isArray(list) ? list.length : -1 });
        if (Array.isArray(list) && list.length > 0) {
          setRecommendations(list);
        } else {
          console.warn('⚠️ Scripted initial: Backend returned empty recommendations array, keeping current list');
        }
      } catch (err) {
        console.error('Failed to fetch initial scripted recommendations:', err);
      } finally {
        setHasLoadedInitialScriptedRecs(true);
      }
    };
    if (mode === 'scripted' && isStarted && !hasScriptedConfirmed && !hasLoadedInitialScriptedRecs) {
      fetchInitialScriptedRecs();
    }
  }, [mode, isStarted, hasScriptedConfirmed, hasLoadedInitialScriptedRecs, selectedDimensions, setRecommendations]);

  const appendMessage = (msg: any) => {
    setMessages((prev) => [...prev, { id: prev.length + 1, ...msg }]);
  };

  const sendMessageToAgent = async (userMessage: string) => {
    if (mode !== 'agent') {
      return;
    }
    const text = (userMessage || '').trim();
    if (!text) return;
    appendMessage({ text, sender: 'user' });
    incrementUserTurn();
    const historyForApi = messages.map((msg) => ({ type: msg.sender, data: msg.text })).concat({ type: 'human', data: text });
    try {
      if (subMode === 'review_qa') {
        // 统一RAG查询计数 - 检查全局搜索状态
        const isGlobalSearch = (globalThis as any).__global_search_enabled__;
        incrementRagQuery(isGlobalSearch);
      }
      const res: any = await fetchRAGAnswer(text, historyForApi, { sub_mode: subMode });
      // Receipt-side fallback: if not in RAG mode, still count once as local RAG
      try {
        if (subMode !== 'review_qa') {
          incrementRagQuery(false);
          console.log('----- METRICS receipt-side RAG increment (container, local) -----');
        }
      } catch {}
      console.log('----- ChatContainer AGENT fetchRAGAnswer response -----', {
        keys: Object.keys(res || {}),
        answerType: typeof res?.answer,
        hasDecisionCard: !!res?.decision_card,
        hasFollowup: !!res?.followup_info,
      });
      if (res?.answer) {
        appendMessage({ text: res.answer, sender: 'system' });
      }
      const charts = res?.visualizations && Array.isArray(res.visualizations.suggested_charts)
        ? (res.visualizations.suggested_charts as string[])
        : [];
      if (charts.length > 0) {
        noteVisualizationTypes(charts);
      }
    } catch (error) {
      console.error('----- ChatContainer AGENT send error -----', error);
      appendMessage({ text: 'Something went wrong in the agent response.', sender: 'system' });
    }
  };

  useEffect(() => {
    onBindAppendMessage?.(appendMessage);
    onBindAgentSendMessage?.(sendMessageToAgent);
  }, [onBindAppendMessage, onBindAgentSendMessage, messages, subMode]);

  const handleStartAgentChat = async () => {
    markTaskStart();
    setIsPreparingRag(true);
    try {
      await fetchPrepareRagContext();
      setMode("agent");
      try { setConversationMode('agent'); } catch {}
      // 取消一次性标记逻辑，不再重置
    } catch {
      console.error("RAG context creation failed");
      setMode("agent");
      try { setConversationMode('agent'); } catch {}
    } finally {
      setIsPreparingRag(false);
      setIsStarted(true);
    }
  };

  const handleStartScripted = () => {
    markTaskStart();
    setMode("scripted");
    try { setConversationMode('scripted'); } catch {}
    setIsStarted(true);
  };

  const handleModeSwitch = () => {
    const newMode = subMode === "review_qa" ? "default" : "review_qa";
    setSubMode(newMode);
    (globalThis as any).__global_search_enabled__ = newMode === 'review_qa' ? (globalThis as any).__global_search_enabled__ : false;
  };

  return (
    <div className="flex flex-col w-full max-w-lg bg-white py-3 rounded-3xl shadow-2xl">
      {mode === "none" && (
        <MessageBubble text="Welcome to the Airbnb Recommendation System!" sender="system" />
      )}

      {mode === "scripted" && (
        <ScriptedChat
          isStarted={isStarted}
          setIsStarted={setIsStarted}
          selectedDimensions={selectedDimensions}
          setSelectedDimensions={setSelectedDimensions}
          messages={messages}
          appendMessage={appendMessage}
          mode={mode}
          onConfirm={async () => {
            setHasScriptedConfirmed(true);
            // setIsLoadingScriptedRecs(true);
            try {
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

          const res = await fetchRecommendations({ selectedDimensions: apiDimensions as any, top_k: 5 });
          const list = Array.isArray(res) ? (res as any as Recommendation[]) : ((((res as any)?.recommendations ?? []) as Recommendation[]));
          console.log('----- SCRIPTED confirm recs fetch -----', { req: { selectedDimensions: apiDimensions, top_k: 5 }, cnt: Array.isArray(list) ? list.length : -1 });
          if (Array.isArray(list) && list.length > 0) {
            setRecommendations(list);
            markTaskCompleted();
          } else {
            console.warn('⚠️ Scripted confirm: Backend returned empty recommendations array, keeping current list');
          }
            } catch (error) {
              console.error('Failed to fetch recommendations on confirm:', error);
              // setScriptedRecs([]);
            } finally {
              // setIsLoadingScriptedRecs(false);
            }
          }}
          onShowMap={onShowMap}
          onBindMapLocationSelected={(fn) => {
            onBindScriptedMapAdvance?.(fn);
          }}
          isFinalized={hasScriptedConfirmed}
          isMapVisible={isMapVisible}
        />
      )}

      {false && hasScriptedConfirmed && <div />}

      {mode === "agent" && (
        <AgentChat
          selectedDimensions={selectedDimensions}
          setSelectedDimensions={setSelectedDimensions}
          messages={messages}
          appendMessage={appendMessage}
          setRecommendations={setRecommendations}
          onShowMap={onShowMap}
          mode={mode}
          subMode={subMode}
          onModeSwitch={handleModeSwitch}
        />
      )}

      {!isStarted && mode === "none" && (
        <div className="flex justify-center gap-6 mt-4">
          <Button type="primary" onClick={handleStartScripted}>Start Scripted Chat</Button>
          <Button type="default" onClick={handleStartAgentChat}>Start Agent Chat</Button>
        </div>
      )}

      <Modal open={isPreparingRag} closable={false} footer={null} centered>
        <div className="text-center py-6">
          <Spin size="large" />
          <p className="mt-4 text-lg font-medium">⏳ A dedicated knowledge base is being built for you ...</p>
          <p className="text-gray-500 text-sm mt-1">Loading comment corpus and generating vector database...</p>
        </div>
      </Modal>

      {showPreferences && (
        <PreferencePanel
          selectedDimensions={selectedDimensions}
          onConfirm={async () => {
            const top_k = 5;
            const res = await fetchRecommendations({ selectedDimensions, top_k });
            if (Array.isArray(res.recommendations) && res.recommendations.length > 0) {
              setRecommendations(res.recommendations);
            } else {
              console.warn('⚠️ PreferencePanel: Backend returned empty recommendations array, keeping current list');
            }
          }}
        />
      )}

      <div ref={chatEndRef} />
    </div>
  );
};

export default ChatContainer;
