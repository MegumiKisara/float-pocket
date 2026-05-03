import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

TRANSLATE_SYSTEM_PROMPT = (
    "你是一个专业的翻译助手。"
    "你的任务是将用户提供的文本翻译成中文。"
    "只返回翻译结果，不要添加任何额外说明或评论。"
)


class TranslateAgent:
    def __init__(self, api_key: str | None = None, model: str = "qwen-max"):
        key = api_key or os.environ.get("QWEN_API_KEY", "")
        self._llm = ChatOpenAI(
            api_key=key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=model,
            max_tokens=4096,
            temperature=0.01,
            timeout=30,
            max_retries=0,
        )

    def translate(self, text: str, target_lang: str = "中文") -> str:
        messages = [
            SystemMessage(content=TRANSLATE_SYSTEM_PROMPT),
            HumanMessage(content=f"请将以下文本翻译成{target_lang}：\n\n{text}"),
        ]
        result = self._llm.invoke(messages)
        return result.content
