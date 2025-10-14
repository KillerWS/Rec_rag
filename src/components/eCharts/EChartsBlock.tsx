// ✅ EChartsBlock.tsx — 通用 ECharts 渲染组件（支持 WordCloud、Pie、Bar，兼容Collapse + resize）
import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";
import "echarts-wordcloud"; // ✅ 必须引入词云类型

interface EChartsBlockProps {
  type: "wordcloud" | "pie" | "bar";
  data: any;
  height?: number;
  options?: any; // allow full custom option override
  onClick?: (params: any) => void;
}

const EChartsBlock: React.FC<EChartsBlockProps> = ({ type, data, height = 250, options, onClick }) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<echarts.EChartsType | null>(null);

  const processedData = Array.isArray(data)
    ? data.map((item: any) => {
        const maxLength = 30; // 你可以自定义，比如30字符以内
        return {
          ...item,
          displayName:
            typeof item.name === 'string' && item.name.length > maxLength
              ? item.name.slice(0, maxLength) + "..."
              : item.name,
        };
      })
    : [];

  useEffect(() => {
    if (!chartRef.current) {
      return;
    }

    if (!chartInstanceRef.current) {
      chartInstanceRef.current = echarts.init(chartRef.current);
    } else {
      chartInstanceRef.current.resize();
    }

    const chart = chartInstanceRef.current;
    let option: any = {};

    if (options) {
      option = options; // full override
    } else {
      if (!data || (Array.isArray(data) && data.length === 0)) {
        console.warn("⚠️ Invalid chart input:", { type, data });
        return;
      }

      if (type === "wordcloud") {
        option = {
          title: {
            text: "Review Word Cloud",
            left: "center",
            textStyle: {
              fontSize: 18,
              fontWeight: "bold",
            },
          },
          tooltip: {
            trigger: "item",
            formatter: (params: any) => {
              return `${params.data.fullText}<br/>Appears: ${params.data.value} times`;
            },
          },
          series: [
            {
              type: "wordCloud",
              shape: "circle", // 🔥 控制形状：circle更美观
              gridSize: 8, // 🔥 控制密度
              sizeRange: [8, 30], // 🔥 字体大小范围
              rotationRange: [-90, 90], // 🔥 允许旋转（不是0）
              rotationStep: 45, // 🔥 旋转步长（可选）
              drawOutOfBound: false,
              textStyle: {
                fontFamily: "sans-serif",
                fontWeight: "bold",
                color: () => {
                  return `rgb(${Math.round(Math.random() * 160)}, ${Math.round(
                    Math.random() * 160
                  )}, ${Math.round(Math.random() * 160)})`;
                },
              },
              data: processedData.map((d: any) => ({
                name: d.displayName,
                value: d.value,
                fullText: d.name,
              })),
            },
          ],
        };
      } else if (type === "pie") {
        option = {
          tooltip: { trigger: "item" },
          legend: { bottom: 0 },
          series: [
            {
              type: "pie",
              radius: "70%",
              data,
              label: {
                formatter: "{b}: {d}%",
              },
            },
          ],
        };
      } else if (type === "bar") {
        option = {
          tooltip: {},
          xAxis: {
            type: "category",
            data: (data as any[]).map((item: any) => item.name),
          },
          yAxis: {
            type: "value",
          },
          series: [
            {
              type: "bar",
              data: (data as any[]).map((item: any) => item.value),
              itemStyle: {
                color: (params: any) => {
                  const label = (data as any[])[params.dataIndex].name;
                  return label === "noisy" ? "#f87171" : "#60a5fa";
                },
              },
            },
          ],
        };
      }
    }

    chart.clear(); // ✅ 避免旧 option 叠加
    chart.setOption(option);

    // bind click if provided
    if (onClick) {
      chart.off('click');
      chart.on('click', (params: any) => {
        try { onClick(params); } catch {}
      });
    }

    const resizeObserver = new ResizeObserver(() => {
      chart.resize();
    });
    resizeObserver.observe(chartRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.dispose();
      chartInstanceRef.current = null;
    };
  }, [type, data, options, onClick]);

  return <div ref={chartRef} style={{ width: "100%", height }} />;
};

export default EChartsBlock;
