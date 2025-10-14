import { ensureSessionId, getConversationMode } from '../api/session';

/**
 * 统一采集策略 - 会话级一次性上报指标收集系统
 * 
 * 核心思路：
 * - 集中计数：前端维护单例的 metrics store（内存态），所有页面/组件只增量更新该 store
 * - 去重与节流：对"可视化触发"按 messageId + chartType 去重；地图交互按"开始-闲置≥5s-结束"为一段累计时长与段数
 * - 一次性提交：会话结束或首次推荐完成后，统一 POST /metrics/commit
 * - 失败不重传：记日志即可（避免多次写入产生脏数据）；用户二次提交覆盖前值
 * 
 * 指标级定义 & 触发时机：
 * - preference_adjust_count: 当且仅当"系统状态中的偏好值被实际更新"为一次，相同字段同值不计数
 * - visualization_trigger_count: 用户可见的图表/地图首次渲染或显式打开计一次，按 messageId + chartType 去重
 * - rag_query_local_count: 发送带上下文/过滤的RAG请求时计数
 * - rag_query_global_count: 发送全局RAG请求时计数  
 * - visualization_diversity: 对本会话中出现过的图表类型去重计数
 * - task_completion_time: 从会话起点到首次生成推荐完成的秒数
 * - total_turns: 用户每发送一条消息 +1，系统消息不计
 * - location_interaction_seconds: 地图交互累计时长（各段时长相加）
 * - location_interaction_episodes: 地图交互段数（5s无操作视为一段结束）
 */

export type Metrics = {
  /** 用户修改或细化偏好的次数（预算、房型、区域等） - 相同字段同值不计数 */
  preference_adjust_count: number;
  /** 用户主动触发可视化的次数 - 按 messageId + chartType 去重 */
  visualization_trigger_count: number;
  /** 局部范围的 RAG 查询次数（带上下文/过滤条件） */
  rag_query_local_count: number;
  /** 全局范围的 RAG 查询次数（无过滤条件的全局问答） */
  rag_query_global_count: number;
  /** 从会话开始到任务完成的时间（秒） - 首次推荐完成时记录 */
  task_completion_time: number | null;
  /** 会话总轮次 - 用户发送消息计数，系统消息不计 */
  total_turns: number;
  /** 使用过的不同可视化类型数量 - 基于 chartType 去重计数 */
  visualization_diversity: number;
  /** 地图交互累计时长（秒） - 各段时长相加，仅存储在 context_json 中 */
  location_interaction_seconds: number;
  /** 地图交互段数 - 5s无操作视为一段结束，仅存储在 context_json 中 */
  location_interaction_episodes: number;
};

const metrics: Metrics = {
  preference_adjust_count: 0,
  visualization_trigger_count: 0,
  rag_query_local_count: 0,
  rag_query_global_count: 0,
  task_completion_time: null,
  total_turns: 0,
  visualization_diversity: 0,
  location_interaction_seconds: 0,
  location_interaction_episodes: 0,
};

// 内部状态管理
let startTsMs: number | null = null;
const vizTypes = new Set<string>(); // 可视化类型去重集合
const vizTriggerKeys = new Set<string>(); // 可视化触发去重集合 (messageId + chartType)
const preferenceHistory = new Map<string, any>(); // 偏好历史记录，用于去重 (fieldName -> value)
let committed = false;

// 地图交互状态管理
let mapInteractionStartTime: number | null = null;
let mapInteractionTimer: number | null = null;
const MAP_INTERACTION_IDLE_THRESHOLD = 5000; // 5秒无操作视为一段结束

/** 初始化计时与计数（每个页面会话一次）- 重置所有指标和内部状态 */
export function initMetrics(): void {
  startTsMs = null;
  committed = false;
  
  // 重置所有指标
  metrics.preference_adjust_count = 0;
  metrics.visualization_trigger_count = 0;
  metrics.rag_query_local_count = 0;
  metrics.rag_query_global_count = 0;
  metrics.task_completion_time = null;
  metrics.total_turns = 0;
  metrics.visualization_diversity = 0;
  metrics.location_interaction_seconds = 0;
  metrics.location_interaction_episodes = 0;
  
  // 重置内部状态
  vizTypes.clear();
  vizTriggerKeys.clear();
  preferenceHistory.clear();
  
  // 重置地图交互状态
  if (mapInteractionTimer) {
    clearTimeout(mapInteractionTimer);
    mapInteractionTimer = null;
  }
  mapInteractionStartTime = null;
  try { console.log('----- METRICS INIT -----'); } catch {}
}

/** 在点击 Start Agent/Scripted 时调用，启动计时 */
export function markTaskStart(): void {
  if (startTsMs == null) {
    startTsMs = Date.now();
  }
}

/** 偏好被实际更新时调用 - 相同字段同值不计数，确保去重 */
export function incrementPreferenceAdjust(fieldName: string, newValue: any): void {
  const currentValue = preferenceHistory.get(fieldName);
  
  // 相同字段同值不计数
  if (currentValue !== undefined && currentValue === newValue) {
    return;
  }
  
  // 记录新值并增加计数
  preferenceHistory.set(fieldName, newValue);
  metrics.preference_adjust_count += 1;
  try { console.log('----- METRICS incrementPreferenceAdjust -----', { fieldName, newValue }); } catch {}
}

/** 当用户可见的图表/地图首次渲染或显式打开时调用 - 按 messageId + chartType 去重 */
export function incrementVisualizationTrigger(messageId: string, chartType: string): void {
  const dedupeKey = `${messageId}_${chartType}`;
  
  // 同一消息内相同图表类型不重复计数
  if (vizTriggerKeys.has(dedupeKey)) {
    return;
  }
  
  // 记录去重键并增加计数
  vizTriggerKeys.add(dedupeKey);
  metrics.visualization_trigger_count += 1;
  try { console.log('----- METRICS incrementVisualizationTrigger -----', { messageId, chartType }); } catch {}
  
  // 同时更新可视化类型多样性
  if (!vizTypes.has(chartType)) {
    vizTypes.add(chartType);
    metrics.visualization_diversity = vizTypes.size;
    try { console.log('----- METRICS visualization_diversity update -----', { chartType, diversity: metrics.visualization_diversity }); } catch {}
  }
}

/** 统一RAG查询计数入口 - 根据是否全局搜索自动分类计数 */
export function incrementRagQuery(isGlobalSearch: boolean): void {
  if (isGlobalSearch) {
    metrics.rag_query_global_count += 1;
    try { console.log('----- METRICS incrementRagQuery(global) -----'); } catch {}
  } else {
    metrics.rag_query_local_count += 1;
    try { console.log('----- METRICS incrementRagQuery(local) -----'); } catch {}
  }
}

/** 发送局部检索时调用（带上下文/过滤条件的RAG请求） - 已废弃，请使用 incrementRagQuery(false) */
export function incrementRagLocal(): void {
  metrics.rag_query_local_count += 1;
  try { console.log('----- METRICS incrementRagLocal (deprecated) -----'); } catch {}
}

/** 发送全局检索时调用（无过滤条件的全局问答） - 已废弃，请使用 incrementRagQuery(true) */
export function incrementRagGlobal(): void {
  metrics.rag_query_global_count += 1;
  try { console.log('----- METRICS incrementRagGlobal (deprecated) -----'); } catch {}
}

/** 任务完成时调用（例如首次生成推荐列表） */
export function markTaskCompleted(): void {
  if (metrics.task_completion_time != null) return;
  const now = Date.now();
  if (startTsMs != null) {
    metrics.task_completion_time = Math.max(0, Math.round((now - startTsMs) / 1000));
  } else {
    metrics.task_completion_time = 0;
  }
  try { console.log('----- METRICS markTaskCompleted -----', { task_completion_time: metrics.task_completion_time }); } catch {}
}

/** 用户发送消息时调用 - 仅用户消息计数，系统消息不计 */
export function incrementUserTurn(): void {
  metrics.total_turns += 1;
  try { console.log('----- METRICS incrementUserTurn -----', { total_turns: metrics.total_turns }); } catch {}
}

/** 可视化类型集合更新（用于多样性统计） - 已集成到 incrementVisualizationTrigger 中 */
export function noteVisualizationTypes(types: string[]): void {
  for (const t of types) {
    if (t) {
      vizTypes.add(String(t));
    }
  }
  metrics.visualization_diversity = vizTypes.size;
  try { console.log('----- METRICS noteVisualizationTypes -----', { types, diversity: metrics.visualization_diversity }); } catch {}
}

/** 在提交前用外部计算结果覆盖轮次 - 避免回退误加，慎用 */
export function setTotalTurns(total: number): void {
  metrics.total_turns = Math.max(0, Math.floor(total || 0));
  try { console.log('----- METRICS setTotalTurns -----', { total_turns: metrics.total_turns }); } catch {}
}

/** 地图交互开始 - 记录交互开始时间，重置闲置计时器 */
export function startMapInteraction(): void {
  const now = Date.now();
  
  // 如果当前没有交互进行中，开始新的交互段
  if (mapInteractionStartTime === null) {
    mapInteractionStartTime = now;
  }
  
  // 重置闲置计时器
  if (mapInteractionTimer) {
    clearTimeout(mapInteractionTimer);
  }
  
  // 设置5秒闲置检测
  mapInteractionTimer = setTimeout(() => {
    endMapInteractionSegment();
  }, MAP_INTERACTION_IDLE_THRESHOLD) as any;
  try { console.log('----- METRICS startMapInteraction -----'); } catch {}
}

/** 结束当前地图交互段 - 计算时长并增加段数 */
function endMapInteractionSegment(): void {
  if (mapInteractionStartTime === null) return;
  
  const now = Date.now();
  const segmentDuration = Math.max(0, Math.round((now - mapInteractionStartTime) / 1000));
  
  // 累计时长和段数
  metrics.location_interaction_seconds += segmentDuration;
  metrics.location_interaction_episodes += 1;
  
  // 重置状态
  mapInteractionStartTime = null;
  if (mapInteractionTimer) {
    clearTimeout(mapInteractionTimer);
    mapInteractionTimer = null;
  }
  try { console.log('----- METRICS endMapInteractionSegment -----', { location_interaction_seconds: metrics.location_interaction_seconds, location_interaction_episodes: metrics.location_interaction_episodes }); } catch {}
}

/** 强制结束地图交互 - 在组件卸载或页面关闭时调用 */
export function forceEndMapInteraction(): void {
  if (mapInteractionStartTime !== null) {
    endMapInteractionSegment();
  }
  try { console.log('----- METRICS forceEndMapInteraction -----'); } catch {}
}

/** 生成一次性提交负载 - 包含核心指标和地图交互数据 */
export function buildPayload() {
  // 强制结束任何进行中的地图交互
  forceEndMapInteraction();
  
  const session_id = ensureSessionId();
  const conversation_mode = getConversationMode?.();
  
  // 构建核心指标（不包含 location_interaction_* 字段）
  const coreMetrics = {
    preference_adjust_count: metrics.preference_adjust_count,
    visualization_trigger_count: metrics.visualization_trigger_count,
    rag_query_local_count: metrics.rag_query_local_count,
    rag_query_global_count: metrics.rag_query_global_count,
    visualization_diversity: metrics.visualization_diversity,
    task_completion_time: metrics.task_completion_time,
    total_turns: metrics.total_turns,
  };
  
  // 构建完整负载
  const payload = {
    session_id,
    conversation_mode,
    metrics: coreMetrics,
    // 地图交互数据放在顶层，后端会写入 context_json.location_interaction
    location_interaction_seconds: metrics.location_interaction_seconds,
    location_interaction_episodes: metrics.location_interaction_episodes,
  };
  
  try { console.log('----- METRICS buildPayload -----', payload); } catch {}

  return payload;
}

export function markCommitted() {
  committed = true;
  try { console.log('----- METRICS markCommitted -----'); } catch {}
}

export function isCommitted() {
  return committed;
} 