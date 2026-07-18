# -*- coding: utf-8 -*-
"""运行预处理+实体识别 Pipeline"""
import os, sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)
os.chdir(project_root)

from src.ner import Pipeline

output_dir = os.path.join("output", "ner")
os.makedirs(output_dir, exist_ok=True)

pipeline = Pipeline(dict_dir="dicts", clean_mode="medical")

# 用采集到的数据运行 Pipeline
entities, top = pipeline.run_with_summary(
    "data/pubmed/pubmed_all_merged.csv",
    export_dir=output_dir,
)

print()
print("=" * 60)
print("  Pipeline 运行完成")
print("=" * 60)
print(f"  总实体提及: {len(entities)}")
unique = len(set((e["entity_name"], e["entity_type"]) for e in entities))
print(f"  唯一实体数: {unique}")
print()

# 按类型分布
from collections import Counter
type_dist = Counter(e["entity_type"] for e in entities)
print("实体类型分布:")
for t, c in type_dist.most_common():
    print(f"  {t:10s}: {c:5d}")
print()

# 按方法分布
method_dist = Counter(e.get("match_method", "unknown") for e in entities)
print("识别方法分布:")
for m, c in method_dist.most_common():
    print(f"  {m:20s}: {c:5d}")
print()

# Top 30 高频实体
print("Top 30 高频实体:")
print("-" * 55)
print(f"  {'实体':22s} {'类型':10s} {'频次':>6s}")
print("-" * 55)
for item in top[:30]:
    print(f"  {item['entity_name']:22s} {item['entity_type']:10s} {item['frequency']:6d}")

print()
pipeline.show_report()

# 保存 CSV
csv_path = os.path.join(output_dir, "entities.csv")
pipeline.export_csv_entities(entities, csv_path)
print(f"\n实体 CSV 已导出: {csv_path}")
