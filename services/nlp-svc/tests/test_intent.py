"""
Tests for the 12-class intent classifier.

Each intent category is tested with at least 3 example sentences.
"""

from __future__ import annotations

import pytest

from src.classifiers.intent import IntentClassifier, IntentType


@pytest.fixture
def classifier() -> IntentClassifier:
    return IntentClassifier()


class TestIntentQuestion:
    """INTENT_CATEGORY_QUESTION (1) — General questions."""

    @pytest.mark.parametrize("text", [
        "这个多少钱",
        "什么时候发货",
        "有没有其他颜色",
        "为什么这么贵",
    ])
    def test_question_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.QUESTION, (
            f"Expected QUESTION for '{text}', got {result.intent.name}"
        )
        assert result.confidence >= 0.3


class TestIntentRequestDemo:
    """INTENT_CATEGORY_REQUEST_DEMO (2) — Request demo/explanation."""

    @pytest.mark.parametrize("text", [
        "讲解一下这款产品",
        "可以演示一下看看",
        "介绍一下这个怎么用",
        "试试上身效果",
        "看看效果怎么样",
        "这个怎么用",
    ])
    def test_request_demo_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.REQUEST_DEMO, (
            f"Expected REQUEST_DEMO for '{text}', got {result.intent.name}"
        )
        assert result.confidence >= 0.3


class TestIntentPurchase:
    """INTENT_CATEGORY_PURCHASE_INTENT (3) — Purchase intent."""

    @pytest.mark.parametrize("text", [
        "我要下单",
        "怎么买这个",
        "上链接吧",
        "已经拍了",
        "在哪里买",
        "求链接",
        "已下单了",
        "帮我买一个",
        "赶紧上链接",
    ])
    def test_purchase_intent_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.PURCHASE_INTENT, (
            f"Expected PURCHASE_INTENT for '{text}', got {result.intent.name}"
        )
        assert result.confidence >= 0.3


class TestIntentBargain:
    """INTENT_CATEGORY_BARGAIN (4) — Bargaining."""

    @pytest.mark.parametrize("text", [
        "能便宜点吗",
        "太贵了，打折吗",
        "有优惠吗",
        "包邮吗",
        "买二送一吗",
        "还能便宜吗",
        "可不可以优惠",
    ])
    def test_bargain_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.BARGAIN, (
            f"Expected BARGAIN for '{text}', got {result.intent.name}"
        )
        assert result.confidence >= 0.3


class TestIntentComplaint:
    """INTENT_CATEGORY_COMPLAINT (5) — Complaints."""

    @pytest.mark.parametrize("text", [
        "质量太差了",
        "退货退款",
        "上当了是假货",
        "发货太慢",
        "不满意这个产品",
        "客服不理人差评",
        "什么质量啊",
    ])
    def test_complaint_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.COMPLAINT, (
            f"Expected COMPLAINT for '{text}', got {result.intent.name}"
        )
        assert result.confidence >= 0.3


class TestIntentGreeting:
    """INTENT_CATEGORY_GREETING (6) — Greetings."""

    @pytest.mark.parametrize("text", [
        "大家好",
        "主播好",
        "来了",
        "晚上好",
        "hello",
        "签到",
    ])
    def test_greeting_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.GREETING, (
            f"Expected GREETING for '{text}', got {result.intent.name}"
        )


class TestIntentPraise:
    """INTENT_CATEGORY_PRAISE (7) — Praise."""

    @pytest.mark.parametrize("text", [
        "太好看了",
        "真不错啊",
        "性价比很高",
        "yyds",
        "很给力",
        "超值划算",
    ])
    def test_praise_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.PRAISE, (
            f"Expected PRAISE for '{text}', got {result.intent.name}"
        )
        assert result.confidence >= 0.3


class TestIntentQuestionProduct:
    """INTENT_CATEGORY_QUESTION_PRODUCT (8) — Skepticism/questioning product."""

    @pytest.mark.parametrize("text", [
        "真的假的",
        "是正品吗",
        "效果真的有用吗",
        "靠谱吗这个",
        "确定是正品",
    ])
    def test_question_product_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.QUESTION_PRODUCT, (
            f"Expected QUESTION_PRODUCT for '{text}', got {result.intent.name}"
        )
        assert result.confidence >= 0.3


class TestIntentUrge:
    """INTENT_CATEGORY_URGE (9) — Urging."""

    @pytest.mark.parametrize("text", [
        "快点开始吧",
        "冲冲冲",
        "快快快",
        "别磨叽了",
        "速度点上",
        "别等了",
    ])
    def test_urge_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.URGE, (
            f"Expected URGE for '{text}', got {result.intent.name}"
        )
        assert result.confidence >= 0.3


class TestIntentCompare:
    """INTENT_CATEGORY_COMPARE (10) — Comparing products."""

    @pytest.mark.parametrize("text", [
        "哪个更好",
        "这两个有什么区别",
        "哪个更划算",
        "跟另一款比怎么样",
        "有什么不同",
    ])
    def test_compare_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.COMPARE, (
            f"Expected COMPARE for '{text}', got {result.intent.name}"
        )
        assert result.confidence >= 0.3


class TestIntentAftersales:
    """INTENT_CATEGORY_AFTERSALES (11) — After-sales."""

    @pytest.mark.parametrize("text", [
        "怎么退货",
        "保修期多久",
        "退换货流程是什么",
        "怎么联系售后",
        "发票怎么开",
    ])
    def test_aftersales_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.AFTERSALES, (
            f"Expected AFTERSALES for '{text}', got {result.intent.name}"
        )
        assert result.confidence >= 0.3


class TestIntentOther:
    """INTENT_CATEGORY_OTHER (12) — Other / fallback."""

    @pytest.mark.parametrize("text", [
        "abc123xyz",
        "test with no keywords",
        "123456",
    ])
    def test_other_detection(self, classifier: IntentClassifier, text: str) -> None:
        result = classifier.classify(text)
        assert result.intent == IntentType.OTHER, (
            f"Expected OTHER for '{text}', got {result.intent.name}"
        )


class TestNeedsReply:
    """Test the needs_reply logic for different intents."""

    def test_question_needs_reply(self, classifier: IntentClassifier) -> None:
        result = classifier.classify("这个多少钱")
        assert result.needs_reply is True

    def test_purchase_needs_reply(self, classifier: IntentClassifier) -> None:
        result = classifier.classify("我要下单")
        assert result.needs_reply is True

    def test_bargain_needs_reply(self, classifier: IntentClassifier) -> None:
        result = classifier.classify("能便宜点吗")
        assert result.needs_reply is True

    def test_complaint_needs_reply(self, classifier: IntentClassifier) -> None:
        result = classifier.classify("质量太差了")
        assert result.needs_reply is True

    def test_empty_text(self, classifier: IntentClassifier) -> None:
        result = classifier.classify("")
        assert result.intent == IntentType.OTHER
        assert result.needs_reply is False
        assert result.confidence == 0.0
