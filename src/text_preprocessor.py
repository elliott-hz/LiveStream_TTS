"""
M3 — Text Preprocessor (Text Normalizer)
POC: 简化实现，只做 HTML 清洗 + 基本数字/日期转写
"""

import re
from typing import Optional


class TextPreprocessor:
    """正则规则引擎实现 Text Normalization。"""

    def __init__(self):
        self._build_rules()

    def _build_rules(self):
        """按顺序构建 TN 规则表。顺序敏感。"""
        self.rules = [
            # 1) HTML/Markdown 标签清洗
            ("clean_html", lambda t: re.sub(r"<[^>]+>", "", t)),
            ("clean_markdown", lambda t: re.sub(r"[#*_~`\[\]()>|-]{1,4}", "", t)),
            # 2) Emoji → 文字
            ("emoji_smile", lambda t: t.replace("😊", "微笑").replace("😄", "大笑")),
            ("emoji_sad", lambda t: t.replace("😢", "哭泣").replace("😭", "大哭")),
            ("emoji_love", lambda t: t.replace("❤️", "爱心").replace("😍", "喜爱")),
            ("emoji_ok", lambda t: t.replace("👍", "赞").replace("👎", "踩")),
            ("emoji_surprise", lambda t: t.replace("😮", "惊讶").replace("😱", "震惊")),
            # 3) URL → 可读形式
            ("url",
             lambda t: re.sub(
                 r"https?://([\w.-]+)(/\S*)?",
                 lambda m: m.group(1).replace(".", " dot "),
                 t,
             )),
            # 4) 连续换行 → 段落停顿标记
            ("double_newline", lambda t: re.sub(r"\n\s*\n", "。 ", t)),
            ("single_newline", lambda t: re.sub(r"\n", "，", t)),
            # 5) 日期 YYYY-MM-DD / YYYY/MM/DD
            ("date",
             lambda t: re.sub(
                 r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
                 lambda m: f"{self._num_to_cn(m.group(1))}年{self._num_to_cn(m.group(2))}月{self._num_to_cn(m.group(3))}日",
                 t,
             )),
            # 6) 时间 HH:MM:SS / HH:MM
            ("time",
             lambda t: re.sub(
                 r"(\d{1,2}):(\d{2})(?::(\d{2}))?",
                 lambda m: f"{self._digits_to_cn(m.group(1))}点{self._digits_to_cn(m.group(2))}分"
                           + (f"{self._digits_to_cn(m.group(3))}秒" if m.group(3) else ""),
                 t,
             )),
            # 7) 货币 ¥ / $ / € + 数字
            ("currency_cny", lambda t: re.sub(
                r"[¥￥](\d+(?:\.\d+)?)",
                lambda m: self._num_to_cn(m.group(1)) + "元",
                t,
            )),
            ("currency_usd", lambda t: re.sub(
                r"[$](\d+(?:\.\d+)?)",
                lambda m: self._num_to_cn(m.group(1)) + "美元",
                t,
            )),
            # 8) 百分比
            ("percent", lambda t: re.sub(
                r"(\d+(?:\.\d+)?)%",
                lambda m: "百分之" + self._num_to_cn(m.group(1)),
                t,
            )),
            # 9) 连续数字（长数字分段）— 用于电话号等
            ("long_digits", lambda t: re.sub(
                r"(?<!\d)(\d{5,})(?!\d)",
                lambda m: " ".join(m.group(1)),
                t,
            )),
            # 10) 纯数字（短数字）
            ("short_digits", lambda t: re.sub(
                r"(?<!\d)(\d{1,4})(?!\d)",
                lambda m: self._num_to_cn(m.group(1)),
                t,
            )),
            # 11) 多余空白清理
            ("whitespace", lambda t: re.sub(r"\s+", "", t)),
        ]

    _CN_NUMS = "零一二三四五六七八九"
    _CN_UNITS = ("", "十", "百", "千", "万", "亿")

    def _num_to_cn(self, s: str) -> str:
        """阿拉伯数字 → 中文数字（支持 ≤ 9999）。"""
        try:
            n = int(s)
        except (ValueError, TypeError):
            return s
        if n == 0:
            return "零"
        if n < 0:
            return "负" + self._num_to_cn(str(-n))
        if n < 10:
            return self._CN_NUMS[n]
        if n < 100:
            tens, ones = divmod(n, 10)
            result = "十" if tens == 1 else (self._CN_NUMS[tens] + "十")
            if ones:
                result += self._CN_NUMS[ones]
            return result
        if n < 1000:
            h, rest = divmod(n, 100)
            result = self._CN_NUMS[h] + "百"
            if rest:
                result += ("零" if rest < 10 else "") + self._num_to_cn(str(rest))
            return result
        if n < 10000:
            th, rest = divmod(n, 1000)
            result = self._CN_NUMS[th] + "千"
            if rest:
                result += ("零" if rest < 100 else "") + self._num_to_cn(str(rest))
            return result
        return s  # > 9999 暂不处理

    def _digits_to_cn(self, s: str) -> str:
        """数字逐位转中文（用于时间等场景）。"""
        return "".join(self._CN_NUMS[int(ch)] for ch in s if ch.isdigit())

    def process(self, text: str) -> str:
        """
        执行 TN 管线。
        输入: LLM 输出的原始文本
        输出: 规范化后的纯文本
        """
        if not text or not text.strip():
            return ""
        for name, fn in self.rules:
            try:
                text = fn(text)
            except Exception as e:
                pass  # 单条规则失败不阻塞管线
        return text
