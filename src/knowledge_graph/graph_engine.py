# -*- coding: utf-8 -*-
"""
NetworkX 图计算引擎
类: GraphEngine - 内存图构建与计算
"""
import json
from typing import List, Dict, Optional
import networkx as nx


class GraphEngine:
    """NetworkX 图计算引擎"""

    def __init__(self):
        self.nx_graph: nx.Graph = nx.Graph()

    def load_from_mysql(self) -> None:
        """从 MySQL 加载全量数据构建 NetworkX 图"""
        # TODO: 从 MySQL article/entity/relation 表加载数据
        self.nx_graph = nx.Graph()

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
