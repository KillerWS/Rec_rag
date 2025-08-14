import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'

export interface RoomTypeSlice { label: string; value: number; color: string }

const RoomTypePie: React.FC<{ items: RoomTypeSlice[]; height?: number; title?: string; showLegend?: boolean }> = ({ items, height = 160, title, showLegend = true }) => {
  const option = useMemo(() => {
    const data = items.map(it => ({ value: it.value, name: it.label, itemStyle: { color: it.color } }))
    return {
      title: title ? { text: title, left: 'center', textStyle: { fontSize: 12, fontWeight: 600 } } : undefined,
      tooltip: { trigger: 'item' },
      legend: showLegend ? { bottom: 0, left: 'center', itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 10 } } : undefined,
      series: [
        {
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: true,
          label: { show: false },
          labelLine: { show: false },
          data
        }
      ]
    }
  }, [items, title, showLegend])

  return <ReactECharts style={{ height }} option={option} />
}

export default RoomTypePie 