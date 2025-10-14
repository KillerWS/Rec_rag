import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Tag, Popover } from "antd";
import type { ListingCardProps } from "./ListingCard.types";
import { buildHoverTexts, formatPriceLabel, getAreaTag, getBadges, getLink, getRating5, toBooleanLike } from "./helpers";
import QuickReasonsOverlay from "./QuickReasonsOverlay";
import "./RecommendationCard.css";

const PLACEHOLDER_IMG = "/vite.svg";

const RecommendationCard = (props: ListingCardProps & Record<string, any>) => {
  const [imgSrc, setImgSrc] = useState<string>(props.picture_url || PLACEHOLDER_IMG);
  const [isTouchLike, setIsTouchLike] = useState<boolean>(false);
  const [popoverOpen, setPopoverOpen] = useState<boolean>(false);
  const [flyoutOpen, setFlyoutOpen] = useState<boolean>(false);
  const [flyoutPos, setFlyoutPos] = useState<{ top: number; left: number; placeAbove?: boolean }>({ top: 0, left: 0, placeAbove: false });
  const [flyoutHovering, setFlyoutHovering] = useState<boolean>(false);
  const closeTimerRef = useRef<number | null>(null);
  const imageWrapRef = useRef<HTMLDivElement | null>(null);
  const flyoutContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    try {
      const mq = window.matchMedia && window.matchMedia("(hover: none)");
      setIsTouchLike(!!mq?.matches);
    } catch {}
  }, []);

  useEffect(() => {
    setImgSrc(props.picture_url || PLACEHOLDER_IMG);
  }, [props.picture_url]);

  const rating5 = useMemo(() => {
    const value5 = props.review_scores_value;
    if (value5 !== undefined && value5 !== null && String(value5).trim() !== '') {
      const n = Number(value5);
      if (!Number.isNaN(n) && Number.isFinite(n)) return String(n);
    }
    return getRating5(props.review_scores_rating);
  }, [props.review_scores_value, props.review_scores_rating]);
  const priceLabel = useMemo(() => formatPriceLabel(props.price, props.price_original), [props.price, props.price_original]);
  const areaTag = useMemo(() => getAreaTag(props.neighbourhood_cleansed, props.neighbourhood_group_cleansed), [props.neighbourhood_cleansed, props.neighbourhood_group_cleansed]);
  const link = useMemo(() => getLink(props.listing_url, props.id), [props.listing_url, props.id]);
  const { whyThis, chips } = useMemo(() => buildHoverTexts(props), [props]);
  const badges = useMemo(() => getBadges(props), [props]);

  const openLink = () => {
    try {
      window.open(link, "_blank", "noopener,noreferrer");
    } catch {}
  };

  const clampFlyoutToViewport = () => {
    const el = flyoutContainerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const margin = 8;
    const viewportTop = window.scrollY + margin;
    const viewportBottom = window.scrollY + window.innerHeight - margin;
    let newTop = flyoutPos.top;
    const desiredBottom = newTop + rect.height;
    if (desiredBottom > viewportBottom) {
      newTop = Math.max(viewportTop, viewportBottom - rect.height);
    }
    if (newTop < viewportTop) newTop = viewportTop;
    if (newTop !== flyoutPos.top) {
      setFlyoutPos(prev => ({ ...prev, top: Math.round(newTop) }));
    }
  };

  useEffect(() => {
    if (!flyoutOpen) return;
    const el = flyoutContainerRef.current;
    if (!el) return;
    const hasRO = typeof (window as any).ResizeObserver === 'function';
    const ro = hasRO ? new (window as any).ResizeObserver(() => clampFlyoutToViewport()) : null;
    ro?.observe(el);
    const onResize = () => clampFlyoutToViewport();
    window.addEventListener('resize', onResize);
    clampFlyoutToViewport();
    return () => {
      ro?.disconnect();
      window.removeEventListener('resize', onResize);
    };
  }, [flyoutOpen, flyoutPos.top]);

  const handleMouseEnter = () => {
    if (isTouchLike) return;
    const el = imageWrapRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const viewportH = window.innerHeight;
    const defaultTop = Math.round(rect.top + window.scrollY + 8);
    const placeAbove = defaultTop + 260 > viewportH + window.scrollY; // heuristic
    const top = placeAbove ? Math.max(8 + window.scrollY, Math.round(rect.bottom + window.scrollY - 260)) : defaultTop;
    setFlyoutPos({ top, left: Math.round(rect.right + window.scrollX - 8), placeAbove });
    setFlyoutOpen(true);
  };

  const handleMouseLeave = () => {
    if (isTouchLike) return;
    if (closeTimerRef.current) {
      window.clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    closeTimerRef.current = window.setTimeout(() => {
      if (!flyoutHovering) setFlyoutOpen(false);
    }, 150);
  };

  const imageEl = (
    <div ref={imageWrapRef} className="rc-image-wrap" onClick={openLink} role="button" aria-label="Open listing">
      {toBooleanLike(props.instant_bookable) ? (
        <div
          aria-label="Instant bookable"
          style={{
            position: "absolute",
            top: 8,
            left: 8,
            zIndex: 1,
            background: "rgba(255,255,255,0.95)",
            borderRadius: 999,
            padding: "2px 8px",
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 12,
            color: "#111"
          }}
        >
          <span>⚡</span>
        </div>
      ) : null}
      <img
        className="rc-image rc-image-top-rounded"
        src={imgSrc}
        alt={props.name}
        loading="lazy"
        onError={() => setImgSrc(PLACEHOLDER_IMG)}
        style={{ height: 176 }}
      />
    </div>
  );

  const hasMeta = badges.length > 0;

  return (
    <div className="rc-card group" style={{ marginBottom: 16, position: "relative" }} onMouseEnter={handleMouseEnter} onMouseLeave={handleMouseLeave} tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') openLink(); }}>
      {/* Image with Popover for touch devices */}
      {isTouchLike ? (
        <Popover
          open={popoverOpen}
          onOpenChange={setPopoverOpen}
          trigger={["click"]}
          placement="bottom"
          overlayInnerStyle={{ padding: 0, background: "transparent" }}
          content={
            <div style={{ width: 288 }}>
              <QuickReasonsOverlay
                whyThis={whyThis}
                chips={chips}
                description={props.description || props.match_reason}
                variant="light"
                room_type={props.room_type}
                accommodates={props.accommodates}
                bedrooms={props.bedrooms}
                beds={props.beds}
                bathrooms_text={props.bathrooms_text}
                bathrooms={props.bathrooms}
                amenities={props.amenities}
              />
            </div>
          }
        >
          {imageEl}
        </Popover>
      ) : (
        imageEl
      )}

      {/* Portal flyout for non-touch, adapt to viewport bottom without inner scrollbars */}
      {!isTouchLike && flyoutOpen && typeof document !== 'undefined'
        ? createPortal(
            <div
              ref={flyoutContainerRef}
              style={{ position: "fixed", top: flyoutPos.top, left: flyoutPos.left, zIndex: 2000, width: 288 }}
              onMouseEnter={() => {
                if (closeTimerRef.current) {
                  window.clearTimeout(closeTimerRef.current);
                  closeTimerRef.current = null;
                }
                setFlyoutHovering(true);
              }}
              onMouseLeave={() => {
                setFlyoutHovering(false);
                setFlyoutOpen(false);
              }}
            >
              <QuickReasonsOverlay
                whyThis={whyThis}
                chips={chips}
                description={props.description || props.match_reason}
                variant="light"
                room_type={props.room_type}
                accommodates={props.accommodates}
                bedrooms={props.bedrooms}
                beds={props.beds}
                bathrooms_text={props.bathrooms_text}
                bathrooms={props.bathrooms}
                amenities={props.amenities}
              />
            </div>,
            document.body
          )
        : null}

      {/* Title + area tag */}
      <div className="rc-title-row">
        <div className="rc-title" onClick={openLink} role="button">{props.name}</div>
        {areaTag ? <Tag>{areaTag}</Tag> : null}
      </div>

      {/* Badges only (hide row if empty) */}
      {hasMeta ? (
        <div className="rc-meta-row">
          {badges.map(b => (
            <Tag key={b.key} color={b.color}>{b.label}</Tag>
          ))}
        </div>
      ) : null}

      {/* Price + rating at right */}
      <div className="rc-price-row">
        <div>{priceLabel}</div>
        {rating5 ? (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#111' }} title={typeof props.number_of_reviews === 'number' ? `Based on ${props.number_of_reviews} reviews` : undefined}>
            <span>⭐ {Number(rating5).toFixed(1)}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default RecommendationCard;
