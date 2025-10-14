import { Card, Row, Col, Statistic, Typography } from "antd";
import { useMemo, useState } from "react";
import EChartsComponent from "../eCharts/EChartsComponent";
import UnifiedChartModal from "../eCharts/UnifiedChartModal";

interface ChartSpec { type: string; data: any[]; highlight?: any[] }
interface PriceOverviewProps {
  summary: any;
  pieChart: ChartSpec;
  barChart: ChartSpec;
  budgetMin?: number;
  budgetMax?: number;
  recommendedAreas?: Array<{ type?: 'budget' | 'popular' | 'balanced'; name: string; note: string }>;
}

const iconForType = (type?: 'budget' | 'popular' | 'balanced') => {
  if (type === 'budget') return '💰';
  if (type === 'popular') return '⭐';
  if (type === 'balanced') return '⚖️';
  return '•';
};

const PriceOverview = ({ summary, pieChart, barChart, budgetMin, budgetMax, recommendedAreas = [] }: PriceOverviewProps) => {
  const [modalVisible, setModalVisible] = useState<boolean>(false);

  const barHighlights = useMemo(() => {
    if (budgetMin == null || budgetMax == null) return (barChart.highlight || []) as any[];
    const labels = (barChart.data || []).map((d: any) => d.name);
    const highlighted: string[] = [];
    labels.forEach((label: string) => {
      const match = label.replace(/€/g, '').match(/(\d+)[^\d]+(\d+)/);
      if (!match) return;
      const binMin = parseInt(match[1], 10);
      const binMax = parseInt(match[2], 10);
      if (binMax >= budgetMin && binMin <= budgetMax) {
        highlighted.push(label);
      }
    });
    return highlighted;
  }, [barChart.data, barChart.highlight, budgetMin, budgetMax]);

  const valueTextStyle = { fontSize: 14, lineHeight: '18px' } as const;

  const totalFromBars = useMemo(() => {
    const vals = (barChart.data || []).map((d: any) => Number(d.value) || 0);
    return vals.reduce((a: number, b: number) => a + b, 0);
  }, [barChart.data]);

  const coveredFromBars = useMemo(() => {
    if (!barHighlights || barHighlights.length === 0) return 0;
    const map: Record<string, number> = {};
    (barChart.data || []).forEach((d: any) => { map[d.name] = Number(d.value) || 0; });
    return barHighlights.reduce((sum: number, label: string) => sum + (map[label] || 0), 0);
  }, [barHighlights, barChart.data]);

  const coveragePct = totalFromBars > 0 ? Math.round((coveredFromBars / totalFromBars) * 100) : null;

  const relation = budgetMin != null && budgetMax != null
    ? (budgetMax! < summary.median_price
        ? 'below'
        : budgetMin! > summary.median_price
          ? 'above'
          : 'around')
    : null;

  const segmentText = relation === 'above'
    ? 'mid‑ to higher‑end tiers'
    : relation === 'below'
      ? 'lower‑ to mid‑range tiers'
      : 'mid‑range tiers';

  return (
    <Card
      title="Airbnb Price Overview"
      bordered={false}
      style={{ marginTop: 12, maxWidth: 720 }}
      bodyStyle={{ paddingBottom: 12 }}
    >
      {/* Summary */}
      <Row gutter={[12, 8]} justify="space-between">
        <Col span={4}>
          <Statistic 
            title="🏘️ Listings" 
            value={summary.total_listings}
            valueStyle={valueTextStyle}
            formatter={(v: any) => (<span>{Number(v).toLocaleString()}</span>)}
          />
        </Col>
        <Col span={4}>
          <Statistic 
            title="💰 Avg Price" 
            value={summary.avg_price}
            precision={2}
            prefix="€"
            valueStyle={valueTextStyle}
          />
        </Col>
        <Col span={4}>
          <Statistic 
            title="🔄 Median" 
            value={summary.median_price}
            precision={0}
            prefix="€"
            valueStyle={valueTextStyle}
          />
        </Col>
        <Col span={4}>
          <Statistic 
            title="⬇️ Min" 
            value={summary.min_price}
            precision={0}
            prefix="€"
            valueStyle={valueTextStyle}
          />
        </Col>
        <Col span={4}>
          <Statistic 
            title="⬆️ Max" 
            value={summary.max_price}
            precision={0}
            prefix="€"
            valueStyle={valueTextStyle}
          />
        </Col>
      </Row>

      {/* Combined Charts: Bar + Pie side by side */}
      <div className="mt-4 border border-gray-100 rounded-md p-2 bg-white">
        <Row gutter={12} align="middle">
          <Col span={16}>
            <Typography.Text strong>Price Histogram</Typography.Text>
            <div className="mt-1">
              <EChartsComponent type="bar" data={barChart.data} highlight={barHighlights} />
            </div>
          </Col>
          <Col span={8}>
            <Typography.Text strong>Price Range Composition</Typography.Text>
            <div className="mt-1">
              <EChartsComponent type="pie" data={pieChart.data} highlight={pieChart.highlight} />
            </div>
          </Col>
        </Row>
        {budgetMin != null && budgetMax != null && (
          <Typography.Paragraph className="!mt-2 !mb-0" style={{ fontSize: 12, color: '#374151' }}>
            Your range (<strong>€{budgetMin}</strong>–<strong>€{budgetMax}</strong>) covers {coveragePct != null ? <strong>~{coveragePct}%</strong> : 'a share'}{coveredFromBars ? <> (~<strong>{coveredFromBars.toLocaleString()}</strong> listings)</> : ''}, mostly in {segmentText}. <a onClick={() => setModalVisible(true)}>View full charts</a>
          </Typography.Paragraph>
        )}
      </div>

      {/* Optional: Top-2 area suggestions inline */}
      {budgetMin != null && budgetMax != null && recommendedAreas.length > 0 && (
        <div className="mt-3">
          <div className="text-sm font-medium">Areas to consider</div>
          <ul className="mt-1 text-sm space-y-1">
            {recommendedAreas.slice(0, 2).map((r, idx) => (
              <li key={`${r.name}-${idx}`} className="flex items-start gap-2">
                <span className="leading-6">{iconForType(r.type)}</span>
                <span><strong>{r.name}</strong> — {r.note}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

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
            chartTitle: 'Price Range Composition (Pie)'
          },
          {
            key: 'bar',
            label: 'Bar',
            renderer: 'echarts_component',
            type: 'bar',
            data: barChart.data,
            highlight: barHighlights,
            chartTitle: 'Price Histogram (Bar)'
          }
        ]}
        defaultChartKey="pie"
      />
    </Card>
  );
};

export default PriceOverview;
