import React, { useMemo, useState } from 'react';
import { Modal, Segmented } from 'antd';
import EChartsComponent from './EChartsComponent';
import GenericOptionChart from '../quickModals/GenericOptionChart';

interface UnifiedChartModalProps {
  visible: boolean;
  onClose: () => void;
  title?: string;
  width?: number | string;
  charts: Array<{
    key: string;
    label: string;
    renderer: 'echarts_component' | 'echarts_option';
    type?: 'pie' | 'bar' | 'bar_dual';
    data?: any;
    highlight?: any[];
    chartTitle?: string;
    echarts_option?: any;
  }>;
  defaultChartKey?: string;
}

const UnifiedChartModal: React.FC<UnifiedChartModalProps> = ({
  visible,
  onClose,
  title,
  width = 720,
  charts,
  defaultChartKey
}) => {
  const initialKey = useMemo(() => {
    if (defaultChartKey && charts.some(c => c.key === defaultChartKey)) return defaultChartKey;
    return charts[0]?.key;
  }, [charts, defaultChartKey]);

  const [activeKey, setActiveKey] = useState<string | undefined>(initialKey);

  const activeChart = useMemo(() => charts.find(c => c.key === activeKey) || charts[0], [charts, activeKey]);

  return (
    <Modal
      open={visible}
      title={title}
      footer={null}
      onCancel={onClose}
      width={width}
    >
      {charts.length > 1 && (
        <div className="mb-3">
          <Segmented
            options={charts.map(c => ({ label: c.label, value: c.key }))}
            value={activeChart?.key}
            onChange={(val) => setActiveKey(val as string)}
          />
        </div>
      )}
      {activeChart && (
        <div>
          {activeChart.renderer === 'echarts_option' && activeChart.echarts_option && (
            <GenericOptionChart option={activeChart.echarts_option} />
          )}
          {activeChart.renderer === 'echarts_component' && activeChart.type && (
            <EChartsComponent
              type={activeChart.type}
              data={activeChart.data}
              highlight={activeChart.highlight}
              title={activeChart.chartTitle}
            />
          )}
        </div>
      )}
    </Modal>
  );
};

export default UnifiedChartModal; 