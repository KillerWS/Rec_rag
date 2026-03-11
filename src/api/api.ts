import axios from 'axios';
import { ensureSessionId, getSessionId, setSessionId, getConversationMode } from './session';

const api = axios.create({
  baseURL: 'http://localhost:5000/api', // 🚀 替换成你的后端地址
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：统一注入 session_id（每次刷新生成新的临时ID）
api.interceptors.request.use(
  (config) => {
    const url = (config.url || '').toString();
    if (url.includes('/session/new')) {
      return config;
    }
    let sid: string | null = null;
    try {
      sid = sessionStorage.getItem('study_session_id');
    } catch {}
    if (!sid) {
      sid = ensureSessionId();
    }
    if (!sid) {
      return Promise.reject(new Error('Missing session_id'));
    }
    // 附到 header，便于后端可靠读取
    config.headers = {
      ...(config.headers || {}),
      'X-Session-Id': sid,
    } as any;
    // 冗余携带到 query/body
    if (config.method === 'get') {
      config.params = { ...(config.params || {}), session_id: sid, conversation_mode: getConversationMode?.() };
    } else if (config.method === 'post' || config.method === 'put' || config.method === 'patch') {
      if (config.data && typeof config.data === 'object') {
        (config.data as any).session_id = sid;
        (config.data as any).conversation_mode = getConversationMode?.();
      } else {
        config.data = { session_id: sid, conversation_mode: getConversationMode?.() };
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器：如果后端回传新的 session_id，则采用之
api.interceptors.response.use(
  (response) => {
    const data = response.data;
    if (data && typeof data === 'object' && (data as any).session_id) {
      const newId = String((data as any).session_id);
      if (newId && newId.toLowerCase() !== 'default' && newId !== getSessionId()) {
        setSessionId(newId);
      }
    }
    return data;
  },
  (error) => {
    console.error("API 请求错误:", error);
    return Promise.reject(error);
  }
);

export default api;

/**
 * 统一提交前端会话指标（一次性）
 */
export const commitSessionMetrics = async (payload: { session_id: string; metrics: Record<string, any> }) => {
  return api.post('/metrics/commit', payload, { timeout: 20000 });
};

/**
 * 5-Likert survey submission
 */
export const commitLikertFeedback = async (payload: {
  session_id: string;
  answers: Record<string, number>;
  task_type?: string;
  system_label?: string;
  block_index?: number | null;
  open_ended?: Record<string, string>;
}) => {
  return api.post('/metrics/likert', payload, { timeout: 20000 });
};

/**
 * 🔹 获取聊天消息回复
 */ 
export const fetchChatResponse = async (message: string) => {
  try {
    const response: any = await api.post('/chat', { message });
    return response.data || { response: "No data received", chart_data: null }; // 返回 AI 生成的回复
  } catch (error) {
    return "Error fetching chat response.";
  }
};


export const fetchPrepareRagContext = async () => {
  try {
    const res = await api.post('/prepare_rag_context', {}, {
      headers: {
        'Content-Type': 'application/json'
      },
      timeout: 120000
    });
    return res as any;  // 返回 { index_id, session_id? }
  } catch (error) {
    console.error("Failed to prepare RAG context:", error);
    return null;
  }
};

/**
 * 🔹 获取任务分配（simple / exploratory）
 * 后端返回字段名可能不同，这里做宽松解析。
 */
export const fetchTaskAssignment = async (): Promise<{
  task_type?: string;
  system?: string;
  assignment?: string;
  mode?: string;
  system_label?: string;
  system_variant?: string;
  block_index?: number;
}> => {
  try {
    const sessionId = sessionStorage.getItem('study_session_id');
    const res: any = await api.get('/task/assignment', {
      params: sessionId ? { session_id: sessionId } : {}
    });
    return (res as any) ?? {};
  } catch (error) {
    console.warn('Failed to fetch task assignment, falling back to default.', error);
    return {};
  }
};



export const completeBlock = async (session_id: string) => {
  return api.post('/block/complete', { session_id });
};

export const fetchRAGAnswer = async (message: string, history: any[], extraParams = {}) => {
  try {
    const response = await api.post('/rag_chat', {
      message,
      history: history,
      ...extraParams
    }, {
      headers: {
        'Content-Type': 'application/json'
      },
      timeout: 180000
    });
    return (response as any)?.data ?? response;
  } catch (error) {
    console.error("Failed to fetch RAG answer:", error);
    throw error;
  }
};

// 🆕 Scripted 模式下的 RAG 对话接口
export const fetchRAGAnswerScripted = async (
  message: string,
  history: any[],
  extraParams: { [key: string]: any } = {}
) => {
  try {
    const response = await api.post('/rag_chat_scripted', {
      message,
      history,
      ...extraParams
    }, {
      headers: {
        'Content-Type': 'application/json'
      },
      timeout: 180000
    });
    return (response as any)?.data ?? response;
  } catch (error) {
    console.error("Failed to fetch scripted RAG answer:", error);
    throw error;
  }
};

// 可选：显式向后端申请一次新的 session（如果后端提供接口）
export const fetchNewSession = async (): Promise<{ session_id: string }> => {
  const res: any = await api.post('/session/new', {});
  if (res && res.session_id) {
    setSessionId(res.session_id);
    return { session_id: res.session_id };
  }
  // 如果后端没有实现该接口，退化到前端 ensureSessionId()
  const sid = ensureSessionId();
  return { session_id: sid };
};

/**
 * 🔹 获取 Top-K 推荐项
 */
export interface Recommendation {
  id: string;
  name: string;
  price: number;
  room_type: string;
  neighbourhood?: string;
  neighbourhood_cleansed?: string;
  neighbourhood_group?: string;
  neighbourhood_group_cleansed?: string;
  availability_365: number;
  number_of_reviews: number;
  number_of_reviews_ltm?: number;
  reviews_per_month: number;
  last_review?: string;
  recommendation_score: number;
  
  // Additional fields for RecommendationCard compatibility
  picture_url?: string;
  listing_url?: string;
  host_name?: string;
  host_id?: number;
  host_is_superhost?: boolean;
  host_url?: string;
  property_type?: string;
  accommodates?: number;
  bedrooms?: string | number;
  beds?: string | number;
  bathrooms?: string;
  bathrooms_text?: string;
  amenities?: any; // JSON string or array of amenities
  description?: string;
  match_reason?: string;
  review_scores_rating?: number | string;
  review_scores_value?: number | string;
  minimum_nights?: number;
  latitude?: number;
  longitude?: number;
  keyword_matches?: string;
  semantic_score?: number;
  final_score?: number;
  
  [key: string]: any;
}

export interface RecommendationResponse {
  recommendations: Recommendation[];
  // success?: boolean;
  // message?: string;
  sql_query?: string; // Add this field to match backend response
}

export const fetchRecommendations = async (data: {
  selectedDimensions: { key: string; value: string }[];
  top_k: number;
}): Promise<RecommendationResponse> => {
  try {
    const response: any = await api.post(`/recommendations`, { data });
    
    if (response && response.recommendations && Array.isArray(response.recommendations)) {
      return { 
        recommendations: response.recommendations,
        sql_query: response.sql_query 
      };
    } else {
      console.error("Invalid response structure:", response);
      return { recommendations: [] };
    }
  } catch (error) {
    console.error("API error:", error);
    return { recommendations: [] };
  }
};

/**
 * 🔹 获取 ECharts 数据
 */
export const fetchChartData = async () => {
  try {
    const response = await api.get('/chart-data');
    return response; // 直接返回 ECharts 格式的数据
  } catch (error) {
    return { title: "Error", type: "scatter", data: [] };
  }
};

// 🆕 测试图表接口：POST 返回 { chart_type, echarts_option }
export const fetchTestChartOption = async (payload: {
  type?: string;
  preferences?: any;
  filters?: any;
  price_min?: number;
  price_max?: number;
  neighbourhood?: string;
  neighbourhood_group?: string;
  room_type?: string;
  level?: 'district' | 'neighbourhood';
  name?: string;
  top_n?: number;
  metric?: string;
} = {}): Promise<any> => {
  try {
    const res: any = await api.post('/test/chart-option', payload);
    return res; // 期待后端返回 { chart_type, echarts_option }
  } catch (error) {
    console.error('Failed to fetch test chart option:', error);
    throw error;
  }
};


// 🆕 Scripted 模式 获取价格概览数据 （价格分布）
export const fetchPriceOverview = async (budget_min?: number, budget_max?: number) => {
  try {
    console.log(budget_min, budget_max)
    const response = await api.get("/price-overview", {
      params: { budget_min, budget_max },
    });
    return response; // 返回格式: { summary, pieChart, barChart }
  } catch (error) {
    console.error("🚨 Failed to fetch price overview:", error);
    return {
      summary: {},
      pieChart: { type: "pie", data: [], highlight: [] },
      barChart: { type: "bar", data: [], highlight: [] },
    };
  }
};


export const fetchNeighbourhoodAggregation = async (budget_min: number, budget_max: number) => {
  const res = await api.get("/fetch_neighbourhood_aggregation", {
    params: { budget_min, budget_max }
  });
  return res.data;
};


export const fetchRoomTypeAggregation = async (min_price: number, max_price: number) => {
  console.log(min_price, max_price)
  const res = await api.get(`/room_type_price_distribution`, {
    params: { min_price, max_price }
  });
  return res.data;
};


export const fetchReviewInsights = async()=>{
  try {
    const res = await api.get(`/fetch_review_insights`, {
      timeout: 100000 // 🔥 设置10秒超时（单位是毫秒）
    });
    return res as any; // 直接返回 ECharts 格式的数据
  } catch (error) {
    return { title: "Error", type: "scatter", data: [] } as any;
  }
  
}


export const fetchPreferenceConfidence = async(message: string, history: any[])=>{
    try {
    const res = await api.post(`/intent-analysis`, {
            message,
        history: history,
    });
    return res; 
  } catch (error) {
    return { title: "Error", type: "scatter", data: [] };
  }
}

// 🆕 获取房源数据用于热力图
export const fetchListingsForHeatmap = async () => {
  try {
    const response = await fetch('/api/listings', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'X-Session-Id': ensureSessionId(),
        'X-Conversation-Mode': getConversationMode?.() || 'none',
      }
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.error || 'Failed to fetch listings');
    }
    
    console.log('📊 获取房源数据成功:', result.count, '条记录');
    return result.data; // 返回房源数组
    
  } catch (error) {
    console.error('❌ 获取房源数据失败:', error);
    throw error;
  }
};

// 🆕 获取区域统计数据
// 🆕 支持两级区域查询的API函数
export const fetchDistrictStats = async (params: any = {}) => {
  try {
    // 🔍 构建查询参数
    const searchParams = new URLSearchParams();
    
    // 根据会话模式控制是否包含预算过滤（agent 模式下不带价格过滤）
    const mode = getConversationMode?.() || 'none';
    const includePriceFilters = mode !== 'agent';

    // 🆕 添加区域名称参数（核心新功能）
    if (params.district_name && params.district_name.trim()) {
      searchParams.append('district_name', params.district_name.trim());
    }
    
    // 添加其他筛选参数
    if (includePriceFilters && params.price_min != null) searchParams.append('price_min', params.price_min);
    if (includePriceFilters && params.price_max != null) searchParams.append('price_max', params.price_max);
    if (params.room_type) searchParams.append('room_type', params.room_type);
    if (params.min_reviews > 0) searchParams.append('min_reviews', params.min_reviews);
    
    // 🌐 构建完整URL
    const url = searchParams.toString() 
      ? `/heatmap/districts?${searchParams.toString()}`
      : '/heatmap/districts';
    
    console.log('🔍 请求区域数据:', url, params.district_name ? '(小社区层级)' : '(大行政区域层级)', { mode, includePriceFilters });
    
    // 📡 发送API请求
    const result: any = await api.get(url);
    
    // ✅ 检查响应格式
    if (!result.success) {
      throw new Error(result.error || 'Failed to fetch district stats');
    }
    
    // 🎯 返回增强的数据结构
    return {
      areas: result.data.areas || result.data.districts || [],  // 兼容新旧字段名
      districts: result.data.districts || result.data.areas || [],  // 向后兼容
      query_level: result.data.query_level || 'neighbourhood_group',  // 🆕 查询层级
      parent_district: result.data.parent_district,  // 🆕 上级区域
      summary: result.data.summary || {}
    };
    
  } catch (error) {
    console.error('❌ 获取区域统计失败:', error);
    throw error;
  }
};

// 🆕 专门获取大行政区域的函数
export const fetchAdministrativeDistricts = async (filters: any = {}) => {
  console.log('🏛️ 获取12个大行政区域统计');
  return await fetchDistrictStats({
    ...filters,
    // 不传district_name，获取所有大行政区域
  });
};

// 🆕 专门获取指定大区域下小社区的函数
export const fetchNeighbourhoods = async (districtName: string, filters: any = {}) => {
  console.log('🏘️ 获取小社区统计:', districtName);
  return await fetchDistrictStats({
    ...filters,
    district_name: districtName  // 传入大区域名称
  });
};

// 📊 额外：获取统计摘要的独立函数
export const fetchDistrictSummary = async (params: any = {}) => {
  try {
    const result = await fetchDistrictStats(params);
    return result.summary; // 只返回摘要数据
  } catch (error) {
    console.error('❌ 获取摘要数据失败:', error);
    return null;
  }
};

export const fetchMapMarkers = async (params: any) => {
  try {
    console.log('🔍 请求标记数据:', params);
    
    // 🆕 使用axios发送请求
    const mode = getConversationMode?.() || 'none';
    const includePriceFilters = mode !== 'agent';
    const requestParams = {
      level: params.level,
      ...(params.district_name && { district_name: params.district_name }),
      ...(includePriceFilters && params.price_min !== null && params.price_min !== undefined && { price_min: params.price_min }),
      ...(includePriceFilters && params.price_max !== null && params.price_max !== undefined && { price_max: params.price_max }),
      ...(params.room_type && { room_type: params.room_type }),
      ...(params.min_reviews && { min_reviews: params.min_reviews }),
    } as any;
    console.log('🧭 会话模式与请求参数:', { mode, includePriceFilters, requestParams });
    const response = await api.get('/map-markers', { params: requestParams });

    console.log('✅ 标记数据响应:', response);
    return response as any;
    
  } catch (error: any) {
    console.error('❌ 获取标记数据失败:', error);
    
    // 🔧 更详细的错误处理
    if (error.response) {
      // 服务器响应了错误状态码
      console.error('📨 错误响应状态:', error.response.status);
      console.error('📨 错误响应数据:', error.response.data);
      throw new Error(`API Error: ${error.response.status} - ${error.response.data?.message || '未知错误'}`);
    } else if (error.request) {
      // 请求发送了但没有收到响应
      console.error('📨 网络错误:', error.request);
      throw new Error('网络连接失败，请检查后端服务是否正常运行');
    } else {
      // 其他错误
      console.error('📨 请求配置错误:', error.message);
      throw new Error(`请求错误: ${error.message}`);
    }
  }
};

/**
 * Send user selection of a dimension (neighbourhood_group | neighbourhood | room_type)
 */
export const sendUserSelection = async (
  level: 'neighbourhood_group' | 'neighbourhood' | 'room_type',
  name: string,
  sessionId?: string
): Promise<any> => {
  try {
    const response = await api.get('/user/selection', {
      params: {
        level,
        name,
        ...(sessionId ? { session_id: sessionId } : {})
      }
    });
    return response;
  } catch (error) {
    console.error('Failed to send user selection:', error);
    throw error;
  }
};

/**
 * 获取区域中心坐标
 * @param {string} districtName - 区域名称
 * @returns {Promise<Object>} 坐标信息
 */
export const fetchDistrictCenter = async (districtName: string) => {
  try {
    const response = await fetch(`/district-center/${encodeURIComponent(districtName)}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
    
  } catch (error) {
    console.error('❌ 获取区域坐标失败:', error);
    throw error;
  }
};




/**
 * 🔹 获取价格分布统计
 * @param level  'district' | 'neighbourhood'
 * @param name   区域名称（大区传 'ALL' 或 ''）
 */
export const fetchPriceStats = async (
  level: 'district' | 'neighbourhood',
  name: string,
  priceMin = 0,
  priceMax = 9999
) => {
  try {
    // 后端 chart-data 接口，type=price_distribution
    const params: any = {
      type: 'price_distribution',
      min_price: priceMin,
      max_price: priceMax,
    };
    if (level === 'district') {
      params.neighbourhood_group = name !== 'ALL' ? name : undefined;
    } else {
      params.neighbourhood = name;
    }
    const response = await api.get('/chart-data', { params });
    return response;
  } catch (error) {
    console.error('❌ fetchPriceStats error:', error);
    throw error;
  }
};

/**
 * 🔹 获取房型占比统计
 * @param level  'district' | 'neighbourhood'
 * @param name   区域名称
 */
export const fetchRoomTypeStats = async (
  level: 'district' | 'neighbourhood',
  name: string,
  priceMin?: number,
  priceMax?: number
) => {
  try {
    // 后端 chart-data 接口，type=room_type_comparison
    const params: any = {
      type: 'room_type_comparison',
      ...(priceMin != null && { min_price: priceMin }),
      ...(priceMax != null && { max_price: priceMax }),
    };
    if (level === 'district') {
      params.neighbourhood_group = name !== 'ALL' ? name : undefined;
    } else {
      params.neighbourhood = name;
    }
    const response = await api.get('/chart-data', { params });
    return response;
  } catch (error) {
    console.error('❌ fetchRoomTypeStats error:', error);
    throw error;
  }
};

/**
 * 🔹 获取评论数量分布（按区间）的分析柱状图
 * @param level  'district' | 'neighbourhood'
 * @param name   区域名称
 */
export const fetchReviewStats = async (
  level: 'district' | 'neighbourhood',
  name: string
) => {
  try {
    // 后端 chart-data 接口，type=reviews_analysis
    const params: any = { type: 'reviews_analysis' };
    if (level === 'district') {
      params.neighbourhood_group = name !== 'ALL' ? name : undefined;
    } else {
      params.neighbourhood = name;
    }
    const response = await api.get('/chart-data', { params });
    return response;
  } catch (error) {
    console.error('❌ fetchReviewStats error:', error);
    throw error;
  }
};

/**
 * 🔹 获取房东房源数量分析（scatter）
 * @param level  'district' | 'neighbourhood'
 */
export const fetchHostStats = async (
  level: 'district' | 'neighbourhood',
  name: string
) => {
  try {
    // 后端 chart-data 接口，type=host_analysis
    const params: any = { type: 'host_analysis' };
    if (level === 'district') {
      params.neighbourhood_group = name !== 'ALL' ? name : undefined;
    } else {
      params.neighbourhood = name;
    }
    const response = await api.get('/chart-data', { params });
    return response;
  } catch (error) {
    console.error('❌ fetchHostStats error:', error);
    throw error;
  }
};

/**
 * 🔹 获取评论数量分布（分区间/也可做时间序列，如果后端支持）
 * @param level  'district' | 'neighbourhood'
 * @param name   区域名称
 */
export const fetchReviewTimeSeries = async (
  level: 'district' | 'neighbourhood',
  name: string
) => {
  try {
    // 如果后端提供真正的时间序列接口，保持此函数以便切换；暂用 reviews_analysis 兜底
    const params: any = { type: 'reviews_analysis' };
    if (level === 'district') {
      params.neighbourhood_group = name !== 'ALL' ? name : undefined;
    } else {
      params.neighbourhood = name;
    }
    const response = await api.get('/chart-data', { params });
    return response;
  } catch (error) {
    console.error('❌ fetchReviewTimeSeries error:', error);
    throw error;
  }
};

export const fetchMapDistribution = async (level: string, name: string) => {
  const res = await api.get('/stats/map_distribution', { params: { level, name } })
  return res
}
export const fetchSquareDistribution = async (level: string, name: string) => {
  const res = await api.get('/stats/square_distribution', { params: { level, name } })
  return res as any
}


/**
 * 获取评论概览：总评论数 / 平均情感得分 / 去重用户数 / 聚类簇数
 */
export async function fetchCommentsSummary(
  level: 'district' | 'neighbourhood',
  groupName: string
): Promise<{
  totalComments: number
  avgSentiment: number
  uniqueUsers: number
  clusters: number
}> {
  const res = await axios.get('/comments/summary', {
    params: { level, name: groupName }
  })
  return res.data
}
/**
 * 获取评论关键词词云数据：[{ word, count }, …]
 */
export async function fetchCommentsWordCloud(
  level: 'district' | 'neighbourhood',
  groupName: string
): Promise<Array<{ word: string; count: number }>> {
  const res = await axios.get('/comments/wordcloud', {
    params: { level, name: groupName }
  })
  return res.data
}
/**
 * 获取情感分布：{ positive, neutral, negative }
 */
export async function fetchCommentsSentiment(
  level: 'district' | 'neighbourhood',
  groupName: string
): Promise<{
  positive: number
  neutral: number
  negative: number
}> {
  const res = await axios.get('/comments/sentiment', {
    params: { level, name: groupName }
  })
  return res.data
}
/**
 * 获取用户聚类结果：[{ x, y, clusterId }, …]
 */
export async function fetchUserClusters(
  level: 'district' | 'neighbourhood',
  groupName: string
): Promise<Array<{ x: number; y: number; clusterId: string }>> {
  const res = await axios.get('/comments/user_clusters', {
    params: { level, name: groupName }
  })
  return res.data
}

// 点击区域确定通知后端的接口
export const selectArea = async( level: string , groupName: string) =>{
  const res = await api.get('/user/selection', {
    params: { level, name: groupName }
  })
  console.log(res)
  return res
  // return axios.post('/api/user/selection', selection)
}

// 🔥 获取热力图原始点
export const fetchHeatPoints = async (params: any) => {
  try {
    const res = await api.get('/heat-points', {
      params: {
        level: params.level,
        district_name: params.district_name,
        price_min: params.price_min ?? undefined,
        price_max: params.price_max ?? undefined,
        room_type: params.room_type ?? undefined,
        min_reviews: params.min_reviews ?? undefined,
        weight_by: params.weight_by ?? 'uniform',
        max_points: params.max_points ?? 20000,
        format: params.format ?? 'json'
      }
    });
    return res as any;
  } catch (e: any) {
    console.error('❌ fetchHeatPoints failed', e);
    throw e;
  }
}

// 🆕 New word cloud APIs (do not use legacy comments/* endpoints)
export interface WordCloudQueryParams {
  level: 'district' | 'neighbourhood';
  name: string; // district or neighbourhood name
  top_n?: number; // 10-100
  metric?: 'frequency' | 'tfidf' | 'pmi';
}

export async function fetchWordCloudV2(params: WordCloudQueryParams): Promise<Array<{ text: string; freq?: number; tfidf?: number; pmi?: number; sentiment?: { pos?: number; neu?: number; neg?: number; conf?: number }; examples?: any[] }>> {
  const res = await api.get('/comments/wordcloud_v2', {
    params: {
      level: params.level,
      name: params.name,
      top_n: params.top_n,
      metric: params.metric
    }
  });
  return res as any;
}

export async function fetchWordCloudSentimentV2(params: { level: 'district' | 'neighbourhood'; name: string }): Promise<{ positive: number; neutral: number; negative: number }> {
  const res = await api.get('/comments/sentiment_v2', {
    params: {
      level: params.level,
      name: params.name
    }
  });
  return res as any;
}

// 🆕 Fetch areas that match a given budget range
export const fetchAreasByBudget = async (price_min: number, price_max: number): Promise<{ areas: Array<{ name: string; listing_count: number; avg_price: number; median_price: number; p25_price?: number; p75_price?: number; distance_to_center?: number }>; meta: any }> => {
  // In-flight dedup to avoid duplicate requests in StrictMode or concurrent calls
  const key = `by_budget:${price_min}-${price_max}`;
  const map = (fetchAreasByBudget as any)._inflight as Map<string, Promise<any>> || new Map<string, Promise<any>>();
  (fetchAreasByBudget as any)._inflight = map;
  const existing = map.get(key);
  if (existing) return existing as any;
  const p = api.get('/areas/by_budget', { params: { price_min, price_max } })
    .then((res: any) => res)
    .finally(() => { map.delete(key); });
  map.set(key, p);
  return p as any;
};

export interface ReviewsOverviewResponse {
  scope: {
    area: string | null;
    budget_min: number | null;
    budget_max: number | null;
    listings_in_scope: number;
    reviews_count: number;
    is_citywide: boolean;
  };
  sentiment: {
    positive: number;
    neutral: number;
    negative: number;
  };
  top_phrases: Array<{ text: string; count: number }>;
  matched_preferences?: string[];
}

export const fetchReviewsOverview = async (
  params: { area?: string | null; bmin?: number | null; bmax?: number | null; top_n?: number; min_count?: number; recent_months?: number } = {}
): Promise<ReviewsOverviewResponse> => {
  const query: any = {};
  if (params.area != null && String(params.area).trim() !== '') {
    query.area = params.area;
  }
  if (params.bmin != null) query.bmin = params.bmin;
  if (params.bmax != null) query.bmax = params.bmax;
  if (params.top_n != null) query.top_n = params.top_n;
  if (params.min_count != null) query.min_count = params.min_count;
  if (params.recent_months != null) query.recent_months = params.recent_months;

  const res: any = await api.get('/reviews/overview', { params: query });
  return res as ReviewsOverviewResponse;
};

export interface ReviewsSentimentResponse {
  positive: number;
  neutral: number;
  negative: number;
  scope?: {
    area?: string | null;
    budget_min?: number | null;
    budget_max?: number | null;
    reviews_count?: number;
    listings_in_scope?: number;
  }
}

export const fetchReviewsSentiment = async (
  params: { area?: string | null; bmin?: number | null; bmax?: number | null; recent_months?: number; room_type?: string | null; min_reviews?: number | null }
): Promise<ReviewsSentimentResponse> => {
  const query: any = {};
  if (params?.area != null && String(params.area).trim() !== '' && params.area !== 'ALL') query.area = params.area;
  if (params?.bmin != null) query.bmin = params.bmin;
  if (params?.bmax != null) query.bmax = params.bmax;
  if (params?.recent_months != null) query.recent_months = params.recent_months;
  if (params?.room_type != null && String(params.room_type).trim() !== '') query.room_type = params.room_type;
  if (params?.min_reviews != null) query.min_reviews = params.min_reviews;
  const raw: any = await api.get('/reviews/sentiment', { params: query });

  // Normalize backend shapes:
  // Case A: { scope: {...}, sentiment: { positive, neutral, negative } }
  if (raw && typeof raw === 'object' && 'sentiment' in raw) {
    const s = (raw as any).sentiment || {};
    return {
      positive: Number(s.positive ?? s.pos ?? 0) || 0,
      neutral: Number(s.neutral ?? s.neu ?? 0) || 0,
      negative: Number(s.negative ?? s.neg ?? 0) || 0,
      scope: (raw as any).scope,
    } as ReviewsSentimentResponse;
  }

  // Case B: flat already { positive, neutral, negative, scope? }
  if (raw && typeof raw === 'object' && 'positive' in raw && 'neutral' in raw && 'negative' in raw) {
    return {
      positive: Number((raw as any).positive) || 0,
      neutral: Number((raw as any).neutral) || 0,
      negative: Number((raw as any).negative) || 0,
      scope: (raw as any).scope,
    } as ReviewsSentimentResponse;
  }

  // Fallback
  return {
    positive: 0,
    neutral: 0,
    negative: 0,
    scope: (raw as any)?.scope,
  } as ReviewsSentimentResponse;
};

export interface ReviewsTopKeywordsResponse {
  top_phrases: Array<{ text: string; count: number }>;
  matched_preferences?: string[];
  scope?: {
    area?: string | null;
    budget_min?: number | null;
    budget_max?: number | null;
    reviews_count?: number;
    listings_in_scope?: number;
    reviews_used?: number;
  };
}

export const fetchReviewsTopKeywords = async (
  params: { area?: string | null; bmin?: number | null; bmax?: number | null; top_n?: number; min_count?: number; recent_months?: number; sample_size?: number; sample_strategy?: string; room_type?: string | null; min_reviews?: number | null }
): Promise<ReviewsTopKeywordsResponse> => {
  const query: any = {};
  if (params?.area != null && String(params.area).trim() !== '' && params.area !== 'ALL') query.area = params.area;
  if (params?.bmin != null) query.bmin = params.bmin;
  if (params?.bmax != null) query.bmax = params.bmax;
  if (params?.top_n != null) query.top_n = params.top_n;
  if (params?.min_count != null) query.min_count = params.min_count;
  if (params?.recent_months != null) query.recent_months = params.recent_months;
  if (params?.sample_size != null) query.sample_size = params.sample_size;
  if (params?.sample_strategy != null) query.sample_strategy = params.sample_strategy;
  if (params?.room_type != null && String(params.room_type).trim() !== '') query.room_type = params.room_type;
  if (params?.min_reviews != null) query.min_reviews = params.min_reviews;
  const res: any = await api.get('/reviews/top_keywords', { params: query, timeout: 180000 });
  return res as ReviewsTopKeywordsResponse;
};

export interface RecentDemand30dResponse {
  level: 'district' | 'neighbourhood' | 'city';
  area?: string;
  n: number;
  active_share: number; // 0..1
  median_l30d_active: number | null;
  l30d_per_100: number;
  label: 'Low' | 'Medium' | 'High' | 'Sparse';
  sparse: boolean;
}

export const fetchRecentDemand30d = async (
  level: 'district' | 'neighbourhood' | 'city',
  name?: string
): Promise<RecentDemand30dResponse> => {
  const res: any = await api.get('/recent_demand_30d', {
    params: {
      level,
      ...(name ? { name } : {})
    }
  });
  // 兼容后端返回 { items: [{...}], level, parent }
  if (res && Array.isArray(res.items) && res.items.length > 0) {
    const it = res.items[0] || {};
    const n = Number(it.listing_count ?? it.n ?? 0) || 0;
    return {
      level,
      area: String(it.name ?? res.parent ?? name ?? ''),
      n,
      active_share: Number(it.active_share ?? 0) || 0,
      median_l30d_active: it.median_l30d_active != null ? Number(it.median_l30d_active) : null,
      l30d_per_100: Number(it.l30d_per_100 ?? 0) || 0,
      label: (it.label as any) || 'Low',
      sparse: n < 50
    };
  }
  return res as RecentDemand30dResponse;
};