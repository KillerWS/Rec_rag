import { ListingCardProps } from "./ListingCard.types";

export const toBooleanLike = (v: any): boolean => v === true || v === 't' || v === 'True' || v === 'true';

export const getRating5 = (review_scores_rating?: number | string | null): string | null => {
  if (review_scores_rating === undefined || review_scores_rating === null || review_scores_rating === '') return null;
  const num = Number(review_scores_rating);
  if (Number.isNaN(num)) return null;
  return (num / 20).toFixed(2);
};

export const formatPriceLabel = (price?: number, price_original?: string): string => {
  if (typeof price === 'number' && !Number.isNaN(price)) return `€${Math.round(price)} / night`;
  return price_original ?? '';
};

export const getAreaTag = (neighbourhood_cleansed?: string, neighbourhood_group_cleansed?: string): string => {
  return neighbourhood_cleansed ?? neighbourhood_group_cleansed ?? '';
};

export const getLink = (listing_url: string | undefined, id: number | string): string => {
  if (listing_url && listing_url.trim()) return listing_url;
  return `https://www.airbnb.com/rooms/${id}`;
};

export type BadgeItem = { key: string; label: string; color: string };

export const getBadges = (p: ListingCardProps): BadgeItem[] => {
  const badges: BadgeItem[] = [];
  const rating = typeof p.review_scores_rating === 'number' ? p.review_scores_rating : Number(p.review_scores_rating);
  if (!Number.isNaN(rating) && rating >= 96 && (p.number_of_reviews ?? 0) >= 100) {
    badges.push({ key: 'guest_favorite', label: 'Guest Favorite', color: 'gold' });
  }
  if (toBooleanLike(p.host_is_superhost)) {
    badges.push({ key: 'superhost', label: 'Superhost', color: 'magenta' });
  }
  if (toBooleanLike(p.instant_bookable)) {
    badges.push({ key: 'instant_book', label: 'Instant Book', color: 'green' });
  }
  if (typeof p.availability_365 === 'number' && p.availability_365 <= 30) {
    badges.push({ key: 'rare_find', label: 'Rare find', color: 'purple' });
  }
  return badges.slice(0, 2);
};

export const buildQuickReasons = (p: ListingCardProps): string[] => {
  const lines: string[] = [];
  if (p.match_reason && p.match_reason.trim()) {
    lines.push(p.match_reason);
  }
  const roomGuest = [p.room_type, typeof p.accommodates === 'number' && p.accommodates > 0 ? (p.accommodates === 1 ? '1 guest' : `Up to ${p.accommodates} guests`) : null]
    .filter(Boolean)
    .join(' • ');
  if (roomGuest) lines.push(roomGuest);

  const bedBathParts: string[] = [];
  if (p.beds !== undefined && p.beds !== null && String(p.beds).trim() !== '') bedBathParts.push(`${p.beds} beds`);
  const bathText = p.bathrooms_text ?? p.bathrooms;
  if (bathText && bathText.trim()) bedBathParts.push(bathText);
  if (bedBathParts.length) lines.push(bedBathParts.join(' • '));

  if (typeof p.availability_365 === 'number') lines.push(`Available ~${p.availability_365} days/yr`);

  if (p.host_name) {
    const superHost = toBooleanLike(p.host_is_superhost) ? ' ⭐ Superhost' : '';
    lines.push(`${p.host_name}${superHost}`);
  }

  return lines.slice(0, 3);
};

export type ReasonItem = { key: 'why' | 'room' | 'bedbath' | 'availability' | 'host'; text: string };

export const buildQuickReasonItems = (p: ListingCardProps): ReasonItem[] => {
  const items: ReasonItem[] = [];
  if (p.match_reason && p.match_reason.trim()) items.push({ key: 'why', text: p.match_reason });

  const roomGuest = [p.room_type, typeof p.accommodates === 'number' && p.accommodates > 0 ? (p.accommodates === 1 ? '1 guest' : `Up to ${p.accommodates} guests`) : null]
    .filter(Boolean)
    .join(' • ');
  if (roomGuest) items.push({ key: 'room', text: roomGuest });

  const bedBathParts: string[] = [];
  if (p.beds !== undefined && p.beds !== null && String(p.beds).trim() !== '') bedBathParts.push(`${p.beds} beds`);
  const bathText = p.bathrooms_text ?? p.bathrooms;
  if (bathText && bathText.trim()) bedBathParts.push(bathText);
  if (bedBathParts.length) items.push({ key: 'bedbath', text: bedBathParts.join(' • ') });

  if (typeof p.availability_365 === 'number') items.push({ key: 'availability', text: `Available ~${p.availability_365} days/yr` });

  if (p.host_name) {
    const superHost = toBooleanLike(p.host_is_superhost) ? ' ⭐ Superhost' : '';
    items.push({ key: 'host', text: `${p.host_name}${superHost}` });
  }

  return items.slice(0, 3);
};

const FEATURE_WHITELIST: Array<{ pattern: RegExp; phrase: string }> = [
  { pattern: /(u-bahn|ubahn|s-bahn|sbahn|subway|metro|train|station)/i, phrase: 'near metro' },
  { pattern: /(balcony|terrace)/i, phrase: 'with balcony' },
  { pattern: /(river|canal|spree)/i, phrase: 'river view' },
  { pattern: /(park|garden|courtyard)/i, phrase: 'near park' },
  { pattern: /(quiet|calm|peaceful)/i, phrase: 'quiet street' },
  { pattern: /(bright|sunny|light-filled)/i, phrase: 'bright' },
  { pattern: /(kitchen)/i, phrase: 'with kitchen' },
  { pattern: /(washer|laundry)/i, phrase: 'with washer' },
  { pattern: /(desk|workspace|work space)/i, phrase: 'with workspace' },
  { pattern: /(family|kid|child)/i, phrase: 'family-friendly' },
];

const extractFeatureFromDescription = (description?: string): string | null => {
  if (!description) return null;
  for (const item of FEATURE_WHITELIST) {
    if (item.pattern.test(description)) return item.phrase;
  }
  return null;
};

const pluralize = (value: number, singular: string, plural: string): string => {
  return `${value} ${value === 1 ? singular : plural}`;
};

export const buildWhyThisAndChips = (p: ListingCardProps): { whyThis: string; chips: string[] } => {
  const segments: string[] = [];

  // Budget / quality
  if (typeof p.price === 'number' && p.price > 0 && p.price <= 150) {
    segments.push('Under €150');
  } else if (typeof p.number_of_reviews === 'number' && p.number_of_reviews > 0) {
    if (p.number_of_reviews >= 200) segments.push('200+ reviews');
    else segments.push(`${p.number_of_reviews} reviews`);
  }

  // Location
  const area = getAreaTag(p.neighbourhood_cleansed, p.neighbourhood_group_cleansed);
  if (area) segments.push(area);

  // Room type
  if (p.room_type) segments.push(p.room_type);

  // Description feature
  const feat = extractFeatureFromDescription(p.description);
  if (feat) segments.push(feat);

  const whyThis = segments.filter(Boolean).slice(0, 4).join(' · ');

  // Chips
  const chips: string[] = [];
  if (p.room_type || typeof p.accommodates === 'number') {
    const cap = typeof p.accommodates === 'number' && p.accommodates > 0
      ? (p.accommodates === 1 ? '1 guest' : `Up to ${p.accommodates} guests`)
      : '';
    chips.push([p.room_type, cap].filter(Boolean).join(' • '));
  }

  const bedsNum = typeof p.beds === 'number' ? p.beds : (p.beds ? Number(p.beds) : NaN);
  const bedsLabel = Number.isFinite(bedsNum) ? pluralize(bedsNum as number, 'bed', 'beds') : (p.beds ? `${p.beds} beds` : '');
  const bathLabel = p.bathrooms_text ?? (p.bathrooms ? String(p.bathrooms) : '');
  if ((bedsLabel && bedsLabel.trim()) || (bathLabel && bathLabel.trim())) {
    chips.push([bedsLabel || null, bathLabel || null].filter(Boolean).join(' • '));
  }

  if (typeof p.availability_365 === 'number') {
    chips.push(`Available ~${Math.round(p.availability_365)} days/yr`);
  }

  if (p.host_name) {
    const sup = toBooleanLike(p.host_is_superhost) ? ' ⭐ Superhost' : '';
    chips.push(`Host: ${p.host_name}${sup}`);
  }

  return { whyThis, chips: chips.filter(Boolean).slice(0, 3) };
}; 

export const buildHoverTexts = (d: ListingCardProps): { whyThis: string; chips: string[] } => {
  const short = (s: string = '', n: number = 110): string => (s.length > n ? s.slice(0, n - 1) + '…' : s);

  const loc = d.neighbourhood_cleansed || d.neighbourhood_group_cleansed;
  const tokens: string[] = [];

  if (typeof d.price === 'number' && !Number.isNaN(d.price) && d.price > 0) tokens.push(`Under €${Math.ceil(d.price)}`);
  if (loc) tokens.push(loc);
  if (d.room_type) tokens.push(d.room_type);

  const baseText = (d.match_reason || d.description || '') as string;
  const match = baseText.match(/\b(balcony|metro|subway|quiet|bright|view|garden|kitchen|washer|desk)\b/i);
  const hint = match ? match[0] : undefined;
  if (hint) {
    const h = hint.toLowerCase();
    tokens.push(h === 'metro' ? 'near metro' : `with ${h}`);
  }

  const whyThis = short(tokens.join(' · '), 110);

  const chips: string[] = [];
  if (d.room_type || d.accommodates) {
    const cap = typeof d.accommodates === 'number' && d.accommodates > 0 ? `Up to ${d.accommodates} guests` : '';
    chips.push(`${d.room_type || ''}${(d.room_type && cap) ? ' • ' : (cap ? '' : '')}${cap}`.trim());
  }

  if (d.beds || d.bathrooms_text || d.bathrooms) {
    const bath = (d.bathrooms_text || d.bathrooms) as string | undefined;
    const bedsLabel = d.beds !== undefined && d.beds !== null && String(d.beds).trim() !== '' ? `${d.beds} bed` : '';
    const middleDot = bedsLabel && bath ? ' • ' : '';
    chips.push(`${bedsLabel}${middleDot}${bath || ''}`.trim());
  }

  if (typeof d.availability_365 === 'number') chips.push(`Available ~${d.availability_365} days/yr`);
  if (d.host_name) chips.push(`Host: ${d.host_name}${toBooleanLike(d.host_is_superhost) ? ' ⭐ Superhost' : ''}`);

  return { whyThis, chips: chips.filter(Boolean).slice(0, 3) };
}; 