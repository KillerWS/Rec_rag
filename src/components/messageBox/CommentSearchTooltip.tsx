import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom';

interface CommentSearchTooltipProps {
  targetButtonSelector: string;
  show: boolean;
  onClose: () => void;
}

const CommentSearchTooltip: React.FC<CommentSearchTooltipProps> = ({
  targetButtonSelector,
  show,
  onClose
}) => {
  const [position, setPosition] = useState<{ top: number; left: number; visible: boolean }>({
    top: 0,
    left: 0,
    visible: false
  });
  
  const [isPositioning, setIsPositioning] = useState(false);
  
  const [isHovered, setIsHovered] = useState(false);

  // Debug logging
  console.log('🔍 CommentSearchTooltip render:', { 
    show, 
    targetButtonSelector, 
    position
  });

  useEffect(() => {
    console.log('🎯 CommentSearchTooltip useEffect triggered:', { show, targetButtonSelector });
    
    if (!show) {
      console.log('❌ show is false, hiding tooltip');
      setPosition(prev => ({ ...prev, visible: false }));
      setIsPositioning(false);
      return;
    }

    // 开始定位过程
    setIsPositioning(true);

    // 添加小延迟确保DOM完全渲染
    const findAndPositionTooltip = () => {

    // Find the target element (could be button, switch, or span)
    const findTargetElement = () => {
      // Look for any element containing the target text
      const allElements = document.querySelectorAll('*');
      console.log('🔍 Searching through elements for text:', targetButtonSelector);
      
      for (const element of allElements) {
        const elementText = element.textContent || '';
        // Check if this element directly contains the text and is a reasonable target
        if (elementText.includes(targetButtonSelector) && 
            (element.tagName === 'BUTTON' || 
             element.tagName === 'SPAN' || 
             element.classList.contains('ant-switch') ||
             element.closest('.ant-switch'))) {
          console.log('✅ Found target element:', element, 'tagName:', element.tagName);
          return element;
        }
      }
      
      // Fallback: look for span containing the text and find its associated switch
      const spans = document.querySelectorAll('span');
      for (const span of spans) {
        if (span.textContent?.includes(targetButtonSelector)) {
          console.log('🔍 Found span with text, looking for nearby switch:', span);
          // Look for switch in the same container
          const container = span.closest('div');
          const switchElement = container?.querySelector('.ant-switch');
          if (switchElement) {
            console.log('✅ Found associated switch element:', switchElement);
            return switchElement;
          }
        }
      }
      
      console.log('❌ Target element not found');
      return null;
    };

    const targetButton = findTargetElement();
    if (!targetButton) {
      console.warn('❌ CommentSearchTooltip: Target button not found');
      // Let's also try to find any button with "comment" or "search" in it
      const allButtons = document.querySelectorAll('button');
      const buttonTexts = Array.from(allButtons).map(btn => btn.textContent?.trim()).filter(Boolean);
      console.log('📋 All button texts found:', buttonTexts);
      return;
    }

    const updatePosition = () => {
      const rect = targetButton.getBoundingClientRect();
      
      const tooltipHeight = 90; // Estimated tooltip height
      const tooltipWidth = 260; // Estimated tooltip width
      
      // Calculate position above the button
      let top = rect.top - tooltipHeight - 15; // Position above button with 15px gap
      let left = rect.left + (rect.width / 2) - (tooltipWidth / 2); // Center horizontally
      
      // Ensure tooltip stays within viewport horizontally
      if (left < 10) left = 10;
      if (left + tooltipWidth > window.innerWidth - 10) {
        left = window.innerWidth - tooltipWidth - 10;
      }
      
      // If tooltip would go above viewport, position it below the button instead
      if (top < 10) {
        top = rect.bottom + 15; // Below button with 15px gap
      }
      
      const newPosition = {
        top: top,
        left: left,
        visible: true
      };
      
      console.log('📍 Button rect:', rect);
      console.log('📍 Calculated position:', newPosition);
      console.log('📍 Viewport dimensions:', { width: window.innerWidth, height: window.innerHeight });
      
      setPosition(newPosition);
      setIsPositioning(false); // 定位完成
    };

    updatePosition();
    window.addEventListener('scroll', updatePosition);
    window.addEventListener('resize', updatePosition);

    return () => {
      window.removeEventListener('scroll', updatePosition);
      window.removeEventListener('resize', updatePosition);
    };
    }; // 结束 findAndPositionTooltip 函数

    // 使用 setTimeout 延迟执行，确保DOM完全渲染
    const delayTimer = setTimeout(() => {
      findAndPositionTooltip();
    }, 100); // 100ms延迟

    return () => {
      clearTimeout(delayTimer);
    };
  }, [show, targetButtonSelector]); // 移除 onClose 和 isHovered，减少重新触发

  // 单独处理自动隐藏功能
  useEffect(() => {
    if (!show || !position.visible) return;

    const autoHideTimer = setTimeout(() => {
      if (!isHovered) {
        onClose();
      }
    }, 5000);

    return () => {
      clearTimeout(autoHideTimer);
    };
  }, [show, position.visible, isHovered, onClose]);

  if (!position.visible || isPositioning) {
    console.log('❌ Tooltip not ready to render:', { visible: position.visible, isPositioning });
    return null;
  }

  console.log('✅ Rendering tooltip at position:', position);

  // 使用 portal 渲染到 body，确保在最上层
  if (typeof document === 'undefined') return null;

  return ReactDOM.createPortal(
    <div
      style={{
        position: 'fixed',
        top: position.top,
        left: position.left,
        zIndex: 1000000, // 最高层级
        pointerEvents: 'auto'
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Arrow pointing down to the button */}
      <div
        style={{
          position: 'absolute',
          bottom: -8,
          left: '50%',
          transform: 'translateX(-50%)',
          width: 0,
          height: 0,
          borderLeft: '8px solid transparent',
          borderRight: '8px solid transparent',
          borderTop: '8px solid rgba(55, 65, 81, 0.95)'
        }}
      />
      
      {/* Tooltip card */}
      <div
        className="text-white px-4 py-3 rounded-lg shadow-xl max-w-xs"
        style={{
          backgroundColor: 'rgba(55, 65, 81, 0.95)',
          backdropFilter: 'blur(8px)',
          animation: 'fadeInScale 0.3s ease-out'
        }}
      >
        <div className="flex items-start gap-2">
          <div className="text-yellow-400 text-lg flex-shrink-0">💡</div>
          <div>
            <div className="font-semibold text-sm mb-1">RAG Feature</div>
            <div className="text-xs text-gray-200 leading-relaxed">
              Enable to search guest reviews for personalized insights.
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-sm leading-none ml-1 flex-shrink-0"
          >
            ×
          </button>
        </div>
      </div>

      <style>{`
        @keyframes fadeInScale {
          from {
            opacity: 0;
            transform: translateX(-50%) scale(0.9);
          }
          to {
            opacity: 1;
            transform: translateX(-50%) scale(1);
          }
        }
      `}</style>
    </div>,
    document.body
  );
};

export default CommentSearchTooltip;
