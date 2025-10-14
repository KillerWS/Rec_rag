import React, { useEffect, useMemo, useState, useRef } from 'react';
import EChartsBlock from './EChartsBlock';
import ReviewsPromptModal from '../messageBox/ReviewsPromptModal';
import QAModal, { ReviewsScope } from '../messageBox/QAModal';
import { fetchRAGAnswer } from '../../api/api';
import { getConversationMode } from '../../api/session';

interface ReviewAnalysisProps {
  chartData: {
    type?: string;
    title?: string;
    data?: {
      wordCloud?: Array<{ name: string; value: number }>;
      sentiment?: Array<{ name: string; value: number }>;
      topKeywords?: Array<{ name: string; value: number }>;
    } | any;
    echarts_option?: any;
    options?: any;
  };
  height?: number;
  width?: string;
  modalVisible?: boolean;
  showControls?: boolean;
  onShowMap?: (district: string) => void;
  selectedDimensions?: any[];
}

const ReviewAnalysis: React.FC<ReviewAnalysisProps> = ({
  chartData,
  height = 300,
  width = '100%',
  modalVisible,
  onShowMap,
  selectedDimensions
}) => {
  // 强制在 Modal 打开后触发一次全局 resize，以避免 ECharts 初次渲染尺寸异常
  useEffect(() => {
    if (modalVisible) {
      const t = setTimeout(() => {
        try { window.dispatchEvent(new Event('resize')); } catch {}
      }, 200);
      return () => clearTimeout(t);
    }
  }, [modalVisible]);

  const data = chartData?.data || {};
  const wordCloud = Array.isArray(data.wordCloud) ? data.wordCloud : [];
  const topKeywords = Array.isArray(data.topKeywords) ? data.topKeywords : [];

  // Agent-only: wire Q&A
  const [qaOpen, setQaOpen] = useState<boolean>(false);
  const [qaLoading, setQaLoading] = useState<boolean>(false);
  const [qaPrefill, setQaPrefill] = useState<string>('');
  const [qaScope, setQaScope] = useState<ReviewsScope>({ area_level: 'city', area_name: null, budget_min: null, budget_max: null, room_type: null, min_reviews: null });
  const [qaResult, setQaResult] = useState<null | { answer: string; sources: Array<{ snippet: string; listing_id?: number; review_date?: string }> }>(null);

  // 🔧 简化：derivedScope 只用于初始化 qaScope，不再用于直接传递
  const derivedScope = useMemo<ReviewsScope>(() => {
    const scopeLike = (chartData?.options?.scope || chartData?.data?.scope || {}) as any;
    const result = {
      area_level: scopeLike.area_level || 'city',
      area_name: scopeLike.area || scopeLike.area_name || null,
      budget_min: scopeLike.budget_min ?? null,
      budget_max: scopeLike.budget_max ?? null,
      room_type: scopeLike.room_type ?? null,
      min_reviews: scopeLike.min_reviews ?? null
    };
    console.log('🔵 [ReviewAnalysis] derivedScope 计算', {
      chartData_options_scope: chartData?.options?.scope,
      chartData_data_scope: chartData?.data?.scope,
      scopeLike,
      result
    });
    return result;
  }, [chartData]);

  // 移除未使用的 strictAreaNameForFilters（现在直接使用 qaScope.area_name）
  // const strictAreaNameForFilters = useMemo(() => {
  //   const raw = (chartData?.options?.scope || chartData?.data?.scope || {}) as any;
  //   return raw?.area || raw?.area_name || null;
  // }, [chartData]);

  // 🔧 使用 ref 追踪是否已初始化和手动设置的 area
  const initializedRef = useRef<boolean>(false);
  const manualAreaRef = useRef<string | null>(null);

  // 🔧 只在首次挂载时从 derivedScope 初始化
  useEffect(() => {
    if (!initializedRef.current) {
      console.log('🔵 [ReviewAnalysis] 初始化 qaScope from derivedScope', derivedScope);
      setQaScope((prev) => ({ ...prev, ...derivedScope }));
      initializedRef.current = true;
    }
  }, [derivedScope]);

  // 🔧 从 qaScope 而不是 derivedScope 生成维度显示
  const derivedSelectedDimensions = useMemo(() => {
    if (Array.isArray(selectedDimensions) && selectedDimensions.length > 0) {
      return selectedDimensions;
    }
    const dims: Array<{ key: string; value: any }> = [];
    try {
      if (qaScope?.area_name) {
        dims.push({ key: 'Location', value: qaScope.area_name });
      }
      if (qaScope?.budget_min != null || qaScope?.budget_max != null) {
        const min: any = qaScope?.budget_min ?? '';
        const max: any = qaScope?.budget_max ?? '';
        const label = (min !== '' && max !== '')
          ? `€${min} - €${max}`
          : (min !== '' ? `€${min}+` : (max !== '' ? `≤ €${max}` : ''));
        dims.push({ key: 'Budget Range', value: label || `${min}-${max}` });
      }
      if (qaScope?.room_type) {
        dims.push({ key: 'Room Type', value: qaScope.room_type });
      }
    } catch {}
    return dims;
   }, [qaScope, selectedDimensions]);

  useEffect(() => {
    try {
      console.log('🔎 ReviewAnalysis: qaScope & selectedDimensions for ReviewsPromptModal', { qaScope, derivedSelectedDimensions });
    } catch {}
  }, [qaScope, derivedSelectedDimensions]);

  const mode = getConversationMode?.() || 'none';

  // 🆕 监听地图本地选择事件（仅作用于 ReviewAnalysis，不影响全局）
  useEffect(() => {
    const handler = (e: any) => {
      try {
        console.log('🔵 [ReviewAnalysis] 收到 reviews_analysis:area_selected 事件', e);
        const name = e?.detail?.area;
        console.log('🔵 [ReviewAnalysis] 提取的地区名称:', name);
        if (!name) {
          console.warn('🔵 [ReviewAnalysis] 地区名称为空，忽略');
          return;
        }
        console.log('🔵 [ReviewAnalysis] 更新 qaScope.area_name =', name);
        // 🔧 记录手动设置的 area，避免被 derivedScope 覆盖
        manualAreaRef.current = name;
        setQaScope((prev) => {
          const updated = { ...prev, area_name: name };
          console.log('🔵 [ReviewAnalysis] qaScope 已更新', { prev, updated, manualAreaRef: manualAreaRef.current });
          return updated;
        });
      } catch (err) {
        console.error('🔵 [ReviewAnalysis] 处理事件时出错', err);
      }
    };
    console.log('🔵 [ReviewAnalysis] 注册 reviews_analysis:area_selected 监听器');
    try { window.addEventListener('reviews_analysis:area_selected', handler as any); } catch {}
    return () => {
      console.log('🔵 [ReviewAnalysis] 移除 reviews_analysis:area_selected 监听器');
      try { window.removeEventListener('reviews_analysis:area_selected', handler as any); } catch {}
    };
  }, []);

  const openQnA = (prefill: string, scope: ReviewsScope) => {
    setQaPrefill(prefill || '');
    setQaScope(scope || derivedScope);
    setQaResult(null);
    setQaOpen(true);
  };

  const templateFromSegment = (segment: 'pos'|'neu'|'neg', scope: ReviewsScope) => {
    const area = scope?.area_name;
    const budget = (scope?.budget_min != null || scope?.budget_max != null)
      ? ` (within €${scope?.budget_min ?? 0}–€${scope?.budget_max ?? '∞'})`
      : '';
    const room = scope?.room_type ? `, ${scope.room_type.toLowerCase()}` : '';
    if (segment === 'neg' && area) return `Top complaints in ${area}? Summarize with 3 citations.`;
    if (segment === 'pos') {
      const areaLabel = area ? area : 'citywide';
      return `What do guests like most ${areaLabel}${budget}${room}? Show 3 citations.`;
    }
    return `What are the neutral themes ${area ? `in ${area}` : 'citywide'}? Show 3 citations.`;
  };

  const templateFromPhrase = (phrase: { text: string }, scope: ReviewsScope) => {
    const p = phrase?.text || '';
    const area = scope?.area_name;
    if (area) return `Why do guests in ${area} mention “${p}”? Show some sources.`;
    return `Why do guests mention “${p}” in Berlin? Show some sources.`;
  };

  const handleQASubmit = async (query: string, scope: ReviewsScope, trigger: any = { source: 'panel_button' }) => {
    setQaLoading(true);
    try {
      const res: any = await fetchRAGAnswer(query, [], { sub_mode: 'review_qa', reviews_scope: scope, trigger });
      const sources = Array.isArray(res?.source_documents) ? res.source_documents.map((d: any) => ({ snippet: d.snippet || d.text || '', listing_id: d.listing_id, review_date: d.review_date })) : [];
      setQaResult({ answer: res?.answer || '', sources });
    } catch (e) {
      setQaResult({ answer: 'Failed to retrieve an answer. Please try again.', sources: [] });
    } finally {
      setQaLoading(false);
    }
  };

  // 缩略图模式（高度很小）时，仅渲染词云预览提升可读性
  if (height <= 100) {
    const previewOption = (chartData as any)?.echarts_option;
    if (previewOption) {
      return (
        <EChartsBlock type="bar" data={[]} options={previewOption} height={height} />
      );
    }
    const previewData = wordCloud.length ? wordCloud : (topKeywords.length ? topKeywords : null);
    return (
      <div style={{ width, height }}>
        {previewData ? (
          <EChartsBlock type="wordcloud" data={previewData} height={height} />
        ) : null}
      </div>
    );
  }

  // Agent mode: render inline Reviews container + Q&A modal
  if (mode === 'agent') {
    return (
      <>
        <ReviewsPromptModal
          open={true}
          onClose={() => {}}
          areaName={qaScope.area_name ?? undefined}
          budgetMin={qaScope.budget_min ?? undefined as any}
          budgetMax={qaScope.budget_max ?? undefined as any}
          selectedDimensions={derivedSelectedDimensions}
          inline
          disableAutoSync={true}
          onRequestMapSelect={(scopeLike: any) => {
            // 打开地图（reviews_analysis 特殊上下文），仅本地更新，不发消息不改维度
            try {
              const area = (scopeLike?.area_name as any) || 'ALL';
              // onShowMap 支持 string 或对象，在 VisualizationCard 内包装为对象上下文
              (onShowMap as any)?.({ context: 'reviews_analysis', suppressChatOnMapSelect: true, suppressDimensionUpdate: true, area });
            } catch {}
          }}
          onScopeToggle={(partial) => setQaScope((prev) => ({ ...prev, ...partial }))}
          
          frameless
          onOpenQnA={(_, scopeLike?: any) => {
            const s = (scopeLike || qaScope) as ReviewsScope;
            openQnA('', s);
          }}
          onSliceClick={(seg: 'pos'|'neu'|'neg', scopeLike?: any) => {
            const s = (scopeLike || qaScope) as ReviewsScope;
            openQnA(templateFromSegment(seg, s), s);
          }}
          onPhraseClick={(phrase: any, scopeLike?: any) => {
            const s = (scopeLike || qaScope) as ReviewsScope;
            openQnA(templateFromPhrase(phrase, s), s);
          }}
        />

        <QAModal
          open={qaOpen}
          initialQuery={qaPrefill}
          scope={qaScope}
          onScopeToggle={(partial) => setQaScope((prev) => ({ ...prev, ...partial }))}
          onCancel={() => setQaOpen(false)}
          onSubmit={(q, s) => handleQASubmit(q, s)}
          result={qaResult}
          loading={qaLoading}
        />
      </>
    );
  }

  return (
    <div style={{ width }}>
      <ReviewsPromptModal
        open={true}
        onClose={() => {}}
        areaName={qaScope.area_name ?? undefined}
        budgetMin={qaScope.budget_min ?? undefined as any}
        budgetMax={qaScope.budget_max ?? undefined as any}
        selectedDimensions={derivedSelectedDimensions}
        inline
        disableAutoSync={true}
      />
    </div>
  );
};

export default ReviewAnalysis;


