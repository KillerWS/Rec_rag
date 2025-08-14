import React, { useEffect, useRef, useState, useMemo } from 'react';
import { Modal, Spin } from 'antd';
import { fetchRoomTypeStats } from '../../api/api';
import GenericOptionChart from './GenericOptionChart';
import UnifiedChartModal from '../eCharts/UnifiedChartModal';

interface RoomTypeMixModalProps {
  visible: boolean;
  onClose: () => void;
}

const RoomTypeMixModal: React.FC<RoomTypeMixModalProps> = ({ visible, onClose }) => {
  const loadedRef = useRef(false);
  const [loading, setLoading] = useState(false);
  const [option, setOption] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      if (!visible || loadedRef.current) return;
      setLoading(true);
      setError(null);
      try {
        const res: any = await fetchRoomTypeStats('district', 'ALL');
        const opt = res?.echarts_option || null;
        setOption(opt);
        loadedRef.current = true;
      } catch (e: any) {
        setError(e?.message || 'Failed to load room-type mix');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [visible]);

  // Try to derive a simple { name, value } array from echarts_option for pie/bar toggling
  const derivedSeriesData = useMemo(() => {
    if (!option) return null;

    // Case 1: series[0].data is already [{ name, value }, ...]
    const series = option.series || [];
    if (Array.isArray(series) && series.length > 0) {
      const first = series[0];
      if (Array.isArray(first.data) && first.data.length > 0) {
        const sample = first.data[0];
        if (sample && typeof sample === 'object' && 'name' in sample && 'value' in sample) {
          return first.data.map((d: any) => ({ name: d.name, value: d.value }));
        }
      }
    }

    // Case 2: category xAxis + numeric series -> zip to {name, value}
    const xData = option?.xAxis?.data || option?.xAxis || [];
    const s0 = option?.series?.[0]?.data;
    if (Array.isArray(xData) && Array.isArray(s0) && xData.length === s0.length) {
      return xData.map((name: any, idx: number) => ({ name, value: s0[idx] }));
    }

    return null;
  }, [option]);

  if (loading) {
    return (
      <Modal
        title="Room-type mix"
        open={visible}
        onCancel={onClose}
        width={1000}
        footer={null}
        destroyOnClose={false}
      >
        <Spin />
      </Modal>
    );
  }

  if (error) {
    return (
      <Modal
        title="Room-type mix"
        open={visible}
        onCancel={onClose}
        width={1000}
        footer={null}
        destroyOnClose={false}
      >
        <div className="text-red-500 text-sm">{error}</div>
      </Modal>
    );
  }

  if (option && derivedSeriesData) {
    return (
      <UnifiedChartModal
        visible={visible}
        onClose={onClose}
        title="Room-type mix"
        width={1000}
        charts={[
          {
            key: 'pie',
            label: 'Pie',
            renderer: 'echarts_component',
            type: 'pie',
            data: derivedSeriesData,
            chartTitle: option?.title?.text || 'Room-type distribution (Pie)'
          },
          {
            key: 'bar',
            label: 'Bar',
            renderer: 'echarts_component',
            type: 'bar',
            data: derivedSeriesData,
            chartTitle: option?.title?.text || 'Room-type distribution (Bar)'
          }
        ]}
        defaultChartKey="pie"
      />
    );
  }

  // Fallback: show original option if derivation failed
  return (
    <Modal
      title="Room-type mix"
      open={visible}
      onCancel={onClose}
      width={1000}
      footer={null}
      destroyOnClose={false}
    >
      {option && <GenericOptionChart option={option} />}
    </Modal>
  );
};

export default RoomTypeMixModal; 