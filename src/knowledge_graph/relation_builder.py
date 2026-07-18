# -*- coding: utf-8 -*-
"""
关系构建器
类: RelationBuilder - 共现/治疗/症状关系构建
对应需求: FR-07
"""
from typing import List, Dict
from collections import defaultdict
from sqlalchemy import text
from ..db.db_session import get_engine


class RelationBuilder:
    """关系构建器"""

    def __init__(self):
        self.engine = get_engine()

    def build_mentions(self, entities: List[Dict]) -> int:
        """构建 MENTIONS 关系（文献 → 实体）"""
        relations = []
        seen = set()
        for ent in entities:
            key = (f"A:{ent['article_id']}", f"E:{ent['entity_name']}", "MENTIONS")
            if key not in seen:
                seen.add(key)
                relations.append({
                    "source_id": f"A:{ent['article_id']}",
                    "target_id": f"E:{ent['entity_name']}",
                    "relation_type": "MENTIONS",
                    "frequency": ent.get("frequency", 1),
                })
        return self._insert_relations(relations)

    def build_co_occur(self, entities: List[Dict], threshold: int = 2) -> int:
        """基于共现频次构建 CO_OCCURS"""
        pairs = defaultdict(int)
        article_entities = defaultdict(list)
        for ent in entities:
            article_entities[ent["article_id"]].append(ent["entity_name"])

        for ents in article_entities.values():
            for i, e1 in enumerate(ents):
                for e2 in ents[i + 1:]:
                    key = tuple(sorted([e1, e2]))
                    pairs[key] += 1

        relations = []
        for (e1, e2), freq in pairs.items():
            if freq >= threshold:
                relations.append({
                    "source_id": f"E:{e1}",
                    "target_id": f"E:{e2}",
                    "relation_type": "CO_OCCURS",
                    "frequency": freq,
                    "confidence": "High" if freq >= 5 else "Low",
                })
        return self._insert_relations(relations)

    def build_treats(self) -> int:
        """构建 TREATS 关系（Drug → Disease，基于词典定义）"""
        # 需要根据医学知识库补充具体规则
        return 0

    def build_has_symptom(self) -> int:
        """构建 HAS_SYMPTOM 关系（Disease → Symptom，基于词典定义）"""
        # 需要根据医学知识库补充具体规则
        return 0

    def _insert_relations(self, relations: List[Dict]) -> int:
        """批量插入关系记录"""
        if not relations:
            return 0
        with self.engine.connect() as conn:
            for rel in relations:
                sql = text("""
                    INSERT INTO relation (source_id, target_id, relation_type, frequency, confidence)
                    VALUES (:source_id, :target_id, :relation_type, :frequency, :confidence)
                    ON DUPLICATE KEY UPDATE frequency=frequency+1
                """)
                conn.execute(sql, rel)
            conn.commit()
        return len(relations)
