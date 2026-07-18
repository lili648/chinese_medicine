# -*- coding: utf-8 -*-
"""
预处理 + 实体识别 Pipeline（编排器）
流程: 加载文献 → 文本预处理 → 实体识别 → 导出结果
对应需求: FR-03, FR-04, FR-05
"""
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..preprocessing.data_loader import DataLoader, LoadStats, Article
from ..preprocessing.preprocessor import Preprocessor, PreprocessStats
from .entity_dict import EntityDict
from .entity_recognizer import EntityRecognizer, RecognizeStats

logger = logging.getLogger(__name__)


@dataclass
class PipelineStats:
    """Pipeline 综合统计"""
    load: Optional[LoadStats] = None
    preprocess: Optional[PreprocessStats] = None
    recognize: Optional[RecognizeStats] = None
    total_articles: int = 0
    total_entities: int = 0
    unique_entities: int = 0
    elapsed_seconds: float = 0.0
    output_files: List[str] = field(default_factory=list)

    def report(self) -> str:
        lines = [
            "=" * 60,
            "  Pipeline 执行报告",
            "=" * 60,
            f"  总耗时:         {self.elapsed_seconds:.1f}s",
            f"  加载文献数:     {self.total_articles}",
            f"  总实体提及数:   {self.total_entities}",
            f"  唯一实体数:     {self.unique_entities}",
            "=" * 60,
        ]
        if self.load:
            lines.append(f"  数据加载:       {self.load.total_loaded} 篇加载, "
                         f"{self.load.total_skipped} 篇跳过")
        if self.preprocess:
            lines.append(f"  预处理:         {self.preprocess.total_tokens_after} tokens, "
                         f"空文本 {self.preprocess.empty_text_count} 篇")
        if self.recognize:
            lines.append(f"  含实体文章:     {self.recognize.articles_with_entities} 篇")
            for etype in ["Disease", "Drug", "Symptom"]:
                lines.append(f"    {etype:10s}: {self.recognize.entities_by_type.get(etype, 0):5d}")
        if self.output_files:
            lines.append(f"  输出文件:       {len(self.output_files)} 个")
            for f in self.output_files[-5:]:  # 最近5个
                lines.append(f"    - {f}")
        lines.append("=" * 60)
        return "\n".join(lines)


class Pipeline:
    """预处理 + 实体识别 Pipeline

    将数据加载、文本预处理、实体识别集成到一个流程中，
    支持批量处理和结果导出。

    用法:
        pipeline = Pipeline(dict_dir="dicts")
        results = pipeline.run("data/pubmed")
        pipeline.export_entities(results, "output/entities.json")
        pipeline.show_report()
    """

    def __init__(
        self,
        dict_dir: str = "dicts",
        clean_mode: str = "medical",
        max_match_length: int = 12,
        load_stopwords: bool = True,
    ):
        """
        Args:
            dict_dir:         词典目录路径
            clean_mode:       清洗模式 ("strict" / "medical")
            max_match_length: 中文正向最大匹配最长词长度
            load_stopwords:   是否加载停用词表
        """
        self.dict_dir = dict_dir
        self.clean_mode = clean_mode
        self.max_match_length = max_match_length

        # 初始化各组件
        self.entity_dict = EntityDict()
        self.entity_dict.load_dicts(dict_dir)

        self.preprocessor = Preprocessor(mode=clean_mode)
        self.recognizer = EntityRecognizer(
            entity_dict=self.entity_dict,
            max_match_length=max_match_length,
        )
        self.data_loader = DataLoader()
        self.stats = PipelineStats()

    # ========== 运行 Pipeline ==========

    def run(
        self,
        input_path: str,
        file_pattern: str = "*.csv",
        progress_every: int = 100,
        export_path: Optional[str] = None,
    ) -> List[Dict]:
        """运行完整 Pipeline: 加载 → 预处理 → 识别 → [(可选)导出]

        Args:
            input_path:     输入文件/目录路径（支持 .csv .json .txt）
            file_pattern:   文件匹配模式（目录模式下生效）
            progress_every: 进度日志间隔
            export_path:    可选，自动导出 entities.json 到此路径

        Returns:
            实体识别结果列表
        """
        start_time = time.monotonic()
        logger.info("Pipeline 启动: %s", input_path)

        # ---- Step 1: 数据加载 ----
        logger.info("--- Step 1: 数据加载 ---")
        articles = self.load_data(input_path, file_pattern)
        self.stats.total_articles = len(articles)
        if not articles:
            logger.warning("未加载到任何文献，Pipeline 终止")
            return []

        # ---- Step 2: 文本预处理 ----
        logger.info("--- Step 2: 文本预处理 ---")
        articles = self.preprocess(articles, show_progress=(progress_every <= 100))

        # ---- Step 3: 实体识别 ----
        logger.info("--- Step 3: 实体识别 ---")
        entities = self.recognize(articles, progress_every)
        self.stats.total_entities = len(entities)
        self.stats.unique_entities = len(set(
            (e["entity_name"], e["entity_type"]) for e in entities
        ))

        # ---- Step 4: 导出（可选）----
        if export_path:
            self.export_entities(entities, export_path)
            self.export_stats(export_path.replace(".json", "_stats.json"))

        self.stats.elapsed_seconds = time.monotonic() - start_time
        logger.info("Pipeline 完成，耗时 %.1fs", self.stats.elapsed_seconds)
        return entities

    def run_with_summary(
        self,
        input_path: str,
        file_pattern: str = "*.csv",
        progress_every: int = 100,
        export_dir: Optional[str] = None,
    ) -> Tuple[List[Dict], List[Dict]]:
        """运行 Pipeline 并返回 (实体列表, Top-N实体摘要)

        Args:
            input_path:   输入路径
            file_pattern: 文件匹配模式
            progress_every: 进度日志间隔
            export_dir:   导出目录（可选，自动生成 entities.json + top_entities.json）

        Returns:
            (entities, top_entities)
        """
        export_path = None
        if export_dir:
            os.makedirs(export_dir, exist_ok=True)
            export_path = os.path.join(export_dir, "entities.json")

        entities = self.run(input_path, file_pattern, progress_every, export_path)

        top_entities = self.recognizer.get_top_entities(entities, top_n=50)

        if export_dir:
            top_path = os.path.join(export_dir, "top_entities.json")
            with open(top_path, "w", encoding="utf-8") as f:
                json.dump(top_entities, f, ensure_ascii=False, indent=2)
            logger.info("Top 实体已导出到 %s", top_path)

        return entities, top_entities

    # ========== Pipeline 各步骤（可独立调用）==========

    def load_data(self, input_path: str, file_pattern: str = "*.csv") -> List[Article]:
        """Step 1: 加载文献数据"""
        if os.path.isfile(input_path):
            if input_path.endswith(".json"):
                articles = self.data_loader.load_json(input_path)
            elif input_path.endswith(".csv"):
                articles = self.data_loader.load_csv(input_path)
            elif input_path.endswith(".txt"):
                articles = self.data_loader.load_txt(input_path)
            else:
                articles = self.data_loader.load_directory(input_path, file_pattern)
        else:
            # DataLoader.load_directory 仅接收 dir_path（内部按扩展名过滤，
            # file_pattern 参数无效），故不传第二参数
            articles = self.data_loader.load_directory(input_path)

        self.stats.load = self.data_loader.stats
        logger.info("加载完成: %d 篇文献", len(articles))
        return articles

    def preprocess(
        self,
        articles: List[Article],
        show_progress: bool = True,
    ) -> List[Article]:
        """Step 2: 文本预处理（清洗 + 分词 + 去停用词）"""
        self.preprocessor.process_batch(articles, show_progress=show_progress)
        self.stats.preprocess = self.preprocessor.stats
        # 过滤掉 token 为空的文章
        valid = [a for a in articles if a.tokens]
        skipped = len(articles) - len(valid)
        if skipped:
            logger.info("预处理后跳过 %d 篇空 token 文献", skipped)
        return valid

    def recognize(
        self,
        articles: List[Article],
        progress_every: int = 100,
    ) -> List[Dict]:
        """Step 3: 实体识别"""
        entities = self.recognizer.recognize_batch(articles, progress_every)
        self.stats.recognize = self.recognizer.stats
        return entities

    # ========== 导出 ==========

    def export_entities(self, entities: List[Dict], output_path: str) -> str:
        """导出实体识别结果为 JSON"""
        path = self.recognizer.export_json(entities, output_path)
        self.stats.output_files.append(path)
        return path

    def export_stats(self, output_path: str) -> str:
        """导出 Pipeline 统计信息为 JSON"""
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        report = {
            "total_articles": self.stats.total_articles,
            "total_entities": self.stats.total_entities,
            "unique_entities": self.stats.unique_entities,
            "elapsed_seconds": self.stats.elapsed_seconds,
            "dict_stats": self.entity_dict.get_stats(),
            "recognize_stats": {
                "articles_with_entities": self.stats.recognize.articles_with_entities
                if self.stats.recognize else 0,
                "entities_by_type": dict(
                    self.stats.recognize.entities_by_type
                ) if self.stats.recognize else {},
                "entities_by_method": dict(
                    self.stats.recognize.entities_by_method
                ) if self.stats.recognize else {},
            } if self.stats.recognize else {},
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info("统计报告已导出到 %s", output_path)
        return output_path

    def export_csv_entities(self, entities: List[Dict], output_path: str) -> str:
        """导出实体为 CSV（entity_name, entity_type, article_id, match_method, frequency）"""
        import csv
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        fieldnames = ["entity_name", "entity_type", "article_id",
                      "match_method", "frequency"]
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for e in entities:
                writer.writerow({
                    "entity_name": e.get("entity_name", ""),
                    "entity_type": e.get("entity_type", ""),
                    "article_id": e.get("article_id", ""),
                    "match_method": e.get("match_method", ""),
                    "frequency": e.get("frequency", 1),
                })
        logger.info("实体 CSV 已导出到 %s (%d 条)", output_path, len(entities))
        return output_path

    # ========== 报告 ==========

    def show_report(self) -> str:
        """显示 Pipeline 执行报告"""
        report = self.stats.report()
        print(report)
        return report

    def get_entity_summary(self, entities: List[Dict]) -> Dict:
        """获取实体摘要（按类型分组统计）"""
        from collections import Counter
        summary = {
            "total": len(entities),
            "unique": len(set((e["entity_name"], e["entity_type"]) for e in entities)),
            "by_type": dict(Counter(e["entity_type"] for e in entities)),
        }
        return summary
