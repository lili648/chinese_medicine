# -*- coding: utf-8 -*-
"""
数据导入器
类: DataImporter - 实体/文献批量导入
对应需求: FR-06
"""
import hashlib
import time
from typing import List, Dict
from sqlalchemy import text
from ..db.db_session import get_engine
from ..preprocessing.data_loader import Article


class DataImporter:
    """数据导入器"""

    def __init__(self):
        self.engine = get_engine()

    def import_articles(self, articles: List[Article]) -> int:
        """批量 INSERT article 表"""
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
                    batch = []
            if batch:
                count += self._batch_execute(conn, "article", batch)
            conn.commit()
        return count

    def import_entities(self, entities: List[Dict]) -> int:
        """批量 INSERT entity 表"""
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
