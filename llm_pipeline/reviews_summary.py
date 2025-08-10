import pandas as pd
from db import execute_query
from collections import Counter
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from load_llm import get_llm  # 🔹 你的 LLM 加载模块

# 这个模块是做word cloud 高频短语的抽取s


# 🔹 Prompt模板
SUMMARY_PROMPT = """
You are an AI assistant helping to summarize Airbnb guest reviews.

Task:
- Read the following guest reviews.
- Extract the core feedback points in English.
- Summarize each feedback into a short phrase (5-10 words).
- Only focus on concrete aspects like host, location, room condition, facilities.
- Ignore generic phrases like "great", "well", "nice", "room".
- If reviews are not in English, translate them first.

Reviews:
{reviews_text}

Output:
- List of feedback points (one per line).
"""

def get_sampled_reviews(sample_size=1000, min_length=30):
    """从 reviews 表中抽取样本"""
    query = "SELECT comments FROM reviews WHERE comments IS NOT NULL"
    df = execute_query(query)
    
    if df.empty:
        return []
    
    comments = df['comments'].dropna()
    comments = comments[comments.str.len() >= min_length]
    
    sampled = comments.sample(n=min(sample_size, len(comments)), random_state=42).tolist()
    return sampled

import re

def summarize_reviews_with_llm(reviews_batch):
    """对一批 reviews 调用 LLM 总结观点"""
    llm = get_llm()

    if llm is None:
        return []

    prompt = PromptTemplate(input_variables=["reviews_text"], template=SUMMARY_PROMPT)
    chain = LLMChain(llm=llm, prompt=prompt, output_key="summary")

    joined_reviews = "\n".join(reviews_batch)

    try:
        response = chain.run(reviews_text=joined_reviews)
    except Exception as e:
        print(f"⚠️ LLM summarization failed: {e}")
        return []

    # 原来简单处理：
    # points = [line.strip("- ").strip() for line in response.strip().split("\n") if line.strip()]

    # ✅ 新版处理，加过滤逻辑
    points = []
    for line in response.strip().split("\n"):
        clean_line = line.strip("- ").strip()

        if not clean_line:
            continue

        # 如果只包含非字母字符（如逗号、括号等），跳过
        if not re.search(r"[a-zA-Z]", clean_line):
            continue

        # 如果太短，比如少于3个字符，也跳过
        if len(clean_line) < 3:
            continue

        points.append(clean_line)

    return points

import re

def clean_phrase(text):
    """清理LLM输出的每个短语"""
    if not isinstance(text, str):
        return ""

    # 去除多余的引号和大括号
    text = text.strip()
    text = re.sub(r"^[{\"\':,.\s]+", "", text)  # 去掉开头的 { " , .
    text = re.sub(r"[}\"',.\s]+$", "", text)    # 去掉结尾的 } " , .
    
    return text

def get_review_insights(sample_size=1000, batch_size=20, top_n=50, min_length=30):
    """
    主函数：返回词云数据
    
    参数：
    - sample_size: 总共抽取多少条评论
    - batch_size: 每一批送给 LLM 多少条评论
    - top_n: 最后统计出现频率最多的短语数
    - min_length: 最短评论长度过滤
    """
    sampled_reviews = get_sampled_reviews(sample_size=sample_size, min_length=min_length)

    if not sampled_reviews:
        return []

    all_points = []

    for i in range(0, len(sampled_reviews), batch_size):
        batch = sampled_reviews[i:i+batch_size]
        batch_points = summarize_reviews_with_llm(batch)
        all_points.extend(batch_points)

        print(f"✅ Processed batch {i // batch_size + 1} ({len(batch)} reviews)")

    # 统计词频
    counter = Counter(all_points)
    top_points = counter.most_common(top_n)

    # 转成前端需要的格式
    wordcloud_data = [{"name": clean_phrase(point), "value": count} for point, count in top_points if clean_phrase(point)]

    return wordcloud_data
