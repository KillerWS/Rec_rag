import React, { useState } from "react";
import { Tag, Button, Checkbox } from "antd";
import { sendUserSelection } from "../../../api/api";

const ROOM_TYPE_OPTIONS = [
  { label: "Entire place", value: "Entire home/apt", color: "geekblue" },
  { label: "Private room", value: "Private room", color: "green" },
  { label: "Shared room", value: "Shared room", color: "purple" },
  { label: "Hotel room", value: "Hotel room", color: "volcano" },
];

interface RoomTypeSelectorProps {
  onSubmit?: (values: string[]) => void;
  setSelectedDimensions?: (updater: (prev: Array<{ key: string; value: string }>) => Array<{ key: string; value: string }>) => void;
  disabled?: boolean;
  submittedRoomTypes?: string[];
  mode?: 'scripted' | 'agent' | 'none';
  appendMessage?: (msg: { text: string; sender: 'user' | 'system'; type?: string }) => void;
}

const RoomTypeSelector: React.FC<RoomTypeSelectorProps> = ({
  onSubmit,
  setSelectedDimensions,
  disabled = false,
  submittedRoomTypes = [],
  mode = 'scripted',
  appendMessage,
}) => {
  const [selected, setSelected] = useState<string[]>(submittedRoomTypes);
  const [isSubmitted, setIsSubmitted] = useState<boolean>(submittedRoomTypes.length > 0);

  const handleChange = (checkedValues: Array<string>) => {
    setSelected(checkedValues as string[]);
  };

  const handleSubmit = async () => {
    if (isSubmitted) return; // prevent repeated submissions

    // 更新上层维度
    if (setSelectedDimensions) {
      setSelectedDimensions((prev) => [
        ...prev.filter((item) => item.key !== "Room Type"),
        ...selected.map((value) => ({ key: "Room Type", value })),
      ]);
    }

    // 始终推送一条用户消息，说明选择
    if (appendMessage) {
      const labelList = selected.join(', ');
      appendMessage({ text: `I prefer room type: ${labelList}.`, sender: 'user' });
    }

    // 在脚本模式：仅推送说明消息，不触发后端
    if (mode === 'scripted') {
      if (appendMessage) {
        const labelList = selected.join(', ');
        appendMessage({ text: `Room type set to ${labelList}.`, sender: 'system' });
      }
    }

    // 在 Agent 模式：调用后端 /user/selection 同步状态
    if (mode === 'agent') {
      try {
        // 后端只能接受单值；逐个发送
        for (const rt of selected) {
          await sendUserSelection('room_type', rt);
        }
        if (appendMessage) {
          const labelList = selected.join(', ');
          appendMessage({ text: `Room type set to ${labelList}.`, sender: 'system' });
        }
      } catch (e) {
        if (appendMessage) {
          appendMessage({ text: 'Failed to sync room type selection with server.', sender: 'system' });
        }
      }
    }

    if (onSubmit) onSubmit(selected);

    // 一次提交后禁用
    setIsSubmitted(true);
  };

  const computedDisabled = disabled || isSubmitted;

  return (
    <div className="flex flex-col items-start gap-3 w-full">
      <div className="text-base font-medium mb-1 text-blue-700">Select Room Type (Multiple Choice)</div>
      <Checkbox.Group
        options={ROOM_TYPE_OPTIONS.map((rt) => ({
          label: (
            <Tag color={rt.color} className="px-3 py-1 rounded-2xl text-base cursor-pointer">
              {rt.label}
            </Tag>
          ),
          value: rt.value,
        }))}
        value={selected}
        onChange={(vals) => handleChange(vals as string[])}
        disabled={computedDisabled}
        style={{ width: "100%" }}
      />
      <Button
        type="primary"
        className="mt-2 w-full"
        disabled={selected.length === 0 || computedDisabled}
        onClick={handleSubmit}
      >
        Submit Room Type
      </Button>
    </div>
  );
};

export default RoomTypeSelector;
