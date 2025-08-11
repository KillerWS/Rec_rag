import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:5000/api', // 🚀 替换成你的后端地址
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error("API 请求错误:", error);
    return Promise.reject(error);
  }
);

export default api;

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
      }
    });
    return res as any;  // 返回 { index_id }
  } catch (error) {
    console.error("Failed to prepare RAG context:", error);
    return null;
  }
};

export const fetchRAGAnswer = async (message: string, history: any[], indexId: string,  extraParams = {}) => {
  try {
    console.log(indexId)
    const response = await api.post('/rag_chat', {
      message,
      history: history,
      index_id: indexId,
      ...extraParams
    }, {
      headers: {
        'Content-Type': 'application/json'
      }
    });
    return response as any;
  } catch (error) {
    console.error("Failed to fetch RAG answer:", error);
    throw error;
  }
};


/**
 * 🔹 获取 Top-K 推荐项
 */
export interface Recommendation {
  id: string;
  name: string;
  price: number;
  room_type: string;
  neighbourhood: string;
  neighbourhood_group: string;
  availability_365: number;
  number_of_reviews: number;
  number_of_reviews_ltm: number;
  reviews_per_month: number;
  last_review: string;
  recommendation_score: number;
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
    console.log("Raw API response:", response);
    
    // Correctly access the data property of the axios response
    if (response && response.recommendations ) {
      console.log("Extracted data:", response.recommendations);
      return response.recommendations;
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
    
    // 🆕 添加区域名称参数（核心新功能）
    if (params.district_name && params.district_name.trim()) {
      searchParams.append('district_name', params.district_name.trim());
    }
    
    // 添加其他筛选参数
    if (params.price_min) searchParams.append('price_min', params.price_min);
    if (params.price_max) searchParams.append('price_max', params.price_max);
    if (params.room_type) searchParams.append('room_type', params.room_type);
    if (params.min_reviews > 0) searchParams.append('min_reviews', params.min_reviews);
    
    // 🌐 构建完整URL
    const url = searchParams.toString() 
      ? `/heatmap/districts?${searchParams.toString()}`
      : '/heatmap/districts';
    
    console.log('🔍 请求区域数据:', url, params.district_name ? '(小社区层级)' : '(大行政区域层级)');
    
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
    const response = await api.get('/map-markers', {
      params: {
        level: params.level,
        ...(params.district_name && { district_name: params.district_name }),
        ...(params.price_min !== null && params.price_min !== undefined && { price_min: params.price_min }),
        ...(params.price_max !== null && params.price_max !== undefined && { price_max: params.price_max }),
        ...(params.room_type && { room_type: params.room_type }),
        ...(params.min_reviews && { min_reviews: params.min_reviews }),
      }
    });

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
    // 后端 chart-data 接口，type=review_analysis
    const params: any = { type: 'review_analysis' };
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
    // 这里复用 review_analysis，后端 ChartDataGenerator._generate_review_analysis
    // 如果后端将来提供真正的时间序列，只要把 type 改为 'review_time_series' 即可
    const params: any = { type: 'review_analysis' };
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