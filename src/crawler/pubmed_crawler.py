# -*- coding: utf-8 -*-
"""
PubMed 文献爬虫
基于 NCBI Entrez E-utilities API
无需 API Key 即可使用（限速 3 req/s），提供 API Key 可提到 10 req/s

数据源: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
文档:   https://www.ncbi.nlm.nih.gov/books/NBK25501/

爬取流程:
  1. ESearch: 关键词检索 → 获取 PMID 列表
  2. EFetch:  批量获取文献详情 XML（每次最多 200 条）
  3. 解析 XML → 提取 title/abstract/authors/journal/pub_year
  4. 导出为 CSV / JSON（兼容项目 DataLoader 格式）
"""
import csv
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from .base import BaseCrawler

logger = logging.getLogger(__name__)

# PubMed E-utilities 端点
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# EFetch 单次最大 PMID 数量
MAX_FETCH_SIZE = 200

# 默认检索最大文献数
DEFAULT_MAX_RESULTS = 500

# 预设检索关键词（中医/中西医结合常用检索策略）
PRESET_QUERIES: Dict[str, str] = {
    # ---- 疾病方向 ----
    "diabetes_tcm": (
        '("diabetes mellitus"[MeSH Terms] OR "diabetes"[Title/Abstract]) '
        'AND ("traditional chinese medicine"[MeSH Terms] OR '
        '"traditional chinese medicine"[Title/Abstract] OR '
        '"chinese herbal"[Title/Abstract] OR "acupuncture"[Title/Abstract])'
    ),
    "hypertension_tcm": (
        '("hypertension"[MeSH Terms] OR "hypertension"[Title/Abstract]) '
        'AND ("traditional chinese medicine"[MeSH Terms] OR '
        '"chinese medicine"[Title/Abstract] OR "chinese herbal"[Title/Abstract])'
    ),
    "chd_tcm": (
        '("coronary heart disease"[Title/Abstract] OR '
        '"coronary artery disease"[MeSH Terms]) '
        'AND ("traditional chinese medicine"[Title/Abstract] OR '
        '"chinese herbal"[Title/Abstract] OR "salvia"[Title/Abstract])'
    ),
    "cancer_tcm": (
        '("neoplasms"[MeSH Terms] OR "cancer"[Title/Abstract]) '
        'AND ("traditional chinese medicine"[Title/Abstract] OR '
        '"chinese herbal medicine"[Title/Abstract])'
    ),
    "stroke_tcm": (
        '("stroke"[MeSH Terms] OR "stroke"[Title/Abstract]) '
        'AND ("traditional chinese medicine"[Title/Abstract] OR '
        '"acupuncture"[Title/Abstract])'
    ),

    # ---- 药物方向 ----
    "metformin": (
        '"metformin"[Title/Abstract] AND '
        '("diabetes"[Title/Abstract] OR "efficacy"[Title/Abstract])'
    ),
    "aspirin_cvd": (
        '"aspirin"[Title/Abstract] AND '
        '("cardiovascular"[Title/Abstract] OR "coronary"[Title/Abstract])'
    ),
    "insulin": (
        '"insulin therapy"[Title/Abstract] AND '
        '("diabetes"[Title/Abstract] OR "glycemic control"[Title/Abstract])'
    ),

    # ---- 中文医学文献（PubMed 收录的中文期刊） ----
    "chinese_medicine_zh": (
        '("zhongguo zhong xi yi jie he za zhi"[Journal] OR '
        '"zhongguo zhong yao za zhi"[Journal] OR '
        '"zhong xi yi jie he xue bao"[Journal] OR '
        '"journal of traditional chinese medicine"[Journal])'
    ),

    # ---- 网络药理学 ----
    "network_pharmacology_tcm": (
        '("network pharmacology"[Title/Abstract]) '
        'AND ("traditional chinese medicine"[Title/Abstract] OR '
        '"chinese herbal"[Title/Abstract])'
    ),

    # ---- COVID相关中医 ----
    "covid_tcm": (
        '("COVID-19"[Title/Abstract] OR "SARS-CoV-2"[Title/Abstract]) '
        'AND ("traditional chinese medicine"[Title/Abstract] OR '
        '"chinese herbal"[Title/Abstract])'
    ),
}


class PubMedCrawler(BaseCrawler):
    """PubMed 文献爬虫

    用法示例:
        crawler = PubMedCrawler()
        articles = crawler.search("diabetes AND traditional chinese medicine",
                                   max_results=200)
        crawler.save_csv(articles, "data/pubmed/diabetes_tcm.csv")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        email: str = "researcher@example.com",
        tool: str = "mlm-kg-crawler",
    ):
        """
        Args:
            api_key: NCBI API Key（可选，提供后限速提到 10 req/s）
            email:   联系邮箱（NCBI 要求，限速时会发通知）
            tool:    工具名称标识
        """
        rate = 10.0 if api_key else 3.0
        super().__init__(requests_per_sec=rate, max_retries=4,
                         user_agent=f"{tool}/1.0 ({email})")
        self.api_key = api_key
        self.email = email
        self.tool = tool

    # ========== 公开接口 ==========

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
    ) -> List[dict]:
        """
        检索 PubMed 并返回文献列表（字典格式，兼容 Article 转换）

        Args:
            query:       PubMed 检索式（支持 MeSH / 布尔逻辑）
            max_results: 最多返回文献数
            year_start:  起始年份（可选）
            year_end:    截止年份（可选）

        Returns:
            [{"article_id":..., "pmid":..., "title":..., "abstract":...,
              "authors":..., "journal":..., "pub_year":..., "language":"en"}, ...]
        """
        # 1. 构建检索式
        full_query = self._build_query(query, year_start, year_end)

        # 2. ESearch → 获取 PMID 列表
        pmids = self._search_pmids(full_query, max_results)
        if not pmids:
            logger.warning("未检索到任何文献: %s", query)
            return []

        logger.info("检索到 %d 篇文献，开始抓取详情...", len(pmids))

        # 3. EFetch → 批量获取详情
        articles = self._fetch_articles(pmids)
        logger.info("成功抓取 %d 篇文献详情", len(articles))
        return articles

    def search_by_preset(self, preset_name: str, **kwargs) -> List[dict]:
        """使用预设检索式检索"""
        if preset_name not in PRESET_QUERIES:
            available = ", ".join(PRESET_QUERIES.keys())
            raise ValueError(f"未知的预设检索式 '{preset_name}'，可用: {available}")
        return self.search(PRESET_QUERIES[preset_name], **kwargs)

    def search_all_presets(
        self,
        max_results: int = 200,
        deduplicate: bool = True,
    ) -> List[dict]:
        """
        遍历所有预设检索式，合并结果

        Args:
            max_results: 每个预设检索的最多结果数
            deduplicate: 是否按 PMID 去重

        Returns:
            合并后的文献列表
        """
        seen_pmids = set()
        all_articles = []

        for name, query in PRESET_QUERIES.items():
            logger.info("检索预设 [%s]: %s", name, query)
            articles = self.search(query, max_results=max_results)

            if deduplicate:
                new_articles = []
                for a in articles:
                    pmid = a.get("pmid", "")
                    if pmid and pmid not in seen_pmids:
                        seen_pmids.add(pmid)
                        new_articles.append(a)
                    elif not pmid:
                        new_articles.append(a)  # 无 PMID 的也保留
                logger.info("  [%s] 新增 %d 篇（去重后）", name, len(new_articles))
                all_articles.extend(new_articles)
            else:
                all_articles.extend(articles)

        logger.info("共获取 %d 篇文献（去重后）", len(all_articles))
        return all_articles

    # ========== 保存 ==========

    def save_csv(self, articles: List[dict], file_path: str) -> str:
        """
        保存为 CSV 文件（兼容 DataLoader 格式）

        CSV 列: article_id, pmid, title, abstract, authors,
                journal, pub_year, language, source_file
        """
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)

        fieldnames = [
            "article_id", "pmid", "title", "abstract",
            "authors", "journal", "pub_year", "language", "source_file",
        ]

        source_name = os.path.basename(file_path)
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for a in articles:
                row = {
                    "article_id": a.get("article_id", a.get("pmid", "")),
                    "pmid": a.get("pmid", ""),
                    "title": a.get("title", ""),
                    "abstract": a.get("abstract", ""),
                    "authors": a.get("authors", ""),
                    "journal": a.get("journal", ""),
                    "pub_year": a.get("pub_year", ""),
                    "language": a.get("language", "en"),
                    "source_file": source_name,
                }
                writer.writerow(row)

        logger.info("已保存 %d 篇文献到 %s", len(articles), file_path)
        return file_path

    def save_json(self, articles: List[dict], file_path: str) -> str:
        """保存为 JSON 文件"""
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=2)
        logger.info("已保存 %d 篇文献到 %s", len(articles), file_path)
        return file_path

    # ========== 内部实现 ==========

    def _search_pmids(self, query: str, max_results: int) -> List[str]:
        """
        ESearch: 关键词检索获取 PMID 列表

        支持分页：每次最多返回 100,000 条，使用 retstart + retmax 翻页
        """
        all_pmids = []
        retmax = min(10000, max_results)  # NCBI 建议单次不超过 10000
        retstart = 0

        while len(all_pmids) < max_results:
            params = {
                "db": "pubmed",
                "term": query,
                "retstart": retstart,
                "retmax": retmax,
                "sort": "relevance",
                "retmode": "json",
                "tool": self.tool,
                "email": self.email,
            }
            if self.api_key:
                params["api_key"] = self.api_key

            resp = self.request_with_retry(ESEARCH_URL, params=params)
            if resp is None:
                break

            data = resp.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                break

            all_pmids.extend(id_list)

            total_count = int(data.get("esearchresult", {}).get("count", 0))
            retstart += retmax
            if retstart >= total_count or retstart >= max_results:
                break

        return all_pmids[:max_results]

    def _fetch_articles(self, pmids: List[str]) -> List[dict]:
        """
        EFetch: 批量获取文献详情（XML），解析为字典

        每次请求最多 MAX_FETCH_SIZE 条 PMID
        """
        articles = []
        total = len(pmids)

        for batch_start in range(0, total, MAX_FETCH_SIZE):
            batch = pmids[batch_start:batch_start + MAX_FETCH_SIZE]
            batch_num = batch_start // MAX_FETCH_SIZE + 1
            total_batches = (total - 1) // MAX_FETCH_SIZE + 1

            logger.info("  EFetch 批次 %d/%d (%d 条 PMID)",
                        batch_num, total_batches, len(batch))

            params = {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
                "tool": self.tool,
                "email": self.email,
            }
            if self.api_key:
                params["api_key"] = self.api_key

            resp = self.request_with_retry(EFETCH_URL, params=params)
            if resp is None:
                logger.warning("批次 %d 请求失败，跳过", batch_num)
                continue

            try:
                batch_articles = self._parse_xml(resp.text, batch)
                articles.extend(batch_articles)
                logger.info("  解析得到 %d 篇文献", len(batch_articles))
            except ET.ParseError as e:
                logger.error("批次 %d XML 解析失败: %s", batch_num, e)
                continue

        return articles

    def _parse_xml(self, xml_text: str, pmids: List[str]) -> List[dict]:
        """解析 PubMed EFetch 返回的 XML，提取文献元数据"""
        root = ET.fromstring(xml_text)
        articles = []

        for article_elem in root.findall(".//PubmedArticle"):
            try:
                article = self._parse_single_article(article_elem)
                if article["title"]:
                    articles.append(article)
                else:
                    self.stats.skipped += 1
            except Exception as e:
                self.stats.skipped += 1
                logger.debug("解析单篇文献失败: %s", e)

        return articles

    def _parse_single_article(self, elem: ET.Element) -> dict:
        """解析单篇 PubMedArticle XML 元素"""
        # PMID
        pmid_elem = elem.find(".//PMID")
        pmid = pmid_elem.text if pmid_elem is not None else ""

        # Title
        title = self._extract_title(elem)

        # Abstract
        abstract = self._extract_abstract(elem)

        # Authors
        authors = self._extract_authors(elem)

        # Journal
        journal = self._extract_journal(elem)

        # Pub Year
        pub_year = self._extract_pub_year(elem)

        # Language
        lang = self._extract_language(elem)

        return {
            "article_id": f"PMID{pmid}",
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "authors": authors,
            "journal": journal,
            "pub_year": pub_year,
            "language": lang,
        }

    # ---- XML 字段提取 ----

    @staticmethod
    def _extract_title(elem: ET.Element) -> str:
        title_elem = elem.find(".//ArticleTitle")
        if title_elem is None or title_elem.text is None:
            # 尝试 BookTitle（部分文献是书籍章节）
            title_elem = elem.find(".//BookTitle")
        text = title_elem.text if title_elem is not None else ""
        return (text or "").strip()

    @staticmethod
    def _extract_abstract(elem: ET.Element) -> str:
        """提取摘要，合并多个 AbstractText 段落"""
        parts = []
        for at in elem.findall(".//AbstractText"):
            label = at.get("Label", "")
            text = (at.text or "").strip()
            # 保留结构化摘要标签
            if label and text:
                parts.append(f"[{label}] {text}")
            elif text:
                parts.append(text)
            # 处理嵌套标签（如 <i>、<b>）
            for child in at:
                if child.tail:
                    parts[-1] = parts[-1] + child.tail.strip()
        return " ".join(parts)

    @staticmethod
    def _extract_authors(elem: ET.Element) -> str:
        """提取作者列表，格式: LastName FN; LastName FN"""
        authors = []
        for author in elem.findall(".//Author"):
            last = author.findtext("LastName", "")
            fore = author.findtext("ForeName", "")
            initials = author.findtext("Initials", "")
            if last:
                name = last
                if fore:
                    name += f" {fore}"
                elif initials:
                    name += f" {initials}"
                authors.append(name)
        return "; ".join(authors)

    @staticmethod
    def _extract_journal(elem: ET.Element) -> str:
        """提取期刊名"""
        # 优先取 ISO Abbreviation
        iso = elem.findtext(".//ISOAbbreviation", "")
        if iso:
            return iso.strip()
        title = elem.findtext(".//Journal/Title", "")
        return (title or "").strip()

    @staticmethod
    def _extract_pub_year(elem: ET.Element) -> Optional[int]:
        """提取发表年份"""
        year_elem = elem.find(".//PubDate/Year")
        if year_elem is None:
            year_elem = elem.find(".//ArticleDate/Year")
        if year_elem is not None and year_elem.text:
            try:
                year = int(year_elem.text)
                if 1800 <= year <= 2100:
                    return year
            except ValueError:
                pass
        # 尝试从 MedlineDate 提取（如 "2020 Jan-Feb"）
        medline = elem.findtext(".//PubDate/MedlineDate", "")
        if medline:
            match = re.search(r"(\d{4})", medline)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def _extract_language(elem: ET.Element) -> str:
        """提取语种"""
        lang_elem = elem.find(".//Language")
        if lang_elem is not None and lang_elem.text:
            lang = lang_elem.text.strip().lower()
            if lang in ("chi", "zh", "chinese", "中文"):
                return "zh"
            return "en"
        return "en"

    # ---- 检索式构建 ----

    @staticmethod
    def _build_query(
        base_query: str,
        year_start: Optional[int] = None,
        year_end: Optional[int] = None,
    ) -> str:
        """拼装带年份筛选的完整检索式"""
        parts = [f"({base_query})"]
        if year_start:
            parts.append(f'("{year_start}"[Date - Publication] : '
                         f'"{year_end or 3000}"[Date - Publication])')
        return " AND ".join(parts)

    # ---- 预检索式中文文献 ----

    def search_chinese_literature(
        self,
        keywords: str = "中医药",
        max_results: int = 300,
    ) -> List[dict]:
        """
        检索 PubMed 中收录的中文医学文献

        PubMed 收录了部分中国医学期刊的英文摘要，
        也可通过 Language 筛选中文文献。
        """
        query = (
            f'("{keywords}"[Title/Abstract]) AND '
            '(Chinese[Language] OR '
            '"zhongguo"[Journal] OR "zhonghua"[Journal] OR '
            '"journal of traditional chinese medicine"[Journal])'
        )
        return self.search(query, max_results=max_results)


# ========== 便捷函数 ==========

def quick_search(
    query: str = "traditional chinese medicine",
    max_results: int = 100,
    output: Optional[str] = None,
    api_key: Optional[str] = None,
) -> List[dict]:
    """
    快速检索并保存。

    Args:
        query:       PubMed 检索式
        max_results: 最大结果数
        output:      输出 CSV 路径（可选）
        api_key:     NCBI API Key（可选）

    Returns:
        文献列表

    Example:
        >>> articles = quick_search(
        ...     "diabetes AND traditional chinese medicine",
        ...     max_results=50,
        ...     output="data/pubmed/diabetes_tcm.csv",
        ... )
    """
    crawler = PubMedCrawler(api_key=api_key)
    articles = crawler.search(query, max_results=max_results)

    if output and articles:
        crawler.save_csv(articles, output)
        print(crawler.stats.report())

    return articles
