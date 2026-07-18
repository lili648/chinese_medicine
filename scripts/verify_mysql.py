# -*- coding: utf-8 -*-
"""验证 MySQL 表结构"""
import pymysql

conn = pymysql.connect(host="localhost", port=3306, user="root",
                       password="Liyizhang_10", database="chinese_medicine")
c = conn.cursor()

c.execute("SHOW TABLES")
print("=== 数据库 chinese_medicine 表列表 ===")
for r in c:
    print(f"  {r[0]}")
print()

for tbl in ["article", "entity", "relation"]:
    c.execute(f"DESCRIBE {tbl}")
    print(f"=== {tbl} 表结构 ===")
    print(f"  {'字段名':16s} {'类型':16s} {'允许空':6s} {'默认值'}")
    print(f"  {'-'*16} {'-'*16} {'-'*6} {'-'*10}")
    for r in c:
        null = "YES" if r[2] == "YES" else "NO"
        default = str(r[4]) if r[4] is not None else ""
        print(f"  {r[0]:16s} {r[1]:16s} {null:6s} {default}")
    print()

c.execute("SHOW INDEX FROM article")
print("=== article 索引 ===")
for r in c:
    print(f"  {r[2]} ({r[4]})")
print()

c.execute("SHOW INDEX FROM relation")
print("=== relation 索引 ===")
for r in c:
    print(f"  {r[2]} ({r[4]})")
print()

c.close()
conn.close()
print("验证完成！")
