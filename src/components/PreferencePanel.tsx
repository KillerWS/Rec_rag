// PreferencePanel.tsx — 可复用的偏好展示与确认卡片
import { Card, Table, Button } from "antd";
import { CheckOutlined } from "@ant-design/icons";

interface PreferencePanelProps {
  selectedDimensions: Array<{ key: string; value: string }>;
  onConfirm: () => void;
}

const PreferencePanel = ({ selectedDimensions, onConfirm }: PreferencePanelProps) => {
  return (
    <div className="mt-4">
      <Card title="🎯 Current Preferences" className="w-full max-w-md mx-auto">
        <Table
          dataSource={selectedDimensions}
          columns={[
            { title: "Dimension", dataIndex: "key" },
            { title: "Value", dataIndex: "value" }
          ]}
          pagination={false}
          rowKey="key"
          size="small"
        />
        <div className="flex justify-center mt-3">
          <Button type="primary" onClick={onConfirm} icon={<CheckOutlined />}>Confirm & Search</Button>
        </div>
      </Card>
    </div>
  );
};

export default PreferencePanel;
