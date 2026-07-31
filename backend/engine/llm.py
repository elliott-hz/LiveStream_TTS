"""DeepSeek API 客户端"""
import httpx
from backend.config import settings


async def chat(prompt: str, system_prompt: str = "") -> str:
    """调用 DeepSeek API 生成回复"""
    if settings.mock_external_api:
        return "亲，这款商品质量很好的哦~纯棉面料穿着舒适透气，有S到XL码，下单即送运费险，放心购买！"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.deepseek_base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            json={
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": 200,
                "temperature": 0.7,
            },
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def clean_script(raw_text: str) -> str:
    """清洗讲解脚本"""
    if settings.mock_external_api:
        return raw_text.strip() or "今天给大家带来一款超值好物，品质保证，价格实惠，喜欢的朋友不要错过哦~"

    system = "你是一个直播脚本编辑。请将以下语音识别的原始文本整理成流畅的商品讲解脚本，去除口语词和重复内容。"
    return await chat(raw_text, system_prompt=system)
