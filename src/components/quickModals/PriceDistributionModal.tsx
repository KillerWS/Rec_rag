import React, { useEffect, useRef, useState } from 'react';
import { Modal, Spin } from 'antd';
import { fetchPriceStats } from '../../api/api';
import GenericOptionChart from './GenericOptionChart';

interface PriceDistributionModalProps {
  visible: boolean;
  onClose: () => void;
}

const PriceDistributionModal: React.FC<PriceDistributionModalProps> = ({ visible, onClose }) => {
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
        const res: any = await fetchPriceStats('district', 'ALL');
        const opt = res?.echarts_option || null;
        setOption(opt);
        loadedRef.current = true;
      } catch (e: any) {
        setError(e?.message || 'Failed to load price distribution');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [visible]);

  return (
    <Modal
      title="Price distribution"
      open={visible}
      onCancel={onClose}
      width={920}
      footer={null}
      destroyOnClose={false}
    >
      {loading && <Spin />}
      {error && <div className="text-red-500 text-sm">{error}</div>}
      {!loading && !error && option && (
        <GenericOptionChart option={option} />
      )}
    </Modal>
  );
};

export default PriceDistributionModal; 