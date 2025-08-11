// SmartDimensionsCard.jsx - 基于target_dimensions的智能选择组件
import React, { useState } from 'react';
import { Button, Card, Input, Tag } from 'antd';
import { 
  DollarOutlined, 
  HomeOutlined, 
  CalendarOutlined,
  TeamOutlined,
  WifiOutlined,
  StarOutlined,
  EnvironmentOutlined,
  CheckOutlined
} from '@ant-design/icons';

interface SmartDimensionsCardProps {
  targetDimensions?: string[];
  followupInfo?: { followup_question?: { question?: string }; strategy?: string } | null;
  onDimensionSelect?: (data: any) => void;
  setSelectedDimensions?: React.Dispatch<React.SetStateAction<any[]>>;
  className?: string;
}

const SmartDimensionsCard = ({ 
  targetDimensions = [], 
  followupInfo = null,
  onDimensionSelect,
  setSelectedDimensions,
  className = ""
}: SmartDimensionsCardProps) => {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [customInput, setCustomInput] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);

  // 🎯 维度配置映射
  const dimensionConfigs: Record<string, { icon: React.ReactNode; color: string; options: string[]; placeholder: string; title: string; multiSelect?: boolean }> = {
    'budget': {
      icon: <DollarOutlined />,
      color: '#52c41a',
      options: ['€50-100', '€100-200', '€200-400', '€400+', 'Flexible budget'],
      placeholder: 'Enter your budget range...',
      title: 'Budget Range'
    },
    'location': {
      icon: <EnvironmentOutlined />,
      color: '#1677ff',
      options: ['City Centre', 'Kreuzberg', 'Neukölln', 'Prenzlauer Berg', 'Friedrichshain', 'Mitte'],
      placeholder: 'Enter preferred area...',
      title: 'Location Preference'
    },
    'area': {
      icon: <EnvironmentOutlined />,
      color: '#1677ff',
      options: ['City Centre', 'Kreuzberg', 'Neukölln', 'Prenzlauer Berg', 'Friedrichshain', 'Mitte'],
      placeholder: 'Enter preferred area...',
      title: 'Area Preference'
    },
    'preferred area': {
      icon: <EnvironmentOutlined />,
      color: '#1677ff',
      options: ['City Centre', 'Kreuzberg', 'Neukölln', 'Prenzlauer Berg', 'Friedrichshain', 'Mitte'],
      placeholder: 'Enter preferred area...',
      title: 'Area Preference'
    },
    'dates': {
      icon: <CalendarOutlined />,
      color: '#722ed1',
      options: ['This weekend', 'Next week', 'Next month', 'Flexible dates'],
      placeholder: 'Enter your travel dates...',
      title: 'Travel Dates'
    },
    'guests': {
      icon: <TeamOutlined />,
      color: '#fa8c16',
      options: ['1 person', '2 people', '3-4 people', '5+ people'],
      placeholder: 'Enter number of guests...',
      title: 'Number of Guests'
    },
    'amenities': {
      icon: <WifiOutlined />,
      color: '#eb2f96',
      options: ['WiFi', 'Kitchen', 'Parking', 'Pet-friendly', 'Gym', 'Pool', 'Air Conditioning'],
      placeholder: 'Enter desired amenities...',
      title: 'Amenities',
      multiSelect: true
    },
    'room_type': {
      icon: <HomeOutlined />,
      color: '#13c2c2',
      options: ['Entire home/apt', 'Private room', 'Shared room', 'Hotel room'],
      placeholder: 'Enter room type preference...',
      title: 'Room Type'
    },
    'rating': {
      icon: <StarOutlined />,
      color: '#faad14',
      options: ['4.5+ stars', '4.0+ stars', '3.5+ stars', 'Any rating'],
      placeholder: 'Enter minimum rating...',
      title: 'Minimum Rating'
    },
    // 🎯 添加更多常见维度的匹配
    'budget range': {
      icon: <DollarOutlined />,
      color: '#52c41a',
      options: ['€50-100', '€100-200', '€200-400', '€400+', 'Flexible budget'],
      placeholder: 'Enter your budget range...',
      title: 'Budget Range'
    }
  };

  // 🎯 获取主要维度配置（取第一个target_dimension）
  const getPrimaryDimension = () => {
    if (!targetDimensions || targetDimensions.length === 0) return null;
    
    // 🎯 尝试匹配维度名称（不区分大小写，支持部分匹配）
    const primaryDimensionName = targetDimensions[0].toLowerCase();
    
    // 直接匹配
    if (dimensionConfigs[primaryDimensionName]) {
      return dimensionConfigs[primaryDimensionName];
    }
    
    // 部分匹配
    for (const [key, config] of Object.entries(dimensionConfigs)) {
      if (primaryDimensionName.includes(key) || key.includes(primaryDimensionName)) {
        return config as any;
      }
    }
    
    // 默认返回budget配置
    return dimensionConfigs['budget'];
  };

  const primaryDimension = getPrimaryDimension();
  const primaryDimensionKey = targetDimensions?.[0]?.toLowerCase();

  // 🎯 处理选项点击
  const handleOptionClick = (option: string) => {
    setSelectedOption(option);
    handleDimensionSelect(option);
  };

  // 🎯 处理自定义输入
  const handleCustomSubmit = () => {
    if (customInput.trim()) {
      handleDimensionSelect(customInput.trim());
    }
  };

  // 🎯 统一的维度选择处理
  const handleDimensionSelect = (value: string) => {
    const dimensionData = {
      type: primaryDimensionKey,
      value: value,
      structured: !showCustomInput,
      timestamp: Date.now()
    };

    console.log('🎯 SmartDimensionsCard - 选择维度:', dimensionData);

    // 调用父组件回调
    if (onDimensionSelect) {
      onDimensionSelect(dimensionData);
    }

    // 更新selectedDimensions状态
    if (setSelectedDimensions && primaryDimensionKey) {
      setSelectedDimensions((prev: any[]) => {
        const newDimensions = [...prev];
        const existingIndex = newDimensions.findIndex(
          (dim: any) => dim.key.toLowerCase() === primaryDimensionKey
        );

        const newDimension = {
          key: primaryDimension?.title || primaryDimensionKey,
          value: value,
          type: primaryDimensionKey,
          structured: !showCustomInput
        };

        if (existingIndex >= 0) {
          newDimensions[existingIndex] = newDimension;
        } else {
          newDimensions.push(newDimension);
        }

        console.log('🎯 更新selectedDimensions:', newDimensions);
        return newDimensions;
      });
    }

    // 重置状态
    setSelectedOption(null);
    setCustomInput('');
    setShowCustomInput(false);
  };

  // 🎯 简化：只要有targetDimensions就显示组件
  if (!targetDimensions || targetDimensions.length === 0) {
    return null;
  }

  // 🎯 如果找不到匹配的配置，使用默认配置
  if (!primaryDimension) {
    console.warn('🎯 未找到匹配的维度配置，使用默认配置:', targetDimensions);
  }

  return (
    <Card 
      size="small" 
      className={`mt-3 border-blue-200 bg-blue-50 ${className}`}
      title={
        <div className="flex items-center space-x-2 text-sm">
          <span style={{ color: primaryDimension!.color }}>
            {primaryDimension!.icon}
          </span>
          <span className="font-medium">
            {followupInfo?.followup_question?.question || `Please specify your ${primaryDimension!.title.toLowerCase()}`}
          </span>
        </div>
      }
    >
      <div className="space-y-3">
        {/* 🎯 预设选项按钮 */}
        <div className="flex flex-wrap gap-2">
          {primaryDimension!.options.map((option: string, index: number) => (
            <Button
              key={index}
              size="small"
              type={selectedOption === option ? "primary" : "default"}
              onClick={() => handleOptionClick(option)}
              className="text-xs hover:scale-105 transition-transform"
              style={{ 
                borderColor: selectedOption === option ? primaryDimension!.color : undefined,
                backgroundColor: selectedOption === option ? primaryDimension!.color : undefined
              }}
            >
              {selectedOption === option && <CheckOutlined className="mr-1" />}
              {option}
            </Button>
          ))}
        </div>

        {/* 🎯 显示所有target_dimensions作为提示 */}
        {targetDimensions.length > 1 && (
          <div className="text-xs text-gray-500">
            <span>Also collecting: </span>
            {targetDimensions.slice(1).map((dim, index) => (
              <Tag key={index} color="default" className="ml-1">
                {dimensionConfigs[dim.toLowerCase()]?.title || (dim as string)}
              </Tag>
            ))}
          </div>
        )}

        {/* 🎯 自定义输入区域 */}
        <div className="border-t pt-2">
          {!showCustomInput ? (
            <Button 
              type="dashed" 
              size="small" 
              onClick={() => setShowCustomInput(true)}
              className="text-xs w-full"
            >
              💭 Or type your own answer
            </Button>
          ) : (
            <div className="flex space-x-2">
              <Input
                size="small"
                placeholder={primaryDimension!.placeholder}
                value={customInput}
                onChange={(e) => setCustomInput(e.target.value)}
                onPressEnter={handleCustomSubmit}
                className="flex-1"
                autoFocus
              />
              <Button 
                size="small" 
                type="primary" 
                onClick={handleCustomSubmit}
                disabled={!customInput.trim()}
                style={{ backgroundColor: primaryDimension!.color }}
              >
                Send
              </Button>
              <Button 
                size="small" 
                onClick={() => {
                  setShowCustomInput(false);
                  setCustomInput('');
                }}
              >
                Cancel
              </Button>
            </div>
          )}
        </div>

        {/* 🎯 调试信息（开发时可见） */}
        {import.meta.env.MODE === 'development' && (
          <div className="text-xs text-gray-400 border-t pt-2">
            <details>
              <summary className="cursor-pointer">Debug Info</summary>
              <div className="mt-1 font-mono">
                <div>Target Dimensions: {JSON.stringify(targetDimensions)}</div>
                <div>Primary: {primaryDimensionKey}</div>
                <div>Followup Strategy: {followupInfo?.strategy}</div>
              </div>
            </details>
          </div>
        )}
      </div>
    </Card>
  );
};

export default SmartDimensionsCard;