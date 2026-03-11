import { Modal, Button, Typography, Divider } from 'antd';

interface SimpleTaskFramingModalProps {
  open: boolean;
  onClose: () => void;
  onStartTask: () => void;
  showStartButton?: boolean;
  showBackButton?: boolean;
  systemLabel?: string;
}

const SimpleTaskFramingModal = ({
  open,
  onClose,
  onStartTask,
  showStartButton = true,
  showBackButton = true,
  systemLabel = 'System 2',
}: SimpleTaskFramingModalProps) => {
  return (
    <Modal
      open={open}
      title={
        <div className="flex items-center justify-between">
          <div className="text-2xl font-bold">TASK BRIEF</div>
          <span className="text-xs text-gray-500">Goal-Focused Guidance</span>
        </div>
      }
      width={760}
      maskClosable={false}
      closable={false}
      onCancel={onClose}
      footer={
        showStartButton ? (
          <div className="flex items-center justify-between w-full">
            {showBackButton ? <Button onClick={onClose}>Back</Button> : <span />}
            <Button type="primary" onClick={onStartTask}>
              Start Task
            </Button>
          </div>
        ) : (
          <div className="flex items-center justify-end w-full">
            {showBackButton ? <Button onClick={onClose}>Back</Button> : null}
          </div>
        )
      }
    >
      <div className="space-y-4">
        <div className="space-y-2">
          <div className="text-sm text-gray-600">
            Task Type:{' '}
            <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-blue-700 font-semibold">
              Simple Decision
            </span>
          </div>
          <div className="text-sm text-gray-600">
            You are now using{' '}
            <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-blue-700 font-semibold">
              {systemLabel}
            </span>
          </div>
        </div>
        <Divider style={{ margin: '8px 0' }} />

        <div className="space-y-2">
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            This task simulates scenarios where users have relatively{' '}
            <span className="font-semibold text-blue-600">clear and stable preferences</span>
            (e.g., budget range, preferred location, room type) and aim to efficiently converge on a{' '}
            <span className="font-semibold text-blue-600">final choice</span>.
          </Typography.Paragraph>
          <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
            <li>Early elicitation and confirmation of <span className="font-semibold text-blue-600">core constraints</span>.</li>
            <li>Concise <span className="font-semibold text-blue-600">follow-up questions</span> to resolve missing or ambiguous preferences.</li>
            <li>Targeted <span className="font-semibold text-blue-600">structural information</span> to confirm affordability or availability.</li>
            <li>Reduced <span className="font-semibold text-blue-600">interaction overhead</span> to support rapid decision closure.</li>
          </ul>
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            <span className="font-semibold text-blue-600">Visualizations</span> are used selectively for confirmation rather than broad exploration.
          </Typography.Paragraph>
        </div>
      </div>
    </Modal>
  );
};

export default SimpleTaskFramingModal;
