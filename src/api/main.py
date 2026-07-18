# -*- coding: utf-8 -*-
"""
FastAPI 主入口 (uvicorn)
提供 REST API 供 Vue 前端调用

启动: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
"""
import logging
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text

from ..db.db_session import get_engine
from ..knowledge_graph.query_api import QueryAPI
from ..knowledge_graph.graph_engine import GraphEngine

logger = logging.getLogger(__name__)

# ======================== FastAPI 应用 ========================

app = FastAPI(title="基于知识图谱的医疗文献管理平台", version="1.0.0")

# CORS — 允许前端开发跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================== 单例 ========================

_query_api: Optional[QueryAPI] = None
_graph_engine: Optional[GraphEngine] = None


def _get_qa() -> QueryAPI:
    global _query_api
    if _query_api is None:
        _query_api = QueryAPI()
    return _query_api


def _get_ge() -> GraphEngine:
    global _graph_engine
    if _graph_engine is None:
        _graph_engine = GraphEngine()
        _graph_engine.load_from_mysql()
    return _graph_engine


# ======================== Pydantic 模型 ========================

class EntityQuery(BaseModel):
    name: str


class PathQuery(BaseModel):
    source: str
    target: str


# ======================== API 端点 ========================

# ---------- 1. 关键词检索 ----------

@app.get("/api/search")
async def keyword_search(q: str = Query(..., description="搜索关键词")):
    """关键词检索文献（标题+摘要），并附带每篇文献的关联实体"""
    qa = _get_qa()
    articles = qa.keyword_search(q, limit=50)

    if not articles:
        return {"articles": [], "total": 0}

    # 批量查询每篇文献的关联实体（避免 N+1）
    article_ids = [a["article_id"] for a in articles]
    id_to_entities: Dict[str, List[Dict]] = {aid: [] for aid in article_ids}

    article_refs = [f"A:{aid}" for aid in article_ids]
    # 用参数化 IN 查询
    sql_entities = text(f"""
        SELECT r.source_id, e.name, e.entity_type
        FROM relation r
        JOIN entity e ON r.target_id = CONCAT('E:', e.name)
        WHERE r.relation_type = 'MENTIONS'
          AND r.source_id IN ({','.join([':r' + str(i) for i in range(len(article_refs))])})
    """)
    params = {f"r{i}": ref for i, ref in enumerate(article_refs)}

    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(sql_entities, params)
        for row in rows:
            aid = row.source_id.replace("A:", "", 1)
            if aid in id_to_entities:
                id_to_entities[aid].append({
                    "name": row.name,
                    "entity_type": row.entity_type,
                })

    # 合并
    for a in articles:
        a["entities"] = id_to_entities.get(a["article_id"], [])

    return {"articles": articles, "total": len(articles)}


# ---------- 2. 实体详情 ----------

@app.post("/api/query/entity")
async def query_by_entity(body: EntityQuery):
    """按实体名查询详情、1-hop 邻居及关联文献"""
    qa = _get_qa()
    result = qa.query_entity(body.name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"实体 '{body.name}' 不存在")
    return result


# ---------- 3. Top-N 实体 ----------

@app.get("/api/query/top")
async def query_top(
    entity_type: Optional[str] = Query(None, description="实体类型：Disease/Drug/Symptom"),
    n: int = Query(20, ge=1, le=200, description="返回条数"),
):
    """按 MENTIONS 频次返回 Top-N 实体，可按类型过滤"""
    qa = _get_qa()
    return qa.get_top_entities(entity_type=entity_type, top_n=n)


# ---------- 4. 最短路径 ----------

@app.post("/api/query/path")
async def query_shortest_path(body: PathQuery):
    """两实体间 CO_OCCURS 最短路径"""
    qa = _get_qa()
    result = qa.query_shortest_path(body.source, body.target)
    if result is None:
        return {"found": False, "path": []}
    return {"found": True, "path": result["path"]}


# ---------- 5. 文献详情 ----------

@app.get("/api/query/article")
async def query_article_entities(
    article_id: str = Query(..., description="文献 ID"),
):
    """查询文献详情及关联实体"""
    qa = _get_qa()
    result = qa.query_article_entities(article_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"文献 '{article_id}' 不存在")
    return result


# ---------- 6. 图谱数据 (ECharts) ----------

@app.get("/api/graph/data")
async def graph_data():
    """返回 ECharts 力导向图 JSON（nodes + links），用于前端可视化"""
    try:
        ge = _get_ge()
        data = ge.to_echarts_format()
        return {
            "nodes": data["nodes"],
            "links": data["links"],
            "node_count": len(data["nodes"]),
            "edge_count": len(data["links"]),
        }
    except Exception as e:
        logger.exception("图谱加载失败")
        raise HTTPException(status_code=500, detail=f"图谱加载失败: {e}")


# ---------- 7. 数据库统计 ----------

@app.get("/api/stats")
async def get_statistics():
    """获取数据库概览统计"""
    qa = _get_qa()
    return qa.get_statistics()


# ---------- 8. 按类型列出实体 ----------

@app.get("/api/entities")
async def list_entities(
    entity_type: str = Query(..., description="实体类型：Disease/Drug/Symptom"),
):
    """按类型列出所有实体（供下拉选择等场景）"""
    qa = _get_qa()
    return qa.get_entities_by_type(entity_type)
