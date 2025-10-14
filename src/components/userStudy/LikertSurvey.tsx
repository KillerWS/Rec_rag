import { useMemo, useState } from 'react';
import { Modal, Radio, Space, Typography, Button, Divider, Tag } from 'antd';
import { commitLikertFeedback } from '../../api/api';
import { ensureSessionId } from '../../api/session';

export interface LikertItem {
  id: string;
  question: string;
  leftLabel?: string;
  rightLabel?: string;
}

export interface LikertSection {
  title: string;
  description?: string;
  items: LikertItem[];
}

interface LikertSurveyProps {
  open: boolean;
  title?: string;
  // Either provide a flat list of questions or structured sections
  questions?: LikertItem[];
  sections?: LikertSection[];
  onClose: () => void;
  onSubmit?: (answers: Record<string, number>) => void;
}

const scaleLabels = ['1', '2', '3', '4', '5'];

const LikertSurvey = ({ open, title = 'Quick Survey', questions, sections, onClose, onSubmit }: LikertSurveyProps) => {
  const allItems: LikertItem[] = useMemo(() => {
    if (sections && sections.length > 0) {
      return sections.flatMap(s => s.items);
    }
    return questions || [];
  }, [questions, sections]);

  const [answers, setAnswers] = useState<Record<string, number>>({});
  const allAnswered = useMemo(() => allItems.length > 0 && allItems.every(q => answers[q.id] !== undefined), [allItems, answers]);

  const handleSubmit = async () => {
    const processedAnswers: Record<string, number> = {};
    Object.entries(answers).forEach(([id, value]) => {
      processedAnswers[id] = id.endsWith('R') ? (6 - value) : value;
    });
    onSubmit?.(processedAnswers);
    try {
      const session_id = ensureSessionId();
      await commitLikertFeedback({ session_id, answers: processedAnswers });
    } catch (_) {}
    onClose();
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      title={<div className="text-lg font-semibold">{title}</div>}
      width={720}
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="primary" onClick={handleSubmit} disabled={!allAnswered}>
            Submit
          </Button>
        </div>
      }
    >
      <div className="space-y-4" style={{ maxHeight: 460, overflowY: 'auto' }}>
        <div className="rounded-lg bg-gray-50 border border-gray-200 p-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
            <span className="font-medium">Anchors:</span>
            <Tag color="red">1 = Strongly Disagree</Tag>
            <Tag color="orange">2 = Disagree</Tag>
            <Tag color="gold">3 = Neutral</Tag>
            <Tag color="green">4 = Agree</Tag>
            <Tag color="blue">5 = Strongly Agree</Tag>
          </div>
          <div className="mt-1 text-[11px] text-gray-500">Items marked “(R)” are reverse-coded.</div>
        </div>

        {/* Sections rendering */}
        {sections && sections.length > 0 ? (
          <div className="space-y-4">
            {sections.map((section, sIdx) => (
              <div key={section.title}>
                <Divider orientation="left" style={{ margin: '8px 0' }}>
                  <span className="text-sm font-semibold">Part {sIdx + 1}: {section.title}</span>
                </Divider>
                {section.description && (
                  <Typography.Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 8 }}>
                    {section.description}
                  </Typography.Paragraph>
                )}
                {section.items.map((q, idx) => (
                  <div key={q.id} className="rounded-xl border border-gray-200 bg-white p-4 mb-3">
                    <div className="flex items-center justify-between mb-2">
                      <Typography.Text strong>Q{idx + 1}. {q.question}</Typography.Text>
                      <Typography.Text type="secondary" className="text-xs">{answers[q.id] ? `Selected: ${answers[q.id]}` : 'Select one'}</Typography.Text>
                    </div>
                    <Divider style={{ margin: '8px 0' }} />
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
            ))}
          </div>
        ) : (
          // Flat questions rendering (backward-compatible)
          <>
            {allItems.map((q, idx) => (
              <div key={q.id} className="rounded-xl border border-gray-200 bg-white p-4">
                <div className="flex items-center justify-between mb-2">
                  <Typography.Text strong>Q{idx + 1}. {q.question}</Typography.Text>
                  <Typography.Text type="secondary" className="text-xs">{answers[q.id] ? `Selected: ${answers[q.id]}` : 'Select one'}</Typography.Text>
                </div>
                <Divider style={{ margin: '8px 0' }} />
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
          </>
        )}
      </div>
    </Modal>
  );
};

export default LikertSurvey; 