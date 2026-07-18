# -*- coding: utf-8 -*-
"""
文献数据加载器
数据类: Article
Loader: DataLoader - 从 CSV/JSON 加载文献
对应需求: FR-01
"""
from dataclasses import dataclass, field
from typing import List, Optional
import csv
import json
import os


@dataclass
class Article:
    """文献数据类"""
    article_id: str
    pmid: Optional[str]
    title: str
    abstract: Optional[str]
    authors: Optional[str]
    journal: Optional[str]
    pub_year: Optional[int]
    language: str          # "en" or "zh"
    source_file: str
    tokens: List[str] = field(default_factory=list)


class DataLoader:
    """文献数据加载器"""

    @staticmethod
    def load_csv(file_path: str) -> List[Article]:
        """从 CSV 加载文献"""
        articles = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                articles.append(DataLoader._parse_row(row))
        return articles

    @staticmethod
    def load_json(file_path: str) -> List[Article]:
        """从 JSON 加载文献"""
        articles = []
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                articles.append(DataLoader._parse_row(item))
        return articles

    @staticmethod
    def load_directory(dir_path: str) -> List[Article]:
        """批量加载目录下所有文献文件"""
        articles = []
        for filename in os.listdir(dir_path):
            file_path = os.path.join(dir_path, filename)
            if filename.endswith(".csv"):
                articles.extend(DataLoader.load_csv(file_path))
            elif filename.endswith(".json"):
                articles.extend(DataLoader.load_json(file_path))
        return articles

    @staticmethod
    def _parse_row(row: dict) -> Article:
        """单行数据解析"""
        article_id = row.get("article_id", row.get("id", ""))
        article = Article(
            article_id=article_id,
            pmid=row.get("pmid"),
            title=row.get("title", ""),
            abstract=row.get("abstract"),
            authors=row.get("authors"),
            journal=row.get("journal"),
            pub_year=int(row["pub_year"]) if row.get("pub_year") else None,
            language=row.get("language", "zh"),
            source_file=os.path.basename(row.get("source_file", "")),
        )
        return DataLoader._handle_missing(article)

    @staticmethod
    def _handle_missing(article: Article) -> Article:
        """缺失值处理，标注空字段"""
        return article
