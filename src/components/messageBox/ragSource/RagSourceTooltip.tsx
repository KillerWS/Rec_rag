// RagSourceTooltip.jsx - 可直接集成的 RAG 源文档悬浮提示组件
import React, { useState } from 'react';
import { 
  Tooltip, 
  Badge, 
  Button, 
  Card, 
  Tag, 
  Space, 
  Typography, 
  Modal
} from 'antd';
import { 
  FileTextOutlined, 
  EnvironmentOutlined, 
  HomeOutlined, 
  UserOutlined,
  LinkOutlined,
  EyeOutlined,
  InfoCircleOutlined,
  DatabaseOutlined
} from '@ant-design/icons';

const { Text, Paragraph } = Typography;

// 单个源文档卡片组件
const SourceDocCard = ({ doc, index }: { doc: any; index: number }) => {
  // 显示完整内容
  const getPreviewContent = (content: string) => {
    if (!content) return '';
    return content;
  };

  // 获取房型图标和颜色
  const getRoomTypeConfig = (roomType: string) => {
    switch (roomType?.toLowerCase()) {
      case 'entire home/apt':
        return { icon: <HomeOutlined />, color: 'blue' };
      case 'private room':
        return { icon: <UserOutlined />, color: 'green' };
      case 'shared room':
        return { icon: <UserOutlined />, color: 'orange' };
      default:
        return { icon: <HomeOutlined />, color: 'default' };
    }
  };

  // 🆕 适配新的数据结构
  const getContent = () => {
    // 优先使用新的snippet字段
    if (doc.snippet) {
      return doc.snippet;
    }
    // 兼容旧的page_content字段
    if (doc.page_content) {
      return doc.page_content;
    }
    return '';
  };

  const getMetadata = () => {
    // 优先使用新的item_detail结构
    if (doc.item_detail) {
      return {
        listing_id: doc.listing_id || doc.item_detail.id,
        name: doc.item_detail.name,
        neighbourhood: doc.item_detail.neighbourhood,
        neighbourhood_group: doc.item_detail.neighbourhood_group,
        room_type: doc.room_type || doc.item_detail.room_type,
        price: doc.item_detail.price,
        host_name: doc.item_detail.host_name,
        availability_365: doc.item_detail.availability_365,
        reviews_per_month: doc.item_detail.reviews_per_month,
        number_of_reviews: doc.item_detail.number_of_reviews,
        review_scores_rating: doc.item_detail.review_scores_rating
      };
    }
    // 兼容旧的metadata结构
    if (doc.metadata) {
      return doc.metadata;
    }
    return {};
  };

  const content = getContent();
  const metadata = getMetadata();
  const roomTypeConfig = getRoomTypeConfig(metadata.room_type);

  return (
    <Card 
      size="small" 
      style={{ 
        marginBottom: 8,
        borderRadius: 6,
        border: '1px solid #f0f0f0',
        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
      }}
      bodyStyle={{ padding: '10px' }}
    >
      {/* 文档头部 */}
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
        <Badge count={index + 1} size="small" style={{ marginRight: 8 }} />
        <FileTextOutlined style={{ color: '#1890ff', marginRight: 4 }} />
        <Text strong style={{ fontSize: '14px' }}>Source Document</Text>
      </div>

      {/* 房源名称 */}
      {metadata.name && (
        <div style={{ marginBottom: 10 }}>
          <Text strong style={{ fontSize: '15px', color: '#1890ff' }}>
            {metadata.name}
          </Text>
        </div>
      )}

      {/* 标签信息 */}
      <Space wrap size={[4, 4]} style={{ marginBottom: 10 }}>
        {/* 地理位置标签 - 合并显示 */}
        {(metadata.neighbourhood || metadata.neighbourhood_group) && (
          <Tag 
            icon={<EnvironmentOutlined />} 
            color="geekblue"
          >
            {metadata.neighbourhood_group && metadata.neighbourhood 
              ? `${metadata.neighbourhood_group} / ${metadata.neighbourhood}`
              : metadata.neighbourhood || metadata.neighbourhood_group
            }
          </Tag>
        )}
        
        {metadata.room_type && (
          <Tag 
            icon={roomTypeConfig.icon} 
            color={roomTypeConfig.color}
          >
            {metadata.room_type}
          </Tag>
        )}
        
        {metadata.listing_id && (
          <Tag 
            icon={<LinkOutlined />} 
            color="purple"
          >
            ID#{metadata.listing_id}
          </Tag>
        )}

        {doc.price_bucket && doc.price_bucket !== "unknown" && (
          <Tag 
            icon={<InfoCircleOutlined />} 
            color="orange"
          >
            {doc.price_bucket}
          </Tag>
        )}
      </Space>

      {/* 内容预览 */}
      <div style={{ 
        backgroundColor: '#fafafa', 
        padding: 12, 
        borderRadius: 4,
        border: '1px solid #f0f0f0',
        marginBottom: 10
      }}>
        <Text 
          style={{ 
            fontSize: '13px', 
            lineHeight: 1.6, 
            color: '#333',
            display: 'block',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word'
          }}
        >
          "{getPreviewContent(content)}"
        </Text>
      </div>

      {/* 价格信息 - 突出显示 */}
      {metadata.price && (
        <div style={{ 
          marginTop: 10, 
          padding: '8px 12px', 
          backgroundColor: '#f6ffed', 
          border: '1px solid #b7eb8f',
          borderRadius: 4,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <Text strong style={{ fontSize: '13px', color: '#52c41a' }}>
            💰 Price
          </Text>
          <Text strong style={{ fontSize: '16px', color: '#52c41a' }}>
            ${metadata.price}
          </Text>
        </div>
      )}

      {/* 热度信息 - 突出显示 */}
      {(metadata.reviews_per_month || metadata.number_of_reviews || metadata.review_scores_rating) && (
        <div style={{ 
          marginTop: 8, 
          padding: '6px 10px', 
          backgroundColor: '#fff7e6', 
          border: '1px solid #ffd591',
          borderRadius: 4
        }}>
          <Space size="small" wrap>
            {metadata.reviews_per_month && (
              <Text type="secondary" style={{ fontSize: '11px' }}>
                🔥 {metadata.reviews_per_month} reviews/month
              </Text>
            )}
            {metadata.number_of_reviews && (
              <Text type="secondary" style={{ fontSize: '11px' }}>
                📊 {metadata.number_of_reviews} total reviews
              </Text>
            )}
            {metadata.review_scores_rating && (
              <Text type="secondary" style={{ fontSize: '11px' }}>
                ⭐ {metadata.review_scores_rating}/100 rating
              </Text>
            )}
          </Space>
        </div>
      )}

      {/* 其他元数据 */}
      <div style={{ marginTop: 8 }}>
        <Space size="small" wrap>
          {metadata.host_name && (
            <Text type="secondary" style={{ fontSize: '11px' }}>
              👤 Host: {metadata.host_name}
            </Text>
          )}
          {metadata.availability_365 && (
            <Text type="secondary" style={{ fontSize: '11px' }}>
              📅 Available: {metadata.availability_365} days
            </Text>
          )}
        </Space>
      </div>
    </Card>
  );
};

// 源文档详情弹窗组件
const SourceDetailModal = ({ visible, onCancel, sourceDocuments }: { visible: boolean; onCancel: () => void; sourceDocuments: any[] }) => {
  return (
    <Modal
      title={
        <Space>
          <DatabaseOutlined />
          <span>source document details</span>
          <Badge count={sourceDocuments?.length || 0} size="small" />
        </Space>
      }
      open={visible}
      onCancel={onCancel}
      footer={null}
      width={700}
      bodyStyle={{ 
        maxHeight: '70vh', 
        overflowY: 'auto',
        padding: '16px'
      }}
    >
      {sourceDocuments && sourceDocuments.length > 0 ? (
        <div>
          <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          The following is a snippet of the source document that was referenced when generating the response. You can view the specific property review content and metadata information.
          </Paragraph>
          
          {sourceDocuments.map((doc, index) => (
            <SourceDocCard 
              key={index} 
              doc={doc} 
              index={index}
            />
          ))}
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Text type="secondary">No source document information available</Text>
        </div>
      )}
    </Modal>
  );
};

// 主要的 RAG 源文档提示组件
const RagSourceTooltip = ({ 
  sourceDocuments, 
  children, 
  placement = "topRight" as const,
  showDetailModal = true 
}: { 
  sourceDocuments: any[]; 
  children: React.ReactNode; 
  placement?: "topRight" | "topLeft" | "bottomRight" | "bottomLeft";
  showDetailModal?: boolean;
}) => {
  const [modalVisible, setModalVisible] = useState(false);
  
  // 检查是否有源文档
  const hasSourceDocs = sourceDocuments && sourceDocuments.length > 0;
  
  if (!hasSourceDocs) {
    return children; // 没有源文档时直接返回原组件
  }

  // 悬浮提示内容
  const tooltipContent = (
    <div style={{ maxWidth: 300 }}>
      <div style={{ marginBottom: 8 }}>
        <Space>
          <DatabaseOutlined style={{ color: '#52c41a' }} />
          <Text strong style={{ color: 'white' }}>Generated from {sourceDocuments.length} source documents</Text>
        </Space>
      </div>
      
      <Text style={{ color: 'rgba(255,255,255,0.85)', fontSize: '12px' }}>
        This response is generated based on relevant property review data. Click to view detailed source information.
      </Text>
      
      {showDetailModal && (
        <div style={{ marginTop: 8, textAlign: 'center' }}>
          <Button 
            type="primary" 
            size="small"
            icon={<EyeOutlined />}
            onClick={(e) => {
              e.stopPropagation();
              setModalVisible(true);
            }}
          >
            View Source Documents
          </Button>
        </div>
      )}
    </div>
  );

  return (
    <>
      {/* 添加 RAG 标识的包装器 */}
      <div style={{ position: 'relative' }}>
        {/* RAG 标识徽章 */}
        <div style={{ 
          position: 'absolute', 
          top: -2, 
          right: -2, 
          zIndex: 10 
        }}>
          <Tooltip 
            title={tooltipContent}
            placement={placement}
            color="#52c41a"
            overlayStyle={{ maxWidth: 320 }}
          >
            <Badge 
              count={
                <DatabaseOutlined 
                  style={{ 
                    color: '#52c41a', 
                    fontSize: '12px',
                    cursor: 'pointer'
                  }} 
                />
              } 
              style={{ 
                backgroundColor: 'transparent',
                boxShadow: 'none'
              }}
              onClick={() => showDetailModal && setModalVisible(true)}
            />
          </Tooltip>
        </div>
        
        {/* 原始内容，添加轻微的样式变化 */}
        <div style={{
          position: 'relative',
          border: hasSourceDocs ? '1px solid #b7eb8f' : 'none',
          borderRadius: hasSourceDocs ? '12px' : '0',
          backgroundColor: hasSourceDocs ? '#f6ffed' : 'transparent'
        }}>
          {children}
        </div>
      </div>

      {/* 源文档详情弹窗 */}
      {showDetailModal && (
        <SourceDetailModal
          visible={modalVisible}
          onCancel={() => setModalVisible(false)}
          sourceDocuments={sourceDocuments}
        />
      )}
    </>
  );
};

export default RagSourceTooltip;

// // 使用示例组件
// export const RagSourceTooltipExample = () => {
//   // 模拟数据
//   const sampleSourceDocs = [
//     {
//       page_content: "这个房源位置很好，交通便利，周围有很多餐厅和商店。房东很友好，回复很及时。房间很干净，设施齐全。整体体验非常满意，下次还会选择这里。",
//       metadata: {
//         listing_id: "12345",
//         neighbourhood: "曼哈顿",
//         room_type: "Entire home/apt",
//         price: 150
//       }
//     },
//     {
//       page_content: "住了三天，总体感觉不错。房间比照片看起来小一些，但是很干净。位置很好，步行到地铁站只需要5分钟。房东人很好，有问题都会及时回复。",
//       metadata: {
//         listing_id: "67890",
//         neighbourhood: "布鲁克林",
//         room_type: "Private room",
//         price: 80
//       }
//     }
//   ];

//   const sampleMessage = (
//     <div style={{ 
//       padding: '12px 16px',
//       backgroundColor: '#f5f5f5',
//       borderRadius: '12px',
//       maxWidth: '400px'
//     }}>
//       根据分析多个房源的用户评论，曼哈顿和布鲁克林地区的房源整体评价较好。用户普遍反馈交通便利，房东响应及时，房间干净。不过部分房源可能实际空间比照片显示的要小一些。
//     </div>
//   );

//   return (
//     <div style={{ padding: '20px', backgroundColor: '#fff' }}>
//       <h3>RAG 源文档提示组件示例</h3>
      
//       <div style={{ marginBottom: '20px' }}>
//         <h4>有源文档的消息（悬停查看提示）:</h4>
//         <RagSourceTooltip sourceDocuments={sampleSourceDocs}>
//           {sampleMessage}
//         </RagSourceTooltip>
//       </div>
      
//       <div style={{ marginBottom: '20px' }}>
//         <h4>普通消息（无源文档）:</h4>
//         <RagSourceTooltip sourceDocuments={null}>
//           {sampleMessage}
//         </RagSourceTooltip>
//       </div>
//     </div>
//   );
// };