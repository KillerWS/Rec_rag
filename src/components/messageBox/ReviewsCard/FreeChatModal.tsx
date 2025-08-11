// ✅ FreeChatModal.tsx — 支持弹窗与嵌入两种模式的对话组件
import { useState, useRef, useEffect } from "react";
import { Modal, Input, Button, Spin, Card, Collapse } from "antd";
import { SendOutlined, CommentOutlined } from "@ant-design/icons";
import { fetchRAGAnswer } from "../../../api/api";

interface FreeChatModalProps {
  open?: boolean;
  onClose?: () => void;
  inline?: boolean;
  indexId?: string | null;
}

const FreeChatModal = ({ open = false, onClose = () => {}, inline = false, indexId }: FreeChatModalProps) => {
  const [chatHistory, setChatHistory] = useState<any[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    console.log("ragIndexId", indexId);
    if (open && !inline) {
      setChatHistory([]);
    }
  }, [open]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [chatHistory]);

  // 发送聊天信息的方法
  const handleSend = async () => {
    if (!inputValue.trim()) return;
    
    const newHistory = [...chatHistory, { sender: "user", text: inputValue }];
    setChatHistory(newHistory);
    setLoading(true);
  
    try {
      // ✅ 调用 fetchRAGAnswer，传完整newHistory
      const res: any = await fetchRAGAnswer(inputValue, newHistory, indexId as string);
  
      const systemMsg = {
        sender: "system",
        text: res.answer,
        sources: res.source_documents || [],
      };
      setChatHistory((prev) => [...prev, systemMsg]);
    } catch (err) {
      console.error("Chat failed:", err);
      setChatHistory((prev) => [...prev, { sender: "system", text: "⚠️ Failed to retrieve answer." }]);
    } finally {
      setLoading(false);
      setInputValue("");
    }
  };

  


  const ChatUI = (
    <div className="w-full">
      <div className="h-[300px] overflow-y-auto px-2 mb-3 border rounded bg-gray-50 p-2">
        {chatHistory.map((msg, idx) => (
          <div
            key={idx}
            className={`mb-4 ${msg.sender === "user" ? "text-right" : "text-left"}`}
          >
            <div
              className={`inline-block p-3 rounded-xl shadow ${
                msg.sender === "user" ? "bg-blue-100" : "bg-gray-100"
              }`}
            >
              {msg.text}

              {msg.sender === "system" && msg.sources?.length > 0 && (
                <div className="mt-2 space-y-2">
                  {/* <Divider plain>Sources</Divider>
                  {msg.sources.map((src: any, i: number) => (
                    <Tooltip title={`Document: ${src.page_content}`} key={i}>
                      <Card size="small" className="bg-yellow-50 border-l-4 border-yellow-400">
                        <p className="text-sm italic">“{src.page_content}”</p>
                      </Card>
                    </Tooltip>
                  ))} */}
                  <Collapse
                    ghost
                    expandIconPosition="end"
                    style={{ marginTop: 12 }}
                  >
                  <Collapse.Panel header={`📎 View ${msg.sources.length} Supporting Reviews`} key="source">
                    <div className="space-y-2">
                        {msg.sources.map((src: any, i: number) => (
                          <Card
                            key={i}
                            size="small"
                            className="bg-yellow-50 border-l-4 border-yellow-400"
                          >
                            <p className="text-sm italic">“{src.page_content}”</p>
                          </Card>
                        ))}
                      </div>
                    </Collapse.Panel>
                  </Collapse>

                </div>
              )}
            </div>
          </div>
        ))}

        {loading && <div className="text-center mt-4"><Spin /></div>}
        <div ref={chatEndRef} />
      </div>

      <div className="flex gap-2">
        <Input
          placeholder="e.g., Is this listing noisy at night?"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onPressEnter={handleSend}
          disabled={loading}  // ✅ 输入框发送中禁用
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading} // ✅ 按钮自动转圈Loading
          disabled={loading || !inputValue.trim()}  // 没输内容或者Loading禁用
        />
      </div>
    </div>
  );

  if (inline) {
    return (
      <div className="mt-4 border rounded-md p-4 bg-white shadow">
        <h3 className="text-lg font-semibold mb-2">💬 Ask the Reviews</h3>
        {ChatUI}
      </div>
    );
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      title={<><CommentOutlined /> Review Assistant</>}
      width={700}
    >
      {ChatUI}
    </Modal>
  );
};

export default FreeChatModal;
