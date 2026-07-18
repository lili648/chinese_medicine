# -*- coding: utf-8 -*-
"""
FastAPI 主入口 (uvicorn)
提供 REST API 供 Vue 前端调用
"""
from fastapi import FastAPI

app = FastAPI(title="基于知识图谱的医疗文献管理平台", version="1.0.0")


@app.get("/api/query/top")
async def query_top(entity_type: str, n: int = 20):
    """按类型查 Top-N 实体"""
    pass


@app.post("/api/query/entity")
async def query_by_entity(name: str):
    """按实体名查询关联"""
    pass


@app.post("/api/query/path")
async def query_shortest_path(source: str, target: str):
    """两实体最短路径"""
    pass


@app.get("/api/query/article")
async def query_article_entities(article_id: str):
    """查文献关联实体"""
    pass


@app.get("/api/search")
async def keyword_search(q: str):
    """关键词检索文献"""
    pass
