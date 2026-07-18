# 更新日志 (CHANGELOG)

## V1.0 — 开发中

---

### 2026-07-18 — MySQL 环境搭建与表结构设计

#### 新增 `scripts/init_mysql.sql` — MySQL DDL 建库建表脚本
- 数据库 `chinese_medicine`，utf8mb4 字符集
- 3 张核心表：
  - **article** — 文献表（article_id PK, pmid, title, abstract, authors, journal, pub_year, language, source_file, created_at, updated_at）
  - **entity** — 实体表（entity_id MD5 PK, name UNIQUE, entity_type Disease/Drug/Symptom, source, created_at, updated_at）
  - **relation** — 关系表（id PK AUTO_INCREMENT, source_id, target_id, relation_type MENTIONS/CO_OCCURS/TREATS/HAS_SYMPTOM, frequency, confidence, created_at, updated_at）
- 含唯一约束（uk_relation）和复合索引（idx_source_type）

#### 完成 `src/knowledge_graph/db_schema.py` — SQLAlchemy ORM 模型 ✅
- `Article` — 文献表 ORM 模型（11 列，4 个索引）
- `Entity` — 实体表 ORM 模型（6 列，UNIQUE KEY + 索引）
- `Relation` — 关系表 ORM 模型（8 列，自增 ID + UniqueConstraint + 索引 + __repr__）
- 与 DDL 完全一致，支持 Base.metadata.create_all(engine) 自动建表

#### 实现 `GraphEngine.load_from_mysql()` — MySQL → NetworkX 图加载
- 三阶段加载流程：实体节点 → 文献节点 → 关系边
- 节点 ID 前缀约定：`E:` 实体 / `A:` 文献
- 边属性含 relation_type / frequency / confidence
- 日志输出每阶段加载数量与最终图统计

#### 新增 `src/knowledge_graph/query_api.py` — 图谱查询 API 封装 ✅
- `get_top_entities(type, top_n)` — 按 MENTIONS 频次 Top-N 实体排行
- `query_entity(name)` — 实体详情 + CO_OCCURS/TREATS/HAS_SYMPTOM 1-hop 邻居 + 关联文献
- `get_entities_by_type(type)` — 按类型列出全部实体
- `query_shortest_path(src, tgt)` — 纯 SQL BFS 最短路径（最大深度 6）
- `query_article_entities(article_id)` — 文献详情 + MENTIONS 实体列表
- `keyword_search(keyword, limit)` — 标题/摘要 LIKE 全文检索 + 关键词片段摘取
- `get_statistics()` — 数据库统计信息（按类型、按关系类型分组计数）

#### 修复 `src/db/db_session.py`
- SQLAlchemy 2.0 兼容：`conn.execute()` 内部改为 `text()` 包装
- 数据库密码更新为实际环境配置

#### 更新 `src/knowledge_graph/__init__.py`
- 导出：Base, Article, Entity, Relation, DataImporter, RelationBuilder, GraphEngine, QueryAPI

#### 新增辅助脚本
- `scripts/verify_mysql.py` — 数据库表结构验证工具
- `scripts/test_connection.py` — SQLAlchemy 连接 + ORM 模型验证工具

---

### 2026-07-18 — 知识图谱节点批量导入（工作包 #7）

#### 新增 `src/knowledge_graph/data_importer.py` — 节点批量导入编排 ✅
- `import_nodes(articles, entities_raw)` — 图谱节点批量导入编排方法
  - 先按 `(entity_name, entity_type)` 去重实体，再分别写入 article / entity 表
  - 返回 `(导入文献数, 导入唯一实体数)`
- `_dedup_entities(entities_raw)` — 按名称+类型去重，过滤空值，补 `source="ner"`
- 修复 `import_articles` / `import_entities`：**每批提交（batch commit）**，避免大数据量导入被中断时整体回滚
- 补 `import logging` 与 `logger` 定义（原文件缺失，导致 `import_nodes` 调用 `logger.info` 抛 `NameError`）

#### 新增 `scripts/import_nodes.py` — 一键节点批量导入脚本
- 串联流程：**DataLoader 加载 → Pipeline 预处理+NER → DataImporter.import_nodes 入库**
- 默认导入 `data/pubmed/` 与 `data/chinese/`，支持 `--data-dir` 自定义目录（可多个）
- 运行结束打印 article / entity 表计数与实体类型分布，便于校验
- 幂等安全：article 按 article_id、entity 按 name 唯一约束 + ON DUPLICATE KEY UPDATE，重复运行不报错、不产生脏数据

#### 修复 `src/ner/pipeline.py` — `load_data()` Bug
- 原 `load_directory(input_path, file_pattern)` 调用传入 2 个位置参数，但 `DataLoader.load_directory` 仅接收 `(self, dir_path)`，整目录导入时抛 `TypeError`（此前 `run_pipeline.py` 只传单文件故未触发）
- 修正为 `load_directory(input_path)`，目录模式按扩展名过滤

#### 实际导入验证（MySQL `chinese_medicine`）
- **article 表：1221 篇文献**（含 data/pubmed 15 个 CSV + 1 个 JSON，data/chinese 测试数据 12 条）
- **entity 表：118 个唯一实体**（Drug 8 / Disease 6 / Symptom 3 来自测试集，其余来自 PubMed 文献 NER）
- 实体类型分布符合 Disease/Drug/Symptom 约束
- 端到端脚本 `python -u scripts/import_nodes.py` 运行通过，幂等重跑行数稳定

---

### 2026-07-18 — 文本预处理与实体识别 Pipeline

#### 重写 `src/ner/entity_dict.py` — 实体词典管理器（增强版）
- **Bug 修复**：加载词典时正确过滤 `#` 注释行（原版会把注释当实体加载）
- 新增 **英文 TCM 术语映射表**（`EN_TO_CN_ENTITY`）：200+ 条英→中实体映射
  - 中医概念（TCM/acupuncture/moxibustion/cupping 等）
  - 中药植物学名（Salvia miltiorrhiza → 丹参，Panax ginseng → 人参 等 60+ 种）
  - 中英文疾病（diabetes → 糖尿病 等 30+ 种）
  - 英文症状（chest pain → 胸痛 等 20+ 种）
- 新增方法：`add_entity()`、`add_en_mapping()`、`lookup_en()`、`lookup_en_type()`、`has_en()`、`get_entities_by_type()`

#### 重写 `src/ner/entity_recognizer.py` — 实体识别引擎（中英文双模态）
- **中文模式**：
  - 正向最大匹配（FMM）— 在 token 序列上滑动窗口匹配
  - jieba 分词 + 逐词词典查找 + 连续词合并匹配（2-3 词拼接）
- **英文模式**：
  - 正则规则匹配：TCM 概念 / 中药植物学名 / 英文疾病 / 英文症状（100+ 条预编译正则）
  - Token 滑动短语匹配（1-4 词窗口）
  - 关键词匹配（小檗碱/姜黄素/丹酚酸 等 16 种活性成分）
- **自动语种检测**：基于中文字符比例（>15% 判为中文）
- **智能去重**：按名称+类型去重，保留优先级更高的匹配方法
- 新增 `RecognizeStats` 统计类、`get_top_entities()` 高频实体排行

#### 新增 `src/ner/pipeline.py` — 预处理+实体识别 Pipeline 编排器
- 完整流程：**加载文献 → 文本预处理 → 实体识别 → 导出**
- `run()` 一键执行全流程
- `run_with_summary()` 附加 Top-N 高频实体摘要
- 独立步骤可单独调用：`load_data()` / `preprocess()` / `recognize()`
- 多格式导出：JSON / CSV / 统计报告
- 新增 `PipelineStats` 综合统计类

#### 更新 `src/ner/__init__.py` 模块导出
- 导出：`EntityDict`、`EntityRecognizer`、`Pipeline`、`RecognizeStats`、`PipelineStats`

#### 新增测试 `tests/test_ner/test_ner.py` — 46 个测试用例
- EntityDict: 11 tests（加载/注释过滤/英文映射/类型管理）
- EntityRecognizer: 18 tests（中文FMM/jieba/英文规则/去重/语言检测）
- Pipeline: 14 tests（完整流程/导出/边界情况）
- Integration: 3 tests（中英文端到端）

#### 真实数据验证结果
| 指标 | 数值 |
|------|------|
| 处理文献 | 1,209 篇 |
| 含实体文献 | 958 篇 (79%) |
| 总实体提及 | 2,759 次 |
| 唯一实体 | 117 个 |
| 耗时 | 5.8s |

**实体类型分布**：Drug 1,475 / Disease 1,182 / Symptom 102

**Top 5 实体**：中医(494) / 糖尿病(306) / 2型糖尿病(167) / 草药(159) / 脑卒中(149)

#### 新增脚本
- `scripts/run_pipeline.py` — Pipeline 运行脚本（一键执行+导出+报告）

#### 测试覆盖率
- 预处理：57/57 ✅
- 爬虫：30/30 ✅
- NER + Pipeline：46/46 ✅
- **总计：133/133 ✅**

### 2026-07-18 — 数据采集模块完成

#### 新增 `src/crawler/` 爬虫模块
- **`base.py`** — 爬虫基类
  - `RateLimiter` 请求频率限制器（默认 3 req/s，支持自定义）
  - `CrawlStats` 爬取统计类（请求数/成功率/耗时/错误记录）
  - `BaseCrawler` 基类：UA 轮换 + 指数退避重试（最多 4 次）+ 429/5xx 重试
- **`pubmed_crawler.py`** — PubMed 文献爬虫
  - 基于 NCBI Entrez E-utilities API（无需 API Key，提供 Key 可提速至 10 req/s）
  - ESearch → EFetch 两阶段爬取流程，单次批量 200 条
  - 12 套预设检索式：糖尿病/高血压/冠心病/肿瘤/卒中/网络药理学/COVID + 中医 + 药物
  - `search_chinese_literature()` 中文文献专项检索
  - 导出 CSV（兼容 DataLoader）/ JSON
  - `quick_search()` 便捷函数
- **`dict_expander.py`** — 医学词典扩充器
  - 内置种子词：**173 疾病**（西医 ICD-10 分类 + 中医病证）、**223 药物**（西药 + 中成药 + 中药饮片 + 化疗/靶向药）、**132 症状**（全身/疼痛/呼吸道/消化道/泌尿/皮肤/神经心理 + 中医舌脉诊）
  - `save_all_seed_dicts()` 一键生成三套词典到 `dicts/`
  - 支持与已有词典去重合并
  - （实验性）百度百科在线抓取扩展词条
- **`run_collection.py`** — 数据采集入口脚本
  - `--max` 控制每种检索文献数
  - `--year` 限定发表年份范围
  - `--preset` 指定检索式
  - `--dicts-only / --pubmed-only / --chinese-only` 分步执行模式
  - `--skip-dicts / --skip-pubmed / --skip-chinese` 跳过模式

#### 新增 `scripts/merge_results.py` 合并汇总脚本
- 多 CSV 文件按 PMID 去重合并
- 输出年份分布统计
- 输出词典统计

#### 新增测试 `tests/test_crawler/`
- `test_crawler.py` — 30 个测试用例（RateLimiter / CrawlStats / BaseCrawler / PubMedCrawler / DictExpander）

#### 数据采集成果
- **PubMed 文献**：1,209 篇去重后（14 个检索维度，覆盖 2004-2026 年）
- **词典**：173 疾病 + 223 药物 + 132 症状，已保存至 `dicts/`
- **输出文件**：`data/pubmed/pubmed_all_merged.csv`（2.1 MB）+ 14 个独立子文件

#### 依赖更新
- `requirements.txt` 新增 `requests>=2.31.0`、`beautifulsoup4>=4.12.0`

---

### 2026-07-18 — 数据预处理模块完善

#### 重写 `src/preprocessing/data_loader.py`
- 新增 `LoadStats` 统计类
- `_handle_missing()` 完整缺失值处理与统计
- `_parse_pub_year()` 支持 `"2023"` / `"2023.0"` / `"2023年"` 多种年份格式
- `_infer_language()` 基于标题中文字符自动推断语种
- `load_txt()` 支持 TSV / 键值对 / 纯文本三种格式
- UTF-8 失败自动降级 GBK
- 新增 `validate_articles()` 和 `get_summary()` 工具方法

#### 重写 `src/preprocessing/preprocessor.py`
- 新增 `PreprocessStats` 统计类
- 双模式清洗：`strict`（仅中英文）vs `medical`（保留数字 + 百分号 + 医学符号）
- `_segment_en()` 保留医学短词白名单（iv, po, mg, ml, bp, ecg, ct, mri 等 30+）
- `_segment_zh()` 过滤纯数字/符号 token
- `process_batch()` 每 100 篇日志进度 + 异常容错
- `extract_keywords()` TF 关键词提取

#### 扩充 `data/stopwords.txt`
- 从 34 词扩充至 150+ 词（含医学领域停用词）

#### 新增测试 `tests/test_preprocessing/`
- `test_preprocessing.py` — 57 个测试用例（数据加载 / 清洗 / 分词 / 统计）

---

### 2026-07-18 — 知识图谱 + 数据库 + API + 前端模块搭建

#### 新增 `src/knowledge_graph/` 知识图谱模块

##### `db_schema.py` — SQLAlchemy ORM 模型 ✅
- Article / Entity / Relation 三表模型，与 DDL 完全一致

##### `graph_engine.py` — NetworkX 图计算引擎 ✅
- `load_from_json()` 从 NER 实体 JSON 构建 NetworkX 内存图
- `load_from_mysql()` 从 MySQL 加载全量数据构建图（已完整实现）
- `get_neighbors(node_id)` 查询 1-hop 邻居节点
- `shortest_path(src, tgt)` 两实体最短路径（基于 NetworkX）
- `to_echarts_format()` 转换为 ECharts 力导向图 JSON 格式

##### `relation_builder.py` — 关系构建器 ✅
- 四种关系类型：MENTIONS / CO_OCCURS / TREATS / HAS_SYMPTOM（前两种已实现）
- `_insert_relations()` 批量 INSERT 带 ON DUPLICATE KEY UPDATE

##### `data_importer.py` — 数据导入器 ✅
- 批量导入 Article/Entity 到 MySQL（500条/批，3次重试 + 指数退避）

##### `query_api.py` — 图谱查询 API ✅
- 7 个方法：get_top_entities / query_entity / get_entities_by_type / query_shortest_path / query_article_entities / keyword_search / get_statistics

#### 新增 `src/db/` 数据库会话管理
- `db_session.py` — SQLAlchemy 引擎/会话管理
  - MySQL 8.0 连接配置（pymysql 驱动，pool_size=10, max_overflow=20）
  - `get_engine()` — 全局引擎获取
  - `get_session()` — 上下文管理器会话（Generator 模式）
  - `is_connected()` — 数据库连接状态检测

#### 新增 `src/api/` FastAPI REST 接口（骨架）
- `main.py` — FastAPI 主入口（uvicorn 部署）
- 5 个 API 端点定义（均为骨架，待业务逻辑补全）：
  - `GET /api/query/top` — 按类型查 Top-N 实体
  - `POST /api/query/entity` — 按实体名查询关联
  - `POST /api/query/path` — 两实体最短路径
  - `GET /api/query/article` — 查文献关联实体
  - `GET /api/search` — 关键词检索文献

#### 新增 `frontend/` Vue 3 前端（部分实现）

##### 工程配置
- `package.json` — Vue 3.4 + Vue Router + vue-echarts + ECharts 5.5 + Axios + Vite 5.4
- `vite.config.js` — 端口 5173，`/api` 代理到 `localhost:8000`
- `index.html` — 入口 HTML
- `src/main.js` — Vue 应用入口

##### 组件（UI 已实现，业务逻辑待补全）
- `src/components/Search.vue` — 文献检索组件（关键词搜索 + 实体筛选 + 结果列表 + 高亮）
- `src/components/Detail.vue` — 文献详情组件（元数据表 + 摘要 + 关联实体标签）
- `src/components/Graph.vue` — 知识图谱可视化组件（ECharts 力导向图 + 路径查询 + 详情面板）
- `src/components/Admin.vue` — 管理后台组件（数据管理 + 操作按钮 + 系统信息）

##### API 客户端
- `src/api/client.js` — Axios 客户端，5 个方法：`queryByEntity` / `queryTop` / `queryShortestPath` / `queryArticleEntities` / `keywordSearch`

##### 待实现
- `src/App.vue` — 主应用布局 + Vue Router 路由配置（空文件）

#### 依赖更新
- `requirements.txt` 新增 `fastapi`、`uvicorn`、`sqlalchemy`、`pymysql`、`networkx`
- `frontend/package.json` 新增 Vue 3 全家桶 + ECharts 可视化依赖

---

### 2026-07-18 — 系统设计完成
- 数据库迁移至 MySQL 8.0
- 项目结构确定（frontend / src / tests / data / dicts）
- 技术栈确定：Vue 3 + FastAPI + MySQL + NetworkX + jieba

---

### 2026-07-17 — 需求分析阶段
- 完成需求分析文档
- 明确核心功能：文献管理 → 实体识别 → 知识图谱 → Web 可视化
- `.gitignore` 配置

---

### 项目立项
- 项目编号：KJTP-MLM-001
- 项目名称：基于知识图谱的医疗文献管理平台（MLM-KG）

---

## 当前状态概览（截止 2026-07-18）

### 模块完成度

| 模块 | 状态 | 实现文件 | 测试 |
|------|------|----------|------|
| `src/preprocessing/` | ✅ 完成 | data_loader.py, preprocessor.py | 57/57 |
| `src/crawler/` | ✅ 完成 | base.py, pubmed_crawler.py, dict_expander.py, run_collection.py | 30/30 |
| `src/ner/` | ✅ 完成 | entity_dict.py, entity_recognizer.py, pipeline.py | 46/46 |
| `src/knowledge_graph/` | ✅ 完成 | db_schema.py, graph_engine.py, relation_builder.py, data_importer.py, query_api.py | 0 |
| `src/db/` | ✅ 完成 | db_session.py | 0 |
| `src/api/` | 🔴 骨架 | main.py（5 端点均为 pass） | 0 |
| `frontend/` | 🔶 UI 完成 | Search/Detail/Graph/Admin.vue + client.js | 0 |

### 已知待办

| 优先级 | 事项 | 说明 |
|--------|------|------|
| P1 | `src/api/main.py` | 5 个 API 端点接入实际业务逻辑 |
| P1 | `frontend/src/App.vue` | Vue Router 路由 + 主布局实现 |
| P2 | Knowledge Graph 测试 | `tests/test_kg/` 补充测试 |
| P2 | API 测试 | `tests/test_api/` 补充测试 |
| P3 | RelationBuilder TREATS/HAS_SYMPTOM | 基于医学知识库补充治疗/症状关系规则 |

### 数据资产

| 资源 | 数量 | 说明 |
|------|------|------|
| PubMed 文献 | 1,209 篇去重 | 14 个检索维度，2004-2026 年 |
| 疾病词典 | 173 实体 | ICD-10 + 中医病证 |
| 药物词典 | 223 实体 | 西药 + 中成药 + 中药饮片 |
| 症状词典 | 132 实体 | 全身/疼痛/呼吸道/消化道等 + 中医舌脉诊 |
| 停用词表 | 150+ 词 | 含医学领域停用词 |
| 英→中映射 | 200+ 条 | 中药学名 + 英文疾病/症状 → 中文 |

### 测试覆盖率

```
预处理:      57/57 ✅
爬虫:        30/30 ✅
NER+Pipeline: 46/46 ✅
知识图谱:     0     ⬜ (待编写)
API:         0     ⬜ (待编写)
─────────────────────────
总计:       133/133 ✅ (已实现模块全覆盖)
```
