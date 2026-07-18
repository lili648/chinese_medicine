# -*- coding: utf-8 -*-
"""
SQLAlchemy 引擎/会话管理
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

# MySQL 连接配置（待实际环境修改）
DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/chinese_medicine"

engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_engine():
    """获取 SQLAlchemy Engine"""
    return engine


def get_session() -> Generator[Session, None, None]:
    """获取数据库会话（上下文管理）"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def is_connected() -> bool:
    """检查数据库连接状态"""
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
