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

const placeholderText = `Study Title: Evaluation of a Conversational Recommender System

Purpose of the Study:
You are invited to take part in a research study evaluating an experimental conversational recommender system. The goal of this study is to understand how users interact with different system designs and how such systems may support decision-making.

Procedures:
If you agree to participate, you will interact with the system to complete a set of decision-making tasks. Your interactions (such as messages, clicks, and choices) will be recorded for analysis. After each task, you may be asked to complete short questionnaires. The total session will take about 30–45 minutes.

Data and Privacy:
- No personally identifiable information (such as your name, email, or IP address) will be collected.
- All data will be stored and analyzed anonymously.
- The data will only be used for academic research purposes.

Voluntary Participation:
Your participation is entirely voluntary. You may withdraw at any time without penalty. You may also choose not to answer any question that makes you uncomfortable.

Risks and Benefits:
There are no known risks beyond normal computer use. While there are no direct benefits to you, your participation will help researchers design better interactive systems.

Confidentiality:
All collected data will remain anonymous and will be kept confidential in accordance with institutional and legal requirements.

Contact:
If you have questions about the study, you may contact the researcher at 495032732@qq.com.

Consent:
By checking the box below, you confirm that:
- You have read and understood the information above,
- You voluntarily agree to participate in this study,
- You understand that you may withdraw at any time without penalty. `;

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
          <div className="text-2xl font-bold">INFORMED CONSENT FORM</div>
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