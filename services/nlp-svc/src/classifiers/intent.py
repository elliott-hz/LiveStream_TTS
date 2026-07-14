"""
12-class intent classifier using keyword + pattern matching.

Intent categories (per proto nlp.v1.IntentCategory):
  1  QUESTION           — 提问 (what/when/why/how questions)
  2  REQUEST_DEMO      — 求讲解 (request demo / explanation)
  3  PURCHASE_INTENT   — 下单意向 (buy / purchase intent)
  4  BARGAIN           — 议价 (bargaining / price negotiation)
  5  COMPLAINT         — 抱怨 (complaints about product/service)
  6  GREETING          — 寒暄 (greetings)
  7  PRAISE            — 赞美 (praise / compliments)
  8  QUESTION_PRODUCT  — 质疑 (skepticism / questioning product)
  9  URGE              — 催促 (urging the host to speed up)
  10 COMPARE           — 对比 (comparing products)
  11 AFTERSALES        — 售后 (after-sales service requests)
  12 OTHER             — 其他 (other / fallback)

Priority: specific intent rules (2-11) are checked first with higher weights.
QUESTION (1) is treated as a fallback for texts with question characteristics
not caught by specific rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import IntEnum
from typing import Pattern

from libs.common.logging import get_logger

logger = get_logger(__name__)


class IntentType(IntEnum):
    """Internal intent enum mapping 1:1 to proto IntentCategory values."""
    UNSPECIFIED = 0
    QUESTION = 1
    REQUEST_DEMO = 2
    PURCHASE_INTENT = 3
    BARGAIN = 4
    COMPLAINT = 5
    GREETING = 6
    PRAISE = 7
    QUESTION_PRODUCT = 8
    URGE = 9
    COMPARE = 10
    AFTERSALES = 11
    OTHER = 12


# Trailing punctuation that can be ignored at end of patterns
_END = r"(?:了|的|啦|嘛|啊|呀|吧|呢|哦|咯|哈|哟|呗|[!！?？。.，,、;；:：\s])*$"


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: IntentType
    confidence: float       # 0.0–1.0
    needs_reply: bool = False
    reason: str = ""


class PatternRule:
    """A single intent matching rule with keywords and regex patterns."""

    __slots__ = ("intent", "keywords", "patterns", "boost", "description")

    def __init__(
        self,
        intent: IntentType,
        keywords: list[str] | None = None,
        patterns: list[str] | None = None,
        boost: float = 0.0,
        description: str = "",
    ):
        self.intent = intent
        self.keywords = [kw.lower() for kw in (keywords or [])]
        self.patterns: list[Pattern] = [re.compile(p, re.IGNORECASE) for p in (patterns or [])]
        self.boost = boost
        self.description = description


class IntentClassifier:
    """
    Rule-based intent classifier covering all 12 intent categories.

    Matching strategy:
    1. Score each specific intent rule (2-11) with keyword + pattern matching.
    2. If the top-scoring specific intent has confidence >= 0.5, use it.
    3. Otherwise, fall through to check QUESTION patterns.
    4. If nothing matches, return OTHER.

    This prevents broad QUESTION patterns from overriding more specific intents.
    """

    def __init__(self) -> None:
        self.specific_rules: list[PatternRule] = self._build_specific_rules()
        self.question_rules: list[PatternRule] = self._build_question_rules()

    def _build_specific_rules(self) -> list[PatternRule]:
        """Build rules for specific intents (2-11, excluding QUESTION and OTHER)."""
        return [
            # ── REQUEST_DEMO (2) — ask for demo / explanation ──
            PatternRule(
                IntentType.REQUEST_DEMO,
                keywords=["讲解", "演示", "示范", "试试", "展示", "介绍一下", "介绍",
                          "看看", "看一下", "看下", "上身", "上脚", "试穿", "试用",
                          "打开", "操作一下", "使用一下", "体验", "展示一下",
                          "试一下", "效果如何", "什么样"],
                patterns=[
                    r"讲解一下",
                    rf"演示.*看{_END}",
                    rf"(怎么|如何).*(用|穿|操作|使用|弄){_END}",
                    rf"可以.*(看看|演示|展示|试穿|试用|试试){_END}",
                    rf"(看看|看下|看一下|试试).*(效果|怎么样|如何){_END}",
                ],
                boost=0.0,
                description="Requests for product demo or explanation",
            ),

            # ── PURCHASE_INTENT (3) — buying intent ──
            PatternRule(
                IntentType.PURCHASE_INTENT,
                keywords=["下单", "购买", "拍下", "买单", "付款", "买了", "拍",
                          "买", "链接", "上链接", "上架", "小黄车", "购物车",
                          "在哪买", "在哪", "我要买", "想买", "求链接", "已下单",
                          "已拍", "已付款", "上车"],
                patterns=[
                    rf"在哪里买{_END}",
                    rf"在哪买{_END}",
                    rf"去哪买{_END}",
                    rf"(怎么|去哪|哪里).*买.{0,4}$",  # generic "where/how to buy"
                    rf"下.*单{_END}",
                    rf"拍.*(下|了){_END}",
                    rf"买.*(了|它|这个|那个|一个){_END}",
                    rf"上.*链接{_END}",
                    rf"发.*链接{_END}",
                    rf"求.*链接{_END}",
                    rf"链接.*(多少|发|给|来){_END}",
                ],
                boost=0.1,
                description="Purchase intent signals",
            ),

            # ── BARGAIN (4) — price negotiation ──
            PatternRule(
                IntentType.BARGAIN,
                keywords=["便宜", "优惠", "打折", "折扣", "降价", "减价", "特价",
                          "划算", "贵", "太贵", "优惠价", "团购", "拼单", "批发",
                          "便宜点", "少点", "抹零", "送", "赠品", "包邮", "免邮",
                          "促销", "减减", "砍价", "优惠券"],
                patterns=[
                    rf"(太|有点|有些).*贵{_END}",
                    rf"能.*(便宜|优惠|打折|少|降){_END}",
                    rf"可以.*(便宜|优惠|打折|少|降){_END}",
                    rf"能不能.*(便宜|优惠|打折|少|降){_END}",
                    rf"有.*(优惠|折扣|赠品|送).*(吗|嘛|么){_END}",
                    rf"包邮.*(吗|嘛){_END}",
                    rf"送.*吗{_END}",
                    rf"便宜.*(点|些|吧|吗|不|下来){_END}",
                    rf"优惠.*(券|码|价格|活动|吗){_END}",
                    rf"还能.*(少|降|减|便宜){_END}",
                    rf"(打折|特价|团购|拼单).*吗{_END}",
                    rf"怎么.*(卖|算).*钱{_END}",
                ],
                boost=0.1,
                description="Bargaining and price negotiation",
            ),

            # ── COMPLAINT (5) — complaints ──
            PatternRule(
                IntentType.COMPLAINT,
                keywords=["差评", "退货", "退款", "坏了", "不好", "不行", "垃圾",
                          "坑", "上当", "骗", "虚假", "发货慢", "没有效果",
                          "不值", "不满意", "投诉", "太差", "很烂", "忽悠",
                          "套路", "质量", "问题", "差", "假货"],
                patterns=[
                    rf"(质量|品质).*(差|不好|问题|堪忧|不行){_END}",
                    rf"(退货|退款|换货){_END}",
                    rf"太差了{_END}",
                    rf"不好.*(用|穿|吃|喝|看|玩|使){_END}",
                    rf"不满意{_END}",
                    rf"上当了{_END}",
                    rf"上当了.*(骗子|假|坑){_END}",
                    rf"骗.*(人|子|钱|我|我们){_END}",
                    rf"虚假.*(宣传|广告|信息|描述){_END}",
                    rf"发[货貨].*(慢|太慢|迟迟|不[发發][货貨]){_END}",
                    rf"(差評|差评|给差|想退){_END}",
                    rf"什么.*(质量|品质|东西).*(啊|呀|嘛){_END}",
                ],
                boost=0.1,
                description="Complaints about product, service, or delivery",
            ),

            # ── GREETING (6) — greetings ──
            PatternRule(
                IntentType.GREETING,
                keywords=["你好", "大家好", "主播好", "来了", "签到", "报道", "早",
                          "晚上好", "下午好", "早上好", "hello", "hi", "hey",
                          "在吗", "大家好呀", "大家好啊", "中午好", "签个到"],
                patterns=[
                    r"^(你好|大家好|主播好|hello|hi|hey)\b",
                    r"^(早(上)?|晚上好|下午好|早上好|中午好|晚安)",
                    r"我来(啦|了|拉|咯)",
                    r"^在吗",
                    r"签个到",
                    r"报道(啦|了)",
                ],
                boost=0.0,
                description="Greetings and check-ins",
            ),

            # ── PRAISE (7) — praise / positive comments ──
            PatternRule(
                IntentType.PRAISE,
                keywords=["好看", "好听", "好吃", "好用", "漂亮", "帅气", "美",
                          "不错", "很棒", "真好", "太好", "完美", "给力",
                          "喜欢", "大爱", "爱了", "绝绝子", "性价比高", "高端",
                          "大气", "yyds", "良心", "实惠", "划算", "超值",
                          "很赞", "太牛", "上档次", "宝藏", "真不错"],
                patterns=[
                    rf"(太好|真棒|给力|完美|超值|很赞|太牛|绝了|真不错){_END}",
                    rf"(很|好|真|太|超|挺|非常).{{0,4}}(看|听|吃|用|玩|美|帅|赞|香|值|行|棒|牛|酷){_END}",
                    rf"(颜值|品质|质量|质感).*(高|好|棒|赞|不错){_END}",
                    rf"性价比.*(高|好|不错|超|绝){_END}",
                    rf"(爱了|大爱|超爱).*{_END}",
                    rf"\byyds\b",
                ],
                boost=0.0,
                description="Praise and positive feedback",
            ),

            # ── QUESTION_PRODUCT (8) — skepticism / questioning product ──
            PatternRule(
                IntentType.QUESTION_PRODUCT,
                keywords=["真的吗", "真假", "正品", "靠谱", "可信", "保证",
                          "效果", "有用吗", "是真的", "假的", "仿品",
                          "质量保证", "官方", "授权", "真货"],
                patterns=[
                    rf"真的假的{_END}",
                    rf"是.*真.*(吗|的|假){_END}",
                    rf"(有|没有).*效果.*(吗|吧|啊|嘛){_END}",
                    rf"正品.*(吗|嘛|不|保|吗){_END}",
                    r"靠谱.*(吗|不|吧)",  # no end anchor — may have trailing chars
                    rf"不会.*(假|骗|坑|水).*吧{_END}",
                    rf"确定.*(吗|不|真的|正品){_END}",
                    rf"(假|仿|山).*(货|品|的|冒|冒牌){_END}",
                    rf"质量.*(保证|保障).*吗{_END}",
                ],
                boost=0.0,
                description="Skepticism and product authenticity concerns",
            ),

            # ── URGE (9) — urging / rushing ──
            PatternRule(
                IntentType.URGE,
                keywords=["快点", "赶紧", "快快", "加速", "太慢了", "快", "速度",
                          "冲冲冲", "冲啊", "干吧", "别磨叽", "别墨迹", "上啊",
                          "开始", "开始吧", "快快快", "别等了"],
                patterns=[
                    rf"快.*(点|些|吧|啊|上|更){_END}",
                    rf"(别|不要|莫).*(磨叽|墨迹|慢|磨蹭|拖|等){_END}",
                    rf"冲.*(啊|呀|吧|鸭){_END}",
                    rf"赶紧.*(上|开始|买|抢|拍){_END}",
                    rf"速度.*(点|啊|上){_END}",
                    r"快快快",
                    r"冲冲冲",
                    r"等.*(不及|不了|不及了)",
                ],
                boost=0.0,
                description="Urging the host to speed up or start",
            ),

            # ── COMPARE (10) — comparing products ──
            PatternRule(
                IntentType.COMPARE,
                keywords=["对比", "区别", "不同", "哪个好", "哪个更好", "比",
                          "性价比", "差别", "差异", "哪个划算", "哪个更",
                          "vs", "还是", "优于", "比较"],
                patterns=[
                    rf"(哪个|哪款).*(好|更好|划算|值得|实用|适合|便宜){_END}",
                    rf"跟.*(比|对比|区别|不同|一样)",  # no end anchor — may have trailing words
                    rf"和.*(区别|不同|对比|差异){_END}",
                    rf"哪.*更.*(好|便宜|划算|实用|适合|耐用){_END}",
                    rf"有什么.*(区别|不同|差别){_END}",
                    rf"(差别|差异).*(在哪|在哪里|是什么|大吗){_END}",
                ],
                boost=0.0,
                description="Product comparisons",
            ),

            # ── AFTERSALES (11) — after-sales requests ──
            PatternRule(
                IntentType.AFTERSALES,
                keywords=["售后", "维修", "保修", "质保", "换货", "退货", "退款",
                          "退换", "客服", "联系", "电话", "地址", "怎么退",
                          "怎么换", "多久到", "发货", "物流", "快递", "发票",
                          "保修期", "修"],
                patterns=[
                    rf"(怎么|如何).*(退|换|修|退款|退货){_END}",
                    rf"(保修|质保|包修).*(期|多久|几年|吗|范围|政策){_END}",
                    rf"(退货|退款|换货).*(流程|多久|几天|申请|办理){_END}",
                    rf"售后.*(怎么|如何|联系|电话|方式){_END}",
                    rf"发.*货.*(了|没|什么时候|了吗|进度|状态|还没){_END}",
                    rf"(地址|电话).*(改|换|更新|修改|填|写|多少){_END}",
                    rf"(物流|快递).*(号|单号|信息|进度|状态|到哪){_END}",
                    rf"发票.*(怎么|开|要|有|需要|电子){_END}",
                ],
                boost=0.0,
                description="After-sales service and logistics inquiries",
            ),
        ]

    def _build_question_rules(self) -> list[PatternRule]:
        """Build rules for the generic QUESTION intent (run as fallback)."""
        return [
            PatternRule(
                IntentType.QUESTION,
                keywords=["?", "?", "怎么", "怎样", "如何", "为什么", "啥",
                          "吗", "呢", "哪个", "什么", "什么时候", "多少",
                          "是不是", "能不能", "会不会", "有没有", "几", "哪"],
                patterns=[
                    r"^(什么|怎么|为什么|如何|怎样|哪个|哪家|几岁|多大)",
                    rf"什么时候{_END}",
                    rf"(多少|几).*(钱|个|件|种|颜色|号|码|尺寸){_END}",
                    rf".*[?？].{{0,3}}$",
                    rf".*[?？]{{2,}}",
                    # "有没有" as a question pattern without end anchor (may continue)
                    r"有没有",
                ],
                boost=0.0,
                description="General questions about products or processes",
            ),
        ]

    def _score_rule(self, text_lower: str, rule: PatternRule) -> float:
        """Score a rule against the given text. Returns 0.0 if no match."""
        score = 0.0

        # Keyword matching
        for kw in rule.keywords:
            if kw in text_lower:
                score += 0.25

        # Regex pattern matching
        for pattern in rule.patterns:
            if pattern.search(text_lower):
                score += 0.5
                break  # Only count the first pattern hit per rule

        if score == 0.0:
            return 0.0

        return round(min(score + rule.boost, 1.0), 4)

    def classify(self, text: str) -> IntentResult:
        """
        Classify the intent of the given text.

        Strategy:
        1. Score all specific intents (2-11).
        2. If best specific intent has confidence >= 0.5, return it.
        3. Otherwise, try QUESTION as a fallback.
        4. If neither, return OTHER.
        """
        if not text or not text.strip():
            return IntentResult(
                intent=IntentType.OTHER,
                confidence=0.0,
                needs_reply=False,
                reason="Empty text",
            )

        text_lower = text.lower().strip()
        specific_scores: dict[IntentType, float] = {}

        # Phase 1: Score specific rules
        for rule in self.specific_rules:
            score = self._score_rule(text_lower, rule)
            if score > 0:
                specific_scores[rule.intent] = score

        # If specific rules matched above threshold, use the best one
        if specific_scores:
            best_intent = max(specific_scores, key=specific_scores.get)
            best_confidence = specific_scores[best_intent]

            if best_confidence >= 0.5:
                return self._make_result(best_intent, best_confidence)

            # Phase 2: Check if a QUESTION rule matches better than the weak specific match
            for rule in self.question_rules:
                q_score = self._score_rule(text_lower, rule)
                if q_score > best_confidence:
                    return self._make_result(IntentType.QUESTION, q_score)

            # Return the best specific match even if below 0.5
            return self._make_result(best_intent, best_confidence)

        # Phase 2: No specific rules matched — try QUESTION
        for rule in self.question_rules:
            q_score = self._score_rule(text_lower, rule)
            if q_score > 0:
                return self._make_result(IntentType.QUESTION, q_score)

        # Phase 3: Nothing matched
        return IntentResult(
            intent=IntentType.OTHER,
            confidence=0.0,
            needs_reply=False,
            reason="No intent pattern matched; classified as OTHER",
        )

    def _make_result(self, intent: IntentType, confidence: float) -> IntentResult:
        """Build an IntentResult with proper needs_reply and reason."""
        # Determine needs_reply based on intent type
        needs_reply_map = {
            IntentType.QUESTION: True,
            IntentType.REQUEST_DEMO: True,
            IntentType.PURCHASE_INTENT: True,
            IntentType.BARGAIN: True,
            IntentType.COMPLAINT: True,
            IntentType.GREETING: None,
            IntentType.PRAISE: None,
            IntentType.QUESTION_PRODUCT: True,
            IntentType.URGE: None,
            IntentType.COMPARE: True,
            IntentType.AFTERSALES: True,
            IntentType.OTHER: None,
        }

        nr = needs_reply_map.get(intent, None)
        if nr is True:
            needs_reply = True
            reason = f"{intent.name} intent detected (confidence={confidence:.2f}) — requires reply"
        elif nr is False:
            needs_reply = False
            reason = f"{intent.name} intent detected (confidence={confidence:.2f}) — no reply needed"
        else:
            if confidence >= 0.5:
                needs_reply = True
                reason = f"{intent.name} intent detected (confidence={confidence:.2f}) — reply recommended"
            else:
                needs_reply = False
                reason = f"{intent.name} intent detected (confidence={confidence:.2f}) — low confidence, optional reply"

        return IntentResult(
            intent=intent,
            confidence=confidence,
            needs_reply=needs_reply,
            reason=reason,
        )


# Singleton instance
intent_classifier = IntentClassifier()
