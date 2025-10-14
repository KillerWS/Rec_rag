// components/NeighbourhoodOverview.tsx
import React, { useState, useEffect } from "react";
import { Card, Modal, Tag, Space, Button } from "antd";
import EChartsComponent from "../eCharts/EChartsComponent";
import { fetchPriceStats } from "../../api/api";

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
  budgetMin?: number | null;
  budgetMax?: number | null;
  // New: scripted mode to show Tier 1 info only after a neighbourhood is chosen
  scriptedMode?: boolean;
  // New: when provided in scripted mode, auto-open and show Tier 1 for this area
  initialArea?: string | null;
}

const NeighbourhoodOverview: React.FC<NeighbourhoodOverviewProps> = ({ chartData, onAreaSelect, budgetMin, budgetMax, scriptedMode = false, initialArea = null }) => {
  const [modalVisible, setModalVisible] = useState(false);
  const [selectedArea, setSelectedArea] = useState<string | null>(null);
  const [summaryText, setSummaryText] = useState<string>("");
  const [barItems, setBarItems] = useState<Array<{ name: string; value: number }>>([]);
  const [highlightBins, setHighlightBins] = useState<string[]>([]);
  const [isLoadingTier1, setIsLoadingTier1] = useState<boolean>(false);

  if (!chartData || !chartData.series) return null;

  const computePopularityText = (listings: number) => {
    const listingsArr = chartData.series["Listings"] || [];
    if (!listingsArr.length) return "";
    const sorted = [...listingsArr].sort((a, b) => a - b);
    const q75 = sorted[Math.floor(0.75 * (sorted.length - 1))] || 0;
    if (listings >= q75) return "This district is relatively popular among visitors.";
    return "";
  };

  const deriveSummaryForArea = (area: string) => {
    const idx = chartData.xAxis.findIndex((x) => x === area);
    if (idx < 0) return "";
    const listings = chartData.series["Listings"]?.[idx] ?? 0;
    const avgPrice = chartData.series["Avg Price (€)"]?.[idx] ?? 0;
    const popularity = computePopularityText(listings);
    const formatted = `${area} has around ${listings.toLocaleString()} listings, with an average nightly price of €${Number(avgPrice).toFixed(0)}.${popularity ? " " + popularity : ""}`;
    return formatted;
  };

  const parseBinLabelToRange = (label: string): { min: number; max: number } | null => {
    // Expect formats like "0-50€" or "0-50" or "€0-€50"
    const match = label.replace(/€/g, "").match(/(\d+)\s*[-–]\s*(\d+)/);
    if (!match) return null;
    return { min: Number(match[1]), max: Number(match[2]) };
  };

  const computeBudgetHighlights = (labels: string[], min?: number | null, max?: number | null) => {
    if (min == null || max == null) return [] as string[];
    const lo = Number(min);
    const hi = Number(max);
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [] as string[];
    return labels.filter((lab) => {
      const range = parseBinLabelToRange(lab);
      if (!range) return false;
      // overlap test
      return !(range.max < lo || range.min > hi);
    });
  };

  const loadTier1Chart = async (area: string) => {
    setIsLoadingTier1(true);
    try {
      const res: any = await fetchPriceStats('neighbourhood', area, (budgetMin ?? undefined) as any, (budgetMax ?? undefined) as any);
      const categories: string[] = res?.data?.categories || [];
      const values: number[] = res?.data?.values || [];
      const items = categories.map((c: string, i: number) => ({ name: c, value: values[i] ?? 0 }));
      setBarItems(items);
      setHighlightBins(computeBudgetHighlights(categories, budgetMin ?? null, budgetMax ?? null));
    } catch (err) {
      setBarItems([]);
      setHighlightBins([]);
      console.error('Failed to load price stats for neighbourhood', err);
    } finally {
      setIsLoadingTier1(false);
    }
  };

  const handleSelectArea = (area: string) => {
    setSelectedArea(area);
    setSummaryText(deriveSummaryForArea(area));
    loadTier1Chart(area);
  };

  const handleConfirm = () => {
    if (selectedArea && onAreaSelect) {
      onAreaSelect(selectedArea);
    }
    setModalVisible(false);
    setSelectedArea(null);
  };

  const handleChooseAnother = () => {
    setSelectedArea(null);
    setSummaryText("");
    setBarItems([]);
    setHighlightBins([]);
  };

  useEffect(() => {
    // reset view when modal closed
    if (!modalVisible) {
      setSelectedArea(null);
      setSummaryText("");
      setBarItems([]);
      setHighlightBins([]);
    }
  }, [modalVisible]);

  useEffect(() => {
    // Scripted mode: auto-open modal and show Tier 1 when initialArea provided
    if (scriptedMode && initialArea) {
      setModalVisible(true);
      setSelectedArea(initialArea);
      setSummaryText(deriveSummaryForArea(initialArea));
      loadTier1Chart(initialArea);
    }
  }, [scriptedMode, initialArea]);

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
        {!selectedArea && !scriptedMode && (
          <>
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
              </div>
            )}
          </>
        )}

        {!selectedArea && scriptedMode && (
          <div className="mt-2 mb-3 text-[13px] text-gray-700 leading-relaxed">
            Select a neighbourhood to view a concise summary and its price distribution.
          </div>
        )}

        {selectedArea && (
          <>
            <div className="mt-2 mb-3 text-[13px] text-gray-700 leading-relaxed">
              {summaryText}
            </div>

            <Card size="small" className="mb-3">
              <EChartsComponent
                type="bar"
                data={barItems}
                highlight={highlightBins}
                title={`Price Distribution — ${selectedArea}`}
                showTitle={true}
              />
            </Card>

            <div className="flex justify-end gap-2 mt-2">
              <Button onClick={handleChooseAnother}>
                🔄 Choose another neighbourhood
              </Button>
              <Button type="primary" onClick={handleConfirm} loading={isLoadingTier1}>
                ✅ Continue with this area
              </Button>
            </div>
          </>
        )}
      </Modal>
    </>
  );
};

export default NeighbourhoodOverview;
