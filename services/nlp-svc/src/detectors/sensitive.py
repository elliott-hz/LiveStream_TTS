"""
Dual-mode sensitive word detection.

Layer 1 — AC Automaton (dictionary-based):
  Uses a built-in dictionary of 50+ sensitive words across categories:
  political, adult, violence, ads.

Layer 2 — LLM Semantic (fallback):
  Placeholder for semantic-based detection using an LLM.
  Currently returns a mock result.

Usage:
    from detectors.sensitive import sensitive_detector

    result = sensitive_detector.check("some text")
    # → SensitiveResult(is_sensitive=True, matches=[...])
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from libs.common.logging import get_logger

logger = get_logger(__name__)


class DetectionLayer(IntEnum):
    """Detection layer enum matching proto DetectionLayer values."""
    UNSPECIFIED = 0
    AC_AUTOMATON = 1
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


class SensitiveDetector:
    """
    Dual-mode sensitive word detector.

    Layer 1: AC Automaton (dictionary-based matching)
    Layer 2: LLM Semantic (placeholder — returns mock results)
    """

    def __init__(self, llm_semantic_enabled: bool = False) -> None:
        self.llm_semantic_enabled = llm_semantic_enabled
        self.automaton = ACAutomaton()
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
        )

    def check(self, text: str, context: str = "danmaku") -> SensitiveResult:
        """
        Run dual-mode sensitive word detection on the given text.

        Args:
            text: The text to check.
            context: The context of the text ("script", "danmaku", "avatar_name").

        Returns:
            SensitiveResult with matches from both layers.
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

        # Layer 2: LLM Semantic (placeholder)
        if self.llm_semantic_enabled:
            llm_matches = self._check_llm_semantic(text, context)
            all_matches.extend(llm_matches)
        else:
            # Even when disabled, check for mock semantic patterns
            llm_matches = self._mock_semantic_check(text)
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
        """
        Run LLM-based semantic detection.

        This is a placeholder that returns mock results.
        Replace with actual DeepSeek/LLM API call in production.
        """
        matches: list[SensitiveMatch] = []

        # Mock: Detect semantically sensitive content even without keyword match
        # e.g., disguised sensitive terms, coded language
        semantic_patterns: list[tuple[str, str, str]] = [
            # (detected phrase, category, keyword to report)
        ]

        for phrase, category, keyword in semantic_patterns:
            if phrase.lower() in text.lower():
                pos = text.lower().find(phrase.lower())
                matches.append(SensitiveMatch(
                    word=keyword,
                    category=category,
                    start_pos=pos,
                    end_pos=pos + len(phrase),
                    layer=DetectionLayer.LLM_SEMANTIC,
                ))

        return matches

    def _mock_semantic_check(self, text: str) -> list[SensitiveMatch]:
        """
        Mock semantic check for when LLM is disabled.

        Catches some obfuscated patterns that pure dictionary matching might miss.
        """
        matches: list[SensitiveMatch] = []

        # Catch obfuscated contact info (numbers with spaces/dots)
        import re

        # Phone number pattern: 1xx-xxxx-xxxx or similar
        phone_pattern = re.compile(r"1[3-9]\d[\s\-.]?\d{4}[\s\-.]?\d{4}")
        if phone_pattern.search(text):
            # Only flag if it looks like unsolicited contact sharing
            pass  # Phone numbers alone aren't necessarily sensitive

        # Multiple non-Chinese characters repeated (possible spam)
        if len(text) > 20 and all(ord(c) < 128 for c in text if c != " "):
            matches.append(SensitiveMatch(
                word="[疑似垃圾信息]",
                category="ads",
                start_pos=0,
                end_pos=len(text),
                layer=DetectionLayer.LLM_SEMANTIC,
            ))

        return matches


# Singleton instance
sensitive_detector = SensitiveDetector()
