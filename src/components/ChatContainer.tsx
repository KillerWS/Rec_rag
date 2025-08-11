// ✅ ChatContainer.tsx — 使用 props 管理维度，移除本地 selectedDimensions 状态
import { useRef, useEffect, useState, Dispatch, SetStateAction } from "react";
import MessageBubble from "./messageBox/MessageBubble";
import { Button, Spin, Modal } from "antd";
import { fetchPrepareRagContext, fetchRecommendations, fetchRAGAnswer } from "../api/api";
import ScriptedChat from "./ScriptedChat";
import PreferencePanel from "./PreferencePanel";
import AgentChat from "./AgentChat";
import RecommendationCard from "./recommendationCard/RecommendationCard";
import type { Recommendation } from "../api/api";

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
  onBindScriptedMapAdvance
}) => {
  const [isPreparingRag, setIsPreparingRag] = useState(false);
  const [indexId, setIndexId] = useState<string | null>(null);
  const [showPreferences] = useState(false);
  const [isStarted, setIsStarted] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      text: "Welcome to the Airbnb Recommendation System!",
      sender: "system"
    }
  ]);
  const [scriptedRecs, setScriptedRecs] = useState<Recommendation[]>([]);
  const [hasScriptedConfirmed, setHasScriptedConfirmed] = useState(false);
  const [isLoadingScriptedRecs, setIsLoadingScriptedRecs] = useState(false);

  const chatEndRef = useRef<HTMLDivElement | null>(null);

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
        if (res && Array.isArray(res.recommendations)) {
          setRecommendations(res.recommendations);
        }
      } catch (error) {
        console.error("Failed to dynamically fetch recommendations:", error);
      }
    };
    if (isStarted && selectedDimensions.length > 0) {
      fetchDynamicRecommendations();
    }
  }, [selectedDimensions, isStarted]);

  const appendMessage = (msg: any) => {
    setMessages((prev) => [...prev, { id: prev.length + 1, ...msg }]);
  };

  // 🆕 供父组件触发：把一条用户消息发送给 Agent（会调用后端）
  const sendMessageToAgent = async (userMessage: string) => {
    // 防御：仅在 Agent 模式下才允许调用后端对话
    if (mode !== 'agent') {
      return;
    }
    const text = (userMessage || '').trim();
    if (!text) return;
    // 先追加用户消息
    appendMessage({ text, sender: 'user' });
    // 组合历史（含这条）
    const historyForApi = messages.map((msg) => ({ type: msg.sender, data: msg.text })).concat({ type: 'human', data: text });
    try {
      let idx = indexId;
      if (!idx) {
        const prep: any = await fetchPrepareRagContext();
        if (prep?.index_id) {
          idx = prep.index_id;
          setIndexId(idx);
        }
      }
      const res: any = await fetchRAGAnswer(text, historyForApi, (idx as string) || '', { sub_mode: subMode });
      if (res?.answer) {
        appendMessage({ text: res.answer, sender: 'system' });
      }
    } catch (error) {
      appendMessage({ text: 'Something went wrong in the agent response.', sender: 'system' });
    }
  };

  // 🆕 将 appendMessage / sendMessageToAgent 暴露给父组件
  useEffect(() => {
    onBindAppendMessage?.(appendMessage);
    onBindAgentSendMessage?.(sendMessageToAgent);
  }, [onBindAppendMessage, onBindAgentSendMessage, messages, indexId, subMode]);

  const handleStartAgentChat = async () => {
    setIsPreparingRag(true);
    try {
      const result = await fetchPrepareRagContext();
      if ((result as any)?.index_id) {
        setIndexId((result as any).index_id);
        setMode("agent");
      }
    } catch {
      console.error("RAG context creation failed");
    } finally {
      setIsPreparingRag(false);
      setIndexId(`00000000000000`);
      setMode("agent");
    }
  };

  const handleModeSwitch = () => {
    const newMode = subMode === "review_qa" ? "default" : "review_qa";
    setSubMode(newMode);
  };

  return (
    <div className="flex flex-col w-full max-w-lg bg-white py-3 rounded-3xl shadow-2xl">
      {/* 🟢 系统欢迎语 */}
      {mode === "none" && (
        <MessageBubble text="Welcome to the Airbnb Recommendation System!" sender="system" />
      )}

      {/* 🤖 Scripted 模式 */}
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
            setIsLoadingScriptedRecs(true);
            try {
              // Merge multiple 'Room Type' dimensions into a single comma-separated value for backend compatibility
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
              setScriptedRecs(Array.isArray(list) ? list : []);
              if (Array.isArray(list)) {
                setRecommendations(list);
              }
            } catch (error) {
              console.error('Failed to fetch recommendations on confirm:', error);
              setScriptedRecs([]);
            } finally {
              setIsLoadingScriptedRecs(false);
            }
          }}
          onShowMap={onShowMap}
          onBindMapLocationSelected={(fn) => {
            onBindScriptedMapAdvance?.(fn);
          }}
          isFinalized={hasScriptedConfirmed}
        />
      )}

      {/* 🔍 scripted 模式下，用户确认后，显示推荐列表 */}
      {mode === "scripted" && hasScriptedConfirmed && (
        <div className="mt-4 max-h-[60vh] overflow-y-auto px-2">
          <div className="text-lg font-semibold mb-2">🔍 Recommended Listings</div>
          {isLoadingScriptedRecs ? (
            <div className="flex items-center justify-center py-6 text-gray-500">
              <Spin size="small" />
              <span className="ml-2">正在生成推荐...</span>
            </div>
          ) : scriptedRecs.length > 0 ? (
            <div className="space-y-3">
              {scriptedRecs.map((item) => (
                <RecommendationCard key={item.id} {...item} />
              ))}
            </div>
          ) : (
            <div className="text-gray-400 text-sm py-4">暂无符合条件的推荐</div>
          )}
        </div>
      )}

      {/* 🧠 Agent 模式 */}
      {mode === "agent" && (
        <AgentChat
          indexId={indexId}
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

      {/* 🟡 起始按钮 */}
      {!isStarted && mode === "none" && (
        <div className="flex justify-center gap-6 mt-4">
          <Button type="primary" onClick={() => setMode("scripted")}>Start Scripted Chat</Button>
          <Button type="default" onClick={handleStartAgentChat}>Start Agent Chat</Button>
        </div>
      )}

      {/* 🔄 模态加载提示 */}
      <Modal open={isPreparingRag} closable={false} footer={null} centered>
        <div className="text-center py-6">
          <Spin size="large" />
          <p className="mt-4 text-lg font-medium">⏳ A dedicated knowledge base is being built for you ...</p>
          <p className="text-gray-500 text-sm mt-1">Loading comment corpus and generating vector database...</p>
        </div>
      </Modal>

      {/* 偏好面板 */}
      {showPreferences && (
        <PreferencePanel
          selectedDimensions={selectedDimensions}
          onConfirm={async () => {
            const top_k = 5;
            const res = await fetchRecommendations({ selectedDimensions, top_k });
            if (Array.isArray(res.recommendations)) {
              setRecommendations(res.recommendations);
            }
          }}
        />
      )}

      <div ref={chatEndRef} />
    </div>
  );
};

export default ChatContainer;
