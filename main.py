import os
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse  # 新增：用于返回 HTML 文件
from google import genai


# 物理网络路由配置 (Proxy Configuration)
# 必须与你电脑实际运行的代理软件端口一致
#os.environ["http_proxy"] = "http://127.0.0.1:7897" 
#os.environ["https_proxy"] = "http://127.0.0.1:7897"

# 引擎鉴权与实例化 (新版逻辑)
#API_KEY = 

# 实例化新版 Client 对象
#client = genai.Client(api_key=API_KEY)


API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL_ID = "gemini-2.5-flash"
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#数据结构强类型约束 (Pydantic 模型)。反序列化：前端传来的 JSON 数据中，必须包含一个名为 text 的字符串字段
class UserInput(BaseModel):
    text: str

# [新增] 1. 声明一个全局列表，充当记忆栈
chat_history = []

# [云端改造]：让 FastAPI 直接返回网页
# 当用户在浏览器输入你的网址（默认请求根目录 "/"）时，把 index.html 发给他们
@app.get("/")
def get_homepage():
    return FileResponse("index.html")
    
# 核心路由：处理前端 POST 请求并调用API
@app.post("/chat")
#当 Uvicorn 收到目标的 URL 是 /chat 且方法是 POST 时，立刻触发并执行下方的 chat_endpoint 函数。
def chat_endpoint(request_data: UserInput):
    #FastAPI 会自动把刚才解析好的 UserInput 结构体实例，作为参数传递进这个函数。
    #1.提取前端传来的文本
    received_text = request_data.text

    print(f"[后端日志] 收到前端文本: {received_text}")
    # [新增] 2. 将用户的新问题压入记忆栈
    # 按照 Google 严格的数据结构要求：标明 role (角色) 和 parts (内容)
    # ==========================================
    chat_history.append({
        "role": "user",
        "parts": [{"text": received_text}]
    })
    
    try:
        # 依然在局部实例化 Client，防止代理层抛出 EOF 断连错误
        client = genai.Client(api_key=API_KEY)

        #print(f"[后端日志] 正在请求 {MODEL_ID}...")
        
        #RPC 调用格式
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=chat_history   #本来是received_text
        )
        
        # 调用大模型，提取模型生成的文本内容
        ai_reply = response.text

        # 将 AI 的回复也压入记忆栈，完成闭环
        # role 必须设定为 "model"
        chat_history.append({
            "role": "model",
            "parts": [{"text": ai_reply}]
        })

        #print(f"[后端日志] Gemini 返回成功，当前记忆栈深度: {len(chat_history)}")
        #FastAPI 会自动拦截这个返回值，将其序列化 (Serialize) 为标准的 JSON 字符串
        return {"reply": ai_reply}
        #随后，这个字符串被打包进 HTTP 响应报文中，顺着原路（刚才建立的 TCP 连接）
        #发回给浏览器的 fetch API。浏览器接收到后，就触发了我们之前讲的前端“渲染灰色气泡”的逻辑
        
    except Exception as e:
        if chat_history:
            chat_history.pop() 
        return {"reply": f"API 调用失败。底层报错: {str(e)}"}