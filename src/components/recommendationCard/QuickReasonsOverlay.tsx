import { useMemo, useState } from "react";

export interface QuickReasonsOverlayProps {
  whyThis: string;
  chips: string[];
  className?: string;
  description?: string;

  variant?: "light" | "dark";
  maxChips?: number;
  dedupeWithWhy?: boolean;

  // structured fields for details
  room_type?: string;
  accommodates?: number;
  bedrooms?: string | number;
  beds?: string | number;
  bathrooms_text?: string;
  bathrooms?: string;
  amenities?: any;
}

const normalize = (s?: string) =>
  (s || "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[.;,|•]+/g, " ")
    .trim();

const uniq = (arr: string[]) => {
  const seen = new Set<string>();
  return arr.filter((x) => {
    const key = normalize(x);
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

const chipIcon = (text: string) => {
  const t = normalize(text);
  if (/\b(guest|guests)\b/.test(t)) return "👥";
  if (/\bbed(s)?\b/.test(t)) return "🛏️";
  if (/\bbath(s)?\b/.test(t)) return "🛁";
  if (/\bavailable|day(s)?\/yr|day\(s\)\/year\b/.test(t)) return "📅";
  if (/\bhost\b/.test(t)) return "👤";
  if (/\bsuperhost\b/.test(t)) return "⭐";
  if (/\bprivate room|entire home|entire place|shared room|studio\b/.test(t)) return "🏠";
  if (/\bmetro|subway|u-bahn|s-bahn|station\b/.test(t)) return "🚇";
  return "•";
};

const decodeEntities = (input: string): string => {
  try {
    if (typeof window === 'undefined' || typeof document === 'undefined') return input;
    const el = document.createElement('textarea');
    el.innerHTML = input;
    return el.value;
  } catch {
    return input;
  }
};

const buildDescriptionLines = (raw?: string): string[] => {
  if (!raw) return [];
  const withBreaks = raw.replace(/<br\s*\/?>(\r?\n)?/gi, "\n");
  const withoutTags = withBreaks.replace(/<[^>]+>/g, " ");
  const decoded = decodeEntities(withoutTags);
  return decoded
    .split(/\n+/)
    .map(s => s.replace(/\s+/g, ' ').trim())
    .filter(Boolean);
};

const parseAmenities = (amenities: any): string[] => {
  try {
    if (Array.isArray(amenities)) {
      return amenities.map(String);
    }
    
    if (typeof amenities === 'string') {
      const s = amenities.trim();
      
      if (s.startsWith('[')) {
        try {
          // First try direct JSON.parse
          const arr = JSON.parse(s);
          if (Array.isArray(arr)) {
            return arr.map((x: any) => String(x));
          }
        } catch (jsonError) {
          try {
            // Try to fix common Unicode escape issues
            // Handle double-escaped Unicode sequences like \\u2019 -> \u2019
            let fixedString = s.replace(/\\\\u([0-9a-fA-F]{4})/g, '\\u$1');
            
            // Also handle cases where backslashes might be over-escaped
            fixedString = fixedString.replace(/\\\\\"/g, '\\"');
            
            const arr = JSON.parse(fixedString);
            if (Array.isArray(arr)) {
              return arr.map((x: any) => String(x));
            }
          } catch (fixedJsonError) {
            // Last resort: try to extract items manually using regex
            const matches = s.match(/"([^"\\]|\\.)*"/g);
            if (matches && matches.length > 0) {
              const result = matches.map(match => {
                try {
                  // Remove outer quotes and parse the individual string
                  return JSON.parse(match);
                } catch {
                  // If individual parsing fails, just remove quotes
                  return match.slice(1, -1);
                }
              });
              return result;
            }
          }
        }
      }
      
      // Final fallback: split by commas (for non-JSON strings)
      return s.split(',').map(v => v.trim()).filter(Boolean);
    }
    
    if (amenities && typeof amenities === 'object') {
      // Handle case where amenities might be an object with properties
      if (amenities.amenities && Array.isArray(amenities.amenities)) {
        return amenities.amenities.map(String);
      }
    }
  } catch (error) {
    console.error('parseAmenities error:', error);
  }
  return [];
};

const amenityIcon = (name: string): string => {
  const t = normalize(name);
  if (/\bwifi\b/.test(t)) return "📶";
  if (/\bkitchen\b/.test(t)) return "👩‍🍳";
  if (/\bwasher|laundry\b/.test(t)) return "🧺";
  if (/\bdryer\b/.test(t)) return "🌀";
  if (/\bworkspace|desk\b/.test(t)) return "💼";
  if (/\belevator\b/.test(t)) return "🛗";
  if (/\bcoffee\b|\bcoffee maker\b/.test(t)) return "☕";
  if (/\bheating\b/.test(t)) return "🔥";
  if (/\bair conditioning|ac\b/.test(t)) return "❄️";
  if (/\btv\b/.test(t)) return "📺";
  if (/\bself check-in\b|\bself check in\b/.test(t)) return "🔑";
  if (/\bfirst aid kit\b/.test(t)) return "⛑️";
  if (/\bfire extinguisher\b/.test(t)) return "🧯";
  if (/\bparking\b/.test(t)) return "🅿️";
  return "•";
};

const QuickReasonsOverlay = ({
  whyThis,
  chips,
  className = "",
  description,
  variant = "light",
  maxChips = 3,
  dedupeWithWhy = true,
  room_type,
  accommodates,
  bedrooms,
  beds,
  bathrooms_text,
  bathrooms,
  amenities
}: QuickReasonsOverlayProps) => {
  const { finalWhy, finalChips } = useMemo(() => {
    const w = (whyThis || "").trim();
    const wNorm = normalize(w);

    const filtered = (chips || [])
      .map((c) => c?.trim())
      .filter(Boolean)
      .map((c) => c!.replace(/\s*•\s*/g, " • ").replace(/\s+/g, " ").trim())
      .filter((c) => {
        if (!dedupeWithWhy) return true;
        const cNorm = normalize(c!);
        return !(cNorm && (wNorm.includes(cNorm) || cNorm.includes(wNorm)));
      });

    const unique = uniq(filtered).slice(0, Math.max(0, maxChips));
    return { finalWhy: w, finalChips: unique };
  }, [whyThis, chips, dedupeWithWhy, maxChips]);

  const descLines = useMemo(() => buildDescriptionLines(description), [description]);
  const descPlain = useMemo(() => (descLines.length ? descLines.join(' ') : ''), [descLines]);

  const isDark = variant === "dark";
  const wrapperBase = isDark
    ? "rounded-xl overflow-hidden bg-gradient-to-t from-black/80 via-black/25 to-transparent"
    : "rounded-xl overflow-hidden shadow-xl ring-1 ring-black/10 bg-white";

  const innerPad = "p-3 md:p-4";

  const titleCls = (isDark ? "text-white/95" : "text-gray-900") +
    " text-[12px] md:text-[13px] font-medium leading-snug line-clamp-2";

  const chipTextCls = (isDark ? "text-gray-200" : "text-gray-600") +
    " text-[11px] space-y-0.5 mt-1";

  const descWrapCls = (isDark ? "mt-2 border-t border-white/15 pt-2" : "mt-2 border-t border-black/10 pt-2");
  const descLineCls = (isDark ? "text-gray-100" : "text-gray-700") +
    " text-[11px] leading-snug";

  // Reorder chips: ensure availability separated
  const { otherChips, availabilityChip } = useMemo(() => {
    let avail: string | null = null;
    const others: string[] = [];

    for (const c of finalChips) {
      const norm = normalize(c);
      const isAvail = /\bavailable\b/i.test(norm);
      if (isAvail && !avail) {
        avail = c;
      } else {
        others.push(c);
      }
    }

    return { otherChips: others, availabilityChip: avail };
  }, [finalChips]);

  // Build combined room line: room_type + guests + bedrooms/beds/bath
  const combinedRoomLine = useMemo(() => {
    const parts: string[] = [];
    if (room_type) parts.push(room_type);

    // Coerce accommodates to number if it is numeric-like
    const guestsNum = typeof accommodates === 'number' ? accommodates : (accommodates !== undefined && accommodates !== null && !Number.isNaN(Number(accommodates)) ? Number(accommodates) : NaN);
    if (Number.isFinite(guestsNum) && guestsNum > 0) parts.push(guestsNum === 1 ? '1 guest' : `Up to ${guestsNum} guests`);

    // Bedrooms: prefer numeric for pluralization, fallback to string
    const bedroomsNum = bedrooms !== undefined && bedrooms !== null && !Number.isNaN(Number(bedrooms)) ? Number(bedrooms) : NaN;
    if (Number.isFinite(bedroomsNum)) {
      parts.push(`${bedroomsNum} ${bedroomsNum === 1 ? 'bedroom' : 'bedrooms'}`);
    } else if (bedrooms !== undefined && bedrooms !== null && String(bedrooms).trim() !== '') {
      const b = String(bedrooms).trim();
      parts.push(`${b} ${b === '1' ? 'bedroom' : 'bedrooms'}`);
    }

    // Beds: prefer numeric for pluralization, fallback to string
    const bedsNum = beds !== undefined && beds !== null && !Number.isNaN(Number(beds)) ? Number(beds) : NaN;
    if (Number.isFinite(bedsNum)) {
      parts.push(`${bedsNum} ${bedsNum === 1 ? 'bed' : 'beds'}`);
    } else if (beds !== undefined && beds !== null && String(beds).trim() !== '') {
      const bd = String(beds).trim();
      parts.push(`${bd} ${bd === '1' ? 'bed' : 'beds'}`);
    }

    const bath = bathrooms_text || bathrooms;
    if (bath && String(bath).trim()) parts.push(String(bath).trim());
    return parts.join(' • ');
  }, [room_type, accommodates, bedrooms, beds, bathrooms_text, bathrooms]);

  // Amenities list
  const amenityList = useMemo(() => parseAmenities(amenities), [amenities]);

  // Description expand/collapse state (single region)
  const [descExpanded, setDescExpanded] = useState<boolean>(false);

  return (
    <div
      className={`${wrapperBase} ${innerPad} ${className}`}
      role="dialog"
      aria-label="Why this"
    >
      {finalWhy ? <div className={titleCls}>{finalWhy}</div> : null}

      {/* Other chips (host, transport, etc.) */}
      {otherChips.length > 0 ? (
        <div className={chipTextCls}>
          {otherChips.map((c, i) => (
            <div key={i} className="truncate">
              <span className="mr-1">{chipIcon(c)}</span>
              {c}
            </div>
          ))}
        </div>
      ) : null}

      {/* Combined room line */}
      {combinedRoomLine ? (
        <div className={chipTextCls}>
          <div className="truncate">
            <span className="mr-1">🏠</span>
            {combinedRoomLine}
          </div>
          </div>
        ) : null}

      {/* Availability line */}
      {availabilityChip ? (
        <div className={chipTextCls}>
          <div className="truncate">
            <span className="mr-1">{chipIcon(availabilityChip)}</span>
            {availabilityChip}
          </div>
          </div>
        ) : null}

      {/* Amenities as pill block */}
      {amenityList.length > 0 ? (
        <div className={(isDark ? "text-gray-200" : "text-gray-700") + " mt-1 text-[11px] flex flex-wrap gap-1.5"}>
          {amenityList.slice(0, 12).map((a, idx) => (
            <span key={idx} className={(isDark ? "bg-white/10 text-white" : "bg-gray-100 text-gray-800") + " inline-flex items-center gap-1 px-2 py-0.5 rounded-full max-w-full truncate"}>
              <span>{amenityIcon(a)}</span>
              <span className="truncate">{a}</span>
            </span>
          ))}
        </div>
      ) : null}

      {/* Description block - single region with toggle */}
      {descLines.length > 0 ? (
        <div className={descWrapCls}>
          <div
            role="button"
            aria-expanded={descExpanded}
            onClick={() => setDescExpanded(v => !v)}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
          >
            <div className={(isDark ? "text-white/90" : "text-gray-900") + " text-[11px] font-medium"}>Description</div>
            <div aria-hidden="true" style={{ fontSize: 10, opacity: 0.8 }}>{descExpanded ? '▴' : '▾'}</div>
          </div>
          <div style={{ marginTop: 6 }}>
            {descExpanded ? (
              <div className="space-y-1">
                {descLines.map((line, idx) => (
                  <div key={idx} className={descLineCls}>{line}</div>
                ))}
              </div>
            ) : (
              <div
                className={descLineCls}
                style={{
                  display: '-webkit-box',
                  WebkitLineClamp: 3 as any,
                  WebkitBoxOrient: 'vertical' as any,
                  overflow: 'hidden'
                }}
              >
                {descPlain}
              </div>
            )}
        </div>
      </div>
      ) : null}
    </div>
  );
};

export default QuickReasonsOverlay; 