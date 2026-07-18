# -*- coding: utf-8 -*-
"""
文献数据加载器
数据类: Article
Loader: DataLoader - 从 CSV/JSON/TXT 加载文献
对应需求: FR-01
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import csv
import json
import logging
import os
import re

logger = logging.getLogger(__name__)


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

    VALID_FIELDS = {
        "article_id", "pmid", "title", "abstract", "authors",
        "journal", "pub_year", "language", "source_file", "id"
    }

    REQUIRED_FIELDS = {"title"}


class LoadStats:
    """数据加载统计信息"""
    def __init__(self):
        self.total_files: int = 0
        self.total_loaded: int = 0
        self.total_skipped: int = 0
        self.total_missing_title: int = 0
        self.total_missing_abstract: int = 0
        self.total_missing_authors: int = 0
        self.total_missing_journal: int = 0
        self.total_missing_pub_year: int = 0
        self.lang_distribution: Dict[str, int] = {}
        self.year_distribution: Dict[int, int] = {}
        self.errors: List[str] = []

    def to_dict(self) -> dict:
        return {
            "total_files": self.total_files,
            "total_loaded": self.total_loaded,
            "total_skipped": self.total_skipped,
            "missing_title": self.total_missing_title,
            "missing_abstract": self.total_missing_abstract,
            "missing_authors": self.total_missing_authors,
            "missing_journal": self.total_missing_journal,
            "missing_pub_year": self.total_missing_pub_year,
            "language_distribution": self.lang_distribution,
            "year_distribution": dict(sorted(self.year_distribution.items())),
            "error_count": len(self.errors),
        }

    def report(self) -> str:
        """生成可读的统计报告"""
        info = self.to_dict()
        lines = [
            "=" * 50,
            "数据加载统计报告",
            "=" * 50,
            f"扫描文件数:       {info['total_files']}",
            f"成功加载记录数:   {info['total_loaded']}",
            f"跳过记录数:       {info['total_skipped']}",
            f"缺失 title:       {info['missing_title']}",
            f"缺失 abstract:    {info['missing_abstract']}",
            f"缺失 authors:     {info['missing_authors']}",
            f"缺失 journal:     {info['missing_journal']}",
            f"缺失 pub_year:    {info['missing_pub_year']}",
            f"语种分布:        {info['language_distribution']}",
            f"加载错误数:       {info['error_count']}",
            "=" * 50,
        ]
        return "\n".join(lines)


class DataLoader:
    """文献数据加载器"""

    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {".csv", ".json", ".txt"}

    def __init__(self):
        self.stats = LoadStats()

    def reset_stats(self) -> None:
        """重置统计信息"""
        self.stats = LoadStats()

    # ---------- 公开加载接口 ----------

    def load_csv(self, file_path: str) -> List[Article]:
        """从 CSV 加载文献"""
        articles = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=2):  # 第1行是表头
                    article = self._parse_row(row, file_path)
                    if article:
                        articles.append(article)
        except UnicodeDecodeError:
            # 尝试 GBK 编码（常见于中文 CSV）
            logger.warning("UTF-8 解码失败，尝试 GBK 编码: %s", file_path)
            try:
                articles = self._load_csv_with_encoding(file_path, "gbk")
            except Exception as e2:
                self.stats.errors.append(f"{file_path}: 编码错误 - {e2}")
        except FileNotFoundError:
            self.stats.errors.append(f"{file_path}: 文件不存在")
        except Exception as e:
            self.stats.errors.append(f"{file_path}: {e}")
            logger.exception("加载文件失败: %s", file_path)
        return articles

    def load_json(self, file_path: str) -> List[Article]:
        """从 JSON 加载文献，支持单个对象或数组"""
        articles = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                self.stats.errors.append(f"{file_path}: JSON 数据格式错误，期待对象或数组")
                return articles
            for item in data:
                article = self._parse_row(item, file_path)
                if article:
                    articles.append(article)
        except json.JSONDecodeError as e:
            self.stats.errors.append(f"{file_path}: JSON 解析错误 - {e}")
        except FileNotFoundError:
            self.stats.errors.append(f"{file_path}: 文件不存在")
        except Exception as e:
            self.stats.errors.append(f"{file_path}: {e}")
            logger.exception("加载文件失败: %s", file_path)
        return articles

    def load_txt(self, file_path: str) -> List[Article]:
        """
        从纯文本文件加载文献，每行一篇文献。
        支持两种格式：
          1. TSV 格式（制表符分隔）：title\tabstract\tpmid\t...
          2. 键值对格式（每行 key: value，空行分隔文献）
        """
        articles = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, "r", encoding="gbk") as f:
                    content = f.read()
            except Exception as e:
                self.stats.errors.append(f"{file_path}: 编码错误 - {e}")
                return articles
        except FileNotFoundError:
            self.stats.errors.append(f"{file_path}: 文件不存在")
            return articles
        except Exception as e:
            self.stats.errors.append(f"{file_path}: {e}")
            return articles

        # 检测格式：检查是否包含 tab 分隔符
        if "\t" in content:
            articles = self._parse_tsv(content, file_path)
        elif ":" in content:
            articles = self._parse_kv(content, file_path)
        else:
            # 纯文本，每行视为一篇文献的标题
            articles = self._parse_plain(content, file_path)

        return articles

    def load_directory(self, dir_path: str) -> List[Article]:
        """批量加载目录下所有支持的文献文件"""
        articles = []
        if not os.path.isdir(dir_path):
            self.stats.errors.append(f"{dir_path}: 目录不存在")
            return articles

        self.stats.total_files = 0
        for filename in sorted(os.listdir(dir_path)):
            file_path = os.path.join(dir_path, filename)
            if not os.path.isfile(file_path):
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext not in self.SUPPORTED_EXTENSIONS:
                continue
            self.stats.total_files += 1
            logger.info("加载文件: %s", file_path)

            if ext == ".csv":
                articles.extend(self.load_csv(file_path))
            elif ext == ".json":
                articles.extend(self.load_json(file_path))
            elif ext == ".txt":
                articles.extend(self.load_txt(file_path))

        return articles

    # ---------- 内部方法 ----------

    def _parse_row(self, row: dict, file_path: str) -> Optional[Article]:
        """单行数据解析，返回 None 表示跳过该行"""
        try:
            # 自动生成 ID（如果缺失）
            article_id = row.get("article_id") or row.get("id") or row.get("pmid") or ""
            if not article_id:
                article_id = f"ARTICLE_{abs(hash(str(row))) % 10**8:08d}"

            title = (row.get("title") or "").strip()
            if not title:
                self.stats.total_skipped += 1
                self.stats.total_missing_title += 1
                logger.warning("跳过无标题记录: %s, id=%s", file_path, article_id)
                return None

            # pub_year 解析
            pub_year = self._parse_pub_year(row.get("pub_year"))

            # 语种推断
            language = self._infer_language(row.get("language"), title)

            article = Article(
                article_id=str(article_id),
                pmid=row.get("pmid") or None,
                title=title,
                abstract=row.get("abstract") or None,
                authors=row.get("authors") or None,
                journal=row.get("journal") or None,
                pub_year=pub_year,
                language=language,
                source_file=os.path.basename(file_path),
            )
            return self._handle_missing(article)

        except Exception as e:
            self.stats.total_skipped += 1
            self.stats.errors.append(f"{file_path}: 行解析错误 - {e}")
            logger.exception("行解析异常: %s", file_path)
            return None

    def _handle_missing(self, article: Article) -> Article:
        """缺失值处理与统计"""
        if not article.abstract:
            self.stats.total_missing_abstract += 1
            article.abstract = None

        if not article.authors:
            self.stats.total_missing_authors += 1
            article.authors = None

        if not article.journal:
            self.stats.total_missing_journal += 1
            article.journal = None

        if article.pub_year is None:
            self.stats.total_missing_pub_year += 1

        # 更新统计
        self.stats.total_loaded += 1
        lang = article.language or "unknown"
        self.stats.lang_distribution[lang] = self.stats.lang_distribution.get(lang, 0) + 1

        if article.pub_year:
            yr = article.pub_year
            self.stats.year_distribution[yr] = self.stats.year_distribution.get(yr, 0) + 1

        return article

    @staticmethod
    def _parse_pub_year(value) -> Optional[int]:
        """安全解析发表年份，支持各种格式"""
        if value is None or value == "":
            return None
        try:
            year = int(float(str(value)))
            if 1800 <= year <= 2100:
                return year
            return None
        except (ValueError, TypeError):
            # 尝试从字符串中提取4位年份
            match = re.search(r"(\d{4})", str(value))
            if match:
                year = int(match.group(1))
                if 1800 <= year <= 2100:
                    return year
            return None

    @staticmethod
    def _infer_language(raw_lang, title: str) -> str:
        """推断/规范化语种"""
        if raw_lang:
            lang = str(raw_lang).lower().strip()
            if lang in ("zh", "cn", "chi", "chinese", "中文"):
                return "zh"
            if lang in ("en", "eng", "english", "英文"):
                return "en"
        # 自动推断：包含至少一个中文字符即视为中文
        if re.search(r"[\u4e00-\u9fa5]", title):
            return "zh"
        return "en"

    @staticmethod
    def _load_csv_with_encoding(file_path: str, encoding: str) -> List[Article]:
        """使用指定编码加载 CSV"""
        articles = []
        loader = DataLoader()
        with open(file_path, "r", encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row in reader:
                article = loader._parse_row(row, file_path)
                if article:
                    articles.append(article)
        return articles

    def _parse_tsv(self, content: str, file_path: str) -> List[Article]:
        """解析 TSV 格式的文本"""
        articles = []
        lines = content.strip().split("\n")
        # 尝试第一行作为表头
        first = lines[0].split("\t")
        has_header = any(h in {"title", "abstract", "pmid", "article_id", "id"}
                          for h in [f.strip().lower() for f in first])

        start_idx = 1 if has_header else 0
        headers = ([h.strip().lower() for h in first] if has_header
                   else ["title", "abstract", "pmid", "journal", "authors", "pub_year", "language"])

        for line in lines[start_idx:]:
            values = line.split("\t")
            row = {}
            for i, val in enumerate(values):
                if i < len(headers):
                    row[headers[i]] = val.strip()
            article = self._parse_row(row, file_path)
            if article:
                articles.append(article)
        return articles

    def _parse_kv(self, content: str, file_path: str) -> List[Article]:
        """解析键值对格式 (key: value, 空行分隔文献)"""
        articles = []
        blocks = re.split(r"\n\s*\n", content.strip())
        for block in blocks:
            row = {}
            for line in block.strip().split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip().lower()
                    value = value.strip()
                    # 映射常见字段名
                    if key in ("title", "标题"):
                        row["title"] = value
                    elif key in ("abstract", "摘要"):
                        row["abstract"] = value
                    elif key in ("pmid", "id", "article_id"):
                        row["pmid"] = value
                    elif key in ("authors", "author", "作者"):
                        row["authors"] = value
                    elif key in ("journal", "期刊", "source"):
                        row["journal"] = value
                    elif key in ("pub_year", "year", "年份", "date"):
                        row["pub_year"] = value
                    elif key in ("language", "lang", "语种"):
                        row["language"] = value
            if row:
                article = self._parse_row(row, file_path)
                if article:
                    articles.append(article)
        return articles

    def _parse_plain(self, content: str, file_path: str) -> List[Article]:
        """解析纯文本（每行一篇标题）"""
        articles = []
        for line in content.strip().split("\n"):
            line = line.strip()
            if line:
                article = self._parse_row({"title": line}, file_path)
                if article:
                    articles.append(article)
        return articles

    # ---------- 工具方法 ----------

    @staticmethod
    def validate_articles(articles: List[Article]) -> Tuple[List[Article], List[str]]:
        """验证文献列表，返回 (有效文献, 警告列表)"""
        valid = []
        warnings = []
        for a in articles:
            a_warnings = []
            if not a.title.strip():
                a_warnings.append(f"文献 {a.article_id}: 标题为空")
                continue
            if a.language not in ("zh", "en"):
                a_warnings.append(f"文献 {a.article_id}: 未知语种 '{a.language}'")
            if a_warnings:
                warnings.extend(a_warnings)
            valid.append(a)
        return valid, warnings

    @staticmethod
    def get_summary(articles: List[Article]) -> dict:
        """获取文献列表的摘要统计"""
        if not articles:
            return {"total": 0}
        langs = {}
        years = {}
        has_abstract = 0
        has_authors = 0
        has_journal = 0
        has_pmid = 0
        for a in articles:
            langs[a.language] = langs.get(a.language, 0) + 1
            if a.pub_year:
                years[a.pub_year] = years.get(a.pub_year, 0) + 1
            if a.abstract:
                has_abstract += 1
            if a.authors:
                has_authors += 1
            if a.journal:
                has_journal += 1
            if a.pmid:
                has_pmid += 1
        return {
            "total": len(articles),
            "language_distribution": langs,
            "year_range": (min(years.keys()), max(years.keys())) if years else None,
            "has_abstract": has_abstract,
            "has_authors": has_authors,
            "has_journal": has_journal,
            "has_pmid": has_pmid,
        }
