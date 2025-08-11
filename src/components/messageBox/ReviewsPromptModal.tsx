// ✅ ReviewsPromptModal.tsx — 每个卡片支持伸缩（Collapse 默认收起）
import { Modal, Typography, Collapse } from "antd";
import { MessageOutlined } from "@ant-design/icons";
import EChartsBlock from "../eCharts/EChartsBlock";
import FreeChatModal from "./ReviewsCard/FreeChatModal";
import { fetchReviewInsights, fetchPrepareRagContext } from "../../api/api"; 
import { useState } from "react";

const { Paragraph, Title } = Typography;
const { Panel } = Collapse;

const mockSentimentData = [
  { name: "Positive", value: 72 },
  { name: "Negative", value: 28 }
];

const mockTopKeywordData = [
  { name: "location", value: 120 },
  { name: "clean", value: 95 },
  { name: "friendly", value: 80 },
  { name: "noisy", value: 50 },
  { name: "host", value: 45 }
];

interface ReviewsPromptModalProps {
  open: boolean;
  onClose: () => void;
}

const ReviewsPromptModal = ({ open, onClose }: ReviewsPromptModalProps) => {
  const [wordCloudData, setWordCloudData] = useState([]);
  const [loadingWordCloud, setLoadingWordCloud] = useState(false);
  const [wordCloudLoaded, setWordCloudLoaded] = useState(false); // ✅ 词云部分是否加载过
  const [isFetchingWordCloud, setIsFetchingWordCloud] = useState(false); // ✅ 新增锁
  
  const [ragContextPrepared, setRagContextPrepared] = useState(false);
  const [ragIndexId, setRagIndexId] = useState<string | null>(null);

  const handleCollapseChange = async(activeKeys: string[] | string) => {
    // activeKeys 是一个数组，比如 ['1', '2']
    const keys = Array.isArray(activeKeys) ? activeKeys : [activeKeys];

    if (keys.includes('1') && !wordCloudLoaded) {
      // 说明 "1. Word Cloud" 这个Panel展开了，而且还没加载过
      loadWordCloud();
    }
    if (keys.includes("4") && !ragContextPrepared) {
      await prepareRagContext();
    }

  };

  const loadWordCloud = async () => {
    if (isFetchingWordCloud || wordCloudLoaded) {
      return; // 防止重复请求
    }
  
    setIsFetchingWordCloud(true);  // 🔒 上锁
    setLoadingWordCloud(true);
  
    try {
      const res: any = await fetchReviewInsights();
      if (res && res.data) {
        setWordCloudData(res.data);
        setWordCloudLoaded(true); // ✅ 成功记住
        console.log(res.data)
      }
    } catch (error) {
      console.error("Failed to fetch wordcloud:", error);
      // 注意失败了也需要处理，比如可以考虑重试机制（可选）
    } finally {
      setLoadingWordCloud(false);
      setIsFetchingWordCloud(false);  // 🔓 解锁
    }
  };

  
  const prepareRagContext = async () => {
    try {
      const res: any = await fetchPrepareRagContext();
      if (res && res.index_id) {
        console.log(res)
        setRagIndexId(res.index_id);
        setRagContextPrepared(true);
      }
    } catch (error) {
      console.error("Failed to prepare RAG context:", error);
      console.error("Failed to prepare review context, please retry later.");
    } finally {
      // setLoadingRagContext(false);
    }
  };
  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={850}
      bodyStyle={{ padding: 0 }}
      title={<Title level={4} className="px-6 pt-4">🧠 Explore Guest Reviews</Title>}
    >
      <div className="space-y-4 px-6 pb-6">
      <Collapse bordered onChange={handleCollapseChange}>
        <Panel header="1. Word Cloud" key="1">
          <Paragraph className="text-gray-700 mb-2">
            <strong>Word Cloud</strong>: Top-mentioned keywords from guest reviews
          </Paragraph>

          {loadingWordCloud ? (
            <div className="text-center py-8 text-gray-400">Loading word cloud...</div>
          ) : wordCloudData && wordCloudData.length > 0 ? (
            <EChartsBlock type="wordcloud" data={wordCloudData} />
          ) : (
            <div className="text-center py-8 text-gray-400">No review data available</div>
          )}
        </Panel>


          <Panel header="2. Sentiment Overview" key="2">
            <Paragraph className="text-gray-700 mb-2">
              <strong>Sentiment</strong>: Overall positive vs negative ratio across reviews
            </Paragraph>
            <EChartsBlock type="pie" data={mockSentimentData} />
          </Panel>

          <Panel header="3. Top Keywords" key="3">
            <Paragraph className="text-gray-700 mb-2">
              <strong>Top Keywords</strong>: Most frequent topics (with color-coded sentiment)
            </Paragraph>
            <EChartsBlock type="bar" data={mockTopKeywordData} />
          </Panel>

          <Panel header="4. Ask the Reviews" key="4">
            <Paragraph className="text-gray-700 mb-2">
              <strong>Ask Anything</strong>: Start chatting with our RAG review assistant
            </Paragraph>
            <FreeChatModal inline indexId={ragIndexId}/>
          </Panel>
        </Collapse>
      </div>

      <div className="border-t text-center text-gray-400 text-xs py-2">
        <MessageOutlined /> Guest review insights powered by RAG Q&A and Visualization
      </div>
    </Modal>
  );
};

export default ReviewsPromptModal;