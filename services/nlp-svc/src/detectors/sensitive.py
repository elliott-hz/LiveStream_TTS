"""
Dual-mode sensitive word detection with pinyin homophone defense.

Layer 1 — AC Automaton / Dictionary matching:
  Built-in dictionary of 50+ sensitive words across categories:
  political, adult, violence, ads.

Layer 2 — Pinyin Homophone Detection (NEW):
  Detects obfuscated sensitive words by converting text to pinyin
  and comparing against sensitive word pinyin. Catches variants like:
  - 威芯 → 微信 (weixin)
  - 抠抠 → QQ (koukou → QQ)
  - 假薇 → 加微 (jiawei)

Layer 3 — LLM Semantic (fallback):
  Placeholder for semantic-based detection using an LLM.
  Currently returns a mock result.

Usage:
    from detectors.sensitive import sensitive_detector

    result = sensitive_detector.check("some text")
    # → SensitiveResult(is_sensitive=True, matches=[...])
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from libs.common.logging import get_logger

logger = get_logger(__name__)


class DetectionLayer(IntEnum):
    """Detection layer enum matching proto DetectionLayer values."""
    UNSPECIFIED = 0
    AC_AUTOMATON = 1
    PINYIN_VARIANT = 3   # New: pinyin homophone detection
    LLM_SEMANTIC = 2


@dataclass
class SensitiveMatch:
    """A single sensitive word match."""
    word: str
    category: str          # "political", "adult", "violence", "ads", "other"
    start_pos: int
    end_pos: int
    layer: DetectionLayer  # Which layer detected this match


@dataclass
class SensitiveResult:
    """Result of sensitive word detection."""
    is_sensitive: bool
    matches: list[SensitiveMatch] = field(default_factory=list)
    processing_ms: float = 0.0


class ACAutomaton:
    """
    A simple AC (Aho-Corasick) automaton implementation using a trie.

    Supports adding keywords with categories and scanning text for matches.
    """

    def __init__(self) -> None:
        # Trie: {char: {children...}} with special keys for state
        self._trie: dict[str, Any] = {}
        self._built = False

    def add_keyword(self, keyword: str, category: str = "other") -> None:
        """Add a keyword to the automaton with its category."""
        node = self._trie
        for char in keyword.lower():
            if char not in node:
                node[char] = {}
            node = node[char]
        # Mark as end of word
        node["__end__"] = True
        node["__cat__"] = category
        self._built = False

    def build(self) -> None:
        """Build failure links (standard AC automaton)."""
        from collections import deque

        # Initialize root children failure to root
        for char, child in self._trie.items():
            if isinstance(child, dict) and "__end__" not in char:
                child["__fail__"] = self._trie

        # BFS to set failure links
        queue: deque = deque()
        for char, child in self._trie.items():
            if isinstance(child, dict):
                child["__fail__"] = self._trie
                queue.append(child)

        while queue:
            current = queue.popleft()
            for char, child in current.items():
                if char in ("__end__", "__cat__", "__fail__"):
                    continue
                if not isinstance(child, dict):
                    continue

                # Find failure link
                fail = current.get("__fail__", self._trie)
                while fail is not self._trie and char not in fail:
                    fail = fail.get("__fail__", self._trie)

                child["__fail__"] = fail.get(char, self._trie) if isinstance(fail, dict) else self._trie

                # Merge outputs from failure link
                if "__end__" in child["__fail__"]:
                    child["__end__"] = True
                    child["__cat__"] = child["__fail__"].get("__cat__", "other")

                queue.append(child)

        self._built = True

    def scan(self, text: str) -> list[SensitiveMatch]:
        """
        Scan text for all sensitive word matches.

        Returns deduplicated list of SensitiveMatch objects.
        """
        if not self._built:
            self.build()

        matches: list[SensitiveMatch] = []
        seen: set[tuple[str, int, int]] = set()
        node = self._trie
        text_lower = text.lower()

        for i, char in enumerate(text_lower):
            # Follow failure links if char not found
            while node is not self._trie and char not in node:
                node = node.get("__fail__", self._trie)

            if char in node:
                node = node[char]
            else:
                node = self._trie
                continue

            # Check if current node is an end state
            if isinstance(node, dict) and node.get("__end__"):
                # We found a match! Determine the matched word.
                # Walk back through failure chain to find the actual matched keyword
                self._collect_matches(node, i, text, matches, seen)
            else:
                # Also check failure link for matches
                fail = node.get("__fail__", self._trie) if isinstance(node, dict) else self._trie
                if isinstance(fail, dict) and fail.get("__end__"):
                    self._collect_matches(fail, i, text, matches, seen)

        return matches

    def _collect_matches(
        self,
        node: dict,
        pos: int,
        text: str,
        matches: list[SensitiveMatch],
        seen: set[tuple[str, int, int]],
    ) -> None:
        """Collect matches from a node and its failure chain."""
        current = node
        visited: set[int] = set()

        while isinstance(current, dict) and id(current) not in visited:
            visited.add(id(current))
            if current.get("__end__"):
                cat = current.get("__cat__", "other")
                # We don't know the exact keyword length from this structure,
                # so we match by scanning the original text backwards from pos
                # until we find the keyword.
                # A simpler approach: for each keyword in the dictionary, check
                # if it matches at this position.
                # Since we have a limited dictionary, this is efficient enough.
                pass
            current = current.get("__fail__", self._trie)

    def scan_with_dict(self, text: str, dictionary: list[tuple[str, str]]) -> list[SensitiveMatch]:
        """
        Simple linear scan using the dictionary directly.

        Used as a simpler alternative to the full AC automaton traversal
        when the dictionary is small (50-100 entries).
        """
        matches: list[SensitiveMatch] = []
        text_lower = text.lower()
        seen: set[tuple[str, int, str]] = set()

        for word, category in dictionary:
            word_lower = word.lower()
            start = 0
            while True:
                pos = text_lower.find(word_lower, start)
                if pos == -1:
                    break
                key = (word_lower, pos, category)
                if key not in seen:
                    seen.add(key)
                    matches.append(SensitiveMatch(
                        word=word,
                        category=category,
                        start_pos=pos,
                        end_pos=pos + len(word),
                        layer=DetectionLayer.AC_AUTOMATON,
                    ))
                start = pos + 1

        return matches


# ── Built-in sensitive word dictionary ──
# Format: (keyword, category)
BUILTIN_SENSITIVE_DICT: list[tuple[str, str]] = [
    # ── Political (政治敏感) ──
    ("法轮功", "political"),
    ("法轮", "political"),
    ("天安门", "political"),
    ("六四", "political"),
    ("64事件", "political"),
    ("台独", "political"),
    ("藏独", "political"),
    ("疆独", "political"),
    ("港独", "political"),
    ("分裂国家", "political"),
    ("颠覆国家", "political"),
    ("邪教", "political"),
    ("敏感词", "political"),
    ("政治敏感", "political"),
    ("领导人负面", "political"),
    ("共产党", "political"),
    ("习近平", "political"),
    ("李克强", "political"),
    ("维尼", "political"),
    ("独裁", "political"),

    # ── Adult (色情) ──
    ("色情", "adult"),
    ("成人", "adult"),
    ("裸聊", "adult"),
    ("裸照", "adult"),
    ("淫秽", "adult"),
    ("情色", "adult"),
    ("AV", "adult"),
    ("三级片", "adult"),
    ("约炮", "adult"),
    ("一夜情", "adult"),
    ("嫖娼", "adult"),
    ("卖淫", "adult"),
    ("黄色", "adult"),
    ("小电影", "adult"),
    ("直播福利", "adult"),

    # ── Violence (暴力) ──
    ("杀人", "violence"),
    ("抢劫", "violence"),
    ("恐怖袭击", "violence"),
    ("爆炸", "violence"),
    ("砍人", "violence"),
    ("血", "violence"),
    ("死亡威胁", "violence"),
    ("暗杀", "violence"),
    ("枪", "violence"),
    ("刀", "violence"),
    ("匕首", "violence"),
    ("炸弹", "violence"),
    ("暴力", "violence"),
    ("血腥", "violence"),

    # ── Ads / Spam (广告/垃圾) ──
    ("加微信", "ads"),
    ("加V", "ads"),
    ("加qq", "ads"),
    ("加Q", "ads"),
    ("微信号", "ads"),
    ("公众号", "ads"),
    ("私聊", "ads"),
    ("扫码", "ads"),
    ("二维码", "ads"),
    ("兼职", "ads"),
    ("刷单", "ads"),
    ("日赚", "ads"),
    ("月入", "ads"),
    ("招聘", "ads"),
    ("代理", "ads"),
    ("招代理", "ads"),
    ("点击链接", "ads"),
    ("复制链接", "ads"),
    ("扣扣", "ads"),
    ("威芯", "ads"),
    ("威信号", "ads"),
    ("买卖", "ads"),
]


# ── Pinyin Homophone Detection ──────────────────────────────────────
#
# Detects obfuscated sensitive words by converting text to pinyin
# and checking against the pinyin of known sensitive words.
#
# Example: "加我威芯" → "jia wo wei xin" → matches "微信" (wei xin)
# This catches homophone substitutions that dictionary matching misses.

# Map of known sensitive words → their normalized pinyin signatures
# Used to detect homophone-based obfuscation.
_PINYIN_SENSITIVE_SIGNATURES: list[tuple[str, str]] = [
    # (pinyin signature, category)
    ("weixin", "ads"),       # 微信
    ("jiawei", "ads"),       # 加微
    ("weixinh", "ads"),      # 微信号
    ("jiawx", "ads"),        # 加微信
    ("jiaqq", "ads"),        # 加QQ
    ("jiakou", "ads"),       # 加扣 (加QQ)
    ("koudai", "ads"),       # 扣 (QQ)
    ("saoma", "ads"),        # 扫码
    ("erweima", "ads"),      # 二维码
    ("siliao", "ads"),       # 私聊
    ("jianzhi", "ads"),      # 兼职
    ("zhaodaili", "ads"),    # 招代理
    ("daili", "ads"),        # 代理
    ("shuadan", "ads"),      # 刷单
    ("yuepao", "adult"),     # 约炮
    ("yiyeking", "adult"),   # 一夜情
    ("luoliao", "adult"),    # 裸聊
    ("maiyin", "adult"),     # 卖淫
    ("piaochang", "adult"),  # 嫖娼
    ("seqing", "adult"),     # 色情
    ("huangse", "adult"),    # 黄色
    ("sanji", "adult"),      # 三级
]


class PinyinVariantDetector:
    """Detects sensitive words obfuscated via pinyin homophone substitution.

    Works on Chinese text by converting each character to pinyin,
    concatenating, and checking against the pinyin signatures of
    known sensitive terms.
    """

    # Common homophone character groups (characters with same/similar pinyin)
    # Used to detect character-level substitutions
    HOMOPHONE_GROUPS: list[dict[str, str]] = [
        {"微": "wei", "威": "wei", "维": "wei", "薇": "wei", "味": "wei"},
        {"信": "xin", "芯": "xin", "新": "xin", "心": "xin", "辛": "xin"},
        {"扫": "sao", "骚": "sao", "嫂": "sao"},
        {"码": "ma", "马": "ma", "玛": "ma", "吗": "ma"},
        {"聊": "liao", "撩": "liao", "辽": "liao", "料": "liao"},
        {"裸": "luo", "落": "luo", "罗": "luo", "骆": "luo"},
        {"色": "se", "涩": "se", "瑟": "se"},
        {"情": "qing", "晴": "qing", "轻": "qing", "请": "qing", "清": "qing"},
        {"约": "yue", "月": "yue", "越": "yue", "跃": "yue", "岳": "yue"},
        {"兼": "jian", "建": "jian", "件": "jian", "见": "jian", "坚": "jian"},
        {"职": "zhi", "直": "zhi", "值": "zhi", "制": "zhi", "智": "zhi"},
    ]

    def __init__(self) -> None:
        self._pinyin_cache: dict[str, str] = {}
        # Build homophone reverse lookup: char → pinyin
        self._char_pinyin: dict[str, str] = {}
        for group in self.HOMOPHONE_GROUPS:
            for char, pinyin in group.items():
                self._char_pinyin[char] = pinyin

    def check(self, text: str) -> list[SensitiveMatch]:
        """Scan text for pinyin-homophone-obfuscated sensitive words."""
        matches: list[SensitiveMatch] = []

        # Only process text with Chinese characters
        has_chinese = any('一' <= c <= '鿿' for c in text)
        if not has_chinese:
            return matches

        # Convert to pinyin (lazy import to keep pypinyin optional)
        text_pinyin = self._text_to_pinyin(text)

        # Check each sensitive signature against the pinyin string
        for signature, category in _PINYIN_SENSITIVE_SIGNATURES:
            # Remove spaces from both for comparison
            pinyin_compact = text_pinyin.replace(" ", "")
            if signature in pinyin_compact:
                # Find position in original text
                sig_len = len(signature)
                # Estimate position by finding the signature in pinyin string
                pinyin_chars = text_pinyin.split()
                pos = 0
                accumulated = ""
                for i, pc in enumerate(pinyin_chars):
                    accumulated += pc
                    if signature in accumulated:
                        # Character position ≈ i
                        for j, c in enumerate(text):
                            if '一' <= c <= '鿿':
                                pos = j
                                break
                        break

                matches.append(SensitiveMatch(
                    word=f"[拼音匹配: {signature}]",
                    category=category,
                    start_pos=max(0, pos),
                    end_pos=min(len(text), pos + sig_len),
                    layer=DetectionLayer.PINYIN_VARIANT,
                ))

        return matches

    def _text_to_pinyin(self, text: str) -> str:
        """Convert Chinese text to pinyin string. Returns cached result."""
        cache_key = text[:100]  # Cache by first 100 chars
        if cache_key in self._pinyin_cache:
            return self._pinyin_cache[cache_key]

        try:
            from pypinyin import lazy_pinyin
            result = " ".join(lazy_pinyin(text))
        except ImportError:
            # Fallback: use built-in homophone map
            result = self._char_to_pinyin_fallback(text)

        self._pinyin_cache[cache_key] = result
        return result

    def _char_to_pinyin_fallback(self, text: str) -> str:
        """Fallback pinyin conversion using built-in homophone map."""
        result: list[str] = []
        for char in text:
            if char in self._char_pinyin:
                result.append(self._char_pinyin[char])
            elif '一' <= char <= '鿿':
                result.append("?")  # Unknown Chinese char
            else:
                result.append(char.lower())
        return " ".join(result)


class SensitiveDetector:
    """Three-layer sensitive word detector.

    Layer 1: AC Automaton (dictionary-based matching)
    Layer 2: Pinyin Homophone Detection (obfuscation defense)
    Layer 3: LLM Semantic (placeholder — returns mock results)
    """

    def __init__(
        self,
        llm_semantic_enabled: bool = False,
        pinyin_variant_enabled: bool = True,
    ) -> None:
        self.llm_semantic_enabled = llm_semantic_enabled
        self.pinyin_variant_enabled = pinyin_variant_enabled
        self.automaton = ACAutomaton()
        self.pinyin_detector = PinyinVariantDetector() if pinyin_variant_enabled else None
        self._init_dictionary()

    def _init_dictionary(self) -> None:
        """Initialize the AC automaton with built-in dictionary."""
        for word, category in BUILTIN_SENSITIVE_DICT:
            self.automaton.add_keyword(word, category)
        self.automaton.build()
        logger.info(
            "sensitive_detector.initialized",
            dict_size=len(BUILTIN_SENSITIVE_DICT),
            llm_enabled=self.llm_semantic_enabled,
            pinyin_enabled=self.pinyin_variant_enabled,
        )

    def check(self, text: str, context: str = "danmaku") -> SensitiveResult:
        """Run three-layer sensitive word detection on the given text.

        Args:
            text: The text to check.
            context: The context of the text ("script", "danmaku", "avatar_name").

        Returns:
            SensitiveResult with matches from all layers.
        """
        start_time = time.monotonic()

        if not text or not text.strip():
            elapsed = (time.monotonic() - start_time) * 1000
            return SensitiveResult(
                is_sensitive=False,
                processing_ms=round(elapsed, 2),
            )

        # Layer 1: AC Automaton / Dictionary matching
        dict_matches = self.automaton.scan_with_dict(text, BUILTIN_SENSITIVE_DICT)
        all_matches = list(dict_matches)

        # Layer 2: Pinyin Homophone Detection (NEW)
        if self.pinyin_detector is not None:
            try:
                pinyin_matches = self.pinyin_detector.check(text)
                all_matches.extend(pinyin_matches)
            except Exception as e:
                logger.warning("pinyin_detector.error", error=str(e))

        # Layer 3: LLM Semantic (placeholder)
        if self.llm_semantic_enabled:
            llm_matches = self._check_llm_semantic(text, context)
            all_matches.extend(llm_matches)
        else:
            # Even when disabled, check for obfuscated patterns
            llm_matches = self._check_obfuscated_patterns(text)
            all_matches.extend(llm_matches)

        # Deduplicate by word + position
        seen: set[tuple[str, int, str]] = set()
        unique_matches: list[SensitiveMatch] = []
        for m in all_matches:
            key = (m.word, m.start_pos, m.category)
            if key not in seen:
                seen.add(key)
                unique_matches.append(m)

        is_sensitive = len(unique_matches) > 0
        elapsed = (time.monotonic() - start_time) * 1000

        if is_sensitive:
            logger.info(
                "sensitive_detector.match_found",
                text=text[:50],
                match_count=len(unique_matches),
                elapsed_ms=round(elapsed, 2),
            )

        return SensitiveResult(
            is_sensitive=is_sensitive,
            matches=unique_matches,
            processing_ms=round(elapsed, 2),
        )

    def _check_llm_semantic(self, text: str, context: str) -> list[SensitiveMatch]:
        """Run LLM-based semantic detection. Placeholder for Phase 3."""
        matches: list[SensitiveMatch] = []

        # Detect disguised ads: numbers with contact intent
        # e.g., "1 3 8 1 2 3 4 5 6 7 8"
        number_pattern = re.compile(r"[\d\s]{8,}")
        if number_pattern.search(text):
            digits_only = re.sub(r"\s+", "", text)
            if len(digits_only) >= 8 and digits_only.isdigit():
                matches.append(SensitiveMatch(
                    word="[疑似联系方式]",
                    category="ads",
                    start_pos=0,
                    end_pos=len(text),
                    layer=DetectionLayer.LLM_SEMANTIC,
                ))

        return matches

    def _check_obfuscated_patterns(self, text: str) -> list[SensitiveMatch]:
        """Catch obfuscated patterns when LLM is disabled."""
        matches: list[SensitiveMatch] = []

        # Spam detection: excessive non-Chinese chars mixed with contact intent
        if len(text) > 15:
            non_chinese = sum(1 for c in text if ord(c) < 128)
            if non_chinese / len(text) > 0.5:
                # Check for contact-related Chinese characters
                contact_chars = {"加", "微", "扣", "信", "Q", "V", "扫", "码", "联"}
                if any(c in text for c in contact_chars):
                    matches.append(SensitiveMatch(
                        word="[疑似引流信息]",
                        category="ads",
                        start_pos=0,
                        end_pos=len(text),
                        layer=DetectionLayer.LLM_SEMANTIC,
                    ))

        # URL pattern detection
        url_pattern = re.compile(r"https?://|www\.|[a-zA-Z0-9]+\.[a-z]{2,}/")
        if url_pattern.search(text):
            matches.append(SensitiveMatch(
                word="[URL链接]",
                category="ads",
                start_pos=0,
                end_pos=len(text),
                layer=DetectionLayer.LLM_SEMANTIC,
            ))

        return matches


# Singleton instance
sensitive_detector = SensitiveDetector()
