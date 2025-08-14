import { useMemo, useState } from 'react';
import { Modal, Button, Checkbox, Typography, Divider } from 'antd';

interface UserStudyAgreementModalProps {
  open: boolean;
  agreed: boolean;
  onAgree: () => void;
  onClose: () => void;
  // When true (first time opening), user must choose Agree/Disagree. Mask/close is disabled.
  isFirstOpen?: boolean;
  content?: string;
  onDisagree?: () => void;
}

const placeholderText = `This is a placeholder user study agreement.\n\n` +
  `- Purpose: To improve product experience.\n` +
  `- Data: Interaction logs, anonymized.\n` +
  `- Participation: Voluntary; you may withdraw at any time.\n` +
  `- Contact: research@example.com.\n\n` +
  `Please read carefully. The real text will be provided later. ` +
  `Scroll to review the full agreement before consenting.`;

const UserStudyAgreementModal = ({
  open,
  agreed,
  onAgree,
  onClose,
  isFirstOpen = false,
  content,
  onDisagree,
}: UserStudyAgreementModalProps) => {
  const [hasChecked, setHasChecked] = useState(false);
  const bodyText = useMemo(() => content?.trim() || placeholderText, [content]);

  const handleDisagree = () => {
    if (onDisagree) {
      onDisagree();
      return;
    }
    // Default behavior: exit page
    try {
      window.location.replace('about:blank');
    } catch (_) {}
  };

  return (
    <Modal
      open={open}
      title={
        <div className="flex items-center justify-between">
          <div className="text-lg font-semibold">User Study Consent</div>
          <span className="text-xs text-gray-500">Thank you for helping us improve</span>
        </div>
      }
      width={720}
      maskClosable={!isFirstOpen}
      closable={!isFirstOpen}
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-3">
            <Checkbox
              checked={agreed || hasChecked}
              disabled={agreed}
              onChange={(e) => setHasChecked(e.target.checked)}
            >
              I have read and agree to the terms
            </Checkbox>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={handleDisagree} disabled={agreed}>Disagree</Button>
            <Button
              type="primary"
              danger
              className="font-semibold"
              disabled={agreed || (!agreed && !hasChecked)}
              onClick={() => {
                onAgree();
                if (!isFirstOpen) onClose();
              }}
            >
              Agree and Continue
            </Button>
          </div>
        </div>
      }
      onCancel={onClose}
    >
      <div className="space-y-3">
        <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
          Please review the following consent information. After agreeing, the checkbox will be locked, but you can always revisit and read the agreement.
        </Typography.Paragraph>
        <Divider style={{ margin: '8px 0' }} />
        <div
          className="rounded-lg border border-gray-200 bg-white"
          style={{ maxHeight: 360, overflowY: 'auto', padding: 16 }}
        >
          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
            {bodyText}
          </Typography.Paragraph>
        </div>
      </div>
    </Modal>
  );
};

export default UserStudyAgreementModal; 