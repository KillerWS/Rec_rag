// ScriptedChat.tsx — 拆分自 ChatContainer，保留脚本式对话流程
import { useEffect, useRef, useState } from "react";
import MessageBubble from "./messageBox/MessageBubble";
import { Input, Button, Card, Table, InputNumber, message as antdMessage } from "antd";
import { SendOutlined, CheckOutlined } from "@ant-design/icons";

interface ScriptedChatProps {
  isStarted: boolean;
  setIsStarted: (started: boolean) => void;
  setSelectedDimensions: (updater: any) => void;
  selectedDimensions: any[];
  onConfirm: () => void;
  messages: any[];
  appendMessage: (msg: any) => void;
  mode: string;
  onShowMap?: (data?: any) => void;
  onBindMapLocationSelected?: (fn: (district: string) => void) => void;
}

const ScriptedChat: React.FC<ScriptedChatProps> = ({
    isStarted,
    setIsStarted,
  setSelectedDimensions,
  selectedDimensions,
  onConfirm,
  messages,
  appendMessage,
  mode, // script还是Agent mode
  onShowMap,
  onBindMapLocationSelected
}) => {
//   const [isStarted, setIsStarted] = useState(false);
  const [inputValue, setInputValue] = useState<string>("");
  const [currentDimensionIndex, setCurrentDimensionIndex] = useState<number>(0);
  const [priceRange, setPriceRange] = useState<{ min: number | null; max: number | null }>({ min: null, max: null });
  const [submittedPriceRange, setSubmittedPriceRange] = useState<{ min: number | null; max: number | null }>({ min: null, max: null });
  const [isConfirming, setIsConfirming] = useState<boolean>(false);
  const [isChatAreaVisible, setIsChatAreaVisible] = useState<boolean>(true);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  const conversationSteps = [
    { key: "Price", question: "What is your budget? (e.g., 'Under 100 euros')", showChartOption: true },
    { key: "Location", question: `💡 Based on your budget of €${priceRange.min}–${priceRange.max}, would you like to explore which neighbourhoods have the most listings or the lowest average price?` },
    { key: "Room Type", question: "What type of room are you looking for? Entire home/apt or Private room 🏡" },
    { key: "Social Dimension", question: "Would you like to see what previous guests said about different listings?" }
  ];

  useEffect(() => {
    const timeout = setTimeout(() => {
      chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100);
    return () => clearTimeout(timeout);
  }, [messages]);

  const startConversation = () => {
    setIsChatAreaVisible(false);
    setIsStarted(true);
    appendMessage({ text: conversationSteps[0].question, sender: "system" });
  };

  const handlePriceSubmit = () => {
    const { min, max } = priceRange;
    if (min == null || max == null) return antdMessage.warning("Please enter both min and max price.");
    if (min > max) return antdMessage.warning("Min should not be greater than Max.");
    setSubmittedPriceRange({ min, max });
    const priceString = `${min}-${max}`;
    setSelectedDimensions((prev: any[]) => [...prev, { key: "Price", value: priceString }]);

    appendMessage({ text: priceString, sender: "user" });
    appendMessage({ text: "Would you like to see the overall price distribution?", sender: "system", type: "chart_option" });

    const nextIndex = currentDimensionIndex + 1;
    if (nextIndex < conversationSteps.length) {
      appendMessage({ text: conversationSteps[nextIndex].question, sender: "system", type: "neighbourhood_prompt", targetDimensions: ["location"] });
      setCurrentDimensionIndex(nextIndex);
    } else {
      setIsConfirming(true);
    }
    setPriceRange({ min: null, max: null });
    setIsChatAreaVisible(true);
  };

  const handleUserInput = (messageText: string) => {
    if (!messageText.trim()) return;
    const dimensionKey = conversationSteps[currentDimensionIndex]?.key;
    appendMessage({ text: messageText, sender: "user" });
    if (dimensionKey) {
      setSelectedDimensions((prev: any[]) => [...prev, { key: dimensionKey, value: messageText }]);
    }
    if (dimensionKey === "Location") {
      appendMessage({ text: "Let’s explore neighbourhoods matching your budget!", sender: "system", type: "neighbourhood_prompt", targetDimensions: ["location"] });
    }
    // 不在此处推送房型提示；进入房型步骤时统一推送
    if (dimensionKey === "Social Dimension") {
      setIsConfirming(false);
      appendMessage({ text: "", sender: "system", type: "social_prompt" });
    }

    const nextIndex = currentDimensionIndex + 1;
    if (nextIndex < conversationSteps.length) {
      appendMessage({ text: conversationSteps[nextIndex].question, sender: "system" });
      // 如进入房型步骤，先推送提示语，再显示 RoomTypeSelector
      if (conversationSteps[nextIndex].key === 'Room Type') {
        appendMessage({ text: "Let’s explore Room Types that match your budget!", sender: "system", type: "roomtype_prompt" });
        appendMessage({ text: '', sender: 'system', type: 'roomtype_input', targetDimensions: ['room_type'] });
      }
      setCurrentDimensionIndex(nextIndex);
    }
    setInputValue("");
  };

  const setConfirm = () => {
    setIsConfirming(true);
    appendMessage({ text: "Okay, skipping social info. Ready to search?", sender: "system" });
  };

  // 🗺️ 在 Scripted 模式下也支持打开热力图
  const handleOpenHeatmap = (messageData: any = null, selectedDistrict: string | null = null) => {
    const mapData = {
      userPreferences: selectedDimensions,
      chatContext: messages.slice(-5),
      triggerData: messageData,
      requestType: (messageData as any)?.test ? 'debug' : 'user_request',
      selectedDistrict: selectedDistrict,
      timestamp: new Date().toISOString()
    };
    onShowMap?.(mapData);
  };

  // 🆕 在脚本模式下处理可视化里的区划选择，保持脚本流程
  const handleScriptedLocationSelected = (district: string) => {
    // 追加用户选择和系统引导，不触发RAG
    appendMessage({ text: `I selected the district: ${district}.`, sender: "user" });

    // 更新偏好中的 Location
    setSelectedDimensions((prev: any[]) => {
      const withoutLocation = prev.filter((d: any) => d.key !== 'Location');
      return [...withoutLocation, { key: 'Location', value: district }];
    });

    // 系统跟进
    appendMessage({ text: "Let’s explore neighbourhoods matching your budget!", sender: "system", type: "neighbourhood_prompt", targetDimensions: ["location"] });

    // 推进到下一步（房型）
    const nextIndex = conversationSteps.findIndex(s => s.key === 'Location') + 1;
    if (nextIndex < conversationSteps.length) {
      appendMessage({ text: conversationSteps[nextIndex].question, sender: "system" });
      // 如进入房型步骤，先推送提示语，再显示 RoomTypeSelector
      if (conversationSteps[nextIndex].key === 'Room Type') {
        appendMessage({ text: "Let’s explore Room Types that match your budget!", sender: "system", type: "roomtype_prompt" });
        appendMessage({ text: '', sender: 'system', type: 'roomtype_input', targetDimensions: ['room_type'] });
      }
      setCurrentDimensionIndex(nextIndex);
    } else {
      setIsConfirming(true);
    }
  };

  // 🆕 地图选择时的脚本推进：不重复显示可视化按钮
  const handleMapLocationSelected = (district: string) => {
    // 更新偏好中的 Location（幂等）
    setSelectedDimensions((prev: any[]) => {
      const withoutLocation = prev.filter((d: any) => d.key !== 'Location');
      return [...withoutLocation, { key: 'Location', value: district }];
    });

    // 直接推进到下一步（房型），不再追加 neighbourhood_prompt
    const nextIndex = conversationSteps.findIndex(s => s.key === 'Location') + 1;
    if (nextIndex < conversationSteps.length) {
      appendMessage({ text: conversationSteps[nextIndex].question, sender: "system" });
      // 如进入房型步骤，先推送提示语，再显示 RoomTypeSelector
      if (conversationSteps[nextIndex].key === 'Room Type') {
        appendMessage({ text: "Let’s explore Room Types that match your budget!", sender: "system", type: "roomtype_prompt" });
        appendMessage({ text: '', sender: 'system', type: 'roomtype_input', targetDimensions: ['room_type'] });
      }
      setCurrentDimensionIndex(nextIndex);
    } else {
      setIsConfirming(true);
    }
  };

  // 绑定给父组件
  useEffect(() => {
    onBindMapLocationSelected?.(handleMapLocationSelected);
  }, [onBindMapLocationSelected, selectedDimensions, currentDimensionIndex]);

  return (
    <div className="flex flex-col w-full max-w-lg bg-white py-3 rounded-3xl shadow-2xl">
      <div className="flex-1 overflow-y-auto max-h-[70vh] px-4 scroll-smooth">
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            text={msg.text}
            sender={msg.sender}
            type={msg.type}
            isPriceStep={msg.type === "chart_option"}
            priceRange={submittedPriceRange as any}
            setConfirm={setConfirm}
            targetDimensions={msg.targetDimensions}
            setSelectedDimensions={setSelectedDimensions}
            onOpenHeatmap={(m, d) => handleOpenHeatmap(m, d)}
            mode={mode}
            onScriptedLocationSelected={handleScriptedLocationSelected}
            locationResolved={selectedDimensions.some((d: any) => d.key === 'Location')}
            appendMessage={appendMessage}
          />
        ))}
        <div ref={chatEndRef} />
      </div>

      {!isStarted && isChatAreaVisible && (
        <div className="flex justify-center mt-4">
          <Button type="primary" onClick={startConversation}>Start</Button>
        </div>
      )}

      {isStarted && !isConfirming && conversationSteps[currentDimensionIndex]?.key === "Price" && (
        <div className="flex items-center p-3 border-t bg-gray-100 rounded-b-3xl shadow-inner gap-3">
          <InputNumber className="w-1/2" placeholder="Min Price" min={0} value={priceRange.min as number | null} onChange={(v) => setPriceRange((prev) => ({ ...prev, min: (v as number | null) }))} />
          <InputNumber className="w-1/2" placeholder="Max Price" min={0} value={priceRange.max as number | null} onChange={(v) => setPriceRange((prev) => ({ ...prev, max: (v as number | null) }))} />
          <Button type="primary" onClick={handlePriceSubmit} disabled={priceRange.min == null || priceRange.max == null}>Submit</Button>
        </div>
      )}

      {isStarted && !isConfirming && isChatAreaVisible && (
        <div className="flex items-center p-3 border-t bg-gray-100 rounded-b-3xl shadow-inner">
          <Input className="flex-1 mr-3 p-3 rounded-full border border-gray-300" placeholder="Type your answer..." value={inputValue} onChange={(e) => setInputValue(e.target.value)} onPressEnter={() => handleUserInput(inputValue)} />
          <Button type="primary" shape="circle" size="large" icon={<SendOutlined />} onClick={() => handleUserInput(inputValue)} />
        </div>
      )}

      {isConfirming && (
        <div className="flex justify-center mt-4">
          <Card title="📝 Confirm Your Preferences" className="w-full max-w-sm">
            <Table
              dataSource={selectedDimensions}
              columns={[
                { title: "Dimension", dataIndex: "key" },
                { title: "Value", dataIndex: "value" }
              ]}
              pagination={false}
              size="small"
              rowKey="key"
            />
            <div className="flex justify-center mt-3">
              <Button type="primary" onClick={onConfirm} icon={<CheckOutlined />}>
                Confirm & Search
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default ScriptedChat;
