import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface CoverageItem {
  room_type: string;
  count_in_budget: number;
  share_in_budget: number; // 0..1
}

interface BudgetCoverageMiniDonutProps {
  coverage: CoverageItem[];
  overall_coverage: number; // 0..1 or 0..100, we'll normalize
  onOpenHeatmap: (payload: { room_type: string }) => void;
  height?: number;
}

const BudgetCoverageMiniDonut: React.FC<BudgetCoverageMiniDonutProps> = ({ coverage, overall_coverage, onOpenHeatmap, height = 220 }) => {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current || !Array.isArray(coverage)) return;
    if (!chartInstanceRef.current) chartInstanceRef.current = echarts.init(chartRef.current);
    const chart = chartInstanceRef.current as echarts.ECharts;

    const data = coverage.map((c) => ({ name: c.room_type, value: Math.max(0, Number(c.share_in_budget) || 0) }));
    const percent = overall_coverage > 1 ? Math.round(overall_coverage) : Math.round(overall_coverage * 100);

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'item',
        formatter: (p: any) => {
          const item = coverage[p.dataIndex];
          const share = (item?.share_in_budget ?? 0) * 100;
          return `${item.room_type}<br/>In budget: ${item.count_in_budget}<br/>Share: ${share.toFixed(1)}%`;
        }
      },
      legend: { show: false },
      graphic: [{
        type: 'text',
        left: 'center',
        top: 'middle',
        style: {
          text: `${percent}%\nwithin budget`,
          textAlign: 'center',
          fill: '#111827',
          fontSize: 14,
          fontWeight: 600,
          lineHeight: 18
        }
      }],
      series: [{
        name: 'Budget coverage',
        type: 'pie',
        radius: ['58%', '78%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 2 },
        label: { show: false },
        labelLine: { show: false },
        data
      }]
    };

    chart.clear();
    chart.setOption(option);
    chart.off('click');
    chart.on('click', (p: any) => {
      const rt = coverage?.[p?.dataIndex]?.room_type;
      if (rt) onOpenHeatmap({ room_type: rt });
    });

    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(chartRef.current);
    return () => { ro.disconnect(); chart.dispose(); chartInstanceRef.current = null; };
  }, [coverage, overall_coverage, onOpenHeatmap]);

  return <div ref={chartRef} style={{ width: '100%', height }} />;
};

export default BudgetCoverageMiniDonut;


