import { Card, Row, Col, Statistic } from "antd";
import { useState } from "react";
import EChartsComponent from "../eCharts/EChartsComponent";
import UnifiedChartModal from "../eCharts/UnifiedChartModal";

interface ChartSpec { type: string; data: any[]; highlight?: any[] }
interface PriceOverviewProps {
  summary: any;
  pieChart: ChartSpec;
  barChart: ChartSpec;
}

const PriceOverview = ({ summary, pieChart, barChart }: PriceOverviewProps) => {
  const [modalVisible, setModalVisible] = useState<boolean>(false);

  return (
    <Card
      title="Airbnb Price Overview"
      bordered={false}
      style={{ marginTop: 12, maxWidth: 720 }}
      bodyStyle={{ paddingBottom: 12 }}
    >
      {/* Summary */}
      <Row gutter={[16, 8]} justify="space-between">
        <Col span={4}><Statistic title="🏘️ Listings" value={summary.total_listings} /></Col>
        <Col span={4}><Statistic title="💰 Avg Price" value={`€${summary.avg_price}`} /></Col>
        <Col span={4}><Statistic title="🔄 Median" value={`€${summary.median_price}`} /></Col>
        <Col span={4}><Statistic title="⬇️ Min" value={`€${summary.min_price}`} /></Col>
        <Col span={4}><Statistic title="⬆️ Max" value={`€${summary.max_price}`} /></Col>
      </Row>

      {/* Chart Thumbnails */}
      <Row gutter={16} className="mt-4">
        <Col span={12}>
          <Card
            size="small"
            title="Price Distribution (Pie)"
            hoverable
            onClick={() => setModalVisible(true)}
            style={{ cursor: "pointer" }}
          >
            <EChartsComponent type="pie" data={pieChart.data} highlight={pieChart.highlight} />
          </Card>
        </Col>
        <Col span={12}>
          <Card
            size="small"
            title="Price Histogram (Bar)"
            hoverable
            onClick={() => setModalVisible(true)}
            style={{ cursor: "pointer" }}
          >
            <EChartsComponent type="bar" data={barChart.data} highlight={barChart.highlight} />
          </Card>
        </Col>
      </Row>

      {/* Unified Modal for Fullscreen View */}
      <UnifiedChartModal
        visible={modalVisible}
        onClose={() => setModalVisible(false)}
        title="Price Distribution"
        width={700}
        charts={[
          {
            key: 'pie',
            label: 'Pie',
            renderer: 'echarts_component',
            type: 'pie',
            data: pieChart.data,
            highlight: pieChart.highlight,
            chartTitle: 'Price Distribution (Pie Chart)'
          },
          {
            key: 'bar',
            label: 'Bar',
            renderer: 'echarts_component',
            type: 'bar',
            data: barChart.data,
            highlight: barChart.highlight,
            chartTitle: 'Price Histogram (Bar Chart)'
          }
        ]}
        defaultChartKey="pie"
      />
    </Card>
  );
};

export default PriceOverview;
