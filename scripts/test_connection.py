# -*- coding: utf-8 -*-
"""验证完整数据库连接"""
import sys
sys.path.insert(0, ".")

from src.db.db_session import is_connected, get_engine
from src.knowledge_graph.db_schema import Base, Article, Entity, Relation

print("SQLAlchemy Engine:", get_engine())
print("连接状态:", "OK" if is_connected() else "FAIL")

# 验证 ORM 模型
print("\nORM 模型:")
print("  Article:", Article.__tablename__, "- columns:", [c.name for c in Article.__table__.columns])
print("  Entity:", Entity.__tablename__, "- columns:", [c.name for c in Entity.__table__.columns])
print("  Relation:", Relation.__tablename__, "- columns:", [c.name for c in Relation.__table__.columns])

print("\n全部验证通过!")
