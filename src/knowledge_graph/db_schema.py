# -*- coding: utf-8 -*-
"""
MySQL 数据库表结构 — SQLAlchemy ORM 模型定义
表: article / entity / relation
对应需求: FR-06 (MySQL环境搭建与表结构设计)
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Index, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Article(Base):
    """文献表 — 存储 PubMed 及中文医学文献元数据"""
    __tablename__ = "article"

    article_id  = Column(String(64), primary_key=True, comment="文献唯一ID")
    pmid        = Column(String(32), nullable=True, index=True, comment="PubMed PMID")
    title       = Column(Text, nullable=True, comment="文献标题")
    abstract    = Column(Text, nullable=True, comment="文献摘要")
    authors     = Column(Text, nullable=True, comment="作者列表")
    journal     = Column(String(512), nullable=True, comment="期刊名称")
    pub_year    = Column(Integer, nullable=True, index=True, comment="发表年份")
    language    = Column(String(10), default="en", index=True, comment="语种")
    source_file = Column(String(256), nullable=True, index=True, comment="来源文件名")
    created_at  = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at  = Column(DateTime, default=datetime.now, onupdate=datetime.now,
                         nullable=False, comment="更新时间")

    def __repr__(self):
        return f"<Article(id={self.article_id}, title={self.title[:30] if self.title else None})>"


class Entity(Base):
    """实体表 — 疾病/药物/症状三类医学实体"""
    __tablename__ = "entity"

    entity_id   = Column(String(32), primary_key=True, comment="实体MD5 ID")
    name        = Column(String(256), unique=True, nullable=False, comment="实体名称")
    entity_type = Column(String(20), nullable=False, index=True, comment="类型: Disease/Drug/Symptom")
    source      = Column(String(64), default="", comment="来源: dict/extracted")
    created_at  = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at  = Column(DateTime, default=datetime.now, onupdate=datetime.now,
                         nullable=False, comment="更新时间")

    __table_args__ = (
        Index("idx_entity_type", "entity_type"),
    )

    def __repr__(self):
        return f"<Entity(name={self.name}, type={self.entity_type})>"


class Relation(Base):
    """关系表 — 文献-实体、实体-实体间多种关系"""
    __tablename__ = "relation"

    id            = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")
    source_id     = Column(String(128), nullable=False, index=True,
                           comment="源节点: A:{article_id} / E:{entity_name}")
    target_id     = Column(String(128), nullable=False, index=True,
                           comment="目标节点: A:{article_id} / E:{entity_name}")
    relation_type = Column(String(20), nullable=False, index=True,
                           comment="关系类型: MENTIONS/CO_OCCURS/TREATS/HAS_SYMPTOM")
    frequency     = Column(Integer, default=1, comment="频次/权重")
    confidence    = Column(String(10), nullable=True, comment="置信度")
    created_at    = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at    = Column(DateTime, default=datetime.now, onupdate=datetime.now,
                           nullable=False, comment="更新时间")

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "relation_type", name="uk_relation"),
        Index("idx_source_type", "source_id", "relation_type"),
    )

    def __repr__(self):
        return f"<Relation({self.source_id} -[{self.relation_type}]-> {self.target_id})>"
