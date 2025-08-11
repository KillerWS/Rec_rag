// ✅ ReviewWordCloud.tsx — 评论词云图组件（使用 mock 数据）
import { useEffect, useRef } from "react";
import * as echarts from "echarts";

const mockWordCloudData = [
  { name: "location", value: 123 },
  { name: "clean", value: 98 },
  { name: "friendly", value: 85 },
  { name: "noise", value: 72 },
  { name: "wifi", value: 60 },
  { name: "kitchen", value: 55 },
  { name: "bed", value: 50 },
  { name: "comfortable", value: 45 },
  { name: "host", value: 40 },
  { name: "checkin", value: 35 }
];

const ReviewWordCloud = ({ data = mockWordCloudData, height = 300 }) => {
  const chartRef = useRef(null);

  useEffect(() => {
    if (!chartRef.current) return;

    const chart = echarts.init(chartRef.current);
    const option = {
      title: {
        text: "Review Word Cloud",
        left: "center",
        textStyle: {
          fontSize: 18,
          fontWeight: "bold"
        }
      },
      tooltip: {
        show: true
      },
      series: [
        {
          type: "wordCloud",
          gridSize: 8,
          sizeRange: [12, 50],
          rotationRange: [-45, 90],
          shape: "circle",
          width: "100%",
          height: "100%",
          drawOutOfBound: false,
          textStyle: {
            color: function () {
              return `rgb(${Math.round(Math.random() * 160)}, ${Math.round(
                Math.random() * 160
              )}, ${Math.round(Math.random() * 160)})`;
            }
          },
          data: data
        }
      ]
    };

    chart.setOption(option);
    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [data]);

  return <div ref={chartRef} style={{ width: "100%", height }} />;
};

export default ReviewWordCloud;
