// ChartBoard.tsx
import React, { useEffect, useState } from 'react'
import { Tabs, Modal, Button, Spin } from 'antd'
import ReactECharts from 'echarts-for-react'
import {
  fetchPriceStats,
  fetchRoomTypeStats,
  fetchReviewTimeSeries,
  fetchHostStats,
  fetchCommentsWordCloud,
  fetchSquareDistribution
} from '../../../api/api'
import './ChartBoard.css'

export interface ChartBoardProps {
  level: 'district' | 'neighbourhood'
  groupName: string
  initialTab?: 'price'|'room'|'review'|'host'|'word'|'square'
}

const { TabPane } = Tabs

const ChartBoard: React.FC<ChartBoardProps> = ({
  level,
  groupName,
  initialTab
}) => {
  const [loading, setLoading] = useState(false)

  const [priceOption, setPriceOption] = useState<any>(null)
  const [roomOption, setRoomOption] = useState<any>(null)
  const [reviewOption, setReviewOption] = useState<any>(null)
  const [hostOption, setHostOption] = useState<any>(null)
  const [wordOption, setWordOption] = useState<any>(null)
  const [squareOption, setSquareOption] = useState<any>(null)

  const [modal, setModal] = useState<{ visible: boolean; theme: string }>({
    visible: false,
    theme: ''
  })

  useEffect(() => {
    loadPrice()
    loadRoomType()
  }, [level, groupName])

  const loadPrice = async () => {
    setLoading(true)
    try {
      const res = await fetchPriceStats(level, groupName)
      setPriceOption({
        title: { text: 'Price Distribution', left: 'center' },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: res.data.categories, name: 'Price Range' },
        yAxis: { type: 'value', name: 'Count' },
        series: [{ name: 'Count', type: 'bar', data: res.data.values }]
      })
    } catch (e) {
      console.error('loadPrice failed', e)
      setPriceOption(null)
    } finally {
      setLoading(false)
    }
  }

  const loadRoomType = async () => {
    setLoading(true)
    try {
      const res = await fetchRoomTypeStats(level, groupName)
      setRoomOption({
        title: { text: 'Room Type Share', left: 'center' },
        tooltip: { trigger: 'item' },
        legend: { orient: 'vertical', left: 'left' },
        series: [
          {
            name: 'Rooms',
            type: 'pie',
            radius: '50%',
            data: res.data.categories.map((c: string, i: number) => ({
              value: res.data.values[i], name: c
            }))
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

  const loadReview = async () => {
    setLoading(true)
    try {
      const res = await fetchReviewTimeSeries(level, groupName)
      setReviewOption({
        title: { text: 'Review Count Distribution', left: 'center' },
        tooltip: { trigger: 'axis' },
        xAxis: { type: 'category', data: res.data.categories, name: 'Review Range' },
        yAxis: { type: 'value', name: 'Count' },
        series: [{ name: 'Count', type: 'bar', data: res.data.values }]
      })
    } catch (e) {
      console.error('loadReview failed', e)
      setReviewOption(null)
    } finally {
      setLoading(false)
    }
  }

  const loadHost = async () => {
    setLoading(true)
    try {
      const res = await fetchHostStats(level, groupName)
      setHostOption({
        title: { text: 'Host Listing Count vs Hosts', left: 'center' },
        tooltip: { trigger: 'item' },
        xAxis: { type: 'value', name: 'Listings per Host' },
        yAxis: { type: 'value', name: 'Number of Hosts' },
        series: [
          {
            name: 'Hosts',
            type: 'scatter',
            data: res.data.categories.map((x: number, i: number) => [x, res.data.values[i]])
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

  const loadWord = async () => {
    setLoading(true)
    try {
      const res = await fetchCommentsWordCloud(level, groupName)
      const top20 = res.slice(0, 20)
      setWordOption({
        title: { text: 'Top Review Keywords', left: 'center' },
        tooltip: {},
        xAxis: { type: 'category', data: top20.map(w => w.word) },
        yAxis: { type: 'value', name: 'Count' },
        series: [{ name: 'Count', type: 'bar', data: top20.map(w => w.count) }]
      })
    } catch (e) {
      console.error('loadWord failed', e)
      setWordOption(null)
    } finally {
      setLoading(false)
    }
  }

  const loadSquareDistribution = async () => {
    setLoading(true)
    try {
      const res: any = await fetchSquareDistribution(level, groupName)
      setSquareOption({
        title: { text: 'Square Distribution', left: 'center' },
        tooltip: { trigger: 'item' },
        visualMap: {
          min: 0,
          max: Math.max(...res.bins.map((b: any) => b.value)),
          right: 10,
          bottom: 20
        },
        series: [
          {
            type: 'heatmap',
            coordinateSystem: 'cartesian2d',
            data: res.bins.map((b: any) => [b.x, b.y, b.value])
          }
        ],
        xAxis: { type: 'value', name: 'X' },
        yAxis: { type: 'value', name: 'Y' }
      })
    } catch (e) {
      console.error('loadSquareDistribution failed', e)
      setSquareOption(null)
    } finally {
      setLoading(false)
    }
  }

  const openModal = (theme: string) => {
    setModal({ visible: true, theme })
    switch (theme) {
      case 'price': loadPrice(); break
      case 'room': loadRoomType(); break
      case 'review': loadReview(); break
      case 'host': loadHost(); break
      case 'word': loadWord(); break
      case 'square': loadSquareDistribution(); break
    }
  }

  return (
    <>
      <Tabs
        className="chartboard-tabs"
        defaultActiveKey={initialTab || 'price'}
        tabBarGutter={16}
        tabBarStyle={{ whiteSpace: 'nowrap', overflowX: 'auto' }}
      >
        <TabPane tab="Price Distribution" key="price">
          {loading || !priceOption ? <Spin /> : <ReactECharts style={{ height: 300 }} option={priceOption} />}
          <Button onClick={() => openModal('price')}>Zoom</Button>
        </TabPane>

        <TabPane tab="Room Type Share" key="room">
          {loading || !roomOption ? <Spin /> : <ReactECharts style={{ height: 300 }} option={roomOption} />}
          <Button onClick={() => openModal('room')}>Zoom</Button>
        </TabPane>

        <TabPane tab="Review Distribution" key="review">
          <Button onClick={loadReview}>Load</Button>
          {loading || !reviewOption ? (reviewOption === null ? <div>No data</div> : <Spin />) : <ReactECharts style={{ height: 300 }} option={reviewOption} />}
          <Button onClick={() => openModal('review')}>Zoom</Button>
        </TabPane>

        <TabPane tab="Host Analysis" key="host">
          <Button onClick={loadHost}>Load</Button>
          {loading || !hostOption ? (hostOption === null ? <div>No data</div> : <Spin />) : <ReactECharts style={{ height: 300 }} option={hostOption} />}
          <Button onClick={() => openModal('host')}>Zoom</Button>
        </TabPane>

        <TabPane tab="Keywords" key="word">
          <Button onClick={loadWord}>Load</Button>
          {loading || !wordOption ? (wordOption === null ? <div>No data</div> : <Spin />) : <ReactECharts style={{ height: 300 }} option={wordOption} />}
          <Button onClick={() => openModal('word')}>Zoom</Button>
        </TabPane>

        <TabPane tab="Square Distribution" key="square">
          <Button onClick={loadSquareDistribution}>Load</Button>
          {loading || !squareOption ? (squareOption === null ? <div>No data</div> : <Spin />) : <ReactECharts style={{ height: 300 }} option={squareOption} />}
          <Button onClick={() => openModal('square')}>Zoom</Button>
        </TabPane>
      </Tabs>

      <Modal
        visible={modal.visible}
        title={{
          price: 'Price Distribution (Zoomed)',
          room: 'Room Type Share (Zoomed)',
          review: 'Review Distribution (Zoomed)',
          host: 'Host Analysis (Zoomed)',
          word: 'Top Keywords (Zoomed)',
          square: 'Square Distribution (Zoomed)'
        }[modal.theme]}
        footer={null}
        onCancel={() => setModal({ visible: false, theme: '' })}
        width="80vw"
      >
        {modal.theme === 'price' && priceOption && <ReactECharts style={{ height: '70vh' }} option={priceOption} />}
        {modal.theme === 'room' && roomOption && <ReactECharts style={{ height: '70vh' }} option={roomOption} />}
        {modal.theme === 'review' && reviewOption && <ReactECharts style={{ height: '70vh' }} option={reviewOption} />}
        {modal.theme === 'host' && hostOption && <ReactECharts style={{ height: '70vh' }} option={hostOption} />}
        {modal.theme === 'word' && wordOption && <ReactECharts style={{ height: '70vh' }} option={wordOption} />}
        {modal.theme === 'square' && squareOption && <ReactECharts style={{ height: '70vh' }} option={squareOption} />}
      </Modal>
    </>
  )
}

export default ChartBoard
