// ✅ FreeChatModal.tsx — 支持弹窗与嵌入两种模式的对话组件
import { useState, useRef, useEffect } from "react";
import { Modal, Input, Button, Spin, Card, Collapse } from "antd";
import { SendOutlined, CommentOutlined } from "@ant-design/icons";
import { fetchRAGAnswerScripted } from "../../../api/api";

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
  const [showSourcesModal, setShowSourcesModal] = useState(false);
  const [modalSources, setModalSources] = useState<any[]>([]);

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
      // ✅ 调用 scripted RAG 接口，传完整 newHistory
      const extra = indexId ? { index_id: indexId } : {};
      const res: any = await fetchRAGAnswerScripted(inputValue, newHistory, extra);
  
      const systemMsg = {
        sender: "system",
        text: res.answer,
        sources: res.source_documents || [],
        is_scripted_mode: !!res.is_scripted_mode,
        route_info: res.route_info || null,
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

  const truncate = (text: string, max = 140) => {
    if (!text) return '';
    return text.length > max ? `${text.slice(0, max)}…` : text;
  };

  const openSourcesModal = (sources: any[]) => {
    setModalSources(Array.isArray(sources) ? sources : []);
    setShowSourcesModal(true);
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

              {msg.sender === "system" && (msg.is_scripted_mode || msg.route_info) && (
                <div className="mt-2 text-xs text-gray-500">
                  {msg.is_scripted_mode && <span className="mr-2">Mode: Scripted</span>}
                  {msg.route_info && (
                    <span>
                      Route: {msg.route_info.route_type || 'unknown'}{typeof msg.route_info.retrieval_triggered === 'boolean' ? ` · Retrieval: ${msg.route_info.retrieval_triggered ? 'on' : 'off'}` : ''}
                    </span>
                  )}
                </div>
              )}

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
                      {(msg.sources as any[]).slice(0, 3).map((src: any, i: number) => {
                        const snippet = src?.snippet || src?.page_content || src?.item_detail?.description || '';
                        const name = src?.item_detail?.name;
                        const price = src?.item_detail?.price;
                        const url = src?.item_detail?.listing_url;
                        const roomType = src?.room_type || src?.item_detail?.room_type;
                        return (
                          <Card
                            key={i}
                            size="small"
                            className="bg-yellow-50 border-l-4 border-yellow-400"
                          >
                            <p className="text-sm italic">“{truncate(String(snippet || ''))}”</p>
                            <div className="text-xs text-gray-600 mt-1">
                              {name && <span className="mr-2">{name}</span>}
                              {typeof price !== 'undefined' && <span className="mr-2">€{price}</span>}
                              {roomType && <span className="mr-2">{roomType}</span>}
                              {url && (
                                <a href={url} target="_blank" rel="noreferrer" className="text-blue-600">View</a>
                              )}
                            </div>
                          </Card>
                        );
                      })}
                      {msg.sources.length > 3 && (
                        <div className="pt-2">
                          <Button size="small" onClick={() => openSourcesModal(msg.sources)}>Open all reviews</Button>
                        </div>
                      )}
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
      <Modal
        open={showSourcesModal}
        onCancel={() => setShowSourcesModal(false)}
        footer={null}
        width={740}
        title={`📎 Supporting Reviews (${modalSources.length})`}
        bodyStyle={{ maxHeight: '60vh', overflowY: 'auto' }}
      >
        <div className="space-y-2">
          {modalSources.map((src: any, i: number) => {
            const snippet = src?.snippet || src?.page_content || src?.item_detail?.description || '';
            const name = src?.item_detail?.name;
            const price = src?.item_detail?.price;
            const url = src?.item_detail?.listing_url;
            const roomType = src?.room_type || src?.item_detail?.room_type;
            const neighbourhood = src?.item_detail?.neighbourhood_group_cleansed || src?.item_detail?.neighbourhood;
            return (
              <Card key={i} size="small" className="bg-white">
                <p className="text-sm italic">“{String(snippet || '')}”</p>
                <div className="text-xs text-gray-600 mt-1 flex flex-wrap gap-2">
                  {name && <span>🏷️ {name}</span>}
                  {typeof price !== 'undefined' && <span>💶 €{price}</span>}
                  {roomType && <span>🛏️ {roomType}</span>}
                  {neighbourhood && <span>📍 {neighbourhood}</span>}
                  {url && <a href={url} target="_blank" rel="noreferrer" className="text-blue-600">Listing</a>}
                </div>
              </Card>
            );
          })}
        </div>
      </Modal>
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
