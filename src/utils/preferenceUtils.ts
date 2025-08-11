// preferenceUtils.js - 修正版：正确处理后端所有关键词类型

// Define interfaces for our data structures
interface Preferences {
  price_min?: number;
  price_max?: number;
  room_type?: string;
  neighbourhood?: string;
  neighbourhood_group?: string;
  minimum_nights?: number;
  amenities_keywords?: string[];
  location_keywords?: string[];
  comfort_keywords?: string[];
  min_reviews?: number;
  completeness_score?: number;
  preference_count?: number;
}

interface Dimension {
  key: string;
  value: string;
  icon: string;
}

interface DecisionCard {
  completeness_score?: number;
  preference_count?: number;
  preferences?: Preferences;
  should_update?: boolean;
}

interface FollowupInfo {
  ready_for_recommendation?: boolean;
}

interface BackendResponse {
  decision_card?: DecisionCard;
  followup_info?: FollowupInfo;
}

interface DebugInfo {
  originalResponse?: any;
  newDimensions?: Dimension[];
  generatedUserCare?: Dimension | null;
}

/**
 * 🎯 将后端偏好格式转换为前端selectedDimensions格式 - 修正版
 * @param {Preferences} preferences - 后端返回的偏好对象
 * @returns {Dimension[]} 前端格式的偏好数组
 */
export const convertPreferencesToDimensions = (preferences: Preferences): Dimension[] => {
  if (!preferences) return [];
  
  const dimensions: Dimension[] = [];
  
  // 🎯 价格相关处理 - 统一使用"Budget"作为key
  if (preferences.price_min && preferences.price_max) {
    dimensions.push({ 
      key: "Budget", 
      value: `€${preferences.price_min}-${preferences.price_max}`,
      icon: "💰"
    });
  } else if (preferences.price_max) {
    dimensions.push({ 
      key: "Budget", 
      value: `Under €${preferences.price_max}`,
      icon: "💰"
    });
  } else if (preferences.price_min) {
    dimensions.push({ 
      key: "Budget", 
      value: `From €${preferences.price_min}`,
      icon: "💰"
    });
  }

  // 🎯 房间类型
  if (preferences.room_type) {
    const roomTypeIcons: Record<string, string> = {
      "Private room": "🚪",
      "Entire home/apt": "🏠",
      "Shared room": "👥",
      "Hotel room": "🏨"
    };
    
    dimensions.push({ 
      key: "Room Type", 
      value: preferences.room_type,
      icon: roomTypeIcons[preferences.room_type] || "🏠"
    });
  }

  // 🎯 地理位置处理 - 优先处理neighbourhood，然后处理location_keywords
  if (preferences.neighbourhood) {
    // 如果有具体社区，优先使用它
    dimensions.push({ 
      key: "Location", 
      value: preferences.neighbourhood,
      icon: "📍"
    });
  } else if (preferences.neighbourhood_group) {
    // 其次使用区域组名
    dimensions.push({ 
      key: "Location", 
      value: preferences.neighbourhood_group,
      icon: "🗺️"
    });
  } else if (preferences.location_keywords && preferences.location_keywords.length > 0) {
    // 如果没有具体地址但有位置关键词，把位置关键词也作为Location维度
    dimensions.push({ 
      key: "Location", 
      value: preferences.location_keywords.join(", "),
      icon: "📍"
    });
  }

  // 🎯 停留天数
  if (preferences.minimum_nights) {
    dimensions.push({ 
      key: "Stay Duration", 
      value: `${preferences.minimum_nights} day${preferences.minimum_nights > 1 ? 's' : ''}`,
      icon: "📅"
    });
  }

  // 🎯 设施关键词 - 单独显示（不放在User Care中）
  if (preferences.amenities_keywords && preferences.amenities_keywords.length > 0) {
    dimensions.push({ 
      key: "Amenities", 
      value: preferences.amenities_keywords.slice(0, 3).join(", "), // 最多显示3个
      icon: "🛠️"
    });
  }

  // 🎯 最小评论数（热门程度）
  if (preferences.min_reviews && preferences.min_reviews > 0) {
    dimensions.push({ 
      key: "Popularity", 
      value: `${preferences.min_reviews}+ reviews`,
      icon: "⭐"
    });
  }

  return dimensions;
};

/**
 * 🎯 新增：动态生成User Care内容
 * @param {Preferences} preferences - 偏好对象
 * @returns {Dimension|null} User Care对象或null
 */
export const generateUserCare = (preferences: Preferences): Dimension | null => {
  if (!preferences) return null;
  
  const careItems: string[] = [];
  
  // 🎯 收集所有类型的特殊需求关键词
  const allKeywords = [
    ...(preferences.amenities_keywords || []),
    ...(preferences.location_keywords || []),
    ...(preferences.comfort_keywords || [])
  ];
  
  console.log("🔍 生成User Care，所有关键词:", allKeywords);
  
  // 🎯 分类特殊需求
  const comfortNeeds = allKeywords.filter(keyword => 
    ['quiet', 'clean', 'comfortable', 'spacious', 'bright', 'cozy', 'peaceful'].includes(keyword.toLowerCase())
  );
  
  const connectivityNeeds = allKeywords.filter(keyword => 
    ['wifi', 'internet', 'workspace', 'desk'].includes(keyword.toLowerCase())
  );
  
  const serviceNeeds = allKeywords.filter(keyword => 
    ['fast response', 'responsive', 'quick', 'asap', 'immediate'].some(service => 
      keyword.toLowerCase().includes(service)
    )
  );
  
  const accessibilityNeeds = allKeywords.filter(keyword => 
    ['accessible', 'elevator', 'ground floor', 'disabled access'].includes(keyword.toLowerCase())
  );
  
  // 🎯 生成关怀项目
  if (comfortNeeds.length > 0) {
    careItems.push(`🤫 ${comfortNeeds.slice(0, 2).join(', ')} environment`);
  }
  
  if (connectivityNeeds.length > 0) {
    careItems.push(`💻 ${connectivityNeeds.slice(0, 2).join(', ')} connectivity`);
  }
  
  if (serviceNeeds.length > 0) {
    careItems.push(`⚡ responsive host service`);
  }
  
  if (accessibilityNeeds.length > 0) {
    careItems.push(`♿ ${accessibilityNeeds.slice(0, 2).join(', ')} features`);
  }
  
  // 🎯 根据住宿天数生成建议
  if (preferences.minimum_nights && preferences.minimum_nights >= 7) {
    careItems.push('📅 extended stay comfort');
  }
  
  // 🎯 根据预算生成建议
  if (preferences.price_max && preferences.price_max > 200) {
    careItems.push('✨ premium service expected');
  }
  
  // 🎯 特殊处理：如果没有具体的关怀项，但有关键词，显示通用关怀
  if (careItems.length === 0 && allKeywords.length > 0) {
    careItems.push(`💝 special needs: ${allKeywords.slice(0, 2).join(', ')}`);
  }
  
  if (careItems.length === 0) {
    return {
      key: "User Care",
      value: "💡 Customizable preferences",
      icon: "💝"
    };
  }
  
  console.log("✅ 生成的User Care项目:", careItems);
  
  return {
    key: "User Care",
    value: careItems.slice(0, 2).join(' • '), // 最多显示2个关怀项
    icon: "💝"
  };
};

/**
 * 合并偏好维度，避免重复，新的覆盖旧的 - 修正版
 * @param {Dimension[]} existingDimensions - 现有的偏好维度
 * @param {Dimension[]} newDimensions - 新的偏好维度
 * @returns {Dimension[]} 合并后的偏好维度
 */
export const mergePreferenceDimensions = (existingDimensions: Dimension[], newDimensions: Dimension[]): Dimension[] => {
  // 创建一个Map来存储最新的偏好，key为维度名称
  const dimensionMap = new Map<string, Dimension>();
  
  // 🎯 定义字段名映射关系（处理同义字段）
  const fieldMappings: Record<string, string> = {
    "Price": "Budget",        // Price -> Budget
    "Budget": "Budget",       // Budget -> Budget
    "Room Type": "Room Type",
    "Location": "Location",
    "Stay Duration": "Stay Duration",
    "Amenities": "Amenities",
    "Location Preferences": "Location Preferences",
    "User Care": "User Care",
    "Experience": "User Care", // Experience也映射到User Care
    "Popularity": "Popularity"
  };
  
  // 先添加现有的偏好，使用标准化的key
  existingDimensions.forEach(dim => {
    const standardKey = fieldMappings[dim.key] || dim.key;
    // 只添加有意义的字段，跳过默认的User Care
    if (standardKey !== "User Care" || (dim.value && !dim.value.includes("💡 Customizable preferences"))) {
      dimensionMap.set(standardKey, {
        ...dim,
        key: standardKey
      });
    }
  });
  
  // 用新偏好覆盖同名的旧偏好
  newDimensions.forEach(dim => {
    const standardKey = fieldMappings[dim.key] || dim.key;
    dimensionMap.set(standardKey, {
      ...dim,
      key: standardKey
    });
  });
  
  return Array.from(dimensionMap.values());
};

/**
 * 根据偏好数据生成摘要文本
 * @param {Preferences} preferences - 偏好对象
 * @returns {string} 摘要文本
 */
export const generatePreferenceSummary = (preferences: Preferences): string => {
  if (!preferences) return "No preferences set";
  
  const parts: string[] = [];
  
  // 预算
  if (preferences.price_min && preferences.price_max) {
    parts.push(`€${preferences.price_min}-${preferences.price_max}`);
  } else if (preferences.price_max) {
    parts.push(`under €${preferences.price_max}`);
  }
  
  // 房间类型
  if (preferences.room_type) {
    parts.push(preferences.room_type.toLowerCase());
  }
  
  // 位置
  if (preferences.neighbourhood) {
    parts.push(`in ${preferences.neighbourhood}`);
  } else if (preferences.neighbourhood_group) {
    parts.push(`in ${preferences.neighbourhood_group}`);
  }
  
  // 停留时间
  if (preferences.minimum_nights) {
    parts.push(`${preferences.minimum_nights} days`);
  }
  
  // 🎯 新增：所有类型的特殊需求
  const allKeywords = [
    ...(preferences.amenities_keywords || []),
    ...(preferences.location_keywords || []),
    ...(preferences.comfort_keywords || [])
  ];
  
  if (allKeywords.length > 0) {
    parts.push(`needs: ${allKeywords.slice(0, 2).join(", ")}`);
  }
  
  return parts.length > 0 ? parts.join(" • ") : "Basic preferences";
};

/**
 * 计算偏好完整度百分比
 * @param {DecisionCard} decisionCard - 决策卡片对象
 * @returns {number} 完整度百分比 (0-100)
 */
export const calculateCompletenessPercentage = (decisionCard: DecisionCard): number => {
  if (!decisionCard || typeof decisionCard.completeness_score !== 'number') {
    return 0;
  }
  
  return Math.round(decisionCard.completeness_score * 100);
};

/**
 * 判断是否应该显示推荐按钮
 * @param {DecisionCard} decisionCard - 决策卡片对象
 * @param {FollowupInfo} followupInfo - 追问信息对象
 * @returns {boolean} 是否显示推荐按钮
 */
export const shouldShowRecommendationButton = (decisionCard: DecisionCard, followupInfo: FollowupInfo): boolean => {
  // 检查追问信息
  if (followupInfo?.ready_for_recommendation) {
    return true;
  }
  
  // 检查决策卡片完整度
  if (decisionCard?.completeness_score && decisionCard.completeness_score >= 0.8) {
    return true;
  }
  
  // 检查偏好数量
  if (decisionCard?.preference_count && decisionCard.preference_count >= 3) {
    return true;
  }
  
  return false;
};

/**
 * 格式化缺失的偏好信息
 * @param {string[]} missingPreferences - 缺失的偏好数组
 * @returns {string} 格式化的缺失偏好文本
 */
export const formatMissingPreferences = (missingPreferences: string[]): string => {
  if (!missingPreferences || missingPreferences.length === 0) {
    return "All key preferences provided";
  }
  
  if (missingPreferences.length === 1) {
    return `Still need: ${missingPreferences[0]}`;
  }
  
  const last = missingPreferences.pop();
  return `Still need: ${missingPreferences.join(", ")} and ${last}`;
};

/**
 * 🎯 新增：准备推荐请求的数据格式
 * @param {Dimension[]} selectedDimensions - 前端选择的维度
 * @param {number} topK - 推荐数量
 * @returns {Object} 推荐请求数据
 */
export const prepareRecommendationRequest = (selectedDimensions: Dimension[], topK = 5): { selectedDimensions: { key: string, value: string }[], top_k: number } => {
  // 将前端format转换为后端期望的format
  const dimensionsForBackend = selectedDimensions
    .filter(dim => dim.key !== "User Care" || !dim.value.includes("💡 Customizable preferences"))
    .map(dim => ({
      key: dim.key,
      value: dim.value
    }));
  
  console.log("🎯 准备推荐请求数据:", {
    selectedDimensions: dimensionsForBackend,
    top_k: topK
  });
  
  return {
    selectedDimensions: dimensionsForBackend,
    top_k: topK
  };
};

interface HandleBackendResponseResult {
  updated: boolean;
  showRecommendBtn: boolean;
  summary: string;
  userCareUpdated: boolean;
  debugInfo: DebugInfo;
}

/**
 * 🎯 处理后端响应的主要处理函数 - 修正版，正确处理User Care
 * @param {BackendResponse} response - 后端响应
 * @param {Function} setSelectedDimensions - 更新偏好维度的函数
 * @returns {HandleBackendResponseResult} 处理结果
 */
export const handleBackendResponse = (response: BackendResponse, setSelectedDimensions: (fn: (prev: Dimension[]) => Dimension[]) => void): HandleBackendResponseResult => {
  const result: HandleBackendResponseResult = {
    updated: false,
    showRecommendBtn: false,
    summary: "",
    userCareUpdated: false,
    debugInfo: {}
  };
  
  // 🎯 调试：记录原始响应
  result.debugInfo.originalResponse = {
    hasDecisionCard: !!response?.decision_card,
    shouldUpdate: response?.decision_card?.should_update,
    preferences: response?.decision_card?.preferences,
    followupInfo: response?.followup_info
  };
  
  console.log("🔍 处理后端响应:", result.debugInfo.originalResponse);
  
  // 处理决策卡片更新
  if (response?.decision_card?.should_update && response?.decision_card?.preferences) {
    console.log("🎯 开始处理决策卡片更新:", response.decision_card.preferences);
    
    // 转换基础偏好（不包括User Care）
    const newDimensions = convertPreferencesToDimensions(response.decision_card.preferences);
    
    // 🎯 生成动态User Care
    const userCare = generateUserCare(response.decision_card.preferences);
    
    result.debugInfo.newDimensions = newDimensions;
    result.debugInfo.generatedUserCare = userCare;
    
    setSelectedDimensions(prevDimensions => {
      console.log("🔄 当前偏好维度:", prevDimensions);
      
      // 先合并基础偏好（排除User Care）
      const merged = mergePreferenceDimensions(prevDimensions, newDimensions);
      
      // 🎯 然后添加或更新User Care
      const finalDimensions = [...merged];
      
      if (userCare) {
        // 移除旧的User Care
        const withoutOldUserCare = finalDimensions.filter(dim => 
          dim.key !== "User Care"
        );
        
        // 添加新的User Care
        withoutOldUserCare.push(userCare);
        
        console.log("🎯 User Care已更新:", userCare);
        result.userCareUpdated = true;
        
        const final = withoutOldUserCare;
        console.log("✅ 最终偏好维度:", final);
        return final;
      } else {
        // 如果没有生成User Care，添加默认的
        const hasUserCare = finalDimensions.some(dim => dim.key === "User Care");
        if (!hasUserCare) {
          finalDimensions.push({
            key: "User Care",
            value: "💡 Customizable preferences",
            icon: "💝"
          });
        }
        console.log("✅ 最终偏好维度（含默认User Care）:", finalDimensions);
        return finalDimensions;
      }
    });
    
    result.updated = true;
    result.summary = generatePreferenceSummary(response.decision_card.preferences);
    
    console.log("🎯 决策卡片已更新:", result.summary);
  }
  
  // 检查是否应该显示推荐按钮
  const shouldShow = shouldShowRecommendationButton(
    response?.decision_card || { completeness_score: 0, preference_count: 0 }, 
    response?.followup_info || {}
  );
  
  if (shouldShow) {
    result.showRecommendBtn = true;
    console.log("✅ 显示推荐按钮");
  }
  
  return result;
};