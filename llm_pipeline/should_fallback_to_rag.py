from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from load_llm import get_llm  # 你已有的 LLM 加载方法
from langchain_core.messages import HumanMessage

RAG_CLASSIFICATION_PROMPT = """
You are a classification assistant helping to decide whether a user's message requires knowledge base retrieval (RAG) or is just a general conversational inquiry.

Instructions:
- Read the message below.
- Decide whether the user is asking for factual information, comparisons, statistics, maps, analysis, or insights that are not part of casual chat.
- If yes, classify it as: RAG
- If it's just a greeting, thanks, or vague preference, classify it as: CONVERSATIONAL

User message:
{message}

Answer with a single word: RAG or CONVERSATIONAL.
"""

def should_fallback_to_rag(user_message: str) -> bool:
    """调用 LLM 判断是否应走 RAG 路由"""
    try:
        llm = get_llm()
        if llm is None:
            print("⚠️ 无法加载LLM，默认返回 False")
            return False
        
        # 使用 LangChain 的 API
        prompt = RAG_CLASSIFICATION_PROMPT.format(message=user_message)
        response = llm.invoke([HumanMessage(content=prompt)])
        
        # 获取响应文本并处理
        result = response.content.strip().upper()
        
        print(f"🔍 LLM 分类结果: {result}")
        return result == "RAG"

    except Exception as e:
        print(f"❌ LLM分类异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_should_fallback_to_rag():
    """测试 should_fallback_to_rag 函数"""
    # 测试应该返回 RAG 的情况
    rag_message = "哪些酒店在柏林米特区评价最好？"
    result_rag = should_fallback_to_rag(rag_message)
    print(f"测试信息: '{rag_message}'")
    print(f"预期结果: RAG, 实际结果: {'RAG' if result_rag else 'CONVERSATIONAL'}")
    
    # 测试应该返回 CONVERSATIONAL 的情况
    conv_message = "你好，很高兴认识你！"
    result_conv = should_fallback_to_rag(conv_message)
    print(f"测试信息: '{conv_message}'")
    print(f"预期结果: CONVERSATIONAL, 实际结果: {'RAG' if result_conv else 'CONVERSATIONAL'}")
    
    return result_rag, result_conv

# 如果直接运行此文件，则执行测试
if __name__ == "__main__":
    test_should_fallback_to_rag()
