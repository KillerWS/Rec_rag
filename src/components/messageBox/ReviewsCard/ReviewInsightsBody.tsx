// ✅ ReviewInsightsBody.tsx — 模态框内滚动内容主体（词云 + 饼图 + 条形图 + 聊天）
import { Divider, Typography } from "antd";
import EChartsBlock from "../../eCharts/EChartsBlock";
import FreeChatModal from "./FreeChatModal"; // ✅ 使用 inline 模式嵌入

const { Paragraph } = Typography;

// mock 数据
const mockWordCloudData = [
  { name: "location", value: 120 },
  { name: "clean", value: 95 },
  { name: "friendly", value: 80 },
  { name: "noisy", value: 50 },
  { name: "host", value: 45 }
];
 
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

const ReviewInsightsBody = () => {
  return (
    <div style={{ maxHeight: 520, overflowY: "auto", paddingRight: 12 }}>
      <Divider orientation="left" orientationMargin={8}>1. Word Cloud</Divider>
      <Paragraph>🔍 Top-mentioned keywords among all reviews</Paragraph>
      <EChartsBlock type="wordcloud" data={mockWordCloudData} />

      <Divider orientation="left" orientationMargin={8}>2. Sentiment Distribution</Divider>
      <Paragraph>🙂 Positive vs 😡 Negative sentiment across guest reviews</Paragraph>
      <EChartsBlock type="pie" data={mockSentimentData} />

      <Divider orientation="left" orientationMargin={8}>3. Top Keywords</Divider>
      <Paragraph>📊 Most frequently mentioned topics by guests</Paragraph>
      <EChartsBlock type="bar" data={mockTopKeywordData} />

      <Divider orientation="left" orientationMargin={8}>4. Ask the Reviews</Divider>
      <Paragraph>💬 Start a natural language Q&A based on guest comments</Paragraph>
      <FreeChatModal inline />
    </div>
  );
};

export default ReviewInsightsBody;
