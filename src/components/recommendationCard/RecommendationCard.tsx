import { Card, Tag, Tooltip, Rate, Descriptions, Badge } from "antd";
import { HomeOutlined, EnvironmentOutlined, EuroOutlined } from "@ant-design/icons";

// Update interface to match backend response format
interface RecommendationProps {
  id: string;
  name: string;
  price: number;
  room_type: string;
  neighbourhood?: string;
  neighbourhood_group?: string;
  availability_365?: number;
  number_of_reviews?: number;
  number_of_reviews_ltm?: number;
  reviews_per_month?: number | null;
  last_review?: string | null;
  recommendation_score?: number | null;
  latitude?: number;
  longitude?: number;
  license?: string;
  minimum_nights?: number;
  host_id?: number;
  host_name?: string;
  calculated_host_listings_count?: number;
  [key: string]: any;
}

const RecommendationCard = ({
  name,
  price,
  room_type,
  neighbourhood,
  neighbourhood_group,
  availability_365,
  number_of_reviews,
  reviews_per_month,
  last_review,
  recommendation_score,
  host_name,
  minimum_nights,
}: RecommendationProps) => {
  // 🔹 将 availability 转成"活跃度"标签
  const availabilityLevel = availability_365 && availability_365 > 300 ? "High"
                         : availability_365 && availability_365 > 150 ? "Medium"
                         : "Low";

  // 🔹 将评分转换为星级评分（模拟，实际可用评论分析）
  // Handle NaN values by providing defaults
  const reviewsPerMonth = typeof reviews_per_month === 'number' && !isNaN(reviews_per_month) ? reviews_per_month : 0;
  const recScore = typeof recommendation_score === 'number' && !isNaN(recommendation_score) ? recommendation_score : 0.5;
  
  const estimatedRating = Math.min(5, Number((reviewsPerMonth / 10 + recScore * 2).toFixed(1)));

  // Format recommendation score for display
  const scoreDisplay = typeof recommendation_score === 'number' && !isNaN(recommendation_score) 
    ? recommendation_score.toFixed(2)
    : "N/A";

  return (
    <Card
      title={name}
      bordered
      style={{ marginBottom: 16 }}
      extra={<Tag color="green">Score: {scoreDisplay}</Tag>}
    >
      <Descriptions size="small" column={1}>
        <Descriptions.Item label="💰 Price">
          <EuroOutlined /> {price} / night
        </Descriptions.Item>

        <Descriptions.Item label="🏡 Room Type">
          <HomeOutlined /> {room_type}
        </Descriptions.Item>

        {neighbourhood && neighbourhood_group && (
          <Descriptions.Item label="📍 Location">
            <EnvironmentOutlined /> {neighbourhood}, {neighbourhood_group}
          </Descriptions.Item>
        )}

        {last_review && (
          <Descriptions.Item label="📆 Last Review">
            {last_review}
          </Descriptions.Item>
        )}

        {host_name && (
          <Descriptions.Item label="👤 Host">
            {host_name}
          </Descriptions.Item>
        )}

        {minimum_nights && (
          <Descriptions.Item label="🗓️ Min. Stay">
            {minimum_nights} nights
          </Descriptions.Item>
        )}

        <Descriptions.Item label="⭐ Popularity">
          <Tooltip title={`Total Reviews: ${number_of_reviews || 0}, Monthly: ${reviewsPerMonth}`}>
            <Rate disabled allowHalf defaultValue={estimatedRating} />
          </Tooltip>
        </Descriptions.Item>

        <Descriptions.Item label="🕓 Availability">
          <Badge status={availabilityLevel === "High" ? "success" : availabilityLevel === "Medium" ? "warning" : "error"} text={availabilityLevel} />
        </Descriptions.Item>
      </Descriptions>
    </Card>
  );
};

export default RecommendationCard;
