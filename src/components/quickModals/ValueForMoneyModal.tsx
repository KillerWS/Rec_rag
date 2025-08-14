import React, { useEffect, useRef, useState } from 'react';
import { Modal, Spin } from 'antd';
import { fetchPriceStats } from '../../api/api';
import GenericOptionChart from './GenericOptionChart';

interface ValueForMoneyModalProps {
  visible: boolean;
  onClose: () => void;
}

const ValueForMoneyModal: React.FC<ValueForMoneyModalProps> = ({ visible, onClose }) => {
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
        // 复用 chart-data，后端返回包含 echarts_option 的结构
        const res: any = await fetchPriceStats('district', 'ALL');
        console.log('[ValueForMoney] /chart-data response:', res);
        const opt = res?.echarts_option || null;
        if (!opt) {
          throw new Error('No echarts_option returned from API');
        }
        setOption(opt);
        loadedRef.current = true;
      } catch (e: any) {
        setError(e?.message || 'Failed to load value-for-money insights');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [visible]);

  return (
    <Modal
      title="Value-for-money"
      open={visible}
      onCancel={onClose}
      width={1000}
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

export default ValueForMoneyModal; 