# -*- coding: utf-8 -*-
"""
数据导入器
类: DataImporter - 实体/文献批量导入
对应需求: FR-06
"""
import hashlib
import logging
import time
from typing import List, Dict, Tuple
from sqlalchemy import text
from ..db.db_session import get_engine
from ..preprocessing.data_loader import Article
from .relation_builder import RelationBuilder

logger = logging.getLogger(__name__)


class DataImporter:
    """数据导入器"""

    def __init__(self):
        self.engine = get_engine()

    def import_articles(self, articles: List[Article]) -> int:
        """批量 INSERT article 表（每批提交，避免中断导致整体回滚）"""
        count = 0
        batch = []
        with self.engine.connect() as conn:
            for a in articles:
                batch.append({
                    "article_id": a.article_id,
                    "pmid": a.pmid,
                    "title": a.title,
                    "abstract": a.abstract,
                    "authors": a.authors,
                    "journal": a.journal,
                    "pub_year": a.pub_year,
                    "language": a.language,
                    "source_file": a.source_file,
                })
                if len(batch) >= 500:
                    count += self._batch_execute(conn, "article", batch)
                    conn.commit()
                    batch = []
            if batch:
                count += self._batch_execute(conn, "article", batch)
                conn.commit()
        return count

    def import_entities(self, entities: List[Dict]) -> int:
        """批量 INSERT entity 表（每批提交，避免中断导致整体回滚）"""
        count = 0
        batch = []
        with self.engine.connect() as conn:
            for ent in entities:
                entity_id = hashlib.md5(ent["entity_name"].encode()).hexdigest()[:32]
                batch.append({
                    "entity_id": entity_id,
                    "name": ent["entity_name"],
                    "entity_type": ent["entity_type"],
                    "source": ent.get("source", ""),
                })
                if len(batch) >= 500:
                    count += self._batch_execute(conn, "entity", batch)
                    conn.commit()
                    batch = []
            if batch:
                count += self._batch_execute(conn, "entity", batch)
                conn.commit()
        return count

    def _batch_execute(self, conn, table: str, data: List[Dict], max_retries: int = 3) -> int:
        """批量执行 INSERT ON DUPLICATE KEY UPDATE"""
        if not data:
            return 0
        columns = list(data[0].keys())
        placeholders = ", ".join([f":{c}" for c in columns])
        col_names = ", ".join(columns)
        sql = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE updated_at=NOW()"
        for attempt in range(max_retries):
            try:
                conn.execute(text(sql), data)
                return len(data)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(0.5)
        return 0

    # ========== 节点批量导入编排 ==========

    def import_nodes(self, articles: List[Article], entities_raw: List[Dict]) -> Tuple[int, int]:
        """图谱节点批量导入（文献节点 + 实体节点）

        负责将 NER 抽取的实体按 (entity_name, entity_type) 去重后，
        连同文献一起写入 MySQL 的 article / entity 表。

        Args:
            articles:     文献列表（Article 对象）
            entities_raw: NER 实体提及列表（每个元素含 entity_name/entity_type 等）

        Returns:
            (导入文献数, 导入唯一实体数)
        """
        # 1) 实体去重并补 source
        unique_entities = self._dedup_entities(entities_raw)

        # 2) 写入文献节点
        article_count = self.import_articles(articles)
        logger.info("文献节点导入完成: %d", article_count)

        # 3) 写入实体节点
        entity_count = self.import_entities(unique_entities)
        logger.info("实体节点导入完成: %d", entity_count)

        return article_count, entity_count

    def _dedup_entities(self, entities_raw: List[Dict]) -> List[Dict]:
        """按 (entity_name, entity_type) 去重，去除空名，并补 source 字段

        注意：entity_id 的生成（md5(entity_name)[:32]）由 import_entities 统一处理，
        此处仅做去重，保证与 graph_engine / query_api 约定的 E:{name} 节点前缀一致。
        """
        seen = set()
        unique = []
        for ent in entities_raw:
            name = (ent.get("entity_name") or "").strip()
            etype = (ent.get("entity_type") or "").strip()
            if not name or not etype:
                continue
            key = (name, etype)
            if key in seen:
                continue
            seen.add(key)
            unique.append({
                "entity_name": name,
                "entity_type": etype,
                "source": ent.get("source") or "ner",
            })
        return unique

    # ========== 关系边批量导入编排 ==========

    def import_relations(self, entities_raw: List[Dict]) -> Dict[str, int]:
        """从 NER 实体提及列表构建并写入关系边（MENTIONS + CO_OCCURS）

        注意：此处需要的是 NER 抽取的原始实体列表（含 article_id），
        而非去重后的实体。每条提及 === 一个 MENTIONS 边。

        Args:
            entities_raw: NER 实体提及列表（每个元素含 entity_name/article_id 等）

        Returns:
            {"mentions": N, "co_occurs": N}
        """
        builder = RelationBuilder()
        result = {}

        mentions_count = builder.build_mentions(entities_raw)
        logger.info("MENTIONS 关系写入完成: %d", mentions_count)
        result["mentions"] = mentions_count

        co_occur_count = builder.build_co_occur(entities_raw, threshold=1)
        logger.info("CO_OCCURS 关系写入完成: %d", co_occur_count)
        result["co_occurs"] = co_occur_count

        return result
