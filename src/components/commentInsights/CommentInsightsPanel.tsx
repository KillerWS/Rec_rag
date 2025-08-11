// CommentInsightsPanel.tsx
import React, { useEffect, useState } from 'react'
import { Tabs, Card, Spin, Row, Col } from 'antd'
import ReactECharts from 'echarts-for-react'
import {
  fetchCommentsSummary,
  fetchCommentsWordCloud,
  fetchCommentsSentiment,
  fetchUserClusters
} from '../../api/api'

const { TabPane } = Tabs

export interface CommentInsightsPanelProps {
  level: 'district' | 'neighbourhood'
  groupName: string
}

const CommentInsightsPanel: React.FC<CommentInsightsPanelProps> = ({
  level,
  groupName
}) => {
  // 哪个 Tab 当前激活
  const [activeTab, setActiveTab] = useState<'word'|'sentiment'|'clusters'>('word')
  const [loading, setLoading] = useState<boolean>(false)

  // ECharts option states
  const [wordOption, setWordOption] = useState<any>(null)
  const [sentimentOption, setSentimentOption] = useState<any>(null)
  const [clusterOption, setClusterOption] = useState<any>(null)

  // 概览数据
  const [summary, setSummary] = useState<{
    totalComments: number
    avgSentiment: number
    uniqueUsers: number
    clusters: number
  }>({
    totalComments: 0,
    avgSentiment: 0,
    uniqueUsers: 0,
    clusters: 0
  })

  // 加载概览 & WordCloud & Sentiment（初次）
  useEffect(() => {
    loadSummary()
    loadWordCloud()
    loadSentiment()
    // 聚类数据延后到 Tab 切换
  }, [level, groupName])

  // Tab 切到 clusters 时再加载
  useEffect(() => {
    if (activeTab === 'clusters') {
      loadClusters()
    }
  }, [activeTab, level, groupName])

  /** 1️⃣ 概览 */
  async function loadSummary() {
    try {
      const res = await fetchCommentsSummary(level, groupName)
      setSummary(res)
    } catch (e) {
      console.error('fetchCommentsSummary failed', e)
    }
  }

  /** 2️⃣ 词云 */
  async function loadWordCloud() {
    setLoading(true)
    try {
      const data = await fetchCommentsWordCloud(level, groupName)
      // 取 top20
      const top = data.slice(0, 20)
      setWordOption({
        title: { text: 'Top Review Keywords', left: 'center' },
        tooltip: {},
        series: [{
          type: 'wordCloud',
          shape: 'circle',
          gridSize: 2,
          sizeRange: [14, 50],
          rotationRange: [-45, 45],
          textStyle: {
            fontFamily: 'sans-serif',
            color: () => '#' + Math.floor(Math.random()*0xffffff).toString(16)
          },
          data: top.map(w => ({ name: w.word, value: w.count }))
        }]
      })
    } catch (e) {
      console.error('loadWordCloud failed', e)
      setWordOption(null)
    } finally {
      setLoading(false)
    }
  }

  /** 3️⃣ 情感分析 */
  async function loadSentiment() {
    setLoading(true)
    try {
      const res = await fetchCommentsSentiment(level, groupName)
      setSentimentOption({
        title: { text: 'Sentiment Analysis', left: 'center' },
        tooltip: { trigger: 'item' },
        legend: { bottom: 10, left: 'center' },
        series: [
          {
            name: 'Sentiment',
            type: 'pie',
            radius: ['40%', '70%'],
            label: { formatter: '{b}: {d}%' },
            data: [
              { value: res.positive, name: 'Positive' },
              { value: res.neutral,  name: 'Neutral' },
              { value: res.negative, name: 'Negative' }
            ]
          }
        ]
      })
    } catch (e) {
      console.error('loadSentiment failed', e)
      setSentimentOption(null)
    } finally {
      setLoading(false)
    }
  }

  /** 4️⃣ 用户聚类散点 */
  async function loadClusters() {
    setLoading(true)
    try {
      const data = await fetchUserClusters(level, groupName)
      const clusterIds = Array.from(new Set(data.map(d => d.clusterId)))
      setClusterOption({
        title: { text: 'User Clusters', left: 'center' },
        tooltip: { trigger: 'item', formatter: '{a} ({c})' },
        legend: { bottom: 10, data: clusterIds },
        xAxis: { type: 'value', name: 'Component 1' },
        yAxis: { type: 'value', name: 'Component 2' },
        series: clusterIds.map(cid => ({
          name: cid,
          type: 'scatter',
          data: data
            .filter(d => d.clusterId === cid)
            .map(d => [d.x, d.y])
        }))
      })
    } catch (e) {
      console.error('loadClusters failed', e)
      setClusterOption(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      {/* —— 概览卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col><Card size="small" title="💬 Total Comments">{summary.totalComments.toLocaleString()}</Card></Col>
        <Col><Card size="small" title="😊 Avg Sentiment">{summary.avgSentiment.toFixed(2)}</Card></Col>
        <Col><Card size="small" title="👥 Unique Users">{summary.uniqueUsers.toLocaleString()}</Card></Col>
        <Col><Card size="small" title="🔢 Clusters">{summary.clusters}</Card></Col>
      </Row>

      {/* —— 子Tab */}
      <Tabs activeKey={activeTab} onChange={k => setActiveTab(k as any)}>
        <TabPane key="word" tab="📝 Word Cloud">
          {loading || !wordOption
            ? <Spin />
            : <ReactECharts style={{ height: 400 }} option={wordOption} />}
        </TabPane>
        <TabPane key="sentiment" tab="📊 Sentiment">
          {loading || !sentimentOption
            ? <Spin />
            : <ReactECharts style={{ height: 400 }} option={sentimentOption} />}
        </TabPane>
        <TabPane key="clusters" tab="🔍 User Clusters">
          {loading || !clusterOption
            ? <Spin />
            : <ReactECharts style={{ height: 400 }} option={clusterOption} />}
        </TabPane>
      </Tabs>
    </div>
  )
}

export default CommentInsightsPanel
