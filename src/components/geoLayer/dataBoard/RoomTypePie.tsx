import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'

export interface RoomTypeSlice { label: string; value: number; color: string }

const RoomTypePie: React.FC<{ items: RoomTypeSlice[]; height?: number; title?: string; showLegend?: boolean; centerText?: string }> = ({ items, height = 160, title, centerText }) => {
  const option = useMemo(() => {
    const total = items.reduce((s, it) => s + (Number(it.value) || 0), 0)
    const data = items.map(it => ({ value: it.value, name: it.label, itemStyle: { color: it.color } }))
    return {
      title: title ? { text: title, left: 'center', textStyle: { fontSize: 12, fontWeight: 600 } } : undefined,
      tooltip: {
        show: true,
        trigger: 'item',
        formatter: (params: any) => {
          const pct = total > 0 ? Math.round((Number(params.value) || 0) / total * 100) : 0;
          return `<strong>${params.name}</strong><br/>
                  ${params.value.toLocaleString()} listings (${pct}%)`;
        }
      },
      legend: {
        show: false  // 隐藏图例
      },
      // 简洁布局，无需额外边距
      grid: {
        left: '5%',
        right: '5%',
        top: '5%',
        bottom: '5%',
        containLabel: true
      },
      graphic: undefined,
      series: [
        {
          type: 'pie',
          radius: ['45%', '72%'],   // 恢复原来的饼图大小
          center: ['50%', '50%'],   // 居中显示
          avoidLabelOverlap: true,
          label: {
            show: false  // 完全隐藏标签，只通过上层图例和tooltip显示信息
          },
          labelLine: { 
            show: false  // 隐藏引导线
          },
          emphasis: {
            label: {
              show: true,
              fontSize: 12,
              fontWeight: 'bold'
            },
            itemStyle: {
              shadowBlur: 10,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.5)'
            }
          },
          data
        }
      ]
    }
  }, [items, title, centerText])

  return <ReactECharts 
    style={{ height, width: '100%' }} 
    option={option as any}
    opts={{ renderer: 'canvas' }}
  />
}

export default RoomTypePie 