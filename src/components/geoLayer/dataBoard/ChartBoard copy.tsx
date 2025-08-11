// ChartBoard.tsx
import React, { useEffect, useState } from 'react'
import { Tabs, Modal, Button, Spin } from 'antd'
import ReactECharts from 'echarts-for-react'
import {
  fetchPriceStats,
  fetchRoomTypeStats,
  fetchReviewTimeSeries,
  fetchHostStats,
  fetchCommentsWordCloud
} from '../../../api/api'

export interface ChartBoardProps {
  level: 'district' | 'neighbourhood'
  groupName: string
}

const { TabPane } = Tabs

const ChartBoard: React.FC<ChartBoardProps> = ({ level, groupName }) => {
  const [loading, setLoading] = useState(false)
  const [priceOption, setPriceOption] = useState<any>(null)
  const [roomOption, setRoomOption] = useState<any>(null)
  const [reviewOption, setReviewOption] = useState<any>(null)
  const [hostOption, setHostOption] = useState<any>(null)
  const [wordOption, setWordOption] = useState<any>(null)
  const [modal, setModal] = useState<{ visible: boolean; theme: string }>({
    visible: false,
    theme: ''
  })

  useEffect(() => {
    loadPrice()
    loadRoomType()
  }, [level, groupName])

  // 1) Price Distribution → histogram
  const loadPrice = async () => {
    setLoading(true)
    try {
      const res = await fetchPriceStats(level, groupName)
      const cats: string[] = res.data.categories
      const vals: number[] = res.data.values
      setPriceOption({
        title: { text: 'Price Distribution', left: 'center' },
        tooltip: { trigger: 'axis' },
        xAxis: {
          type: 'category',
          data: cats,
          name: 'Price Range'
        },
        yAxis: {
          type: 'value',
          name: 'Count'
        },
        series: [
          {
            name: 'Count',
            type: 'bar',
            data: vals
          }
        ]
      })
    } catch (e) {
      console.error('loadPrice failed', e)
      setPriceOption(null)
    } finally {
      setLoading(false)
    }
  }

  // 2) Room Type → pie
  const loadRoomType = async () => {
    setLoading(true)
    try {
      const res = await fetchRoomTypeStats(level, groupName)
      const cats: string[] = res.data.categories
      const vals: number[] = res.data.values
      setRoomOption({
        title: { text: 'Room Type Share', left: 'center' },
        tooltip: { trigger: 'item' },
        legend: { orient: 'vertical', left: 'left' },
        series: [
          {
            name: 'Rooms',
            type: 'pie',
            radius: '50%',
            data: cats.map((c, i) => ({ value: vals[i], name: c })),
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0, 0, 0, 0.5)'
              }
            }
          }
        ]
      })
    } catch (e) {
      console.error('loadRoomType failed', e)
      setRoomOption(null)
    } finally {
      setLoading(false)
    }
  }

  // 3) Review Time Series → line
  const loadReview = async () => {
    setLoading(true)
    try {
      const res = await fetchReviewTimeSeries(level, groupName)
      const cats: string[] = res.data.categories
      const vals: number[] = res.data.values
      setReviewOption({
        title: { text: 'Review Count Distribution', left: 'center' },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: cats, name: 'Review Range' },
        yAxis: { type: 'value', name: 'Count' },
        series: [
          {
            name: 'Count',
            type: 'bar',
            data: vals
          }
        ]
      })
    } catch (e) {
      console.error('loadReview failed', e)
      setReviewOption(null)
    } finally {
      setLoading(false)
    }
  }

  // 4) Host Stats → scatter
  const loadHost = async () => {
    setLoading(true)
    try {
      const res = await fetchHostStats(level, groupName)
      const cats: number[] = res.data.categories  // host listing counts
      const vals: number[] = res.data.values      // host counts
      setHostOption({
        title: { text: 'Host Listing Count vs Hosts', left: 'center' },
        tooltip: { trigger: 'item' },
        xAxis: { type: 'value', name: 'Listings per Host' },
        yAxis: { type: 'value', name: 'Number of Hosts' },
        series: [
          {
            name: 'Hosts',
            type: 'scatter',
            data: cats.map((x, i) => [x, vals[i]])
          }
        ]
      })
    } catch (e) {
      console.error('loadHost failed', e)
      setHostOption(null)
    } finally {
      setLoading(false)
    }
  }

  // 5) Word Cloud
  const loadWord = async () => {
    setLoading(true)
    try {
      const res = await fetchCommentsWordCloud(level, groupName)
      // echarts wordcloud requires `echarts-wordcloud` extension…
      // fallback: show bar of top 20
      const top20 = res.slice(0, 20)
      setWordOption({
        title: { text: 'Top Review Keywords', left: 'center' },
        tooltip: {},
        xAxis: { type: 'category', data: top20.map(w => w.word) },
        yAxis: { type: 'value', name: 'Count' },
        series: [
          {
            name: 'Count',
            type: 'bar',
            data: top20.map(w => w.count)
          }
        ]
      })
    } catch (e) {
      console.error('loadWord failed', e)
      setWordOption(null)
    } finally {
      setLoading(false)
    }
  }

  const openModal = (theme: string) => {
    setModal({ visible: true, theme })
    switch (theme) {
      case 'review':
        loadReview()
        break
      case 'host':
        loadHost()
        break
      case 'word':
        loadWord()
        break
    }
  }

  return (
    <>
      <Tabs defaultActiveKey="price">
        <TabPane tab="Price Distribution" key="price">
          {loading || !priceOption ? (
            <Spin />
          ) : (
            <ReactECharts style={{ height: 300 }} option={priceOption} />
          )}
          <Button onClick={() => openModal('price')}>Zoom</Button>
        </TabPane>

        <TabPane tab="Room Type Share" key="room">
          {loading || !roomOption ? (
            <Spin />
          ) : (
            <ReactECharts style={{ height: 300 }} option={roomOption} />
          )}
          <Button onClick={() => openModal('room')}>Zoom</Button>
        </TabPane>

        <TabPane tab="Review Distribution" key="review">
          <Button onClick={loadReview}>Load</Button>
          {loading || !reviewOption ? (
            reviewOption === null ? <div>No data</div> : <Spin />
          ) : (
            <ReactECharts style={{ height: 300 }} option={reviewOption} />
          )}
          <Button onClick={() => openModal('review')}>Zoom</Button>
        </TabPane>

        <TabPane tab="Host Analysis" key="host">
          <Button onClick={loadHost}>Load</Button>
          {loading || !hostOption ? (
            hostOption === null ? <div>No data</div> : <Spin />
          ) : (
            <ReactECharts style={{ height: 300 }} option={hostOption} />
          )}
          <Button onClick={() => openModal('host')}>Zoom</Button>
        </TabPane>

        <TabPane tab="Keywords" key="word">
          <Button onClick={loadWord}>Load</Button>
          {loading || !wordOption ? (
            wordOption === null ? <div>No data</div> : <Spin />
          ) : (
            <ReactECharts style={{ height: 300 }} option={wordOption} />
          )}
          <Button onClick={() => openModal('word')}>Zoom</Button>
        </TabPane>
      </Tabs>

      <Modal
        visible={modal.visible}
        title={{
          price: 'Price Distribution (Zoomed)',
          room: 'Room Type Share (Zoomed)',
          review: 'Review Distribution (Zoomed)',
          host: 'Host Analysis (Zoomed)',
          word: 'Top Keywords (Zoomed)'
        }[modal.theme]}
        footer={null}
        onCancel={() => setModal({ visible: false, theme: '' })}
        width="80vw"
      >
        {modal.theme === 'price' && priceOption && (
          <ReactECharts style={{ height: '70vh' }} option={priceOption} />
        )}
        {modal.theme === 'room' && roomOption && (
          <ReactECharts style={{ height: '70vh' }} option={roomOption} />
        )}
        {modal.theme === 'review' && reviewOption && (
          <ReactECharts style={{ height: '70vh' }} option={reviewOption} />
        )}
        {modal.theme === 'host' && hostOption && (
          <ReactECharts style={{ height: '70vh' }} option={hostOption} />
        )}
        {modal.theme === 'word' && wordOption && (
          <ReactECharts style={{ height: '70vh' }} option={wordOption} />
        )}
      </Modal>
    </>
  )
}

export default ChartBoard
