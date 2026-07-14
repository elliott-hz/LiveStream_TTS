"""
ML model backends for NLP classification (Phase 2).

Provides transformer-based intent and sentiment classifiers that
can optionally replace the rule-based defaults when ``NLP_BACKEND=model``.

Models are loaded lazily on first use and cached in memory.
Uses small, CPU-friendly models:
  - Intent: text2vec-base-chinese with zero-shot classification
  - Sentiment: bert-base-chinese fine-tuned or pipeline

All model classifiers implement the same interface as their rule-based
counterparts, so NLPService can swap them transparently.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from libs.common.logging import get_logger

logger = get_logger(__name__)


class ModelBackend(ABC):
    """Base class for ML model backends. Lazy-loads the transformer model."""

    _pipeline = None
    _model_name: str = ""

    def is_loaded(self) -> bool:
        return self._pipeline is not None

    @abstractmethod
    def _load_model(self) -> None:
        """Load the model into memory. Called once on first use."""
        ...

    def ensure_loaded(self) -> None:
        """Ensure the model is loaded. No-op if already loaded."""
        if not self.is_loaded():
            self._load_model()


# ── Intent Classification Model ────────────────────────────────────

# E-commerce intent labels (12 categories) with descriptive prompts
INTENT_LABELS_ZH = [
    "提问问题",           # QUESTION
    "请求演示产品",       # REQUEST_DEMO
    "想要购买下单",       # PURCHASE_INTENT
    "讨价还价议价",       # BARGAIN
    "抱怨投诉不满",       # COMPLAINT
    "打招呼寒暄",         # GREETING
    "赞美夸奖好评",       # PRAISE
    "质疑产品真假",       # QUESTION_PRODUCT
    "催促快点上架",       # URGE
    "对比比较产品",       # COMPARE
    "售后物流维修",       # AFTERSALES
    "其他非购物相关",     # OTHER
]

# Map label index → IntentType value (matches the order above)
LABEL_TO_INTENT: dict[int, int] = {
    0: 1,   # QUESTION
    1: 2,   # REQUEST_DEMO
    2: 3,   # PURCHASE_INTENT
    3: 4,   # BARGAIN
    4: 5,   # COMPLAINT
    5: 6,   # GREETING
    6: 7,   # PRAISE
    7: 8,   # QUESTION_PRODUCT
    8: 9,   # URGE
    9: 10,  # COMPARE
    10: 11, # AFTERSALES
    11: 12, # OTHER
}


class ModelIntentClassifier(ModelBackend):
    """Zero-shot intent classifier using transformer models.

    Uses HuggingFace ``zero-shot-classification`` pipeline.
    Falls back to rule-based on model failure.
    """

    _model_name: str = "MoritzLaurer/mDeBERTa-v3-base-xnli"
    # mDeBERTa supports Chinese and is good for zero-shot classification

    def __init__(self, model_name: str = "", cache_dir: str = "") -> None:
        if model_name:
            self._model_name = model_name
        self.cache_dir = cache_dir

    def _load_model(self) -> None:
        """Load the zero-shot classification pipeline."""
        try:
            from transformers import pipeline

            logger.info("model_intent.loading", model=self._model_name)
            self._pipeline = pipeline(
                "zero-shot-classification",
                model=self._model_name,
                cache_dir=self.cache_dir or None,
                device=-1,  # CPU
            )
            logger.info("model_intent.loaded", model=self._model_name)
        except ImportError:
            logger.warning("model_intent.no_transformers", hint="pip install transformers")
        except Exception as e:
            logger.error("model_intent.load_failed", error=str(e))

    def classify(self, text: str) -> dict:
        """Classify intent and return result dict compatible with IntentResult.

        Returns a dict with keys:
            intent, confidence, needs_reply, reason
        """
        from src.classifiers.intent import IntentType

        if not text or not text.strip():
            return {
                "intent": IntentType.OTHER,
                "confidence": 0.0,
                "needs_reply": False,
                "reason": "Empty text",
            }

        self.ensure_loaded()

        if not self.is_loaded():
            return {
                "intent": IntentType.OTHER,
                "confidence": 0.0,
                "needs_reply": False,
                "reason": "Model not loaded — fallback to OTHER",
            }

        try:
            result = self._pipeline(
                text,
                candidate_labels=INTENT_LABELS_ZH,
                multi_label=False,
            )

            top_label = result["labels"][0]
            confidence = round(result["scores"][0], 4)

            # Find matching intent index
            label_idx = INTENT_LABELS_ZH.index(top_label) if top_label in INTENT_LABELS_ZH else 11
            intent_val = LABEL_TO_INTENT.get(label_idx, 12)  # default OTHER
            intent = IntentType(intent_val)

            # Determine needs_reply
            needs_reply_map = {
                IntentType.QUESTION: True,
                IntentType.REQUEST_DEMO: True,
                IntentType.PURCHASE_INTENT: True,
                IntentType.BARGAIN: True,
                IntentType.COMPLAINT: True,
                IntentType.QUESTION_PRODUCT: True,
                IntentType.COMPARE: True,
                IntentType.AFTERSALES: True,
            }
            needs_reply = needs_reply_map.get(intent, confidence >= 0.6)

            return {
                "intent": intent,
                "confidence": confidence,
                "needs_reply": needs_reply,
                "reason": f"Model classified as {intent.name} (conf={confidence:.2f})",
            }

        except Exception as e:
            logger.error("model_intent.classify_error", error=str(e))
            return {
                "intent": IntentType.OTHER,
                "confidence": 0.0,
                "needs_reply": False,
                "reason": f"Model error: {e}",
            }


# ── Sentiment Analysis Model ──────────────────────────────────────

SENTIMENT_LABELS_ZH = [
    "积极正面",
    "消极负面",
    "中性普通",
    "愤怒情绪",
    "兴奋激动",
]

LABEL_TO_SENTIMENT: dict[int, int] = {
    0: 1,  # POSITIVE
    1: 2,  # NEGATIVE
    2: 3,  # NEUTRAL
    3: 4,  # ANGRY
    4: 5,  # EXCITED
}


class ModelSentimentAnalyzer(ModelBackend):
    """Zero-shot sentiment analyzer using transformer models.

    Uses the same underlying model as intent for consistency
    (can share the pipeline or use a separate one).
    """

    _model_name: str = "MoritzLaurer/mDeBERTa-v3-base-xnli"

    def __init__(self, model_name: str = "", cache_dir: str = "") -> None:
        if model_name:
            self._model_name = model_name
        self.cache_dir = cache_dir

    def _load_model(self) -> None:
        """Load the zero-shot classification pipeline."""
        try:
            from transformers import pipeline

            logger.info("model_sentiment.loading", model=self._model_name)
            self._pipeline = pipeline(
                "zero-shot-classification",
                model=self._model_name,
                cache_dir=self.cache_dir or None,
                device=-1,  # CPU
            )
            logger.info("model_sentiment.loaded", model=self._model_name)
        except ImportError:
            logger.warning("model_sentiment.no_transformers", hint="pip install transformers")
        except Exception as e:
            logger.error("model_sentiment.load_failed", error=str(e))

    def analyze(self, text: str) -> dict:
        """Analyze sentiment and return result dict compatible with SentimentResult.

        Returns a dict with keys:
            sentiment, intensity, reason
        """
        from src.classifiers.sentiment import SentimentType

        if not text or not text.strip():
            return {
                "sentiment": SentimentType.NEUTRAL,
                "intensity": 0.0,
                "reason": "Empty text — classified as NEUTRAL",
            }

        self.ensure_loaded()

        if not self.is_loaded():
            return {
                "sentiment": SentimentType.NEUTRAL,
                "intensity": 0.0,
                "reason": "Model not loaded — fallback to NEUTRAL",
            }

        try:
            result = self._pipeline(
                text,
                candidate_labels=SENTIMENT_LABELS_ZH,
                multi_label=False,
            )

            top_label = result["labels"][0]
            intensity = round(result["scores"][0], 4)

            label_idx = SENTIMENT_LABELS_ZH.index(top_label) if top_label in SENTIMENT_LABELS_ZH else 2
            sentiment_val = LABEL_TO_SENTIMENT.get(label_idx, 3)  # default NEUTRAL
            sentiment = SentimentType(sentiment_val)

            return {
                "sentiment": sentiment,
                "intensity": intensity,
                "reason": f"Model classified as {sentiment.name} (intensity={intensity:.2f})",
            }

        except Exception as e:
            logger.error("model_sentiment.classify_error", error=str(e))
            return {
                "sentiment": SentimentType.NEUTRAL,
                "intensity": 0.0,
                "reason": f"Model error: {e}",
            }


# ── Singleton instances (lazy, only created when NLP_BACKEND=model) ──

model_intent_classifier: ModelIntentClassifier | None = None
model_sentiment_analyzer: ModelSentimentAnalyzer | None = None


def get_model_backends(
    model_name: str = "",
    cache_dir: str = "",
) -> tuple[ModelIntentClassifier, ModelSentimentAnalyzer]:
    """Get or create singleton model backend instances."""
    global model_intent_classifier, model_sentiment_analyzer

    if model_intent_classifier is None:
        model_intent_classifier = ModelIntentClassifier(
            model_name=model_name,
            cache_dir=cache_dir,
        )
    if model_sentiment_analyzer is None:
        model_sentiment_analyzer = ModelSentimentAnalyzer(
            model_name=model_name,
            cache_dir=cache_dir,
        )

    return model_intent_classifier, model_sentiment_analyzer
