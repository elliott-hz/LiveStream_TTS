"""
DeepSeek / OpenAI-compatible LLM reply service for live-stream interactions.

Handles:
  - Chat API calls (DeepSeek-Chat, compatible with OpenAI format)
  - Prompt assembly from session + product + RAG context
  - Automatic fallback to keyword templates on API failure
  - Retry with exponential backoff + circuit breaker
  - Multi-turn conversation context management

Usage::

    service = ReplyService(api_key="sk-...", model="deepseek-chat")
    reply = await service.generate(prompt, session_id="xxx")
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

import httpx

from libs.common.logging import get_logger

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_API_BASE = "https://api.deepseek.com"
DEFAULT_MAX_TOKENS = 80       # Short replies for livestream
DEFAULT_TEMPERATURE = 0.9     # Creative but coherent
DEFAULT_TIMEOUT_SECONDS = 5.0  # Must respond fast for live interaction
MAX_RETRIES = 2
RETRY_BASE_DELAY = 0.3

# Circuit breaker
CIRCUIT_OPEN_THRESHOLD = 5   # consecutive failures
CIRCUIT_HALF_OPEN_AFTER = 30  # seconds before retry
CIRCUIT_HALF_OPEN_MAX = 1     # max requests in half-open state


@dataclass
class LLMConfig:
    """Configuration for the LLM API client."""
    api_key: str = ""
    api_base: str = DEFAULT_API_BASE
    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = MAX_RETRIES


@dataclass
class ReplyResult:
    """Result of LLM reply generation."""
    text: str
    emotion: int          # proto emotion enum value
    action: str           # action keyword for the pipeline
    model: str = ""       # which model generated this
    is_fallback: bool = False  # True if using template fallback
    latency_ms: float = 0.0


class CircuitBreaker:
    """Simple circuit breaker for LLM API calls."""

    def __init__(self, threshold: int = CIRCUIT_OPEN_THRESHOLD,
                 recovery_seconds: float = CIRCUIT_HALF_OPEN_AFTER) -> None:
        self.threshold = threshold
        self.recovery_seconds = recovery_seconds
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = "closed"  # closed / open / half_open
        self._half_open_count = 0

    @property
    def is_open(self) -> bool:
        if self._state == "closed":
            return False
        if self._state == "open":
            if time.monotonic() - self._last_failure_time >= self.recovery_seconds:
                self._state = "half_open"
                self._half_open_count = 0
                logger.info("circuit_breaker.half_open")
                return False
            return True
        # half_open: allow limited requests
        return self._half_open_count >= CIRCUIT_HALF_OPEN_MAX

    def success(self) -> None:
        if self._state == "half_open":
            self._state = "closed"
            self._failure_count = 0
            logger.info("circuit_breaker.closed")
        self._failure_count = 0

    def failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._state == "half_open":
            self._state = "open"
            logger.warning("circuit_breaker.open_again", failures=self._failure_count)
        elif self._failure_count >= self.threshold:
            self._state = "open"
            logger.warning("circuit_breaker.open", failures=self._failure_count)


class ReplyService:
    """LLM-powered reply generator for livestream danmaku interactions.

    Uses DeepSeek Chat API (OpenAI-compatible format) with automatic
    fallback to keyword-based templates. Includes retry logic and
    circuit breaker for resilience.
    """

    # ── Keyword template fallbacks (same as POC mocks) ──
    TEMPLATE_REPLIES: dict[int, tuple[str, int, str]] = {
        3: ("{product} 现在下单只要 {price} 元，点击下方链接购买哦~", 2, "show_product_card"),
        1: ("这款 {product} 富含多种有效成分，效果特别好哦！", 4, "point_product"),
        2: ("好的，给大家详细讲解一下 {product}~", 3, "show_detail"),
        4: ("亲，这个价格已经是最优惠了，性价比超高哦！", 4, "wave_hand"),
        5: ("亲亲别着急，有什么问题可以私信客服帮您解决哦~", 4, "wave_hand"),
        6: ("欢迎来到直播间！喜欢的话点个关注哦~", 2, "wave_hand"),
        7: ("谢谢亲的夸奖！喜欢的话记得分享给朋友哦~", 2, "wave_hand"),
        10: ("我们的 {product} 比同类产品更有优势哦！", 3, "show_detail"),
        11: ("售后问题请私信客服，我们会第一时间为您处理！", 4, "wave_hand"),
        9: ("马上给大家安排！正在准备中~", 3, "wave_hand"),
    }

    DEFAULT_TEMPLATE = ("感谢您的关注！有什么问题可以随时问我哦~", 2, "wave_hand")

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.circuit_breaker = CircuitBreaker()
        self._http_client: httpx.AsyncClient | None = None
        # Per-session conversation history
        self._conversations: dict[str, list[dict[str, str]]] = defaultdict(list)
        self._max_history = 6  # Keep last 6 messages for context

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init httpx client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout_seconds),
                limits=httpx.Limits(max_keepalive_connections=10),
            )
        return self._http_client

    async def generate(
        self,
        prompt: str,
        session_id: str = "",
        system_prompt: str = "",
        product_title: str = "",
        product_price: str = "",
    ) -> ReplyResult:
        """Generate a reply using the LLM API.

        Falls back to template if:
        - No API key configured
        - Circuit breaker is open
        - API call fails after retries

        Args:
            prompt: The full assembled prompt.
            session_id: Session ID for conversation context.
            system_prompt: System prompt for the LLM.
            product_title: Product name (for template fallback).
            product_price: Product price (for template fallback).

        Returns:
            ReplyResult with text, emotion, action.
        """
        start = time.monotonic()

        # Fallback conditions: no API key or circuit open
        if not self.config.api_key:
            return self._template_fallback(prompt, product_title, product_price, start, "No API key configured")

        if self.circuit_breaker.is_open:
            return self._template_fallback(prompt, product_title, product_price, start, "Circuit breaker open")

        # Build messages for API
        messages = self._build_messages(prompt, system_prompt, session_id)

        # Call API with retries
        for attempt in range(self.config.max_retries + 1):
            try:
                reply_text = await self._call_api(messages)
                self.circuit_breaker.success()

                # Parse emotion from reply
                emotion = self._extract_emotion(reply_text)
                action = self._extract_action(reply_text)
                latency = (time.monotonic() - start) * 1000

                # Store in conversation history
                self._add_to_history(session_id, prompt, reply_text)

                logger.debug(
                    "llm.reply.generated",
                    session_id=session_id,
                    latency_ms=round(latency, 1),
                    model=self.config.model,
                )

                return ReplyResult(
                    text=reply_text.strip(),
                    emotion=emotion,
                    action=action,
                    model=self.config.model,
                    is_fallback=False,
                    latency_ms=round(latency, 1),
                )

            except Exception as e:
                logger.warning(
                    "llm.api.attempt_failed",
                    attempt=attempt + 1,
                    error=str(e),
                )
                if attempt < self.config.max_retries:
                    await self._sleep(RETRY_BASE_DELAY * (2 ** attempt))
                else:
                    self.circuit_breaker.failure()

        return self._template_fallback(prompt, product_title, product_price, start, "API call failed after retries")

    async def _call_api(self, messages: list[dict[str, str]]) -> str:
        """Make a single API call to DeepSeek / OpenAI-compatible endpoint."""
        client = await self._get_client()
        url = f"{self.config.api_base}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "stream": False,
        }

        response = await client.post(url, json=body, headers=headers)
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def _build_messages(
        self,
        prompt: str,
        system_prompt: str,
        session_id: str,
    ) -> list[dict[str, str]]:
        """Build the message list for the API call."""
        messages: list[dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            messages.append({"role": "system", "content": _DEFAULT_SYSTEM_PROMPT})

        # Add conversation history for this session
        if session_id and session_id in self._conversations:
            history = self._conversations[session_id][-self._max_history:]
            messages.extend(history)

        messages.append({"role": "user", "content": prompt})
        return messages

    def _add_to_history(self, session_id: str, user_msg: str, reply: str) -> None:
        """Add a conversation turn to the session history."""
        if not session_id:
            return
        self._conversations[session_id].append({"role": "user", "content": user_msg})
        self._conversations[session_id].append({"role": "assistant", "content": reply})
        # Trim to keep memory bounded
        if len(self._conversations[session_id]) > self._max_history * 2:
            self._conversations[session_id] = self._conversations[session_id][-self._max_history * 2:]

    def clear_history(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        self._conversations.pop(session_id, None)

    # ── Template Fallback ─────────────────────────────────────

    def _template_fallback(
        self,
        prompt: str,
        product_title: str,
        product_price: str,
        start: float,
        reason: str,
    ) -> ReplyResult:
        """Fall back to keyword template matching when LLM unavailable."""
        intent = self._guess_intent_from_prompt(prompt)
        template = self.TEMPLATE_REPLIES.get(intent)
        if template:
            text, emotion, action = template
            text = text.format(product=product_title, price=product_price)
        else:
            text, emotion, action = self.DEFAULT_TEMPLATE

        latency = (time.monotonic() - start) * 1000

        logger.info(
            "llm.fallback.used",
            reason=reason,
            intent=intent,
            latency_ms=round(latency, 1),
        )

        return ReplyResult(
            text=text,
            emotion=emotion,
            action=action,
            model="template",
            is_fallback=True,
            latency_ms=round(latency, 1),
        )

    @staticmethod
    def _guess_intent_from_prompt(prompt: str) -> int:
        """Quick intent guess from the prompt text for template fallback."""
        prompt_lower = prompt.lower()
        # Check for intent markers in the prompt
        if "购买" in prompt_lower or "下单" in prompt_lower or "链接" in prompt_lower:
            return 3  # PURCHASE_INTENT
        if "议价" in prompt_lower or "便宜" in prompt_lower or "优惠" in prompt_lower:
            return 4  # BARGAIN
        if "投诉" in prompt_lower or "不满" in prompt_lower:
            return 5  # COMPLAINT
        if "寒暄" in prompt_lower or "打招呼" in prompt_lower:
            return 6  # GREETING
        if "赞美" in prompt_lower or "夸奖" in prompt_lower:
            return 7  # PRAISE
        if "对比" in prompt_lower or "比较" in prompt_lower:
            return 10  # COMPARE
        if "售后" in prompt_lower or "退货" in prompt_lower:
            return 11  # AFTERSALES
        if "催促" in prompt_lower or "快点" in prompt_lower:
            return 9  # URGE
        if "演示" in prompt_lower or "讲解" in prompt_lower:
            return 2  # REQUEST_DEMO
        return 1  # QUESTION (generic)

    @staticmethod
    def _extract_emotion(text: str) -> int:
        """Extract emotion from LLM response (simple keyword heuristic)."""
        # In production, the LLM would return structured JSON with emotion.
        # For now, use keyword matching on the reply text.
        if any(kw in text for kw in ["!", "！", "~", "哦", "啦", "呀", "冲冲冲"]):
            return 2  # HAPPY
        if any(kw in text for kw in ["抱歉", "对不起", "别急", "别着急", "亲亲"]):
            return 4  # WARM
        if "!!" in text or "！！" in text:
            return 3  # EXCITED
        return 2  # default HAPPY

    @staticmethod
    def _extract_action(text: str) -> str:
        """Extract suggested action from LLM response."""
        if any(kw in text for kw in ["链接", "下单", "购买", "买"]):
            return "show_product_card"
        if any(kw in text for kw in ["讲解", "介绍", "看看", "示范", "展示"]):
            return "show_detail"
        return "wave_hand"

    @staticmethod
    async def _sleep(seconds: float) -> None:
        """Async sleep helper."""
        import asyncio
        await asyncio.sleep(seconds)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# ── System Prompt ────────────────────────────────────────────

_DEFAULT_SYSTEM_PROMPT = (
    "你是一名专业带货主播，热情、亲切、专业。"
    "回复要简短有力（不超过40字），适合直播场景。"
    "禁止使用违禁词，始终围绕商品和直播主题。"
    "如果不知道答案，可以引导用户咨询客服。"
)
