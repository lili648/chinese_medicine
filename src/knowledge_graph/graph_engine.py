# -*- coding: utf-8 -*-
"""
NetworkX 图计算引擎
类: GraphEngine - 内存图构建与计算
"""
import json
import logging
from typing import List, Dict, Optional
import networkx as nx
from sqlalchemy import text
from ..db.db_session import get_engine

logger = logging.getLogger(__name__)


class GraphEngine:
    """NetworkX 图计算引擎"""

    def __init__(self):
        self.nx_graph: nx.Graph = nx.Graph()
        self._loaded = False

    def load_from_mysql(self) -> None:
        """从 MySQL article/entity/relation 表加载全量数据构建 NetworkX 图

        加载流程:
        1. 从 entity 表加载所有实体，作为图节点
        2. 从 article 表加载文献，作为图节点 (为 MENTIONS 边提供端点)
        3. 从 relation 表加载所有关系，作为图边
        """
        self.nx_graph = nx.Graph()
        engine = get_engine()

        with engine.connect() as conn:
            # ---- Step 1: 加载实体节点 ----
            rows = conn.execute(text(
                "SELECT entity_id, name, entity_type FROM entity"
            ))
            entity_count = 0
            for row in rows:
                node_id = f"E:{row.name}"
                self.nx_graph.add_node(
                    node_id,
                    name=row.name,
                    entity_type=row.entity_type,
                    label=row.name,
                )
                entity_count += 1
            logger.info("已加载实体节点: %d", entity_count)

            # ---- Step 2: 加载文献节点 ----
            rows = conn.execute(text(
                "SELECT article_id, title, pub_year FROM article"
            ))
            article_count = 0
            for row in rows:
                node_id = f"A:{row.article_id}"
                self.nx_graph.add_node(
                    node_id,
                    name=row.title[:80] if row.title else row.article_id,
                    entity_type="Article",
                    label=row.title[:50] if row.title else row.article_id,
                    pub_year=row.pub_year,
                )
                article_count += 1
            logger.info("已加载文献节点: %d", article_count)

            # ---- Step 3: 加载关系边 ----
            rows = conn.execute(text(
                "SELECT source_id, target_id, relation_type, frequency, confidence "
                "FROM relation"
            ))
            relation_count = 0
            for row in rows:
                self.nx_graph.add_edge(
                    row.source_id,
                    row.target_id,
                    relation_type=row.relation_type,
                    frequency=row.frequency,
                    confidence=row.confidence,
                )
                relation_count += 1
            logger.info("已加载关系边: %d", relation_count)

        self._loaded = True
        logger.info(
            "MySQL 加载完成: 节点=%d, 边=%d",
            self.nx_graph.number_of_nodes(),
            self.nx_graph.number_of_edges(),
        )

    def load_from_json(self, file_path: str) -> None:
        """从 entities.json 构建 NetworkX 图（降级方案）"""
        self.nx_graph = nx.Graph()
        with open(file_path, "r", encoding="utf-8") as f:
            entities = json.load(f)
        for ent in entities:
            node_id = f"E:{ent['entity_name']}"
            self.nx_graph.add_node(
                node_id,
                name=ent["entity_name"],
                entity_type=ent["entity_type"],
                label=ent["entity_name"],
            )

    def get_neighbors(self, node_id: str) -> List[Dict]:
        """查询 1-hop 邻居"""
        if node_id not in self.nx_graph:
            return []
        neighbors = []
        for neighbor in self.nx_graph.neighbors(node_id):
            node_data = self.nx_graph.nodes[neighbor]
            neighbors.append({
                "id": neighbor,
                "name": node_data.get("name", neighbor),
                "entity_type": node_data.get("entity_type", "Unknown"),
            })
        return neighbors

    def shortest_path(self, src: str, tgt: str) -> Optional[List[str]]:
        """两节点最短路径"""
        try:
            return nx.shortest_path(self.nx_graph, source=src, target=tgt)
        except (nx.NodeNotFound, nx.NetworkXNoPath):
            return None

    def to_echarts_format(self) -> Dict:
        """转换为 ECharts 力导向图 JSON 格式"""
        nodes = []
        for node_id, data in self.nx_graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "name": data.get("name", node_id),
                "category": data.get("entity_type", "Unknown"),
                "symbolSize": min(10 + self.nx_graph.degree(node_id) * 2, 50),
            })
        links = []
        for u, v, data in self.nx_graph.edges(data=True):
            links.append({
                "source": u,
                "target": v,
                "value": data.get("frequency", 1),
            })
        return {"nodes": nodes, "links": links}
