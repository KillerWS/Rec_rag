from llm_pipeline.should_fallback_to_rag import should_fallback_to_rag

def test_should_fallback_to_rag():
    """测试 should_fallback_to_rag 函数"""
    print("\n=== 测试 should_fallback_to_rag 函数 ===\n")
    
    # 测试应该返回 RAG 的情况
    rag_messages = [
        "柏林米特区有哪些最好的酒店？",
        "请比较柏林的克罗伊茨贝格和弗里德里希斯海因区域的酒店价格。",
        "在柏林哪里可以找到最便宜的公寓？",
        "柏林的酒店平均评分是多少？",
        "哪些地区的酒店提供免费早餐？"
    ]
    
    print("测试应该返回 RAG 的情况:")
    for message in rag_messages:
        result = should_fallback_to_rag(message)
        print(f"信息: '{message}'")
        print(f"预期: RAG, 实际: {'RAG' if result else 'CONVERSATIONAL'}")
        print("-" * 50)
    
    # 测试应该返回 CONVERSATIONAL 的情况
    conv_messages = [
        "你好，很高兴认识你！",
        "我更喜欢安静的地方",
        "谢谢你的帮助",
        "你能做什么？",
        "我想要一家靠近市中心的酒店"
    ]
    
    print("\n测试应该返回 CONVERSATIONAL 的情况:")
    for message in conv_messages:
        result = should_fallback_to_rag(message)
        print(f"信息: '{message}'")
        print(f"预期: CONVERSATIONAL, 实际: {'RAG' if result else 'CONVERSATIONAL'}")
        print("-" * 50)

if __name__ == "__main__":
    test_should_fallback_to_rag() 