import { useEffect, useMemo, useState } from 'react';
import { Modal, Radio, Space, Typography, Button, Divider, Tag, Input } from 'antd';
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
  openEndedPrompts?: string[];
  openEndedRequired?: boolean;
  openEndedHint?: string;
  forceCompletion?: boolean;
  taskType?: string | null;
  systemLabel?: string | null;
  blockIndex?: number | null;
  onClose: () => void;
  onSubmit?: (answers: Record<string, number>, openEnded?: Record<string, string>) => void;
}

const scaleLabels = ['1', '2', '3', '4', '5'];

const LikertSurvey = ({
  open,
  title = 'Quick Survey',
  questions,
  sections,
  openEndedPrompts,
  openEndedRequired = false,
  openEndedHint,
  forceCompletion = false,
  taskType,
  systemLabel,
  blockIndex,
  onClose,
  onSubmit
}: LikertSurveyProps) => {
  const allItems: LikertItem[] = useMemo(() => {
    if (sections && sections.length > 0) {
      return sections.flatMap(s => s.items);
    }
    return questions || [];
  }, [questions, sections]);

  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [openEndedAnswers, setOpenEndedAnswers] = useState<Record<string, string>>({});
  const openEndedAnswered = useMemo(() => {
    if (!openEndedPrompts || openEndedPrompts.length === 0) return true;
    if (!openEndedRequired) return true;
    return openEndedPrompts.every((_, idx) => Boolean((openEndedAnswers[String(idx)] ?? '').trim()));
  }, [openEndedAnswers, openEndedPrompts, openEndedRequired]);
  const allAnswered = useMemo(
    () => allItems.length > 0 && allItems.every(q => answers[q.id] !== undefined) && openEndedAnswered,
    [allItems, answers, openEndedAnswered]
  );

  useEffect(() => {
    setAnswers({});
    setOpenEndedAnswers({});
  }, [blockIndex, allItems.length, openEndedPrompts?.length]);

  const submitAnswers = async () => {
    const processedAnswers: Record<string, number> = {};
    Object.entries(answers).forEach(([id, value]) => {
      processedAnswers[id] = id.endsWith('R') ? (6 - value) : value;
    });
    const openEnded: Record<string, string> = {};
    if (openEndedPrompts && openEndedPrompts.length > 0) {
      openEndedPrompts.forEach((prompt, idx) => {
        const keyMatch = prompt.match(/\(([^)]+)\)\s*$/);
        const key = keyMatch?.[1] ?? `OPEN_${idx + 1}`;
        const value = (openEndedAnswers[String(idx)] ?? '').trim();
        if (value) {
          openEnded[key] = value;
        }
      });
    }
    const hasOpenEnded = Object.keys(openEnded).length > 0;
    onSubmit?.(processedAnswers, hasOpenEnded ? openEnded : undefined);
    // Close immediately to avoid late async close overriding a new survey open.
    onClose();
    try {
      const storedId = sessionStorage.getItem('study_session_id');
      const session_id = storedId || ensureSessionId();
      await commitLikertFeedback({
        session_id,
        answers: processedAnswers,
        task_type: taskType ?? undefined,
        system_label: systemLabel ?? undefined,
        block_index: blockIndex ?? undefined,
        open_ended: hasOpenEnded ? openEnded : undefined
      });
    } catch (_) {}
  };

  const handleAutoFill = () => {
    const randomLikert = () => Math.floor(Math.random() * 5) + 1;
    const openEndedAnswerBank = [
      'The price and location visualizations helped me weigh trade-offs quickly.',
      'Seeing review snippets alongside the recommendations made the choice feel more grounded.',
      'The system asking follow-up questions clarified what mattered most to me.',
      'I could compare options faster because the key criteria were summarized clearly.',
      'The interaction flow helped me narrow down choices without feeling overwhelmed.'
    ];
    const randomOpenEnded = () => openEndedAnswerBank[Math.floor(Math.random() * openEndedAnswerBank.length)];
    setAnswers(prev => {
      const filled: Record<string, number> = { ...prev };
      allItems.forEach(item => {
        if (filled[item.id] === undefined) {
          filled[item.id] = randomLikert();
        }
      });
      return filled;
    });
    if (openEndedPrompts && openEndedPrompts.length > 0) {
      setOpenEndedAnswers(prev => {
        const filled = { ...prev };
        openEndedPrompts.forEach((_, idx) => {
          const key = String(idx);
          if (!filled[key] || !filled[key].trim()) {
            filled[key] = randomOpenEnded();
          }
        });
        return filled;
      });
    }
  };

  const handleSubmit = () => {
    Modal.confirm({
      title: 'Submit this block?',
      content: 'Submitting will end the current block and move to the next one.',
      okText: 'Submit',
      cancelText: 'Cancel',
      centered: true,
      onOk: submitAnswers
    });
  };

  return (
    <Modal
      open={open}
      onCancel={() => {
        if (!forceCompletion) {
          onClose();
        }
      }}
      title={<div className="text-lg font-semibold">{title}</div>}
      width={720}
      maskClosable={!forceCompletion}
      closable={!forceCompletion}
      keyboard={!forceCompletion}
      footer={
        <div className="flex items-center justify-end gap-2">
          {!forceCompletion && <Button onClick={onClose}>Cancel</Button>}
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
          <div className="mt-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold">The following questions refer to the system you just used in this task.</span>
              <Button size="small" onClick={handleAutoFill}>
                Auto-fill
              </Button>
            </div>
          </div>
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
        {openEndedPrompts && openEndedPrompts.length > 0 && (
          <div className="space-y-4">
            <Divider orientation="left" style={{ margin: '8px 0' }}>
              <span className="text-sm font-semibold">
                Part {(sections?.length ?? 0) + 1}: Open-ended
              </span>
            </Divider>
            <Typography.Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 8 }}>
              {openEndedHint ?? 'Please answer in your own words. You may respond by typing or speaking, and you can leave these blank if you prefer.'}
            </Typography.Paragraph>
            {openEndedPrompts.map((prompt, idx) => (
              <div key={`${prompt}-${idx}`} className="rounded-xl border border-gray-200 bg-white p-4">
                <Typography.Text strong>Q{idx + 1}. {prompt}</Typography.Text>
                <Input.TextArea
                  rows={3}
                  value={openEndedAnswers[String(idx)] ?? ''}
                  onChange={(e) => setOpenEndedAnswers(prev => ({ ...prev, [String(idx)]: e.target.value }))}
                  placeholder="Type your response here..."
                  className="mt-2"
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
};

export default LikertSurvey; 