import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

export interface District {
  name: string;
  listing_count: number;
  avg_price: number;
  popularity_score: number;
}

interface DataInsightsProps {
  districtsData: District[] | null;
  selectedDistrict: string;
  loading: boolean;
}

/**
 * DataInsights: 独立的 Insights 模块组件
 * - 显示列表分布 (BarChart)
 * - 显示价格分布 (PieChart)
 * - 显示选中区 vs 平均值对比
 */
const DataInsights: React.FC<DataInsightsProps> = ({ districtsData, selectedDistrict, loading }) => {
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="bg-white p-3 rounded-lg border border-gray-200">
          <div className="text-sm font-medium text-gray-700 mb-2">📊 Loading Charts...</div>
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        </div>
      </div>
    );
  }

  if (!districtsData || districtsData.length === 0) return null;

  // 准备图表数据
  const chartData = districtsData
    .map(d => ({
      name: d.name.replace(' - ', '-').replace('Charlottenburg-Wilm.', 'Charl-W'),
      listings: d.listing_count,
      price: d.avg_price,
      popularity: d.popularity_score
    }))
    .sort((a, b) => b.listings - a.listings);

  // 价格分布数据（带颜色）
  const priceRanges = [
    { range: '<€60', count: districtsData.filter(d => d.avg_price < 60).length, color: '#10b981' },
    { range: '€60-80', count: districtsData.filter(d => d.avg_price >= 60 && d.avg_price < 80).length, color: '#f59e0b' },
    { range: '€80-100', count: districtsData.filter(d => d.avg_price >= 80 && d.avg_price < 100).length, color: '#ef4444' },
    { range: '>€100', count: districtsData.filter(d => d.avg_price >= 100).length, color: '#8b5cf6' }
  ];

  return (
    <div className="space-y-4">
      {/* 列表分布 */}
      <div className="bg-white p-3 rounded-lg border border-gray-200">
        <div className="text-sm font-medium text-gray-700 mb-2">📊 Listings by Top Districts</div>
        <div style={{ width: '100%', height: '180px' }}>
          <ResponsiveContainer>
            <BarChart data={chartData.slice(0, 6)}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-45} textAnchor="end" height={60} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              {/* 恢复蓝色填充 */}
              <Bar dataKey="listings" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 价格分布 */}
      <div className="bg-white p-3 rounded-lg border border-gray-200">
        <div className="text-sm font-medium text-gray-700 mb-2">💰 Price Distribution</div>
        <div style={{ width: '100%', height: '120px' }}>
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={priceRanges}
                dataKey="count"
                nameKey="range"
                cx="50%"
                cy="50%"
                outerRadius={40}
                label={({ range, count }) => (count > 0 ? `${range}: ${count}` : '')}
                labelLine={false}
              >
                {priceRanges.map((entry, idx) => (
                  <Cell key={idx} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 选中区域 vs 平均对比 */}
      {selectedDistrict !== 'all' && (
        <div className="bg-gradient-to-r from-blue-50 to-purple-50 p-3 rounded-lg border border-blue-200">
          <div className="text-sm font-medium text-blue-800 mb-2">📍 {selectedDistrict} vs Average</div>
          {(() => {
            const districtData = districtsData.find(d => d.name === selectedDistrict);
            const avgPrice = Math.round(
              districtsData.reduce((sum, d) => sum + d.avg_price * d.listing_count, 0) /
                districtsData.reduce((sum, d) => sum + d.listing_count, 0)
            );
            const avgPopularity = Math.round(
              districtsData.reduce((sum, d) => sum + d.popularity_score, 0) / districtsData.length
            );

            if (!districtData) return <div className="text-xs text-gray-500">No data available</div>;

            const priceComparison = districtData.avg_price > avgPrice ? '📈' : '📉';
            const popularityComparison = districtData.popularity_score > avgPopularity ? '📈' : '📉';

            return (
              <div className="grid grid-cols-2 gap-2 text-xs text-blue-700">
                <div className="bg-white p-2 rounded">
                  <div className="font-medium">Price {priceComparison}</div>
                  <div>€{districtData.avg_price} vs €{avgPrice}</div>
                  <div className="text-gray-600">
                    {districtData.avg_price > avgPrice ? '+' : ''}
                    {Math.round(((districtData.avg_price - avgPrice) / avgPrice) * 100)}%
                  </div>
                </div>
                <div className="bg-white p-2 rounded">
                  <div className="font-medium">Popularity {popularityComparison}</div>
                  <div>{districtData.popularity_score}% vs {avgPopularity}%</div>
                  <div className="text-gray-600">
                    {districtData.popularity_score > avgPopularity ? '+' : ''}
                    {districtData.popularity_score - avgPopularity}%
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      )}
    </div>
  );
};

export default DataInsights;
