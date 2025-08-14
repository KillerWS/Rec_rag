import { useMemo, useState } from 'react';
import { Modal, Radio, Space, Typography, Button, Divider, Tag } from 'antd';

export interface LikertItem {
  id: string;
  question: string;
  leftLabel?: string;
  rightLabel?: string;
}

interface LikertSurveyProps {
  open: boolean;
  title?: string;
  questions: LikertItem[];
  onClose: () => void;
  onSubmit?: (answers: Record<string, number>) => void;
}

const scaleLabels = ['1', '2', '3', '4', '5'];

const LikertSurvey = ({ open, title = 'Quick Survey', questions, onClose, onSubmit }: LikertSurveyProps) => {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const allAnswered = useMemo(() => questions.length > 0 && questions.every(q => answers[q.id] !== undefined), [questions, answers]);

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={<div className="text-lg font-semibold">{title}</div>}
      width={720}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="primary" onClick={() => onSubmit?.(answers)} disabled={!allAnswered}>
            Submit
          </Button>
        </div>
      }
    >
      <div className="space-y-4" style={{ maxHeight: 460, overflowY: 'auto' }}>
        <div className="rounded-lg bg-gray-50 border border-gray-200 p-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
            <span className="font-medium">Scale legend:</span>
            <Tag color="red">1 = Strongly Disagree</Tag>
            <Tag color="orange">2 = Disagree</Tag>
            <Tag color="gold">3 = Neutral</Tag>
            <Tag color="green">4 = Agree</Tag>
            <Tag color="blue">5 = Strongly Agree</Tag>
          </div>
        </div>
        {questions.map((q, idx) => (
          <div key={q.id} className="rounded-xl border border-gray-200 bg-white p-4">
            <div className="flex items-center justify-between mb-2">
              <Typography.Text strong>Q{idx + 1}. {q.question}</Typography.Text>
              <Typography.Text type="secondary" className="text-xs">{answers[q.id] ? `Selected: ${answers[q.id]}` : 'Select one'}</Typography.Text>
            </div>
            <Divider style={{ margin: '8px 0' }} />
            <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
              <span>{q.leftLabel || 'Strongly Disagree'}</span>
              <span>{q.rightLabel || 'Strongly Agree'}</span>
            </div>
            <Radio.Group
              value={answers[q.id]}
              onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
              className="w-full"
            >
              <Space size="large" wrap>
                {scaleLabels.map((label, value) => (
                  <Radio key={label} value={value + 1}>{label}</Radio>
                ))}
              </Space>
            </Radio.Group>
          </div>
        ))}
      </div>
    </Modal>
  );
};

export default LikertSurvey; 