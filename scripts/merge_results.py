# -*- coding: utf-8 -*-
"""合并爬取结果并生成汇总报告"""
import csv, os, glob
from datetime import datetime
from collections import Counter

# 脚本在 scripts/ 下，项目根目录为上级目录
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
data_dir = os.path.join(project_root, "data", "pubmed")
dict_dir = os.path.join(project_root, "dicts")
files = glob.glob(os.path.join(data_dir, "*.csv"))
# 排除已有的合并文件
files = [f for f in files if "merged" not in os.path.basename(f)]

print(f"共 {len(files)} 个CSV文件:")

seen_pmids = set()
all_articles = []
rec_count = 0

for fpath in sorted(files):
    fname = os.path.basename(fpath)
    count = 0
    with open(fpath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pmid = row.get("pmid", "")
            if pmid and pmid not in seen_pmids:
                seen_pmids.add(pmid)
                all_articles.append(row)
                count += 1
            elif not pmid:
                all_articles.append(row)
                count += 1
            rec_count += 1
    size_kb = os.path.getsize(fpath) / 1024
    print(f"  {fname:45s} {count:4d} 篇  ({size_kb:7.1f} KB)")

# 保存合并文件
merged_path = os.path.join(data_dir, "pubmed_all_merged.csv")
fieldnames = ["article_id", "pmid", "title", "abstract", "authors", "journal", "pub_year", "language", "source_file"]
with open(merged_path, "w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for a in all_articles:
        writer.writerow(a)

print()
print("=" * 60)
print("  数据采集完成汇总")
print("=" * 60)
print(f"  采集时间:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  原始记录总数:   {rec_count} 条")
print(f"  去重后总数:     {len(all_articles)} 篇")
print(f"  合并文件:       {merged_path}")
print(f"  文件大小:       {os.path.getsize(merged_path)/1024:.1f} KB")
print("=" * 60)

# 年份分布
years = Counter()
for a in all_articles:
    y = a.get("pub_year", "")
    if y and y != "":
        try:
            years[int(y)] += 1
        except ValueError:
            pass
print()
print("年份分布 (Top 15):")
for y, c in sorted(years.items(), reverse=True)[:15]:
    print(f"  {y}: {c:4d} 篇")

# 词典统计
print()
print("词典统计:")
for dt in ["disease", "drug", "symptom"]:
    path = os.path.join(dict_dir, f"{dt}_dict.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            entities = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        print(f"  {dt:12s}: {len(entities):4d} 个实体")
print()
print("数据采集全部完成!")
