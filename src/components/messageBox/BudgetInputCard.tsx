// BudgetRangeInput.jsx - 预算范围输入组件
import { useState } from 'react';
import { Button, Card, Space, InputNumber } from 'antd';
import { DollarOutlined, CheckOutlined } from '@ant-design/icons';

interface BudgetRangeInputProps {
  onBudgetSubmit?: (budgetData: { min: number; max: number; range: string }) => void;
  setSelectedDimensions?: React.Dispatch<React.SetStateAction<any[]>>;
  className?: string;
}

interface BudgetData {
  min: number;
  max: number;
  range: string;
}

const BudgetRangeInput = ({ 
  onBudgetSubmit,
  setSelectedDimensions,
  className = ""
}: BudgetRangeInputProps) => {
  const [minBudget, setMinBudget] = useState<number | null>(null);
  const [maxBudget, setMaxBudget] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);

  // 🎯 处理预算提交
  const handleSubmit = () => {
    if (!minBudget || !maxBudget) {
      return;
    }

    if (minBudget >= maxBudget) {
      alert('Maximum budget should be greater than minimum budget');
      return;
    }

    const budgetData: BudgetData = {
      min: minBudget,
      max: maxBudget,
      range: `€${minBudget} - €${maxBudget}`
    };

    console.log('🎯 BudgetRangeInput - 提交预算:', budgetData);

    // 更新selectedDimensions
    if (setSelectedDimensions) {
      setSelectedDimensions(prev => {
        const newDimensions = [...prev];
        const existingIndex = newDimensions.findIndex(
          dim => dim.key === 'Budget' || dim.key === 'Budget Range'
        );

        const newDimension = {
          key: 'Budget',
          value: budgetData.range,
          type: 'budget',
          min: budgetData.min,
          max: budgetData.max
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

    // 调用父组件回调
    if (onBudgetSubmit) {
      onBudgetSubmit(budgetData);
    }

    setSubmitted(true);
  };

  // 🎯 快速选择预设
  const quickSelectBudgets = [
    { label: '€50-100', min: 50, max: 100 },
    { label: '€100-200', min: 100, max: 200 },
    { label: '€200-400', min: 200, max: 400 },
    { label: '€400-800', min: 400, max: 800 }
  ];

  const handleQuickSelect = (budget: { min: number; max: number }) => {
    setMinBudget(budget.min);
    setMaxBudget(budget.max);
  };

  if (submitted) {
    return (
      <Card 
        size="small" 
        className={`mt-3 border-green-200 bg-green-50 ${className}`}
      >
        <div className="flex items-center justify-center space-x-2 text-green-600">
          <CheckOutlined />
          <span className="font-medium">Budget set: €{minBudget}-{maxBudget}</span>
        </div>
      </Card>
    );
  }

  return (
    <Card 
      size="small" 
      className={`mt-3 border-blue-200 bg-blue-50 ${className}`}
      title={
        <div className="flex items-center space-x-2 text-sm">
          <DollarOutlined style={{ color: '#52c41a' }} />
          <span className="font-medium">Set your budget range per night</span>
        </div>
      }
    >
      <div className="space-y-4">
        {/* 🎯 快速选择按钮 */}
        <div>
          <div className="text-xs text-gray-600 mb-2">Quick select:</div>
          <div className="flex flex-wrap gap-2">
            {quickSelectBudgets.map((budget, index) => (
              <Button
                key={index}
                size="small"
                type="default"
                onClick={() => handleQuickSelect(budget)}
                className="text-xs"
              >
                {budget.label}
              </Button>
            ))}
          </div>
        </div>

        {/* 🎯 自定义输入 */}
        <div>
          <div className="text-xs text-gray-600 mb-2">Or enter custom range:</div>
          <Space.Compact className="w-full">
            <InputNumber
              placeholder="Min €"
              value={minBudget}
              onChange={(value) => setMinBudget(value)}
              min={0}
              max={9999}
              className="flex-1"
              size="small"
              prefix="€"
            />
            <span className="flex items-center px-2 text-gray-400">-</span>
            <InputNumber
              placeholder="Max €"
              value={maxBudget}
              onChange={(value) => setMaxBudget(value)}
              min={(minBudget || 0) + 1}
              max={9999}
              className="flex-1"
              size="small"
              prefix="€"
            />
          </Space.Compact>
        </div>

        {/* 🎯 提交按钮 */}
        <div className="flex justify-center">
          <Button 
            type="primary" 
            size="small"
            onClick={handleSubmit}
            disabled={!minBudget || !maxBudget || minBudget >= maxBudget}
            className="w-full"
            style={{ backgroundColor: '#52c41a', borderColor: '#52c41a' }}
          >
            <CheckOutlined className="mr-1" />
            Confirm Budget
          </Button>
        </div>

        {/* 🎯 验证提示 */}
        {minBudget && maxBudget && minBudget >= maxBudget && (
          <div className="text-xs text-red-500 text-center">
            Maximum budget should be greater than minimum budget
          </div>
        )}
      </div>
    </Card>
  );
};

export default BudgetRangeInput;