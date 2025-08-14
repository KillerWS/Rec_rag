import React from 'react';
import { Modal } from 'antd';

interface CompareDistrictsModalProps {
  visible: boolean;
  onClose: () => void;
}

const CompareDistrictsModal: React.FC<CompareDistrictsModalProps> = ({ visible, onClose }) => {
  return (
    <Modal
      title="Compare districts"
      open={visible}
      onCancel={onClose}
      width={960}
      footer={null}
      destroyOnClose
    >
      <div className="text-sm text-gray-600">
        Coming soon: pick two districts to compare price, listings, reviews, and room-type mix.
      </div>
    </Modal>
  );
};

export default CompareDistrictsModal; 