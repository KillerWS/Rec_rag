import { Card, Row, Col, Statistic, Modal } from "antd";
import { useState } from "react";
import EChartsComponent from "../eCharts/EChartsComponent";

interface ChartSpec { type: string; data: any[]; highlight?: any[] }
interface PriceOverviewProps {
  summary: any;
  pieChart: ChartSpec;
  barChart: ChartSpec;
}

const PriceOverview = ({ summary, pieChart, barChart }: PriceOverviewProps) => {
  const [modalVisible, setModalVisible] = useState<boolean>(false);
  const [modalChart, setModalChart] = useState<any>(null);

  const openModal = (chart: any, title: string) => {
    setModalChart({ ...chart, title });
    setModalVisible(true);
  };

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
            onClick={() => openModal(pieChart, "Price Distribution (Pie Chart)")}
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
            onClick={() => openModal(barChart, "Price Histogram (Bar Chart)")}
            style={{ cursor: "pointer" }}
          >
            <EChartsComponent type="bar" data={barChart.data} highlight={barChart.highlight} />
          </Card>
        </Col>
      </Row>

      {/* Modal for Fullscreen View */}
      <Modal
        title={modalChart?.title}
        open={modalVisible}
        footer={null}
        onCancel={() => setModalVisible(false)}
        width={700}
      >
        {modalChart && (
          <EChartsComponent type={modalChart.type} data={modalChart.data} highlight={modalChart.highlight} />
        )}
      </Modal>
    </Card>
  );
};

export default PriceOverview;
