from typing import Dict, Optional
from db import execute_query
from .utils import generate_error_response


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    where = []
    if preferences.get("neighbourhood_group"):
        ng = preferences["neighbourhood_group"].replace("'", "''")
        where.append(f"neighbourhood_group_cleansed = '{ng}'")
    wc_where = " AND ".join(where) or "TRUE"
    sql = f"""
    WITH tokenized AS (
      SELECT unnest(string_to_array(regexp_replace(lower(comments), '[^a-z0-9 ]', '', 'g'), ' ')) AS word
      FROM reviews
      WHERE {wc_where}
    )
    SELECT word, COUNT(*) AS count
    FROM tokenized
    WHERE length(word) > 2
    GROUP BY word
    ORDER BY count DESC
    LIMIT 50;
    """
    df = execute_query(sql)
    if df.empty:
        return generate_error_response("No review keyword data found")
    return {
        "success": True,
        "chart_config": {"type": "wordcloud", "title": "Review Keywords Wordcloud"},
        "data": {"words": df["word"].tolist(), "counts": df["count"].tolist()},
        "metadata": {"distinct_words": len(df)}
    } 