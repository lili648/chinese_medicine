# -*- coding: utf-8 -*-
"""
文本预处理器
类: Preprocessor - 文本清洗 + jieba分词
类: StopWords - 停用词管理器
对应需求: FR-02
"""
import re
from typing import List
import jieba

from .data_loader import Article


class StopWords:
    """停用词管理器"""

    def __init__(self):
        self._stopwords: set = set()

    def load(self, file_path: str) -> None:
        """加载停用词表"""
        with open(file_path, "r", encoding="utf-8") as f:
            self._stopwords = {line.strip() for line in f if line.strip()}

    def is_stopword(self, word: str) -> bool:
        """判断是否为停用词"""
        return word in self._stopwords

    def remove(self, text_list: List[str]) -> List[str]:
        """从词列表中移除停用词"""
        return [w for w in text_list if not self.is_stopword(w)]


class Preprocessor:
    """文本预处理器"""

    def __init__(self, stopwords: StopWords = None):
        self.stopwords = stopwords or StopWords()

    def clean_text(self, text: str) -> str:
        """文本清洗：去HTML/特殊字符/数字"""
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", "", text)       # 去 HTML 标签
        text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z]", " ", text)  # 保留中英文
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def segment(self, text: str, lang: str = "zh") -> List[str]:
        """分词：中文用jieba，英文按空格+大小写归一化"""
        if lang == "en":
            return [w.lower() for w in text.split() if len(w) > 1]
        else:
            return [w for w in jieba.cut(text) if len(w.strip()) > 1]

    def process_article(self, article: Article) -> Article:
        """处理单篇文献，返回填充了 tokens 的对象"""
        title_clean = self.clean_text(article.title)
        abstract_clean = self.clean_text(article.abstract or "")
        combined = f"{title_clean} {abstract_clean}"
        tokens = self.segment(combined, article.language)
        article.tokens = self.stopwords.remove(tokens)
        return article

    def process_batch(self, articles: List[Article]) -> List[Article]:
        """批量处理文献列表"""
        return [self.process_article(a) for a in articles]
