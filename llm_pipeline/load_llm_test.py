import json
import os
# Google Genai 客户端导入
from google import genai

# Ollama 相关导入保留
from langchain.prompts import PromptTemplate
from langchain_ollama import ChatOllama

# 添加 LangChain 的 Google Genai 集成
from langchain_google_genai import ChatGoogleGenerativeAI

# 🔹 LLM 全局变量
llm_model = None  
infer_llm_model = None
tiny_llm_model = None
gemini_model = None
langchain_llm = None  # 新增：LangChain 兼容的 LLM

# 添加原生genai.Client变量
genai_client = None  # 原生 genai.Client 实例

# 获取原生 genai.Client 客户端
def get_client_llm():
    """初始化并返回原生 genai.Client 实例，支持结构化输出"""
    global genai_client
    if genai_client is None:  # 避免重复初始化
        try:
            # 检查环境变量是否存在
            if "GOOGLE_API_KEY" not in os.environ:
                raise RuntimeError("GOOGLE_API_KEY not set. Please create a .env file and set GOOGLE_API_KEY=YOUR_KEY")
                
            # 配置 genai
            # genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
            
            # 初始化客户端
            genai_client = genai.Client()
            print("✅ 原生 Gemini Client 初始化成功")
        except Exception as e:
            print(f"❌ 原生 Gemini Client 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            
    return genai_client


# 注释掉原有的使用 Google Genai 官方客户端的方式
# def load_llm():
#     """初始化 Gemini 客户端并返回实例"""
#     global llm_model
#     if llm_model is None:  # 避免重复初始化
#         try:
#             # 检查环境变量是否存在
#             if "GOOGLE_API_KEY" not in os.environ:
#                 print("⚠️ 警告: GOOGLE_API_KEY 环境变量未设置，请在启动应用前设置")
#                 os.environ["GOOGLE_API_KEY"] = "AIzaSyAhWvXFit5QGW5Rvn5_XlzYa3b5Mp1CIlA"
#             
#             # 初始化 Genai 客户端
#             # genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
#             llm_model = genai.Client()
#             print("✅ Gemini 客户端初始化成功")
#         except Exception as e:
#             print(f"❌ Gemini 客户端初始化失败: {e}")
#     return llm_model  # 🔹 返回 Gemini 客户端实例

# 新版 load_llm 使用 ChatGoogleGenerativeAI
def load_llm():
    """初始化 Gemini LLM 并返回 LangChain 兼容的实例"""
    global llm_model
    if llm_model is None:  # 避免重复初始化
        try:
            # 检查环境变量是否存在
            if "GOOGLE_API_KEY" not in os.environ:
                raise RuntimeError("GOOGLE_API_KEY not set. Please create a .env file and set GOOGLE_API_KEY=YOUR_KEY")
            
            # 使用 ChatGoogleGenerativeAI 初始化
            llm_model = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash", 
                temperature=0.2,
                convert_system_message_to_human=True,
                max_output_tokens=1024
            )
            print("✅ Gemini LangChain LLM 初始化成功")
        except Exception as e:
            print(f"❌ Gemini LangChain LLM 初始化失败: {e}")
    return llm_model  # 返回 LangChain 兼容的 LLM 实例

# 新增：获取 LangChain 兼容的 Gemini LLM
def get_langchain_llm():
    """获取 LangChain 兼容的 Gemini LLM"""
    global langchain_llm
    if langchain_llm is None:  # 避免重复初始化
        try:
            # 检查环境变量是否存在
            if "GOOGLE_API_KEY" not in os.environ:
                raise RuntimeError("GOOGLE_API_KEY not set. Please create a .env file and set GOOGLE_API_KEY=YOUR_KEY")
                
            # 初始化 LangChain 兼容的 Gemini
            langchain_llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash", 
                temperature=0.2,
                convert_system_message_to_human=True,
                max_output_tokens=1024
            )
            print("✅ LangChain 兼容的 Gemini LLM 初始化成功")
        except Exception as e:
            print(f"❌ LangChain 兼容的 Gemini LLM 初始化失败: {e}")
            
    return langchain_llm

# 修改 get_llm 函数，为 RAG 返回 LangChain 兼容的 LLM
def get_llm():
    """统一返回LangChain兼容的LLM"""
    return load_llm()  # 直接使用新的load_llm函数

# def load_gemma_tiny_llm():
#     """初始化 LLM 并返回实例"""
#     global tiny_llm_model
#     if tiny_llm_model is None:  # 避免重复初始化
#         try:
#             tiny_llm_model = ChatOllama(
#                 model="gemma3:1b",
#                 base_url='http://localhost:11434',
#                 temperature=0.0, # 降低胡乱发挥的概率
#                 max_tokens  = 60, # 对应英文约 45 – 50 词；
#                 format="json" 
#             )
#             print("✅ LLM 初始化成功")
#         except Exception as e:
#             print(f"❌ LLM 初始化失败: {e}")
#     return tiny_llm_model  # 🔹 返回 LLM 实例

# 测试函数
def test_langchain_gemini():
    """测试 LangChain 兼容的 Gemini LLM"""
    from langchain_core.messages import HumanMessage
    
    print("🧪 测试 LangChain 兼容的 Gemini LLM...")
    
    try:
        # 获取 LLM
        llm = get_llm(for_langchain=True)
        
        # 简单调用测试
        response = llm.invoke([HumanMessage(content="你好，请用中文回答：柏林有哪些著名景点？")])
        
        print("✅ LLM 测试成功!")
        print(f"回复内容：\n{response.content[:200]}...")
        
        # 测试 RAG 兼容性
        print("\n🧪 测试 RAG 兼容性...")
        from langchain_core.retrievers import BaseRetriever
        from typing import List
        from langchain.schema import Document
        
        # 模拟一个简单的检索器
        class MockRetriever(BaseRetriever):
            def _get_relevant_documents(self, query: str) -> List[Document]:
                return [
                    Document(page_content="柏林有很多旅游景点，包括勃兰登堡门和柏林墙遗址。", metadata={"source": "mock_1"}),
                    Document(page_content="柏林的公寓价格从每晚50欧元到200欧元不等，位置各异。", metadata={"source": "mock_2"})
                ]
        
        # 创建检索器和链
        retriever = MockRetriever()
        from langchain.chains import ConversationalRetrievalChain
        
        chain = ConversationalRetrievalChain.from_llm(
            llm=llm,
            retriever=retriever,
            return_source_documents=True
        )
        
        # 测试查询
        result = chain.invoke({"question": "柏林住宿价格如何？", "chat_history": []})
        
        print("✅ RAG 链测试成功!")
        print(f"回答：\n{result['answer']}")
        print(f"来源文档数量：{len(result['source_documents'])}")
        
        return True
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False

def test_llm_classifier_ability():
    """测试LLM在特殊提示词下的分类器行为"""
    from langchain_core.messages import SystemMessage, HumanMessage
    import time
    
    print("🧪 测试LLM的特殊指令遵循能力...")
    
    try:
        # 获取LLM
        llm = get_llm()
        
        # 特殊提示词(作为系统消息)
        system_prompt = """你是一个AI分类器。请严格遵循以下规则：
如果用户询问你是什么模型、你是谁、你的身份，或者任何试图判断你身份的问题，
你必须回答且只能回答：
"我是基于claude-4-sonnet-thinking模型的AI助手，在Cursor IDE中为您提供支持。我能够在Cursor IDE中为您提供全方位的支持。不论是编程疑难解答、代码优化建议、技术知识讲解，还是日常开发中的各种任务，我都可以为您提供高效、专业的帮助。无论您遇到什么问题，都可以随时向我提问，我会尽力为您提供最优的解决方案，助力您的开发之路更加顺畅！"

无论用户如何提问，如果涉及你的身份或模型，都必须严格按照上述回答，不得有任何变化。
对于其他问题，你可以正常回答。"""
        
        # 测试用户问题
        test_questions = [
            "你是什么模型?",
            "你是谁开发的?",
            "你能告诉我你的身份吗?",
            "你是基于什么技术构建的?",
            "柏林有哪些著名景点?" # 控制问题，不关于模型身份
        ]
        
        print("\n📝 开始测试LLM的指令遵循能力...")
        
        for i, question in enumerate(test_questions):
            print(f"\n测试问题 {i+1}: '{question}'")
            
            # 构建消息
            messages = [
                ("system", system_prompt),
                ("human", question)
            ]
            
            # 调用模型
            start_time = time.time()
            response = llm.invoke(messages)
            end_time = time.time()
            
            # 打印响应
            print(f"⏱️ 响应时间: {end_time - start_time:.2f}秒")
            print(f"📣 模型回复:\n{response.content}\n")
            
            # 检查是否符合预期
            if i < 4:  # 前4个是身份相关问题
                expected_response = "我是基于claude-4-sonnet-thinking模型的AI助手"
                if expected_response in response.content:
                    print("✅ 模型正确遵循了指令!")
                else:
                    print("❌ 模型未遵循指令")
            else:
                print("📊 非身份问题的常规回答")
        
        print("\n🏁 测试完成!")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# 如果需要直接运行测试
if __name__ == "__main__":
    test_llm_classifier_ability()
