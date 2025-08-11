import React, { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface EChartsComponentProps {
  type: "pie" | "bar" | "bar_dual";
  data: any; // 可以细化类型
  highlight?: string[];
  title?: string;
  showTitle?: boolean;
}


const EChartsComponent: React.FC<EChartsComponentProps> = ({ type, data = [], highlight = [], title = "", showTitle }) => {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const chartInstanceRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!chartRef.current || !data || (Array.isArray(data) && data.length === 0)) {
      console.warn("⚠️ Invalid chart input:", { type, data });
      return;
    }

    // 初始化或重用实例
    if (!chartInstanceRef.current) {
      chartInstanceRef.current = echarts.init(chartRef.current as HTMLDivElement);
    }

    const chartInstance = chartInstanceRef.current as echarts.ECharts;
    let option: any = {};
    const highlightSet = new Set(highlight);
    console.log("highlightSet", highlightSet)

    if (type === "pie") {
      option = {
        title: { text: title || "Price Distribution", left: "center" },
        tooltip: {
          trigger: "item",
          formatter: (params: any) => {
            const highlight = highlightSet.has(params.name);
            const note = highlight ? "  This is your selected budget range ✅" : "";
            return `${params.name}: ${params.value} (${params.percent.toFixed(1)}%)${note}`;
          },
        },
        series: [
          {
            type: "pie",
            radius: "60%",
            data: (data as any[]).map((d) => ({
              ...d,
              itemStyle: highlightSet.has(d.name)
                ? { borderColor: "#f5222d", borderWidth: 3 }
                : {},
            })),
            label: {
              show: true,
              formatter: ({ name, percent }: any) => {
                const highlight = highlightSet.has(name);
                const note = highlight ? " (Selected Range)" : "";
                return `${name}: ${percent.toFixed(1)}%${note}`;
              },
              fontSize: 12,
            },
          },
        ],
      };
    } else if (type === "bar") { 
      option = {
        title: { text: title || "Price Histogram", left: "center" },
        tooltip: { trigger: "axis" },
        xAxis: {
          type: "category",
          data: (data as any[]).map((d) => d.name),
        },
        yAxis: { type: "value" },
        series: [
          {
            type: "bar",
            data: (data as any[]).map((d) => ({
              value: d.value,
              itemStyle: {
                color: highlightSet.has(d.name) ? "#f5222d" : "#409EFF",
              },
            })),
          },
        ],
      };
    } else if (type === "bar_dual") {
      const { xAxis = [], series = {} } = (data || {}) as any;

      const listingSeries = {
        name: "Listings",
        type: "bar",
        data: (xAxis as any[]).map((label: string, idx: number) => ({
          value: series["Listings"][idx],
          itemStyle: {
            color: highlightSet.has(label) ? "#f5222d" : "#409EFF",
          },
        })),
        yAxisIndex: 0,
      };

      const priceSeries = {
        name: "Avg Price (€)",
        type: "bar",
        data: (xAxis as any[]).map((label: string, idx: number) => ({
          value: series["Avg Price (€)"][idx],
          itemStyle: {
            color: highlightSet.has(label) ? "#f5222d" : "#36cfc9",
          },
        })),
        yAxisIndex: 1,
      };

      option = {
        title: showTitle
        ? { text: title, left: "center" }
        : { show: false },
        tooltip: { trigger: "axis" },
        legend: { data: ["Listings", "Avg Price (€)"] },
        xAxis: { type: "category", data: xAxis as any[] },
        yAxis: [
          { type: "value", name: "Listings" },
          { type: "value", name: "Avg Price (€)" },
        ],
        series: [listingSeries, priceSeries],
      };
    } else {
      console.error("❌ Unknown chart type:", type);
      return;
    }

    chartInstance.setOption(option as any);

    const resizeObserver = new ResizeObserver(() => {
      chartInstance?.resize();
    });
    resizeObserver.observe(chartRef.current as HTMLDivElement);

    return () => {
      resizeObserver.disconnect();
      chartInstance?.dispose();
      chartInstanceRef.current = null;
    };
  }, [type, data, highlight, title]);

  return <div ref={chartRef} style={{ width: "100%", height: "300px" }} />;
};

export default EChartsComponent;
