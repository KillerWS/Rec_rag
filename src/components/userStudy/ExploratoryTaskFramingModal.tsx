import { Modal, Button, Typography, Divider } from 'antd';

interface ExploratoryTaskFramingModalProps {
  open: boolean;
  onClose: () => void;
  onStartTask: () => void;
  showStartButton?: boolean;
  showBackButton?: boolean;
  systemLabel?: string;
}

const ExploratoryTaskFramingModal = ({
  open,
  onClose,
  onStartTask,
  showStartButton = true,
  showBackButton = true,
  systemLabel = 'System 2',
}: ExploratoryTaskFramingModalProps) => {
  return (
    <Modal
      open={open}
      title={
        <div className="flex items-center justify-between">
          <div className="text-2xl font-bold">TASK BRIEF</div>
          <span className="text-xs text-gray-500">Sensemaking-Oriented Guidance</span>
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
              Exploratory Decision
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
            This task represents scenarios where preferences are{' '}
            <span className="font-semibold text-blue-600">uncertain or evolving</span>, and where
            understanding the <span className="font-semibold text-blue-600">structure of the item space</span> is essential for informed decision-making.
          </Typography.Paragraph>
          <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
            <li>Open-ended prompts encouraging reflection on <span className="font-semibold text-blue-600">trade-offs</span>.</li>
            <li>Adaptive prompts that surface <span className="font-semibold text-blue-600">exploratory intent</span> or hesitation.</li>
            <li>Proactive <span className="font-semibold text-blue-600">structural information</span> such as price distributions and room-type breakdowns.</li>
            <li>Frequent use of <span className="font-semibold text-blue-600">interactive visualizations</span> for comparison and pattern recognition.</li>
          </ul>
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            The system emphasizes <span className="font-semibold text-blue-600">progressive sensemaking</span> over immediate decision closure.
          </Typography.Paragraph>
        </div>
      </div>
    </Modal>
  );
};

export default ExploratoryTaskFramingModal;
