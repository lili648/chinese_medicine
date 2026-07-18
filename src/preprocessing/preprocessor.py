# -*- coding: utf-8 -*-
"""
文本预处理器
类: Preprocessor - 文本清洗 + jieba分词
类: StopWords - 停用词管理器
对应需求: FR-02
"""
import logging
import re
from typing import Dict, List, Optional, Tuple
import jieba

from .data_loader import Article

logger = logging.getLogger(__name__)


class StopWords:
    """停用词管理器"""

    def __init__(self):
        self._stopwords: set = set()
        self._file_path: Optional[str] = None

    def load(self, file_path: str) -> None:
        """加载停用词表"""
        with open(file_path, "r", encoding="utf-8") as f:
            self._stopwords = {line.strip() for line in f if line.strip()}
        self._file_path = file_path
        logger.info("加载停用词 %d 个，来自: %s", len(self._stopwords), file_path)

    def add(self, words: List[str]) -> None:
        """动态添加停用词"""
        self._stopwords.update(words)

    def is_stopword(self, word: str) -> bool:
        """判断是否为停用词"""
        return word in self._stopwords

    def remove(self, text_list: List[str]) -> List[str]:
        """从词列表中移除停用词"""
        return [w for w in text_list if not self.is_stopword(w)]

    def __len__(self) -> int:
        return len(self._stopwords)

    def __contains__(self, word: str) -> bool:
        return word in self._stopwords


class PreprocessStats:
    """预处理统计信息"""

    def __init__(self):
        self.total_articles: int = 0
        self.total_tokens_before: int = 0
        self.total_tokens_after: int = 0
        self.empty_text_count: int = 0
        self.empty_abstract_count: int = 0
        self.empty_title_count: int = 0
        self.zh_count: int = 0
        self.en_count: int = 0

    @property
    def avg_tokens(self) -> float:
        """平均每篇文献 token 数（去停用词后）"""
        if self.total_articles == 0:
            return 0.0
        return self.total_tokens_after / self.total_articles

    @property
    def stopword_removal_rate(self) -> float:
        """停用词移除率"""
        if self.total_tokens_before == 0:
            return 0.0
        return 1.0 - self.total_tokens_after / self.total_tokens_before

    def to_dict(self) -> dict:
        return {
            "total_articles": self.total_articles,
            "total_tokens_before": self.total_tokens_before,
            "total_tokens_after": self.total_tokens_after,
            "avg_tokens_per_article": round(self.avg_tokens, 1),
            "stopword_removal_rate": f"{self.stopword_removal_rate:.1%}",
            "empty_text": self.empty_text_count,
            "empty_abstract": self.empty_abstract_count,
            "empty_title": self.empty_title_count,
            "zh_articles": self.zh_count,
            "en_articles": self.en_count,
        }

    def report(self) -> str:
        info = self.to_dict()
        lines = [
            "=" * 50,
            "文本预处理统计报告",
            "=" * 50,
            f"处理文献总数:     {info['total_articles']}",
            f"  - 中文文献:     {info['zh_articles']}",
            f"  - 英文文献:     {info['en_articles']}",
            f"分词前 token 总数: {info['total_tokens_before']}",
            f"分词后 token 总数: {info['total_tokens_after']}",
            f"平均每篇 token 数: {info['avg_tokens_per_article']}",
            f"停用词移除率:      {info['stopword_removal_rate']}",
            f"标题为空:         {info['empty_title']}",
            f"摘要为空:         {info['empty_abstract']}",
            f"全文为空:         {info['empty_text']}",
            "=" * 50,
        ]
        return "\n".join(lines)


class Preprocessor:
    """文本预处理器

    支持两种清洗模式：
      - strict (默认): 仅保留中英文字符
      - medical: 保留中英文 + 数字 + 常用医学符号
    """

    def __init__(self, stopwords: StopWords = None, mode: str = "medical"):
        """
        Args:
            stopwords: 停用词管理器
            mode: 清洗模式 - "strict" 或 "medical"
        """
        self.stopwords = stopwords or StopWords()
        self.mode = mode
        self.stats = PreprocessStats()

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = PreprocessStats()

    # ---------- 文本清洗 ----------

    def clean_text(self, text: str) -> str:
        """文本清洗：去 HTML/特殊字符"""
        if not text:
            return ""

        # 1. 去除 HTML 标签
        text = re.sub(r"<[^>]+>", "", text)

        # 2. 去除/替换特殊字符（保留集合取决于模式）
        if self.mode == "medical":
            # 保留：中文字符、英文字母、数字、常用医学符号
            # 包括：百分号、摄氏度、加减号、小数点、括号、连字符等
            text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9.%\u00b0℃+\-()（）/]", " ", text)
            # 清理多余的小数点（非数字间）
            text = re.sub(r"(?<!\d)\.(?!\d)", " ", text)
        else:
            # strict 模式：仅保留中英文
            text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z]", " ", text)

        # 3. 规范化空白
        text = re.sub(r"\s+", " ", text).strip()

        return text

    # ---------- 分词 ----------

    def segment(self, text: str, lang: str = "zh") -> List[str]:
        """
        分词：
          - 中文：jieba 分词，过滤超短 token
          - 英文：空格分词 + 小写归一化，过滤常见无意义短词
        """
        if not text.strip():
            return []

        if lang == "en":
            return self._segment_en(text)
        else:
            return self._segment_zh(text)

    @staticmethod
    def _segment_zh(text: str) -> List[str]:
        """中文分词"""
        tokens = jieba.lcut(text)
        # 过滤：空字符、纯空白、纯标点
        return [w.strip() for w in tokens
                if w.strip() and not re.match(r'^[\s\d.%\u00b0℃+\-()（）/]+$', w)]

    @staticmethod
    def _segment_en(text: str) -> List[str]:
        """英文分词：空格分割 + 小写归一化"""
        # 保留的英文短词（常见医学英文缩写和有意义短词）
        KEEP_SHORT = {"iv", "po", "qd", "bid", "tid", "qid", "hs", "prn",
                      "pc", "ac", "im", "sc", "id", "ng", "cm", "kg", "mg",
                      "ml", "dl", "bp", "hr", "rr", "ecg", "ct", "mri"}
        words = text.lower().split()
        return [w.strip(".,;:!?()[]{}'\"") for w in words
                if len(w.strip(".,;:!?()[]{}'\"")) > 1
                or w.strip(".,;:!?()[]{}'\"") in KEEP_SHORT]

    # ---------- 文献处理 ----------

    def process_article(self, article: Article) -> Article:
        """处理单篇文献，返回填充了 tokens 的对象"""
        # 清洗标题和摘要
        title_clean = self.clean_text(article.title or "")
        abstract_clean = self.clean_text(article.abstract or "")

        # 边界处理
        if not title_clean:
            self.stats.empty_title_count += 1
        if not abstract_clean:
            self.stats.empty_abstract_count += 1

        combined = f"{title_clean} {abstract_clean}".strip()
        if not combined:
            self.stats.empty_text_count += 1
            article.tokens = []
            self.stats.total_articles += 1
            return article

        # 分词
        tokens = self.segment(combined, article.language)
        self.stats.total_tokens_before += len(tokens)

        # 去停用词
        article.tokens = self.stopwords.remove(tokens)
        self.stats.total_tokens_after += len(article.tokens)

        # 更新统计
        self.stats.total_articles += 1
        if article.language == "zh":
            self.stats.zh_count += 1
        else:
            self.stats.en_count += 1

        return article

    def process_batch(self, articles: List[Article],
                      show_progress: bool = True) -> List[Article]:
        """批量处理文献列表，带进度日志"""
        total = len(articles)
        if total == 0:
            return []

        self.reset_stats()
        results = []

        for i, article in enumerate(articles):
            try:
                results.append(self.process_article(article))
            except Exception as e:
                logger.error("处理文献失败 [%s]: %s", article.article_id, e)
                self.stats.total_articles += 1
                self.stats.empty_text_count += 1
                article.tokens = []
                results.append(article)

            # 每 100 篇或最后一篇输出进度
            if show_progress and (i % 100 == 0 or i == total - 1):
                logger.info("预处理进度: %d/%d (%.1f%%)", i + 1, total,
                            (i + 1) / total * 100)

        logger.info("预处理完成，统计:\n%s", self.stats.report())
        return results

    # ---------- 工具方法 ----------

    def extract_keywords(self, article: Article, top_n: int = 10) -> List[Tuple[str, int]]:
        """基于 TF 提取文献关键词（简易版）"""
        from collections import Counter
        if not article.tokens:
            return []
        counter = Counter(article.tokens)
        return counter.most_common(top_n)

    @staticmethod
    def get_tokens_summary(articles: List[Article]) -> dict:
        """获取处理后文献的 token 摘要"""
        if not articles:
            return {"total_articles": 0}
        token_counts = [len(a.tokens) for a in articles]
        return {
            "total_articles": len(articles),
            "total_tokens": sum(token_counts),
            "min_tokens": min(token_counts),
            "max_tokens": max(token_counts),
            "avg_tokens": round(sum(token_counts) / len(token_counts), 1),
            "zero_token_count": sum(1 for c in token_counts if c == 0),
        }
