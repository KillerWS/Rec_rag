import { Card } from "antd";

interface PriceSummaryCardProps {
  totalListings: number;
  avgPrice: number;
  medianPrice: number;
  minPrice: number;
  maxPrice: number;
  budgetMin?: number | null;
  budgetMax?: number | null;
  coveragePct?: number | null;
  city?: string;
  recommendedAreas?: Array<{ type?: 'budget' | 'popular' | 'balanced'; name: string; note: string }>;
}

const Highlight = ({ children }: { children: any }) => (
  <span className="font-semibold text-blue-700">{children}</span>
);

const iconForType = (type?: 'budget' | 'popular' | 'balanced') => {
  if (type === 'budget') return '💰';
  if (type === 'popular') return '⭐';
  if (type === 'balanced') return '⚖️';
  return '•';
};

const PriceSummaryCard = ({
  totalListings,
  avgPrice,
  medianPrice,
  minPrice,
  maxPrice,
  budgetMin = null,
  budgetMax = null,
  coveragePct = null,
  city = "Berlin",
  recommendedAreas = [],
}: PriceSummaryCardProps) => {
  const hasBudget = budgetMin != null && budgetMax != null;
  const avgRounded = Math.round(avgPrice);

  const relation = hasBudget
    ? (budgetMax! < medianPrice
        ? 'below'
        : budgetMin! > medianPrice
          ? 'above'
          : 'around')
    : null;

  const relationText = relation === 'above'
    ? 'sits above the median'
    : relation === 'below'
      ? 'sits below the median'
      : 'straddles the median';

  const segmentText = relation === 'above'
    ? 'mostly in mid‑ to higher‑end categories'
    : relation === 'below'
      ? 'mostly in lower‑ to mid‑range categories'
      : 'largely in mid‑range categories';

  const coveragePhrase = (() => {
    if (!hasBudget) return '';
    if (coveragePct == null) return 'covers a share of available listings';
    const pct = Math.round(coveragePct);
    if (pct >= 70) return `covers most of available listings (~${pct}%)`;
    if (pct >= 40) return `covers a substantial share (~${pct}%)`;
    if (pct >= 20) return `covers a moderate share (~${pct}%)`;
    return `covers a smaller share (~${pct}%)`;
  })();

  return (
    <Card size="small" bordered className="mt-2">
      {/* <Typography.Title level={5} className="!mb-2">Summary</Typography.Title> */}
      <div className="text-sm space-y-2">
        <div>
          <Highlight>{city}</Highlight> currently has <Highlight>{totalListings.toLocaleString()}</Highlight> listings.
        </div>
        {!hasBudget && (
          <div>
            The average price is about <Highlight>€{avgRounded}</Highlight> per night, but the median is lower at <Highlight>€{medianPrice}</Highlight> — meaning half of listings cost less than <Highlight>€{medianPrice}</Highlight>.
          </div>
        )}
        {!hasBudget && (
          <div>
            Prices span a wide range (<Highlight>€{minPrice}</Highlight>–<Highlight>€{maxPrice}</Highlight>), though most options cluster well below the extreme high end.
          </div>
        )}
        {hasBudget && (
          <div>
            The average nightly rate is about <Highlight>€{avgRounded}</Highlight>, and half of listings are under <Highlight>€{medianPrice}</Highlight>.
          </div>
        )}
        {hasBudget && (
          <div>
            Your budget (<Highlight>€{budgetMin}</Highlight>–<Highlight>€{budgetMax}</Highlight>) {relationText} and {coveragePhrase}, {segmentText}.
          </div>
        )}

        {hasBudget && recommendedAreas.length > 0 && (
          <div className="mt-1">
            <div className="font-medium">Some areas you might consider:</div>
            <ul className="mt-1 space-y-1">
              {recommendedAreas.map((r, idx) => (
                <li key={`${r.name}-${idx}`} className="flex items-start gap-2">
                  <span className="leading-6">{iconForType(r.type)}</span>
                  <span><Highlight>{r.name}</Highlight> — {r.note}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Card>
  );
};

export default PriceSummaryCard; 