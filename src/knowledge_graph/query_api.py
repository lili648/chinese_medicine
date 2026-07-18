# -*- coding: utf-8 -*-
"""
知识图谱查询 API 封装
提供: Top实体查询 / 实体详情 / 最短路径 / 文献关联 / 关键词检索
对应需求: FR-08, FR-09
"""

import logging
from typing import List, Dict, Optional
from sqlalchemy import text
from ..db.db_session import get_engine

logger = logging.getLogger(__name__)


class QueryAPI:
    """知识图谱 MySQL 查询封装

    提供面向 FastAPI 后端的查询方法，所有方法返回可直接 JSON 序列化的 dict/list。

    用法:
        q = QueryAPI()
        top = q.get_top_entities(entity_type="Disease", top_n=20)
        neighbors = q.query_entity("糖尿病")
        path = q.query_shortest_path("丹参", "糖尿病")
        entities = q.query_article_entities("PMID_12345")
        results = q.keyword_search("糖尿病")
    """

    def __init__(self):
        self.engine = get_engine()

    # ==================== 实体查询 ====================

    def get_top_entities(
        self,
        entity_type: Optional[str] = None,
        top_n: int = 20,
    ) -> List[Dict]:
        """按频次统计 Top-N 实体

        Args:
            entity_type:  实体类型过滤 (Disease/Drug/Symptom)，None=全部
            top_n:        返回 Top N 条

        Returns:
            [{entity_id, name, entity_type, mention_count}, ...]
        """
        where_clause = ""
        params = {"top_n": top_n}
        if entity_type:
            where_clause = "WHERE e.entity_type = :entity_type"
            params["entity_type"] = entity_type

        sql = text(f"""
            SELECT e.entity_id, e.name, e.entity_type,
                   COUNT(r.id) AS mention_count
            FROM entity e
            LEFT JOIN relation r
              ON CONCAT('E:', e.name) = r.target_id
             AND r.relation_type = 'MENTIONS'
            {where_clause}
            GROUP BY e.entity_id, e.name, e.entity_type
            ORDER BY mention_count DESC
            LIMIT :top_n
        """)

        with self.engine.connect() as conn:
            rows = conn.execute(sql, params)
            return [{
                "entity_id": row.entity_id,
                "name": row.name,
                "entity_type": row.entity_type,
                "mention_count": row.mention_count,
            } for row in rows]

    def query_entity(self, entity_name: str) -> Optional[Dict]:
        """查询单个实体详情及其 1-hop 邻居

        Args:
            entity_name: 实体名称

        Returns:
            {entity: {...}, neighbors: [...], related_articles: [...]}  或 None
        """
        # 查实体基本信息
        sql_entity = text("""
            SELECT entity_id, name, entity_type, source
            FROM entity WHERE name = :name
        """)
        # 查 CO_OCCURS 邻居实体
        sql_neighbors = text("""
            SELECT
                CASE WHEN r.source_id = :entity_ref THEN r.target_id ELSE r.source_id END AS neighbor_ref,
                r.relation_type, r.frequency, r.confidence
            FROM relation r
            WHERE (r.source_id = :entity_ref OR r.target_id = :entity_ref)
              AND r.relation_type IN ('CO_OCCURS', 'TREATS', 'HAS_SYMPTOM')
            ORDER BY r.frequency DESC
            LIMIT 50
        """)
        # 查 MENTIONS 关联文献
        sql_articles = text("""
            SELECT a.article_id, a.title, a.pub_year, r.frequency
            FROM relation r
            JOIN article a ON r.source_id = CONCAT('A:', a.article_id)
            WHERE r.target_id = :entity_ref
              AND r.relation_type = 'MENTIONS'
            ORDER BY r.frequency DESC
            LIMIT 20
        """)

        entity_ref = f"E:{entity_name}"

        with self.engine.connect() as conn:
            # 实体信息
            row = conn.execute(sql_entity, {"name": entity_name}).fetchone()
            if not row:
                return None

            entity_info = {
                "entity_id": row.entity_id,
                "name": row.name,
                "entity_type": row.entity_type,
                "source": row.source,
            }

            # 邻居实体
            neighbors = []
            n_rows = conn.execute(sql_neighbors, {"entity_ref": entity_ref})
            for nr in n_rows:
                neighbor_name = nr.neighbor_ref.replace("E:", "", 1)
                neighbors.append({
                    "entity_name": neighbor_name,
                    "relation_type": nr.relation_type,
                    "frequency": nr.frequency,
                    "confidence": nr.confidence,
                })

            # 关联文献
            articles = []
            a_rows = conn.execute(sql_articles, {"entity_ref": entity_ref})
            for ar in a_rows:
                articles.append({
                    "article_id": ar.article_id,
                    "title": ar.title,
                    "pub_year": ar.pub_year,
                    "frequency": ar.frequency,
                })

        return {
            "entity": entity_info,
            "neighbors": neighbors,
            "related_articles": articles,
        }

    def get_entities_by_type(self, entity_type: str) -> List[Dict]:
        """按类型列出所有实体

        Args:
            entity_type: Disease / Drug / Symptom

        Returns:
            [{entity_id, name, entity_type}, ...]
        """
        sql = text("""
            SELECT entity_id, name, entity_type
            FROM entity
            WHERE entity_type = :entity_type
            ORDER BY name
        """)
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"entity_type": entity_type})
            return [{
                "entity_id": row.entity_id,
                "name": row.name,
                "entity_type": row.entity_type,
            } for row in rows]

    # ==================== 路径查询 ====================

    def query_shortest_path(self, src_entity: str, tgt_entity: str) -> Optional[Dict]:
        """查询两实体间的最短路径（纯 SQL 方式，基于 CO_OCCURS 边）

        使用 BFS 思路在 CO_OCCURS 关系上查找两实体间最短路径。

        Args:
            src_entity: 起始实体名称
            tgt_entity: 目标实体名称

        Returns:
            {path: [...], length: N}  或 None (无路径)
        """
        src_ref = f"E:{src_entity}"
        tgt_ref = f"E:{tgt_entity}"

        # 如果两个实体相同
        if src_ref == tgt_ref:
            return {"path": [src_entity], "length": 0}

        # BFS 搜索 CO_OCCURS 路径（限制最大深度 6）
        sql_edges = text("""
            SELECT source_id, target_id, frequency, relation_type
            FROM relation
            WHERE relation_type = 'CO_OCCURS'
        """)

        with self.engine.connect() as conn:
            rows = conn.execute(sql_edges)

            # 构建邻接表
            adj: Dict[str, List[str]] = {}
            for row in rows:
                adj.setdefault(row.source_id, []).append(row.target_id)
                adj.setdefault(row.target_id, []).append(row.source_id)

        # BFS
        from collections import deque
        queue = deque([[src_ref]])
        visited = {src_ref}

        while queue:
            path = queue.popleft()
            node = path[-1]

            if len(path) > 7:  # 最大深度限制
                continue

            for neighbor in adj.get(node, []):
                if neighbor == tgt_ref:
                    final_path = path + [neighbor]
                    return {
                        "path": [n.replace("E:", "", 1) for n in final_path],
                        "length": len(final_path) - 1,
                    }
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])

        return None

    # ==================== 文献查询 ====================

    def query_article_entities(self, article_id: str) -> Optional[Dict]:
        """查询文献详情及其关联的实体。

        Args:
            article_id: 文献 ID

        Returns:
            {article: {...}, entities: [...]}  或 None
        """
        sql_article = text("""
            SELECT article_id, pmid, title, abstract, authors, journal,
                   pub_year, language, source_file
            FROM article
            WHERE article_id = :article_id
        """)
        sql_entities = text("""
            SELECT e.entity_id, e.name, e.entity_type, r.frequency
            FROM relation r
            JOIN entity e ON CONCAT('E:', e.name) = r.target_id
            WHERE r.source_id = :article_ref
              AND r.relation_type = 'MENTIONS'
            ORDER BY r.frequency DESC
        """)

        article_ref = f"A:{article_id}"

        with self.engine.connect() as conn:
            row = conn.execute(sql_article, {"article_id": article_id}).fetchone()
            if not row:
                return None

            article_info = {
                "article_id": row.article_id,
                "pmid": row.pmid,
                "title": row.title,
                "abstract": row.abstract[:500] if row.abstract else None,
                "authors": row.authors,
                "journal": row.journal,
                "pub_year": row.pub_year,
                "language": row.language,
                "source_file": row.source_file,
            }

            entities = []
            e_rows = conn.execute(sql_entities, {"article_ref": article_ref})
            for er in e_rows:
                entities.append({
                    "entity_id": er.entity_id,
                    "name": er.name,
                    "entity_type": er.entity_type,
                    "frequency": er.frequency,
                })

        return {"article": article_info, "entities": entities}

    # ==================== 关键词搜索 ====================

    def keyword_search(
        self,
        keyword: str,
        limit: int = 50,
    ) -> List[Dict]:
        """按关键词检索文献（标题 + 摘要全文搜索）

        Args:
            keyword: 搜索关键词
            limit:   返回条数上限

        Returns:
            [{article_id, title, abstract_snippet, pub_year, journal}, ...]
        """
        sql = text("""
            SELECT article_id, pmid, title, abstract, pub_year, journal, language
            FROM article
            WHERE title LIKE :kw OR abstract LIKE :kw
            ORDER BY pub_year DESC
            LIMIT :limit
        """)

        kw = f"%{keyword}%"
        with self.engine.connect() as conn:
            rows = conn.execute(sql, {"kw": kw, "limit": limit})
            results = []
            for row in rows:
                # 截取关键词附近的摘要片段
                snippet = ""
                if row.abstract:
                    idx = row.abstract.lower().find(keyword.lower())
                    if idx >= 0:
                        start = max(0, idx - 60)
                        end = min(len(row.abstract), idx + len(keyword) + 120)
                        snippet = ("..." if start > 0 else "") + \
                                  row.abstract[start:end] + \
                                  ("..." if end < len(row.abstract) else "")

                results.append({
                    "article_id": row.article_id,
                    "pmid": row.pmid,
                    "title": row.title,
                    "abstract_snippet": snippet or (row.abstract[:200] if row.abstract else ""),
                    "pub_year": row.pub_year,
                    "journal": row.journal,
                    "language": row.language,
                })
        return results

    # ==================== 统计查询 ====================

    def get_statistics(self) -> Dict:
        """获取数据库统计信息"""
        with self.engine.connect() as conn:
            article_count = conn.execute(
                text("SELECT COUNT(*) FROM article")
            ).scalar()
            entity_count = conn.execute(
                text("SELECT COUNT(*) FROM entity")
            ).scalar()
            relation_count = conn.execute(
                text("SELECT COUNT(*) FROM relation")
            ).scalar()
            entity_type_counts = conn.execute(text("""
                SELECT entity_type, COUNT(*) AS cnt
                FROM entity GROUP BY entity_type
            """))
            entity_types = {row.entity_type: row.cnt for row in entity_type_counts}
            relation_type_counts = conn.execute(text("""
                SELECT relation_type, COUNT(*) AS cnt
                FROM relation GROUP BY relation_type
            """))
            relation_types = {row.relation_type: row.cnt for row in relation_type_counts}

        return {
            "article_count": article_count,
            "entity_count": entity_count,
            "relation_count": relation_count,
            "entities_by_type": entity_types,
            "relations_by_type": relation_types,
        }
