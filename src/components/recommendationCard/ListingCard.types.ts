export type ListingCardProps = {
  id: number | string;
  listing_url?: string;
  picture_url?: string;
  name: string;
  neighbourhood_cleansed?: string;
  neighbourhood_group_cleansed?: string;
  room_type?: string;
  accommodates?: number;
  beds?: string | number;
  bedrooms?: string | number;
  bathrooms_text?: string;
  bathrooms?: string;
  price: number;
  price_original?: string;
  number_of_reviews?: number;
  review_scores_rating?: number | string; // 0–100
  review_scores_value?: number | string; // 0–5
  host_is_superhost?: boolean | 't' | 'f' | 'True' | 'False';
  instant_bookable?: boolean | 't' | 'f' | 'True' | 'False';
  availability_365?: number;
  host_name?: string;
  match_reason?: string;
  description?: string;
  amenities?: any;
}; 