# -*- coding: utf-8 -*-
"""
实体识别引擎
类: EntityRecognizer - 词典正向最大匹配 + jieba分词 + AI联合识别
对应需求: FR-04
"""
import json
from typing import List, Dict
from .entity_dict import EntityDict
from ..preprocessing.data_loader import Article


class EntityRecognizer:
    """实体识别引擎"""

    def __init__(self, entity_dict: EntityDict, max_match_length: int = 10):
        self.entity_dict = entity_dict
        self.max_match_length = max_match_length

    def recognize(self, tokens: List[str]) -> List[Dict]:
        """正向最大匹配 + jieba 分词联合识别"""
        entities = []
        entities.extend(self._dict_match(tokens))
        entities.extend(self._jieba_match(tokens))
        return self._deduplicate(entities)

    def _dict_match(self, tokens: List[str]) -> List[Dict]:
        """词典正向最大匹配"""
        entities = []
        n = len(tokens)
        i = 0
        while i < n:
            matched = False
            for length in range(min(self.max_match_length, n - i), 0, -1):
                phrase = "".join(tokens[i:i + length])
                entity_type = self.entity_dict.lookup(phrase)
                if entity_type:
                    entities.append({
                        "entity_name": phrase,
                        "entity_type": entity_type,
                        "match_method": "dict",
                    })
                    i += length
                    matched = True
                    break
            if not matched:
                i += 1
        return entities

    def _jieba_match(self, tokens: List[str]) -> List[Dict]:
        """jieba 分词后逐词匹配词典"""
        entities = []
        for token in tokens:
            entity_type = self.entity_dict.lookup(token)
            if entity_type:
                entities.append({
                    "entity_name": token,
                    "entity_type": entity_type,
                    "match_method": "jieba",
                })
        return entities

    def _deduplicate(self, entities: List[Dict]) -> List[Dict]:
        """同篇文献内实体去重"""
        seen = {}
        result = []
        for ent in entities:
            key = (ent["entity_name"], ent["entity_type"])
            if key not in seen:
                seen[key] = ent
                result.append(ent)
        return result

    def recognize_batch(self, articles: List[Article]) -> List[Dict]:
        """批量识别，输出 JSON"""
        results = []
        for article in articles:
            entities = self.recognize(article.tokens)
            # 统计频次
            freq: Dict[str, int] = {}
            for ent in entities:
                key = ent["entity_name"]
                freq[key] = freq.get(key, 0) + 1
            for ent in entities:
                results.append({
                    "entity_name": ent["entity_name"],
                    "entity_type": ent["entity_type"],
                    "article_id": article.article_id,
                    "frequency": freq.get(ent["entity_name"], 1),
                })
        return results

    def export_json(self, entities: List[Dict], output_path: str) -> None:
        """导出为 entities.json"""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(entities, f, ensure_ascii=False, indent=2)
