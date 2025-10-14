import { useEffect, useState } from "react";
import { Descriptions, Button, Spin, message, Input, Select, Tag, InputNumber } from "antd";
import { CheckOutlined, UpOutlined, DownOutlined, InfoCircleOutlined, EditOutlined, EnvironmentOutlined } from "@ant-design/icons";
import { fetchRecommendations, Recommendation } from "../api/api";
import { CSSTransition } from "react-transition-group";
import "./FreeDecisionCard.css"; // Import animation styles

interface FreeDecisionCardProps {
  selectedDimensions: { key: string; value: string | string[] }[];
  onConfirm: (newRecommendations: Recommendation[]) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  mode?: "scripted" | "agent" | "none";
  onShowMap?: (mapData: any) => void; // Added for map component integration
}

interface Dimension {
  key: string;
  value: string | string[];
}

const FreeDecisionCard = ({
  selectedDimensions,
  onConfirm,
  isLoading,
  setIsLoading,
  //mode,
  onShowMap
}: FreeDecisionCardProps) => {
  // if (mode === "none") return null;

  const [hasChanged, setHasChanged] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  // const [hintVisible, setHintVisible] = useState(true);
  const [editableDimensions, setEditableDimensions] = useState<Dimension[]>([]);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  
  // Budget specific state
  const [budgetMin, setBudgetMin] = useState<number>(0);
  const [budgetMax, setBudgetMax] = useState<number>(0);
  
  // RoomType specific state
  const roomTypeOptions = ["Private room", "Entire home/apt", "Shared room", "Hotel room"];
  const [selectedRoomTypes, setSelectedRoomTypes] = useState<string[]>([]);
  // Stay Duration state
  const [stayNights, setStayNights] = useState<number | null>(null);

  // Listen to external "decisioncard:setDimensions" to update dimensions from other components (agent flow)
  useEffect(() => {
    const handler = (evt: Event) => {
      try {
        const anyEvt: any = evt as any;
        const dims: Array<{ key: string; value: string }> = anyEvt?.detail?.dimensions || (window as any)?.selectedDimensions || [];
        if (!Array.isArray(dims) || dims.length === 0) return;
        // Normalize: handle multiple Room Type values
        const nextEditable: Dimension[] = [];
        const roomTypes: string[] = [];
        dims.forEach((d) => {
          const key = String(d?.key || '').trim();
          const val = String(d?.value ?? '');
          if (!key) return;
          if (key.toLowerCase() === 'room type') {
            // accept CSV or single
            if (val.includes(',')) {
              val.split(',').map((s) => s.trim()).filter(Boolean).forEach((t) => roomTypes.push(t));
            } else if (val) {
              roomTypes.push(val);
            }
          } else {
            nextEditable.push({ key, value: val });
          }
        });
        roomTypes.forEach((rt) => nextEditable.push({ key: 'Room Type', value: rt }));

        // Update state
        setEditableDimensions(nextEditable);
        setHasChanged(true);

        // Sync budget controls if provided
        const budgetDim = nextEditable.find(dim => dim.key === 'Budget' || dim.key === 'Budget Range' || dim.key === 'Price');
        if (budgetDim) {
          const nums = (String(budgetDim.value).match(/\d+/g) || []).map((n) => Number(n));
          setBudgetMin(nums[0] ?? 0);
          setBudgetMax(nums[1] ?? 0);
        }
        // Sync room types
        setSelectedRoomTypes(roomTypes);
      } catch {}
    };
    window.addEventListener('decisioncard:setDimensions', handler as EventListener);
    return () => window.removeEventListener('decisioncard:setDimensions', handler as EventListener);
  }, []);

  useEffect(() => {
    if (selectedDimensions.length > 0) {
      setHasChanged(true);
      
      // 处理房型特殊情况：多个同key对象
      const roomTypeDimensions = selectedDimensions.filter(dim => dim.key === "Room Type");
      const otherDimensions = selectedDimensions.filter(dim => dim.key !== "Room Type");
      
      // 设置当前所选房型
      if (roomTypeDimensions.length > 0) {
        const roomTypes = roomTypeDimensions.map(dim => String(dim.value));
        setSelectedRoomTypes(roomTypes as string[]);
      } else {
        setSelectedRoomTypes([]);
      }
      
      // 合并普通维度和房型维度
      setEditableDimensions([...otherDimensions, ...roomTypeDimensions]);
      
      // Initialize budget values if budget/price dimension exists
      const budgetDim = selectedDimensions.find(dim => 
        dim.key === "Budget" || dim.key === "Budget Range" || dim.key === "Price"
      );
      if (budgetDim) {
        const [min, max] = String(budgetDim.value).replace(/€/g, "").split("-").map(val => parseInt(val.trim()));
        setBudgetMin(min || 0);
        setBudgetMax(max || 0);
      }
      // Initialize stay duration if exists (values may be like "3 days")
      const stayDim = selectedDimensions.find(dim => dim.key === "Stay Duration");
      if (stayDim) {
        const numeric = parseInt(String(stayDim.value).replace(/[^0-9]/g, ""), 10);
        setStayNights(Number.isFinite(numeric) ? numeric : null);
      } else {
        setStayNights(null);
      }
    }
  }, [selectedDimensions]);

  const handleConfirm = async () => {
    console.log("handleConfirm 执行");
    if (editableDimensions.length === 0) {
      message.warning("No dimensions to confirm");
      return;
    }
    
    // 过滤非Room Type维度，并获取原始维度
    const nonRoomTypeDimensions = editableDimensions.filter(dim => dim.key !== "Room Type");
    // 覆盖 Price/Budget 值，使用最新输入的 budgetMin/budgetMax，避免未 onBlur 时值不同步
    const adjustedNonRoomType = nonRoomTypeDimensions.map((dim) => {
      if (dim.key === "Price" || dim.key === "Budget" || dim.key === "Budget Range") {
        // Keep separate numeric controls but store value as "min-max" for compatibility
        return { ...dim, value: `${budgetMin}-${budgetMax}` } as Dimension;
      }
      if (dim.key === "Stay Duration") {
        const validNights = stayNights && stayNights > 0 ? stayNights : 1;
        return { ...dim, value: String(validNights) } as Dimension;
      }
      return dim;
    });
    
    // 获取当前选择的房型
    const currentRoomTypes = editableDimensions
      .filter(dim => dim.key === "Room Type")
      .map(dim => dim.value);
    
    // 构造API请求所需的维度数据
    const apiDimensions: { key: string; value: string }[] = adjustedNonRoomType.map(d => ({ key: d.key, value: String(d.value) }));
    
    // 只添加被选中的房型
    if (currentRoomTypes.length > 0) {
      apiDimensions.push({
        key: "Room Type",
        value: currentRoomTypes.join(", ")
      });
    }
    
    setIsLoading(true);
    try {
      console.log("apiDimensions", apiDimensions);
      const res = await fetchRecommendations({ selectedDimensions: apiDimensions, top_k: 5 });
      // 兼容两种返回形式：数组 或 { recommendations: [] }
      const list = Array.isArray(res)
        ? (res as any[])
        : ((((res as any)?.recommendations ?? []) as any[]));
      if (Array.isArray(list) && list.length >= 0) {
        console.log("----- DECISIONCARD got recommendations -----", { count: list.length });
        onConfirm(list as any);
        message.success("Recommendations updated");
        setHasChanged(false);
      } else {
        console.warn("----- DECISIONCARD no recommendations in response -----", res);
        message.warning("No recommendations received");
      }
    } catch (err) {
      message.error("Failed to fetch recommendations");
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleCollapse = () => {
    if (collapsed === true) {
      // setHintVisible(false); // This line was removed
    }
    setCollapsed(!collapsed);
  };

  const updateDimension = (key: string, newValue: string) => {
    // 对于非Room Type维度，直接更新
    if (key !== "Room Type") {
      const newDimensions = editableDimensions.map(dim => 
        dim.key === key ? { ...dim, value: newValue } : dim
      );
      setEditableDimensions(newDimensions);
      setHasChanged(true);
      message.info(`Updated ${key} preferences`);
      return;
    }
    
    // 这里不应该发生，Room Type通过handleRoomTypeChange处理
  };

  const handleRoomTypeChange = (selectedTypes: string[]) => {
    // 更新内部状态
    setSelectedRoomTypes(selectedTypes);
    
    // 过滤掉所有Room Type维度
    const nonRoomTypeDimensions = editableDimensions.filter(dim => dim.key !== "Room Type");
    
    // 为每个选中的房型创建一个维度对象
    const newRoomTypeDimensions = selectedTypes.map(type => ({
      key: "Room Type",
      value: type
    }));
    
    // 更新可编辑维度列表
    setEditableDimensions([...nonRoomTypeDimensions, ...newRoomTypeDimensions]);
    setHasChanged(true);
    message.info(`Updated Room Type preferences`);
  };

  const handleBudgetChange = (targetKey: string) => {
    const budgetValue = `${budgetMin}-${budgetMax}`;
    updateDimension(targetKey, budgetValue);
  };

  const handleOpenMap = () => {
    if (onShowMap) {
      // const locationDim = editableDimensions.find(dim => dim.key === "Location");
      onShowMap({
        userPreferences: editableDimensions,
        triggerData: {
          test: 'location_edit',
          preferences: editableDimensions,
          timestamp: Date.now()
        },
        requestType: 'location_selection',
        timestamp: new Date().toISOString()
      });
    } else {
      message.warning("Map component not available");
    }
  };

  // 根据维度组生成UI组件
  const renderDimensionGroups = () => {
    // 按key对维度进行分组
    const dimensionGroups = editableDimensions.reduce((groups, dim) => {
      if (!groups[dim.key]) groups[dim.key] = [];
      groups[dim.key].push(dim);
      return groups;
    }, {} as Record<string, Dimension[]>);
    
    return Object.entries(dimensionGroups).map(([key, dims], idx) => {
      // 特殊处理Room Type
      if (key === "Room Type") {
        return (
          <Descriptions.Item label={key} key={idx} className="editable-dimension">
            {renderRoomTypeValue()}
          </Descriptions.Item>
        );
      }
      
      // 处理其他普通维度
      return (
        <Descriptions.Item label={key} key={idx} className="editable-dimension">
          {renderEditableValue(dims[0])}  {/* 只需第一个，因为其他维度每个key只有一个值 */}
        </Descriptions.Item>
      );
    });
  };

  // 显示Room Type选择器和标签
  const renderRoomTypeValue = () => {
    const isEditing = editingKey === "Room Type";
    
    return isEditing ? (
      <Select
        mode="multiple"
        size="small"
        placeholder="Select room types"
        style={{ width: '100%' }}
        value={selectedRoomTypes}
        onChange={handleRoomTypeChange}
        options={roomTypeOptions.map(type => ({ label: type, value: type }))}
      />
    ) : (
      <div className="flex items-center justify-between">
        <div className="flex-1 flex flex-wrap gap-1">
          {selectedRoomTypes.map((type: string, idx: number) => (
            <Tag key={idx} color="blue">{type}</Tag>
          ))}
          {selectedRoomTypes.length === 0 && <span className="text-gray-400">No room type selected</span>}
        </div>
        <Button 
          type="text" 
          size="small" 
          icon={<EditOutlined />} 
          onClick={() => setEditingKey("Room Type")}
        />
      </div>
    );
  };

  const renderEditableValue = (dim: Dimension) => {
    const isEditing = editingKey === dim.key;
    
    switch(dim.key) {
      case "Budget":
      case "Budget Range":
        return (
          <div className="flex flex-col space-y-2">
            <div className="flex items-center">
              <span className="w-12">Min: €</span>
              <InputNumber 
                size="small"
                min={0}
                max={budgetMax || 5000}
                value={budgetMin}
                onChange={(value) => {
                  setBudgetMin(value || 0);
                  setHasChanged(true);
                }}
                onBlur={() => handleBudgetChange(dim.key)}
                style={{ width: '100%' }}
              />
            </div>
            <div className="flex items-center">
              <span className="w-12">Max: €</span>
              <InputNumber 
                size="small"
                min={budgetMin || 0}
                value={budgetMax}
                onChange={(value) => {
                  setBudgetMax(value || 0);
                  setHasChanged(true);
                }}
                onBlur={() => handleBudgetChange(dim.key)}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        );
      case "Price":
        return (
          <div className="flex flex-col space-y-2">
            <div className="flex items-center">
              <span className="w-12">Min: €</span>
              <InputNumber 
                size="small"
                min={0}
                max={budgetMax || 5000}
                value={budgetMin}
                onChange={(value) => {
                  setBudgetMin(value || 0);
                  setHasChanged(true);
                }}
                onBlur={() => handleBudgetChange("Price")}
                style={{ width: '100%' }}
              />
            </div>
            <div className="flex items-center">
              <span className="w-12">Max: €</span>
              <InputNumber 
                size="small"
                min={budgetMin || 0}
                value={budgetMax}
                onChange={(value) => {
                  setBudgetMax(value || 0);
                  setHasChanged(true);
                }}
                onBlur={() => handleBudgetChange("Price")}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        );
      
      case "Stay Duration":
        return (
          <div className="flex items-center">
            <span className="w-20">Nights:</span>
            <InputNumber 
              size="small"
              min={1}
              max={90}
              value={stayNights ?? undefined}
              placeholder="e.g. 3"
              onChange={(value) => {
                const v = typeof value === 'number' ? value : parseInt(String(value || ''), 10);
                if (Number.isFinite(v) && v >= 1) {
                  setStayNights(v);
                  setHasChanged(true);
                } else if (value === null) {
                  setStayNights(null);
                  setHasChanged(true);
                }
              }}
              onBlur={() => {
                const v = stayNights && stayNights > 0 ? stayNights : 1;
                updateDimension("Stay Duration", String(v));
              }}
              style={{ width: '100%' }}
            />
          </div>
        );

      case "Location":
        return (
          <div className="flex items-center justify-between">
            <span>{String(dim.value)}</span>
            <Button 
              type="link" 
              size="small" 
              icon={<EnvironmentOutlined />} 
              onClick={handleOpenMap}
            />
          </div>
        );
      
      default:
        return isEditing ? (
          <Input 
            size="small"
            value={String(dim.value)}
            onChange={(e) => {
              const newValue = e.target.value;
              updateDimension(dim.key, newValue);
            }}
            onBlur={() => setEditingKey(null)}
            autoFocus
          />
        ) : (
          <div className="flex items-center justify-between">
            <span>{String(dim.value)}</span>
            <Button 
              type="text" 
              size="small" 
              icon={<EditOutlined />} 
              onClick={() => setEditingKey(dim.key)}
            />
          </div>
        );
    }
  };

  return (
    <div className="w-[300px] max-w-xs min-w-[260px] bg-white border border-gray-200 shadow-lg rounded-xl p-4 relative transition-all duration-300 ease-in-out">
      <div className="absolute top-2 right-2">
        <Button
          size="small"
          type="text"
          icon={collapsed ? <DownOutlined /> : <UpOutlined />}
          onClick={handleToggleCollapse}
        />
      </div>

      <h3 className="text-lg font-semibold mb-3">🎯 Decision Card</h3>

      <CSSTransition
        in={!collapsed}
        timeout={300}
        classNames="fade"
        unmountOnExit
      >
        <div>
          <div className="text-blue-500 text-xs mb-2 flex items-center gap-1">
            <InfoCircleOutlined />
            Edit preferences directly to refine recommendations.
          </div>

          <CSSTransition
            in={hasChanged}
            timeout={300}
            classNames="pulse"
            unmountOnExit={false}
          >
            <Descriptions size="small" column={1} bordered className={hasChanged ? "preference-changed" : ""}>
              {/* 使用新的分组渲染方法 */}
              {renderDimensionGroups()}
            </Descriptions>
          </CSSTransition>
        </div>
      </CSSTransition>

      <div className="mt-4 text-center">
        <Button
          type="primary"
          icon={isLoading ? <Spin size="small" /> : <CheckOutlined />}
          onClick={handleConfirm}
          disabled={isLoading || editableDimensions.length === 0}
          className={`w-full ${hasChanged ? 'animate-pulse-button' : ''}`}
        >
          {isLoading
            ? "Refreshing..."
            : hasChanged
            ? "Confirm & Refresh"
            : "Get Recommendations !"}
        </Button>
      </div>
    </div>
  );
};

export default FreeDecisionCard;
