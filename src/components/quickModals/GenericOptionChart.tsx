import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

interface GenericOptionChartProps {
  option: any;
  height?: number;
}

const GenericOptionChart: React.FC<GenericOptionChartProps> = ({ option, height = 420 }) => {
  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current || !option) return;

    if (!chartRef.current) {
      chartRef.current = echarts.init(ref.current);
    }

    chartRef.current.setOption(option, true);

    const ro = new ResizeObserver(() => chartRef.current?.resize());
    ro.observe(ref.current);

    return () => {
      ro.disconnect();
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, [option]);

  return <div ref={ref} style={{ width: '100%', height }} />;
};

export default GenericOptionChart; 