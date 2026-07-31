"""
NLP 管线：敏感词过滤 + 意图分类
PoC 阶段用简单的关键词匹配，后续可替换为 FastText 模型。
"""

import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Danmaku:
    user_name: str
    content: str
    time: str = field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))


# ---- 敏感词过滤 ----
SENSITIVE_WORDS = {
    "违禁品", "枪支", "毒品",
}

# ---- 意图关键词 ----
QUESTION_KEYWORDS = [
    "多少钱", "价格", "怎么卖", "便宜", "优惠",
    "尺码", "大小", "颜色", "材质", "面料",
    "有货", "库存", "链接",
    "包邮", "发货", "退换", "售后",
    "怎么样", "好用吗", "适合",
]

ORDER_KEYWORDS = [
    "已下单", "买了", "下单了", "拍了",
    "怎么买", "哪里买", "购买",
]


def is_sensitive(text: str) -> bool:
    """AC 自动机简化版：直接关键词匹配"""
    for word in SENSITIVE_WORDS:
        if word in text:
            return True
    return False


def classify(text: str) -> str:
    """
    意图分类。
    返回: question / order_intent / comment

    规则：先检查下单意图，再检查提问关键词，最后看是否带"吗"等疑问词。
    """
    for kw in ORDER_KEYWORDS:
        if kw in text:
            return "order_intent"
    for kw in QUESTION_KEYWORDS:
        if kw in text:
            return "question"
    # 中文疑问标记
    if any(q in text for q in ("吗", "?", "？", "多大", "多少", "有没有", "能不能")):
        return "question"
    return "comment"


def should_reply(danmaku: Danmaku) -> bool:
    """判断是否需要 AI 回复"""
    if is_sensitive(danmaku.content):
        return False
    intent = classify(danmaku.content)
    return intent in ("question", "order_intent")
