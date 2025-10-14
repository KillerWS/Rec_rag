// ✅ ReviewsPromptModal.tsx — 每个卡片支持伸缩（Collapse 默认收起）
import { Modal, Typography, Collapse, Tag, message, Tooltip, Select } from "antd";
import { MessageOutlined } from "@ant-design/icons";
import EChartsBlock from "../eCharts/EChartsBlock";
import { useEffect, useMemo, useState } from "react";
import { fetchReviewsSentiment, ReviewsSentimentResponse, fetchReviewsTopKeywords, ReviewsTopKeywordsResponse } from "../../api/api";
import { EnvironmentOutlined, ReloadOutlined } from "@ant-design/icons";

const { Paragraph, Title } = Typography;
const { Panel } = Collapse;

const sentimentCache = new Map<string, ReviewsSentimentResponse | any>();
const topKeywordsCache = new Map<string, ReviewsTopKeywordsResponse>();
const topKeywordsInFlight = new Map<string, Promise<ReviewsTopKeywordsResponse>>();

interface ReviewsPromptModalProps {
  open: boolean;
  onClose: () => void;
  areaName?: string | null;
  budgetMin?: number | null;
  budgetMax?: number | null;
  matchedPreferences?: string[]; // optional preference keys like ['wifi','quiet']
  // Agent-mode callbacks (optional, no-op in scripted)
  onOpenQnA?: (prefill?: string, scope?: any) => void;
  onSliceClick?: (segment: 'pos'|'neu'|'neg', scope?: any) => void;
  onPhraseClick?: (phrase: { text: string; count: number }, scope?: any) => void;
  inline?: boolean; // if true, render as inline panel instead of Modal
  frameless?: boolean; // if true with inline, render content only without container/title/footer
  onScopeToggle?: (partial: any) => void; // optional: toggle scope chips
  onRequestMapSelect?: (scope: any) => void; // optional: open map to select area
  // Optional: provide decision card selected dimensions to quickly scope
  selectedDimensions?: any;
  // 🆕 禁用自动同步（用于 Reviews Analysis 场景，避免被全局状态覆盖）
  disableAutoSync?: boolean;
}

const ReviewsPromptModal = ({ open, onClose, areaName = null, budgetMin = null, budgetMax = null, matchedPreferences, onOpenQnA, onSliceClick, onPhraseClick, inline = false, frameless = false, onScopeToggle, onRequestMapSelect, selectedDimensions, disableAutoSync = false }: ReviewsPromptModalProps) => {
  const [sentiment, setSentiment] = useState<ReviewsSentimentResponse | null>(null);
  const [keywords, setKeywords] = useState<ReviewsTopKeywordsResponse | null>(null);
  const [loadingSentiment, setLoadingSentiment] = useState<boolean>(false);
  const [loadingKeywords, setLoadingKeywords] = useState<boolean>(false);
  // Local scope to support chips toggling (agent mode)
  const [localAreaName, setLocalAreaName] = useState<string | null>(areaName ?? null);
  const [localBudgetMin, setLocalBudgetMin] = useState<number | null>(budgetMin ?? null);
  const [localBudgetMax, setLocalBudgetMax] = useState<number | null>(budgetMax ?? null);
  const [localRoomTypes, setLocalRoomTypes] = useState<string[]>([]);
  const [localMinReviews, setLocalMinReviews] = useState<number | null>(null);
  const [refreshTick, setRefreshTick] = useState<number>(0);

  useEffect(() => {
    console.log('🟢 [ReviewsPromptModal] Props 变化检测', { open, areaName, budgetMin, budgetMax });
    // 🔧 修复：即使在 inline 模式（open 始终为 true），也要响应 prop 变化
    setLocalAreaName(areaName ?? null);
    setLocalBudgetMin(budgetMin ?? null);
    setLocalBudgetMax(budgetMax ?? null);
  }, [open, areaName, budgetMin, budgetMax]);

  // Listen for map/district selection updates via sessionStorage or external events
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      try {
        if (!e || (e.key !== 'area_name' && e.key !== 'selected_area' && e.key !== 'district' && e.key !== 'neighbourhood')) return;
        const val = e.newValue || e.oldValue || '';
        const area = val || sessionStorage.getItem('area_name') || sessionStorage.getItem('selected_area') || sessionStorage.getItem('district') || sessionStorage.getItem('neighbourhood');
        if (area) setLocalAreaName(area);
      } catch {}
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  // Listen to custom events for area selection and dimension transfers (same-tab updates)
  useEffect(() => {
    const onAreaEvent = (evt: Event) => {
      try {
        const anyEvt: any = evt as any;
        const d = anyEvt?.detail;
        const cand = d?.area || d?.area_name || d?.district || d?.neighbourhood || d;
        console.log('🟢 [ReviewsPromptModal] 收到区域事件', { type: evt.type, detail: d, candidate: cand });
        if (cand) {
          const newArea = String(cand);
          console.log('🟢 [ReviewsPromptModal] 更新 localAreaName =', newArea);
          setLocalAreaName(newArea);
        }
      } catch (err) {
        console.error('🟢 [ReviewsPromptModal] 处理区域事件时出错', err);
      }
    };
    const onDimsEvent = (evt: Event) => {
      try {
        const anyEvt: any = evt as any;
        const dims: Array<{ key: string; value: string }> = anyEvt?.detail?.dimensions || [];
        const loc = Array.isArray(dims) ? dims.find((x) => String(x?.key || '').toLowerCase() === 'location') : null;
        console.log('🟢 [ReviewsPromptModal] 收到维度事件', { dims, location: loc });
        if (loc?.value) setLocalAreaName(String(loc.value));
      } catch (err) {
        console.error('🟢 [ReviewsPromptModal] 处理维度事件时出错', err);
      }
    };
    // 🆕 添加 reviews_analysis 专用事件
    const names = ['map:areaSelected', 'map:selectedArea', 'district:selected', 'neighbourhood:selected', 'area:selected', 'reviews_analysis:area_selected'];
    console.log('🟢 [ReviewsPromptModal] 注册事件监听器', names);
    names.forEach((n) => window.addEventListener(n, onAreaEvent as EventListener));
    window.addEventListener('decisioncard:setDimensions', onDimsEvent as EventListener);
    return () => {
      console.log('🟢 [ReviewsPromptModal] 移除事件监听器');
      names.forEach((n) => window.removeEventListener(n, onAreaEvent as EventListener));
      window.removeEventListener('decisioncard:setDimensions', onDimsEvent as EventListener);
    };
  }, []);

  // Fallback: periodic sync while open to pick up same-tab changes (map, globals)
  // 🔧 可通过 disableAutoSync 禁用（Reviews Analysis 场景）
  useEffect(() => {
    if (!open || disableAutoSync) return;
    console.log('🟢 [ReviewsPromptModal] 自动同步已启用（每 700ms 检查全局状态）');
    let stopped = false;
    const readArea = () => {
      try {
        const w: any = (window as any) || {};
        const sd = w.decisionScope;
        const dims: Array<{ key: string; value: any }> | undefined = w.selectedDimensions;
        const fromDims = Array.isArray(dims) ? dims.find((d) => String(d?.key || '').toLowerCase() === 'location')?.value : undefined;
        const areaFromStorage = sessionStorage.getItem('area_name') || sessionStorage.getItem('selected_area') || sessionStorage.getItem('district') || sessionStorage.getItem('neighbourhood');
        const candidate = fromDims || sd?.area_name || sd?.area || areaFromStorage || null;
        console.log('🟢 [ReviewsPromptModal] 轮询检查全局状态', { fromDims, areaFromStorage, candidate, currentLocalAreaName: localAreaName });
        if (candidate && candidate !== localAreaName) {
          console.log('🟢 [ReviewsPromptModal] 从全局状态更新 localAreaName =', candidate);
          setLocalAreaName(String(candidate));
        }
      } catch {}
    };
    const id = window.setInterval(() => { if (!stopped) readArea(); }, 700);
    // initial tick
    readArea();
    return () => { stopped = true; window.clearInterval(id); };
  }, [open, localAreaName, disableAutoSync]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const areaKey = localAreaName && localAreaName.trim() ? localAreaName : undefined;

    const normalizeSentiment = (raw: any): ReviewsSentimentResponse => {
      if (raw && typeof raw === 'object' && 'sentiment' in raw) {
        const s = (raw as any).sentiment || {};
        return {
          positive: Number(s.positive ?? s.pos ?? 0) || 0,
          neutral: Number(s.neutral ?? s.neu ?? 0) || 0,
          negative: Number(s.negative ?? s.neg ?? 0) || 0,
          scope: (raw as any).scope,
        };
      }
      if (raw && typeof raw === 'object' && ('positive' in raw || 'neutral' in raw || 'negative' in raw)) {
        return {
          positive: Number((raw as any).positive ?? 0) || 0,
          neutral: Number((raw as any).neutral ?? 0) || 0,
          negative: Number((raw as any).negative ?? 0) || 0,
          scope: (raw as any).scope,
        };
      }
      return { positive: 0, neutral: 0, negative: 0, scope: (raw as any)?.scope };
    };

    // Sentiment
    const sKey = JSON.stringify({ area: areaKey, bmin: localBudgetMin ?? undefined, bmax: localBudgetMax ?? undefined, room_type: (localRoomTypes && localRoomTypes.length > 0) ? localRoomTypes.join(',') : undefined, min_reviews: localMinReviews ?? undefined });
    const sCached = sentimentCache.get(sKey);
    if (sCached) {
      setSentiment(normalizeSentiment(sCached));
    } else {
      setLoadingSentiment(true);
      fetchReviewsSentiment({ area: localAreaName ?? undefined, bmin: localBudgetMin ?? undefined, bmax: localBudgetMax ?? undefined, room_type: (localRoomTypes && localRoomTypes.length > 0) ? localRoomTypes.join(',') : undefined, min_reviews: localMinReviews ?? undefined })
        .then((res) => {
          if (cancelled) return;
          const norm = normalizeSentiment(res);
          setSentiment(norm);
          sentimentCache.set(sKey, norm);
        })
        .catch((e) => console.error('Failed to fetch reviews sentiment', e))
        .finally(() => { if (!cancelled) setLoadingSentiment(false); });
    }

    // Top keywords
    const topN = 10;
    const kKey = JSON.stringify({ area: areaKey, bmin: localBudgetMin ?? undefined, bmax: localBudgetMax ?? undefined, room_type: (localRoomTypes && localRoomTypes.length > 0) ? localRoomTypes.join(',') : undefined, min_reviews: localMinReviews ?? undefined, top_n: topN, recent_months: 12, sample_size: 50, sample_strategy: 'random' });
    const kCached = topKeywordsCache.get(kKey);
    if (kCached) {
      setKeywords(kCached);
    } else {
      setLoadingKeywords(true);
      const inflight = topKeywordsInFlight.get(kKey);
      if (inflight) {
        inflight
          .then((res) => { if (!cancelled) setKeywords(res); })
          .catch((e) => { if (!cancelled) console.error('Failed to fetch top keywords (inflight)', e); })
          .finally(() => { if (!cancelled) setLoadingKeywords(false); });
      } else {
        const p = fetchReviewsTopKeywords({ area: localAreaName ?? undefined, bmin: localBudgetMin ?? undefined, bmax: localBudgetMax ?? undefined, top_n: topN, recent_months: 12, sample_size: 50, sample_strategy: 'random', room_type: (localRoomTypes && localRoomTypes.length > 0) ? localRoomTypes.join(',') : undefined, min_reviews: localMinReviews ?? undefined });
        topKeywordsInFlight.set(kKey, p);
        p.then((res) => {
            if (cancelled) return;
            setKeywords(res);
            topKeywordsCache.set(kKey, res);
          })
          .catch((e) => { if (!cancelled) console.error('Failed to fetch top keywords', e); })
          .finally(() => { topKeywordsInFlight.delete(kKey); if (!cancelled) setLoadingKeywords(false); });
      }
    }

    return () => { cancelled = true; };
  }, [open, refreshTick]);

  const sentimentPieOption = useMemo(() => {
    if (!sentiment) return undefined;
    const colors = ["#22c55e", "#9ca3af", "#ef4444"]; // pos/neu/neg
    return {
      color: colors,
      tooltip: { trigger: "item" },
      legend: { bottom: 12, itemGap: 12, padding: [8, 0, 0, 0] },
      series: [
        {
          type: "pie",
          radius: ["55%", "75%"],
          top: 0,
          bottom: 48,
          avoidLabelOverlap: true,
          label: { formatter: "{b}: {d}%" },
          data: [
            { name: "Positive", value: Math.round((sentiment.positive || 0) * 100) },
            { name: "Neutral", value: Math.round((sentiment.neutral || 0) * 100) },
            { name: "Negative", value: Math.round((sentiment.negative || 0) * 100) }
          ]
        }
      ],
      graphic: [
        {
          type: 'text',
          left: 'center',
          top: 'middle',
          style: {
            text: `n = ${sentiment.scope?.reviews_count?.toLocaleString?.() || sentiment.scope?.reviews_count || ''}`,
            textAlign: 'center',
            fill: '#6b7280',
            fontSize: 14,
          }
        }
      ]
    };
  }, [sentiment]);

  const sentimentSummary = useMemo(() => {
    if (!sentiment) return null;
    const pos = Math.round((sentiment.positive || 0) * 100);
    const neg = Math.round((sentiment.negative || 0) * 100);
    const area = sentiment.scope?.area || localAreaName || '';
    return (
      <div className="text-sm text-gray-700">
        {area ? <>In {area}, </> : null}reviews are mostly positive ({pos}%); negative {neg}%.
      </div>
    );
  }, [sentiment, localAreaName]);

  const greySubtitle = useMemo(() => {
    const scope = sentiment?.scope || keywords?.scope;
    if (!scope && localBudgetMin == null && localBudgetMax == null) return null;
    const bminNum = scope?.budget_min != null ? scope.budget_min : (localBudgetMin ?? 0);
    const bmaxNum = scope?.budget_max != null ? scope.budget_max : (localBudgetMax ?? Infinity);
    const bmin = `€${bminNum.toLocaleString ? bminNum.toLocaleString() : bminNum}`;
    const bmax = bmaxNum === Infinity ? '€∞' : `€${(bmaxNum as number).toLocaleString ? (bmaxNum as number).toLocaleString() : bmaxNum}`;
    const listings = scope?.listings_in_scope;
    const listingsText = listings != null ? (listings as any).toLocaleString ? (listings as any).toLocaleString() : listings : null;
    const sAny: any = scope as any;
    const areaCandidate = (sAny?.area || sAny?.area_name || localAreaName);
    const areaLabel = areaCandidate ? areaCandidate : 'All Berlin';
    return (
      <div className="text-xs text-gray-400">
        <>
          <span>Area: <strong>{areaLabel}</strong></span>
          {localBudgetMin != null || localBudgetMax != null ? <>; filtered by your budget (<strong>{bmin}–{bmax}</strong>)</> : null}
        </>
        {listingsText != null ? <>; covering <strong>{listingsText}</strong> listings.</> : null}
      </div>
    );
  }, [sentiment, keywords, localBudgetMin, localBudgetMax]);

  const topPhrases = useMemo(() => {
    const items = keywords?.top_phrases || [];
    return items.slice(0, 10);
  }, [keywords]);

  const matchSet = useMemo(() => new Set((keywords?.matched_preferences || matchedPreferences || []).map((s) => s.toLowerCase())), [keywords, matchedPreferences]);

  // Helper: robustly retrieve decision scope from multiple sources
  const getDecisionScope = () => {
    const w: any = (window as any) || {};
    const candidate = selectedDimensions || w.selectedDimensions || w.decisionScope;
    try {
      console.log('🔎 ReviewsPromptModal.getDecisionScope called', {
        propsSelectedDimensions: selectedDimensions,
        windowSelectedDimensions: w?.selectedDimensions,
        windowDecisionScope: w?.decisionScope,
        propsAreaName: areaName,
        propsBudget: { budgetMin, budgetMax }
      });
    } catch {}

    // If provided as an array of dimensions, normalize to scope object
    if (Array.isArray(candidate)) {
      // Merge props array with window.selectedDimensions (props优先覆盖)
      const winArr = Array.isArray(w.selectedDimensions) ? (w.selectedDimensions as Array<{ key: string; value: any }>) : [];
      const mergedByKey = new Map<string, { key: string; value: any }>();
      // put window first, then props to override
      winArr.forEach((d) => mergedByKey.set(String(d?.key || '').toLowerCase(), d));
      (candidate as Array<{ key: string; value: any }>).forEach((d) => mergedByKey.set(String(d?.key || '').toLowerCase(), d));

      const mergedList = Array.from(mergedByKey.values());

      const scope: any = {};
      const roomTypes: string[] = [];
      mergedList.forEach((dim) => {
        const key = String(dim?.key || '').toLowerCase();
        const rawVal = dim?.value;
        const val = rawVal == null ? '' : String(rawVal);
        if (key === 'location' || key === 'area' || key === 'preferred area') {
          if (val && val.toLowerCase() !== 'explore on map' && val.toLowerCase() !== 'all') {
            scope.area_name = val;
          }
        } else if (key === 'price' || key === 'budget' || key === 'budget range') {
          // Parse formats like "€100-200", "100-200", "100 – 200" (including different dashes)
          const nums = (val.match(/\d+/g) || []).map((n) => Number(n));
          try { console.log('🧮 Budget parse from dim', { key: dim?.key, raw: val, nums }); } catch {}
          if (nums.length >= 1) scope.price_min = nums[0];
          if (nums.length >= 2) scope.price_max = nums[1];
        } else if (key === 'room type') {
          if (val.includes(',')) {
            const parts = val.split(',').map((s) => s.trim()).filter(Boolean);
            try { console.log('🏷️ RoomType parse (csv)', parts); } catch {}
            parts.forEach((s) => roomTypes.push(s));
          } else if (val) {
            roomTypes.push(val);
          }
        }
      });
      if (roomTypes.length > 0) {
        scope.room_types = Array.from(new Set(roomTypes));
        scope.room_type = scope.room_types.join(',');
      }
      // Fallback to props if budget missing
      if ((scope.price_min == null && budgetMin != null) || (scope.price_max == null && budgetMax != null)) {
        scope.price_min = scope.price_min != null ? scope.price_min : (budgetMin as any);
        scope.price_max = scope.price_max != null ? scope.price_max : (budgetMax as any);
        try { console.log('🧮 Budget fallback from props', { budgetMin, budgetMax }); } catch {}
      }
      if (!scope.area_name && areaName) {
        scope.area_name = areaName;
        try { console.log('📍 Area fallback from props', { areaName }); } catch {}
      }
      const result = Object.keys(scope).length > 0 ? scope : null;
      try { console.log('🔎 ReviewsPromptModal.getDecisionScope from array ->', { candidate, windowSelected: w?.selectedDimensions, result }); } catch {}
      return result;
    }

    // If provided as a plain object already
    if (candidate && typeof candidate === 'object') {
      try { console.log('🔎 ReviewsPromptModal.getDecisionScope from object ->', candidate); } catch {}
      return candidate;
    }

    // Fallback to sessionStorage
    try {
      const area_name = sessionStorage.getItem('area_name') || sessionStorage.getItem('selected_area') || null;
      const district = sessionStorage.getItem('district');
      const neighbourhood = sessionStorage.getItem('neighbourhood');
      const budget_min = sessionStorage.getItem('budget_min');
      const budget_max = sessionStorage.getItem('budget_max');
      const room_type_raw = sessionStorage.getItem('room_type') || sessionStorage.getItem('room_types');
      const parsed: any = {};
      if (area_name || district || neighbourhood) parsed.area_name = area_name || district || neighbourhood;
      if (budget_min) parsed.price_min = Number(budget_min);
      if (budget_max) parsed.price_max = Number(budget_max);
      if (room_type_raw) {
        // Accept JSON string array or comma-separated string
        let rtArr: string[] | null = null;
        try {
          const maybe = JSON.parse(room_type_raw);
          if (Array.isArray(maybe)) {
            rtArr = maybe.map((s) => String(s)).filter(Boolean);
          }
        } catch {}
        if (!rtArr) {
          rtArr = String(room_type_raw)
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean);
        }
        if (rtArr && rtArr.length > 0) {
          parsed.room_types = Array.from(new Set(rtArr));
          parsed.room_type = parsed.room_types.join(',');
        }
      }
      // Fallback to props if missing
      if ((parsed.price_min == null && budgetMin != null) || (parsed.price_max == null && budgetMax != null)) {
        parsed.price_min = parsed.price_min != null ? parsed.price_min : (budgetMin as any);
        parsed.price_max = parsed.price_max != null ? parsed.price_max : (budgetMax as any);
      }
      if (!parsed.area_name && areaName) parsed.area_name = areaName;
      const hasAny = Object.keys(parsed).length > 0;
      const result = hasAny ? parsed : null;
      try { console.log('🔎 ReviewsPromptModal.getDecisionScope from sessionStorage ->', result); } catch {}
      return result;
    } catch {
      return null;
    }
  };

  // Manual refetch for Top Phrases (without affecting sentiment)
  const refetchTopKeywords = async () => {
    try {
      setLoadingKeywords(true);
      const topN = 10;
      const res = await fetchReviewsTopKeywords({
        area: localAreaName ?? undefined,
        bmin: localBudgetMin ?? undefined,
        bmax: localBudgetMax ?? undefined,
        top_n: topN,
        recent_months: 12,
        sample_size: 50,
        sample_strategy: 'random',
        room_type: (localRoomTypes && localRoomTypes.length > 0) ? localRoomTypes.join(',') : undefined,
        min_reviews: localMinReviews ?? undefined
      });
      setKeywords(res);
      try {
        const areaKey = localAreaName && localAreaName.trim() ? localAreaName : undefined;
        const kKey = JSON.stringify({ area: areaKey, bmin: localBudgetMin ?? undefined, bmax: localBudgetMax ?? undefined, room_type: (localRoomTypes && localRoomTypes.length > 0) ? localRoomTypes.join(',') : undefined, min_reviews: localMinReviews ?? undefined, top_n: topN, recent_months: 12, sample_size: 50, sample_strategy: 'random' });
        topKeywordsCache.set(kKey, res);
      } catch {}
    } catch (e) {
      console.error('Failed to refetch top keywords', e);
    } finally {
      setLoadingKeywords(false);
    }
  };

  // Grouped scope bar (area chosen via map, filters here; Apply triggers fetch)
  const scopeChips = (
    <div className="px-6 pt-3 pb-1">
      <div className="w-full bg-gray-50 border border-gray-200 rounded-md p-3">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-gray-700 font-medium">Reviews knowledge base scope</span>

          {/* Area (chip) + Map select */}
          <div className="inline-flex items-center gap-2 bg-gray-100 border border-gray-300 text-gray-700 rounded px-2 py-1">
            <span>{localAreaName || 'All Berlin'}</span>
            {onRequestMapSelect && (
              <button
                className="px-2 py-0.5 border rounded bg-white hover:bg-gray-100"
                onClick={() => onRequestMapSelect?.({ area_name: localAreaName, budget_min: localBudgetMin, budget_max: localBudgetMax })}
                title="Select on map"
              >
                <span className="inline-flex items-center gap-1">
                  <EnvironmentOutlined />
                  Map
                </span>
              </button>
            )}
          </div>

          {/* Budget pill */}
          <div className="inline-flex items-center gap-1 bg-amber-50 border border-amber-200 text-amber-700 rounded px-2 py-1">
            <span>Budget</span>
            <input
              type="number"
              placeholder="min"
              className="w-20 px-2 py-0.5 border rounded bg-white"
              value={localBudgetMin ?? ''}
              onChange={(e) => {
                const n = e.target.value === '' ? null : Math.max(0, Number(e.target.value));
                setLocalBudgetMin(n);
                onScopeToggle?.({ budget_min: n });
              }}
            />
            <span>–</span>
            <input
              type="number"
              placeholder="max"
              className="w-20 px-2 py-0.5 border rounded bg-white"
              value={localBudgetMax ?? ''}
              onChange={(e) => {
                const n = e.target.value === '' ? null : Math.max(0, Number(e.target.value));
                setLocalBudgetMax(n);
                onScopeToggle?.({ budget_max: n });
              }}
            />
          </div>

          {/* Room type pill (agent-only, multi-select) */}
          {(onOpenQnA || onSliceClick || onPhraseClick) && (
            <div className="inline-flex items-center gap-2 bg-purple-50 border border-purple-200 text-purple-700 rounded px-2 py-1">
              <span>Room type</span>
              <Select
                mode="multiple"
                allowClear
                placeholder="All"
                value={localRoomTypes}
                onChange={(vals) => {
                  const arr = Array.isArray(vals) ? vals : [];
                  setLocalRoomTypes(arr as string[]);
                  onScopeToggle?.({ room_types: arr, room_type: (arr && arr.length > 0) ? (arr as string[]).join(',') : null });
                }}
                className="min-w-[200px]"
                options={[
                  { value: 'Entire home/apt', label: 'Entire home/apt' },
                  { value: 'Private room', label: 'Private room' },
                  { value: 'Shared room', label: 'Shared room' },
                  { value: 'Hotel room', label: 'Hotel room' }
                ]}
              />
            </div>
          )}

          {/* Min reviews removed per request */}

          {/* Use Decision Scope (primary, with hover) */}
          <Tooltip title="Shortcut: quickly fill filters from your decision card">
            <button
              className="px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700"
              onClick={() => {
                try {
                console.log('🟦 ReviewsPromptModal.UseDecisionScope clicked');
                  const sd = getDecisionScope();
                if (!sd) { console.warn('⚠️ No decision scope available at click time'); message.info('No decision scope available.'); return; }
                  const area = sd.area_name || sd.district || sd.neighbourhood || null;
                  const bmin = sd.price_min ?? sd.budget_min ?? null;
                  const bmax = sd.price_max ?? sd.budget_max ?? null;
                  const rt = sd.room_types ?? sd.room_type ?? null;
                  const mr = sd.min_reviews ?? null;
                console.log('🟦 Applying decision scope', { sd, apply: { area, bmin, bmax, rt, mr } });
                  setLocalAreaName(area);
                  setLocalBudgetMin(bmin);
                  setLocalBudgetMax(bmax);
                  const arr = Array.isArray(rt) ? rt as string[] : (typeof rt === 'string' && rt.includes(',')) ? (rt as string).split(',').map(s => s.trim()).filter(Boolean) : (rt ? [String(rt)] : []);
                  setLocalRoomTypes(arr);
                  setLocalMinReviews(mr);
                  const payload = { area_name: area, budget_min: bmin, budget_max: bmax, room_types: arr, room_type: arr.length ? arr.join(',') : null, min_reviews: mr };
                  try { console.log('🟦 onScopeToggle payload', payload); } catch {}
                  onScopeToggle?.(payload);
                } catch {
                console.error('❌ Failed to use decision scope');
                  message.warning('Failed to use decision scope.');
                }
              }}
            >
              Use Decision Scope
            </button>
          </Tooltip>

          {/* Agent mode: Send current filters to Decision Card */}
          {(onOpenQnA || onSliceClick || onPhraseClick) && (
            <button
              className="px-3 py-1 rounded bg-green-600 text-white hover:bg-green-700"
              title="Copy current filters to Decision Card"
              onClick={() => {
                try {
                  const dims: Array<{ key: string; value: string }> = [];
                  if (localAreaName && localAreaName.trim()) {
                    dims.push({ key: 'Location', value: localAreaName.trim() });
                  }
                  if (localBudgetMin != null || localBudgetMax != null) {
                    // Send as "Budget" so DecisionCard budget renderer activates two numeric inputs
                    const minLabel = localBudgetMin != null ? String(localBudgetMin) : '';
                    const maxLabel = localBudgetMax != null ? String(localBudgetMax) : '';
                    dims.push({ key: 'Budget', value: `${minLabel}-${maxLabel}` });
                  }
                  if (Array.isArray(localRoomTypes) && localRoomTypes.length > 0) {
                    localRoomTypes.forEach((rt) => dims.push({ key: 'Room Type', value: String(rt) }));
                  }
                  try { (window as any).selectedDimensions = dims; } catch {}
                  window.dispatchEvent(new CustomEvent('decisioncard:setDimensions', { detail: { dimensions: dims } }));
                  message.success('Sent to Decision Card');
                } catch (e) {
                  message.error('Failed to send to Decision Card');
                }
              }}
            >
              Send to Decision Card
            </button>
          )}

          {/* Apply at the end (keeps to the right, wraps to next line on overflow) */}
          <div className="ml-auto">
            <button
              className="px-3 py-1 border rounded bg-blue-50 text-blue-700 hover:bg-blue-100"
              onClick={() => {
                setRefreshTick((t) => t + 1);
                setTimeout(() => {
                  const listings = (sentiment as any)?.scope?.listings_in_scope ?? (keywords as any)?.scope?.listings_in_scope;
                  const reviewsUsed = (keywords as any)?.scope?.reviews_used ?? (sentiment as any)?.scope?.reviews_count;
                  if (!(Number(listings) > 0 || Number(reviewsUsed) > 0)) {
                    message.warning('Not enough data under the current scope. Try broadening the filters.');
                  }
                }, 300);
              }}
            >
              Apply
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const panelScope = useMemo(() => ({
    area_name: localAreaName,
    area: localAreaName,
    budget_min: localBudgetMin,
    budget_max: localBudgetMax,
    room_types: localRoomTypes,
    room_type: localRoomTypes.length ? localRoomTypes.join(',') : null,
    min_reviews: localMinReviews
  }), [localAreaName, localBudgetMin, localBudgetMax, localRoomTypes, localMinReviews]);

  const content = (
    <div className="space-y-4 px-6 pb-6">
      <Collapse bordered>
        <Panel header="Sentiment Overview" key="1">
          <Paragraph className="text-gray-700 mb-2">
            <strong>Sentiment</strong>: Overall positive vs neutral vs negative
          </Paragraph>
          {loadingSentiment && <div className="text-center py-8 text-gray-400">Loading...</div>}
          {!loadingSentiment && sentiment && (
            <div>
              <EChartsBlock
                type="pie"
                data={[]}
                options={sentimentPieOption}
                height={220}
                onClick={(p: any) => {
                  const name: string = (p?.name || '').toLowerCase();
                  const key = name.startsWith('pos') ? 'pos' : name.startsWith('neu') ? 'neu' : name.startsWith('neg') ? 'neg' : null;
                  if (key) onSliceClick?.(key as any, panelScope as any);
                }}
              />
              <div className="mt-2">
                {sentimentSummary}
                {greySubtitle}
              </div>
              {(onOpenQnA || onSliceClick) && (
                <div className="mt-3 flex items-center justify-between">
                  <div className="flex gap-2 text-xs">
                    <span className="text-gray-500">Quick filter:</span>
                    <span className="cursor-pointer px-2 py-1 rounded bg-green-50 text-green-700 border border-green-200" onClick={() => onSliceClick?.('pos', panelScope)}>Positive</span>
                    <span className="cursor-pointer px-2 py-1 rounded bg-gray-50 text-gray-700 border border-gray-200" onClick={() => onSliceClick?.('neu', panelScope)}>Neutral</span>
                    <span className="cursor-pointer px-2 py-1 rounded bg-red-50 text-red-700 border border-red-200" onClick={() => onSliceClick?.('neg', panelScope)}>Negative</span>
                  </div>
                  <button className="px-3 py-1 text-xs rounded bg-blue-500 text-white hover:bg-blue-600" onClick={() => onOpenQnA?.('', panelScope)}>
                    Explore with Q&A
                  </button>
                </div>
              )}
            </div>
          )}
          {!loadingSentiment && !sentiment && (
            <div className="text-center py-8 text-gray-400">No data available</div>
          )}
        </Panel>

        <Panel header="Top Phrases" key="2">
          <div className="flex items-center justify-between mb-2">
            <Paragraph className="text-gray-700 mb-0">
              <strong>Top Phrases from Recent Reviews</strong>
            </Paragraph>
            <button
              className="px-2 py-0.5 text-xs border rounded bg-white hover:bg-gray-50 text-gray-600 flex items-center gap-1"
              onClick={refetchTopKeywords}
              title="Refresh top phrases"
            >
              <ReloadOutlined /> Refresh
            </button>
          </div>
          {loadingKeywords && <div className="text-center py-8 text-gray-400">Loading...</div>}
          {!loadingKeywords && keywords && (keywords as any)?.llm_error && (
            <div className="p-3 bg-orange-50 border border-orange-200 rounded text-sm text-orange-800">
              <div className="mb-2">{String((keywords as any).llm_error)}</div>
              <button
                className="px-2 py-1 text-xs rounded bg-orange-500 text-white hover:bg-orange-600"
                onClick={refetchTopKeywords}
              >
                Retry
              </button>
            </div>
          )}
          {!loadingKeywords && topPhrases.length > 0 && (
            <div className="space-y-2">
              {topPhrases.map((p) => {
                const text = p.text || p["text"]; const count = p.count || p["count"]; // tolerate backend variations
                const lower = String(text || '').toLowerCase();
                const matched = Array.from(matchSet).some((kw) => lower.includes(kw));
                return (
                  <div key={text} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span className={onPhraseClick ? "cursor-pointer hover:underline" : undefined} onClick={() => onPhraseClick?.({ text, count }, panelScope)}>{text}</span>
                      {matched && <Tag color="default">matches your preference</Tag>}
                    </div>
                    <span className="text-gray-500">{count}</span>
                  </div>
                );
              })}
            </div>
          )}
          {!loadingKeywords && !keywords && (
            <div className="text-center py-8 text-gray-400">No data available</div>
          )}
          {!loadingKeywords && keywords && topPhrases.length === 0 && (
            <div className="text-center py-8 text-gray-400">No frequent phrases found</div>
          )}
          {keywords?.scope?.reviews_used != null && (
            <div className="text-xs text-gray-500 mt-2">
              Sample size: <strong>{(keywords.scope.reviews_used as any)?.toLocaleString?.() ?? keywords.scope.reviews_used}</strong> reviews used
            </div>
          )}
          {(onOpenQnA) && (
            <div className="mt-3 text-right">
              <button className="px-3 py-1 text-xs rounded bg-blue-500 text-white hover:bg-blue-600" onClick={() => onOpenQnA?.('', panelScope)}>
                Explore with Q&A
              </button>
            </div>
          )}
        </Panel>
      </Collapse>
    </div>
  );

  if (inline) {
    if (frameless) {
      // return content only, no header/container/footer
      return (
        <>
          {scopeChips}
          {content}
        </>
      );
    }
    return (
      <div className="border rounded-lg overflow-hidden bg-white">
        <div className="px-6 pt-4">
          <Title level={4}>🧠 Explore Guest Reviews</Title>
        </div>
        {scopeChips}
        {content}
        <div className="border-t text-center text-gray-400 text-xs py-2">
          <MessageOutlined /> Guest review insights powered by simple NLP extraction
        </div>
      </div>
    );
  }

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={680}
      bodyStyle={{ padding: 0 }}
      title={<Title level={4} className="px-6 pt-4">🧠 Explore Guest Reviews</Title>}
    >
      {content}

      <div className="border-t text-center text-gray-400 text-xs py-2">
        <MessageOutlined /> Guest review insights powered by simple NLP extraction
      </div>
    </Modal>
  );
};

export default ReviewsPromptModal;