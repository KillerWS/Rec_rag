import pandas as pd
import re
from collections import Counter
from db import execute_query

def clean_text(text):
    """简单清洗评论文本"""
    text = str(text).lower()
    text = re.sub(r"[^\w\s]", "", text)  # 去除标点
    return text

def get_review_wordcloud_data(top_n=50):
    """生成评论词云所需数据（Top N 高频词）"""
    query = "SELECT comments FROM reviews WHERE comments IS NOT NULL"
    df = execute_query(query)

    if df.empty:
        return []

    all_text = " ".join([clean_text(c) for c in df['comments'] if isinstance(c, str)])

    # 拆分单词
    words = all_text.split()

    # 过滤一些常见无意义词（你可以自己扩展）
    stopwords = set(["the", "and", "is", "it", "to", "in", "we", "i", "a", "of", "for", "was", "with", "very"])

    meaningful_words = [w for w in words if w not in stopwords and len(w) > 2]

    # 统计词频
    word_counter = Counter(meaningful_words)

    # 取前 top_n 高频词
    wordcloud_data = [{"name": word, "value": count} for word, count in word_counter.most_common(top_n)]

    return wordcloud_data
