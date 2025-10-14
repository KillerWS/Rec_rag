import React, { useEffect, useMemo, useState } from 'react';
import { Modal, Input, Button, Tag, Space, Typography } from 'antd';

export type ReviewsScope = {
  area_level?: 'city' | 'neighbourhood_group' | 'neighbourhood';
  area_name?: string | null;
  budget_min?: number | null;
  budget_max?: number | null;
  room_type?: string | null;
  min_reviews?: number | null;
};

interface QAModalProps {
  open: boolean;
  initialQuery?: string;
  scope: ReviewsScope;
  onScopeToggle: (partial: Partial<ReviewsScope>) => void;
  onCancel: () => void;
  onSubmit: (query: string, scope: ReviewsScope) => void;
  result?: {
    answer: string;
    sources: Array<{ snippet: string; listing_id?: number; review_date?: string }>;
  } | null;
  loading?: boolean;
}

const { Text } = Typography;

const QAModal: React.FC<QAModalProps> = ({
  open,
  initialQuery = '',
  scope,
  onScopeToggle,
  onCancel,
  onSubmit,
  result,
  loading
}) => {
  const [query, setQuery] = useState<string>(initialQuery || '');

  useEffect(() => {
    setQuery(initialQuery || '');
  }, [initialQuery, open]);

  const scopeChips = useMemo(() => {
    const chips: Array<{ key: string; label: string; toggle: () => void }> = [];
    if (scope?.area_name) {
      chips.push({ key: 'area', label: String(scope.area_name), toggle: () => onScopeToggle({ area_name: null, area_level: 'city' }) });
    } else {
      chips.push({ key: 'area', label: 'Citywide', toggle: () => {} });
    }
    if (scope?.budget_min != null || scope?.budget_max != null) {
      const min = scope?.budget_min ?? 0;
      const max = scope?.budget_max ?? null;
      const label = `€${min}${max != null ? `–€${max}` : '–∞'}`;
      chips.push({ key: 'budget', label, toggle: () => onScopeToggle({ budget_min: null, budget_max: null }) });
    }
    if (scope?.room_type) {
      chips.push({ key: 'room_type', label: String(scope.room_type), toggle: () => onScopeToggle({ room_type: null }) });
    }
    if (scope?.min_reviews != null) {
      chips.push({ key: 'min_reviews', label: `≥${scope.min_reviews} reviews`, toggle: () => onScopeToggle({ min_reviews: null }) });
    }
    return chips;
  }, [scope, onScopeToggle]);

  return (
    <Modal
      open={open}
      onCancel={onCancel}
      title="💬 Review Q&A"
      footer={null}
      width={720}
      bodyStyle={{ paddingTop: 12 }}
    >
      <div className="space-y-3">
        <div className="text-xs text-gray-500">
          Filters:
          <Space size={4} wrap className="ml-2">
            {scopeChips.map((c) => (
              <Tag key={c.key} bordered onClick={c.toggle} className="cursor-pointer">
                {c.label} {c.key !== 'area' && <span className="ml-1">✕</span>}
              </Tag>
            ))}
          </Space>
        </div>

        <Input.TextArea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoSize={{ minRows: 2, maxRows: 6 }}
          placeholder="Type your question about guest reviews..."
        />

        <div className="flex justify-end gap-2">
          <Button onClick={onCancel}>Cancel</Button>
          <Button type="primary" loading={!!loading} onClick={() => onSubmit(query.trim(), scope)} disabled={!query.trim()}>
            Ask
          </Button>
        </div>

        {result && (
          <div className="mt-3 border-t pt-3 space-y-3">
            <div className="text-sm whitespace-pre-wrap">{result.answer}</div>
            {Array.isArray(result.sources) && result.sources.length > 0 && (
              <div className="space-y-2">
                <Text type="secondary" className="text-xs">Citations</Text>
                {result.sources.map((s, idx) => (
                  <div key={idx} className="text-xs p-2 bg-gray-50 border rounded">
                    <div className="mb-1">{s.snippet}</div>
                    <div className="text-gray-400">{s.review_date || ''}{s.listing_id ? ` • #${s.listing_id}` : ''}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
};

export default QAModal;

