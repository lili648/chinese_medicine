# -*- coding: utf-8 -*-
"""
数据采集入口脚本
整合：种子词典扩充 + PubMed 文献爬取

用法:
    python src/crawler/run_collection.py                    # 全量采集
    python src/crawler/run_collection.py --max 100          # 每种检索最多100篇
    python src/crawler/run_collection.py --dicts-only       # 仅扩充词典
    python src/crawler/run_collection.py --pubmed-only      # 仅爬PubMed
    python src/crawler/run_collection.py --preset diabetes_tcm,hypertension_tcm  # 指定预设检索
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime
from typing import List, Optional

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from src.crawler.dict_expander import DictExpander
from src.crawler.pubmed_crawler import PubMedCrawler, PRESET_QUERIES

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("collection")

# 数据输出目录
DATA_DIR = os.path.join(PROJECT_ROOT, "data", "pubmed")
DICT_DIR = os.path.join(PROJECT_ROOT, "dicts")


def step_expand_dicts() -> List[str]:
    """Step 1: 扩充三套种子医学词典"""
    logger.info("=" * 60)
    logger.info("Step 1: 扩充种子医学词典")
    logger.info("=" * 60)

    expander = DictExpander()
    paths = expander.save_all_seed_dicts()

    print(expander.show_stats())
    print()
    return paths


def step_crawl_pubmed(
    max_results: int = 200,
    preset_names: Optional[List[str]] = None,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
) -> List[dict]:
    """Step 2: 从 PubMed 爬取中医相关文献"""
    logger.info("=" * 60)
    logger.info("Step 2: PubMed 文献爬取")
    logger.info("=" * 60)

    os.makedirs(DATA_DIR, exist_ok=True)

    crawler = PubMedCrawler(email="research@example.com")

    if preset_names is None:
        preset_names = list(PRESET_QUERIES.keys())

    # 单独保存每个预设检索的结果
    all_articles = []
    seen_pmids = set()

    for i, name in enumerate(preset_names, 1):
        query = PRESET_QUERIES.get(name)
        if not query:
            logger.warning("跳过未知预设: %s", name)
            continue

        logger.info("--- 检索 %d/%d: [%s] ---", i, len(preset_names), name)
        logger.info("检索式: %s", query)

        try:
            articles = crawler.search(
                query,
                max_results=max_results,
                year_start=year_start,
                year_end=year_end,
            )
        except Exception as e:
            logger.error("检索 [%s] 失败: %s", name, e)
            continue

        if not articles:
            logger.warning("  [%s] 未获取到文献", name)
            continue

        # 去重并保存单文件
        new_articles = []
        for a in articles:
            pmid = a.get("pmid", "")
            if pmid and pmid not in seen_pmids:
                seen_pmids.add(pmid)
                new_articles.append(a)
            elif not pmid:
                new_articles.append(a)

        # 保存为独立文件
        fname = f"{name}_{datetime.now().strftime('%Y%m%d')}.csv"
        filepath = os.path.join(DATA_DIR, fname)
        crawler.save_csv(new_articles, filepath)
        logger.info("  -> 保存 %d 篇到 %s", len(new_articles), filepath)

        all_articles.extend(new_articles)

    # 保存合并后的全量文件
    if len(all_articles) > 1:
        merged_path = os.path.join(
            DATA_DIR,
            f"pubmed_all_{datetime.now().strftime('%Y%m%d')}.csv"
        )
        crawler.save_csv(all_articles, merged_path)
        logger.info("全量合并文件 -> %s", merged_path)

    logger.info("PubMed 采集完成: 共 %d 篇（去重后）", len(all_articles))
    return all_articles


def step_crawl_chinese(
    max_results: int = 200,
    keywords: Optional[List[str]] = None,
) -> List[dict]:
    """Step 3: 爬取 PubMed 中收录的中文医学文献"""
    logger.info("=" * 60)
    logger.info("Step 3: 中文医学文献爬取")
    logger.info("=" * 60)

    os.makedirs(DATA_DIR, exist_ok=True)

    crawler = PubMedCrawler(email="research@example.com")

    if keywords is None:
        keywords = [
            "中医药", "中西医结合", "针灸", "中药",
            "network pharmacology",  # 网络药理学（中国学者发表主力）
        ]

    all_articles = []
    seen_pmids = set()

    for kw in keywords:
        logger.info("--- 检索中文文献: [%s] ---", kw)
        try:
            articles = crawler.search_chinese_literature(
                keywords=kw,
                max_results=max(max_results // len(keywords), 50),
            )
        except Exception as e:
            logger.error("检索 [%s] 失败: %s", kw, e)
            continue

        new_articles = []
        for a in articles:
            pmid = a.get("pmid", "")
            if pmid and pmid not in seen_pmids:
                seen_pmids.add(pmid)
                new_articles.append(a)
            elif not pmid:
                new_articles.append(a)

        fname = f"chinese_{kw}_{datetime.now().strftime('%Y%m%d')}.csv"
        filepath = os.path.join(DATA_DIR, fname)
        crawler.save_csv(new_articles, filepath)
        logger.info("  -> 保存 %d 篇到 %s", len(new_articles), filepath)

        all_articles.extend(new_articles)

    # 合并保存
    if len(all_articles) > 1:
        merged_path = os.path.join(
            DATA_DIR,
            f"chinese_all_{datetime.now().strftime('%Y%m%d')}.csv"
        )
        crawler.save_csv(all_articles, merged_path)
        logger.info("中文文献合并文件 -> %s", merged_path)

    logger.info("中文文献采集完成: 共 %d 篇（去重后）", len(all_articles))
    return all_articles


def print_summary(
    collected_files: List[str],
    total_articles: int,
    elapsed: float,
) -> None:
    """打印最终采集汇总"""
    print()
    print("=" * 60)
    print("     数据采集完成汇总")
    print("=" * 60)
    print(f"  采集时间:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  总耗时:       {elapsed:.1f}s")
    print(f"  采集文献数:   {total_articles} 篇")
    print(f"  输出目录:     {DATA_DIR}")
    print()
    print("  生成文件:")
    for f in collected_files:
        if os.path.exists(f):
            size_kb = os.path.getsize(f) / 1024
            print(f"    - {os.path.basename(f)} ({size_kb:.1f} KB)")
    print()
    print("  词典文件 (dicts/):")
    for dt in ["disease", "drug", "symptom"]:
        path = os.path.join(DICT_DIR, f"{dt}_dict.txt")
        if os.path.exists(path):
            count = sum(1 for _ in open(path, encoding="utf-8")) - 2  # 减掉注释行
            print(f"    - {dt}_dict.txt ({max(count, 0)} 个实体)")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="中医文献知识图谱 — 数据采集脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run_collection.py                              # 全量采集
  python run_collection.py --max 100                    # 每种检索最多100篇
  python run_collection.py --dicts-only                 # 仅扩充词典
  python run_collection.py --pubmed-only                # 仅爬PubMed文献
  python run_collection.py --chinese-only               # 仅爬中文文献
  python run_collection.py --preset diabetes_tcm        # 指定预设检索
  python run_collection.py --year 2018 2024             # 限定年份范围
        """,
    )
    parser.add_argument(
        "--max", type=int, default=200,
        help="每种检索最大文献数 (default: 200)",
    )
    parser.add_argument(
        "--year", nargs=2, type=int, metavar=("START", "END"),
        help="限定发表年份范围，例如 --year 2018 2024",
    )
    parser.add_argument(
        "--preset", type=str,
        help="指定预设检索名，逗号分隔，例如 'diabetes_tcm,hypertension_tcm'",
    )
    parser.add_argument(
        "--dicts-only", action="store_true",
        help="仅扩充词典，不爬取文献",
    )
    parser.add_argument(
        "--pubmed-only", action="store_true",
        help="仅爬取英文文献，不扩充词典和中文文献",
    )
    parser.add_argument(
        "--chinese-only", action="store_true",
        help="仅爬取中文文献",
    )
    parser.add_argument(
        "--skip-dicts", action="store_true",
        help="跳过词典扩充",
    )
    parser.add_argument(
        "--skip-pubmed", action="store_true",
        help="跳过英文文献爬取",
    )
    parser.add_argument(
        "--skip-chinese", action="store_true",
        help="跳过中文文献爬取",
    )
    args = parser.parse_args()

    start_time = time.monotonic()
    collected_files = []
    total_articles = 0

    # Parse preset names
    preset_names = None
    if args.preset:
        preset_names = [n.strip() for n in args.preset.split(",")]

    # Parse year range
    year_start, year_end = None, None
    if args.year:
        year_start, year_end = args.year

    # ---- Step 1: 词典扩充 ----
    if not args.skip_dicts and not args.pubmed_only and not args.chinese_only:
        try:
            paths = step_expand_dicts()
            collected_files.extend(paths)
        except Exception as e:
            logger.error("词典扩充失败: %s", e)

    if args.dicts_only:
        elapsed = time.monotonic() - start_time
        print(f"\n词典扩充完成，耗时 {elapsed:.1f}s")
        return

    # ---- Step 2: PubMed 英文文献 ----
    if not args.skip_pubmed and not args.chinese_only:
        try:
            articles = step_crawl_pubmed(
                max_results=args.max,
                preset_names=preset_names,
                year_start=year_start,
                year_end=year_end,
            )
            total_articles += len(articles)
            # 收集生成的文件
            for f in os.listdir(DATA_DIR):
                filepath = os.path.join(DATA_DIR, f)
                if f.endswith(".csv") and os.path.isfile(filepath):
                    if filepath not in collected_files:
                        collected_files.append(filepath)
        except Exception as e:
            logger.error("PubMed 爬取失败: %s", e)

    # ---- Step 3: 中文文献 ----
    if not args.skip_chinese and not args.pubmed_only:
        try:
            articles = step_crawl_chinese(max_results=args.max)
            total_articles += len(articles)
            for f in os.listdir(DATA_DIR):
                filepath = os.path.join(DATA_DIR, f)
                if f.endswith(".csv") and os.path.isfile(filepath):
                    if filepath not in collected_files:
                        collected_files.append(filepath)
        except Exception as e:
            logger.error("中文文献爬取失败: %s", e)

    elapsed = time.monotonic() - start_time
    print_summary(collected_files, total_articles, elapsed)


if __name__ == "__main__":
    main()
