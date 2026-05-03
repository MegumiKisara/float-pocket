import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

OCR_SYSTEM_PROMPT = (
    "你是一个专业的OCR识别助手。"
    "你的任务是从用户提供的图片中提取所有文字内容，尽可能保持原始格式和排版。"
    "只返回提取的文字，不要添加任何额外说明或评论。"
)


class OcrAgent:
    def __init__(self, api_key: str | None = None, model: str = "qwen-vl-max"):
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

    def extract_text(self, image_base64: str) -> str:
        messages = [
            SystemMessage(content=OCR_SYSTEM_PROMPT),
            HumanMessage(
                content=[
                    {"type": "text", "text": "请识别这张图片中的文字"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}"
                        },
                    },
                ]
            ),
        ]
        result = self._llm.invoke(messages)
        return result.content
