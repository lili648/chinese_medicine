# 基于知识图谱的医疗文献管理平台

> Medical Literature Management Platform Based on Knowledge Graph (MLM-KG)

## 项目简介

基于知识图谱的医疗文献管理平台，帮助医学研究人员：
- 批量导入和管理医学文献数据（PubMed + 中文医学文献）
- 基于词典 + NLP 技术自动识别文献中的疾病、药物、症状实体
- 构建和可视化医学知识图谱，发现实体间的隐性关联
- 通过 Web 界面进行关键词检索和图谱交互浏览

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + Vite + ECharts |
| 后端 | FastAPI + SQLAlchemy |
| 数据库 | MySQL |
| 图计算 | NetworkX |
| 分词 | jieba |

## 项目结构

```
chinese_medicine/
├── data/                    # 文献数据
│   ├── pubmed/              # PubMed 英文文献
│   └── chinese/             # 中文医学文献
├── dicts/                   # 实体词典
│   ├── disease_dict.txt     # 疾病词典
│   ├── drug_dict.txt        # 药物词典
│   └── symptom_dict.txt     # 症状词典
├── output/                  # 中间产物
├── frontend/                # Vue 3 前端
│   └── src/
│       ├── components/      # Vue 组件
│       └── api/             # API 客户端
├── src/                     # Python 后端
│   ├── api/                 # FastAPI 接口
│   ├── db/                  # 数据库会话管理
│   ├── preprocessing/       # 文献加载与预处理
│   ├── ner/                 # 医学实体识别
│   └── knowledge_graph/     # 知识图谱构建与查询
└── tests/                   # 测试
```

## 快速启动

### 后端

```bash
pip install -r requirements.txt
uvicorn src.api.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

## 版本

- 版本: V1.0
- 项目编号: KJTP-MLM-001
