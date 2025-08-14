import React, { useEffect, useRef, useState } from 'react';
import { Modal, Spin } from 'antd';
import EChartsBlock from '../eCharts/EChartsBlock';
import { fetchCommentsSummary, fetchCommentsWordCloud, fetchCommentsSentiment } from '../../api/api';

interface ReviewInsightsModalProps {
  visible: boolean;
  onClose: () => void;
}

const ReviewInsightsModal: React.FC<ReviewInsightsModalProps> = ({ visible, onClose }) => {
  const loadedRef = useRef(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [wordCloudData, setWordCloudData] = useState<Array<{ name: string; value: number }>>([]);
  const [sentimentData, setSentimentData] = useState<Array<{ name: string; value: number }>>([]);
  const [summary, setSummary] = useState<null | { totalComments: number; avgSentiment: number; uniqueUsers: number; clusters: number }>(null);

  useEffect(() => {
    const load = async () => {
      if (!visible || loadedRef.current) return;
      setLoading(true);
      setError(null);
      try {
        // 默认用全局（ALL districts）视图
        const level = 'district' as const;
        const name = 'ALL';
        const [summaryRes, wc, sent] = await Promise.all([
          fetchCommentsSummary(level, name),
          fetchCommentsWordCloud(level, name),
          fetchCommentsSentiment(level, name)
        ]);
        setSummary(summaryRes);
        setWordCloudData(wc.map(w => ({ name: w.word, value: w.count })));
        setSentimentData([
          { name: 'Positive', value: sent.positive },
          { name: 'Neutral', value: sent.neutral },
          { name: 'Negative', value: sent.negative },
        ]);
        loadedRef.current = true;
      } catch (e: any) {
        setError(e?.message || 'Failed to load review insights');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [visible]);

  return (
    <Modal
      title="Review insights"
      open={visible}
      onCancel={onClose}
      width={1000}
      footer={null}
      destroyOnClose={false}
    >
      {loading && <Spin />}
      {error && <div className="text-red-500 text-sm">{error}</div>}
      {!loading && !error && (
        <div className="space-y-4">
          {summary && (
            <div className="text-sm text-gray-600 flex gap-4">
              <div>Total comments: <span className="font-semibold">{summary.totalComments}</span></div>
              <div>Avg sentiment: <span className="font-semibold">{summary.avgSentiment.toFixed(2)}</span></div>
              <div>Unique users: <span className="font-semibold">{summary.uniqueUsers}</span></div>
              <div>Clusters: <span className="font-semibold">{summary.clusters}</span></div>
            </div>
          )}
          <EChartsBlock type="wordcloud" data={wordCloudData} height={360} />
          <EChartsBlock type="bar" data={sentimentData} height={280} />
        </div>
      )}
    </Modal>
  );
};

export default ReviewInsightsModal; 