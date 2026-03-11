import { Modal, Button, Typography } from 'antd';

interface WelcomeModalProps {
  open: boolean;
  onStartStudy: () => void;
  isLoading?: boolean;
}

const WelcomeIllustration = () => (
  <div className="w-full flex items-center justify-center">
    <svg viewBox="0 0 480 220" className="w-full max-w-[520px]" aria-hidden="true">
      <defs>
        <linearGradient id="bgGradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#dbeafe" />
          <stop offset="100%" stopColor="#ede9fe" />
        </linearGradient>
        <linearGradient id="houseGradient" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="480" height="220" rx="18" fill="url(#bgGradient)" />
      <circle cx="85" cy="60" r="26" fill="#fbbf24" opacity="0.9" />
      <path d="M120 160 L240 80 L360 160" stroke="url(#houseGradient)" strokeWidth="12" fill="none" />
      <rect x="160" y="120" width="160" height="72" rx="10" fill="white" opacity="0.85" />
      <rect x="190" y="140" width="40" height="52" rx="6" fill="#c7d2fe" />
      <rect x="250" y="140" width="40" height="28" rx="6" fill="#c7d2fe" />
      <rect x="250" y="174" width="40" height="18" rx="6" fill="#c7d2fe" />
      <path d="M90 180 C150 170, 200 185, 260 176" stroke="#93c5fd" strokeWidth="4" fill="none" />
      <path d="M210 188 C280 175, 340 190, 410 178" stroke="#a78bfa" strokeWidth="4" fill="none" />
    </svg>
  </div>
);

const WelcomeModal = ({ open, onStartStudy, isLoading = false }: WelcomeModalProps) => {
  return (
    <Modal
      open={open}
      footer={null}
      closable={false}
      maskClosable={false}
      width={820}
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="text-2xl font-bold">Welcome</div>
          <span className="text-xs text-gray-500">Airbnb Recommendation Study</span>
        </div>

        <WelcomeIllustration />

        <div className="space-y-2">
          <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
            In this study, you will use an AI-assisted system to explore and select suitable
            accommodations in Berlin. The system will guide you through different decision-making
            contexts while keeping the experience natural and conversational.
          </Typography.Paragraph>
          <Typography.Paragraph style={{ marginBottom: 0 }}>
            Click “Start Study” to proceed. You will first review the consent form before entering the
            task.
          </Typography.Paragraph>
        </div>

        <div className="flex items-center justify-end">
          <Button type="primary" onClick={onStartStudy} disabled={isLoading}>
            {isLoading ? 'Preparing…' : 'Start Study'}
          </Button>
        </div>
      </div>
    </Modal>
  );
};

export default WelcomeModal;
