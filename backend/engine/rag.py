"""
商品知识库匹配
根据 LLM 分析出的商品描述 → 关键词匹配 → 找到对应的 SKU

PoC 阶段用 JSON 文件做关键词匹配。
后续可升级为 Milvus 向量检索。
"""

import json
import os

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "product_kb.json")


def load_kb() -> list[dict]:
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def match_product(product_hint: str) -> dict | None:
    """
    根据商品描述文字，匹配知识库中最接近的商品。

    Args:
        product_hint: LLM 分析出来的商品描述，如 "黑色碎花长裙"

    Returns:
        匹配到的商品信息 dict，如果没匹配到返回 None
    """
    kb = load_kb()
    best = None
    best_score = 0

    for item in kb:
        score = 0
        # 名称匹配
        if item["name"] in product_hint:
            score += 10
        # 关键词匹配
        for kw in item["keywords"]:
            if kw in product_hint:
                score += 5
        if score > best_score:
            best_score = score
            best = item

    return best if best_score >= 5 else None


def enrich_product(product_hint: str) -> dict:
    """
    用知识库信息补全商品描述。

    返回: {matched, sku, name, price, material, sizes, selling_points}
    """
    matched = match_product(product_hint)
    if matched:
        return {
            "matched": True,
            "sku": matched["sku"],
            "name": matched["name"],
            "category": matched.get("category", ""),
            "price": matched["price"],
            "material": matched.get("material", ""),
            "sizes": matched.get("sizes", ""),
            "selling_points": matched.get("selling_points", []),
        }
    else:
        return {
            "matched": False,
            "name": product_hint,
            "sku": "",
            "category": "",
            "price": "",
            "material": "",
            "sizes": "",
            "selling_points": [],
        }
