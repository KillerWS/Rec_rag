// components/NeighbourhoodOverview.tsx
import React, { useState } from "react";
import { Card, Modal, Tag, Space, Button } from "antd";
import EChartsComponent from "../eCharts/EChartsComponent";

interface NeighbourhoodOverviewProps {
  chartData: {
    title: string;
    xAxis: string[];
    series: {
      [key: string]: number[];
    };
    highlight: string[];
  };
  onAreaSelect?: (area: string) => void;
}

const NeighbourhoodOverview: React.FC<NeighbourhoodOverviewProps> = ({ chartData, onAreaSelect }) => {
  const [modalVisible, setModalVisible] = useState(false);
  if (!chartData || !chartData.series) return null;

  const handleSelectArea = (area: string) => {
    console.log("✅ Area selected:", area);
    if (onAreaSelect) {
      onAreaSelect(area);
    }
  };

  return (
    <>
      <Card
        title={chartData.title}
        className="mt-3 rounded-xl shadow-md border border-gray-100"
        size="small"
        hoverable
        onClick={() => setModalVisible(true)}
        style={{ cursor: "pointer" }}
      >
        <EChartsComponent
          type="bar_dual"
          data={{
            xAxis: chartData.xAxis,
            series: chartData.series,
          }}
          highlight={chartData.highlight}
          title={chartData.title}
        />
      </Card>

      <Modal
        title={chartData.title + " (Full View)"}
        open={modalVisible}
        footer={null}
        onCancel={() => setModalVisible(false)}
        width={700}
      >
        <EChartsComponent
          type="bar_dual"
          data={{
            xAxis: chartData.xAxis,
            series: chartData.series,
          }}
          highlight={chartData.highlight}
          title={chartData.title}
          showTitle={false}
        />

        {/* ✅ 高亮区域展示区 */}
        {chartData.highlight?.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold mb-2">🎯 Neighbourhoods Matching Your Budget:</h4>
            <Space wrap>
              {chartData.highlight.map((area) => (
                <Tag key={area} color="red">
                  <Button type="link" size="small" onClick={() => handleSelectArea(area)}>
                    {area}
                  </Button>
                </Tag>
              ))}
              
            </Space>
          </div>
        )}
        {chartData.highlight?.length === 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold mb-2">🎯 No areas match your budget !!!</h4>
            {/* <Space wrap>
              {chartData.highlight.map((area) => (
                <Tag key={area} color="red">
                  <Button type="link" size="small" onClick={() => handleSelectArea(area)}>
                    {area}
                  </Button>
                </Tag>
              ))}
            </Space> */}
          </div>
        )}
      </Modal>
    </>
  );
};

export default NeighbourhoodOverview;
