import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface RoomTypeStackedBarProps {
  title?: string;
  chartData: any;
  height?: number;
  modalVisible?: boolean;
}

const RoomTypeStackedBar: React.FC<RoomTypeStackedBarProps> = ({ title, chartData, height = 360, modalVisible }) => {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current || !chartData || !chartData.xAxis || !chartData.series) {
      console.warn("⛔️ Invalid chart data for RoomTypeStackedBar");
      return;
    }

    if (!chartInstanceRef.current) {
      chartInstanceRef.current = echarts.init(chartRef.current);
    }
    const chartInstance = chartInstanceRef.current;

    const option = {
      title: {
        text: title || "Room Type Distribution by Price Range",
        left: "center"
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" }
      },
      legend: {
        bottom: 0
      },
      grid: {
        top: 60,
        left: "3%",
        right: "4%",
        bottom: "12%",
        containLabel: true
      },
      xAxis: {
        type: "category",
        data: chartData.xAxis,
        axisLabel: {
          interval: 0,
          rotate: 30
        }
      },
      yAxis: {
        type: "value",
        name: "Listings"
      },
      series: chartData.series.map((seriesItem: any, index: number) => ({
        ...seriesItem,
        type: "bar",
        stack: "total",
        emphasis: {
          focus: "series"
        },
        itemStyle: {
          opacity: chartData.highlight && chartData.highlight.includes(index) ? 1 : 0.6
        }
      }))
    } as echarts.EChartsCoreOption;

    chartInstance.setOption(option);

    const resizeObserver = new ResizeObserver(() => {
      chartInstance.resize();
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      chartInstance.dispose();
      chartInstanceRef.current = null;
    };
  }, [chartData, title]);

  // When modal visibility changes, trigger a resize after animation
  useEffect(() => {
    if (modalVisible !== undefined && chartInstanceRef.current) {
      const timer = setTimeout(() => {
        chartInstanceRef.current?.resize();
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [modalVisible]);

  return <div ref={chartRef} style={{ width: "100%", height: `${height}px` }} />;
};

export default RoomTypeStackedBar;
