<template>
  <div class="detail-page">
    <button class="btn-back" @click="$emit('back')">返回检索</button>

    <div class="detail-card">
      <h2>文献详情</h2>
      <table class="meta-table">
        <tr><th>标题</th><td>{{ article.title || '暂无数据' }}</td></tr>
        <tr><th>作者</th><td>{{ article.authors || '暂无数据' }}</td></tr>
        <tr><th>期刊</th><td>{{ article.journal || '暂无数据' }}</td></tr>
        <tr><th>年份</th><td>{{ article.pub_year || '暂无数据' }}</td></tr>
        <tr><th>PMID</th><td>{{ article.pmid || '暂无数据' }}</td></tr>
        <tr><th>语种</th><td>{{ article.language === 'zh' ? '中文' : '英文' }}</td></tr>
        <tr><th>来源</th><td>{{ article.source_file || '暂无数据' }}</td></tr>
      </table>

      <div class="abstract-section">
        <h3>摘要</h3>
        <p>{{ article.abstract || '暂无摘要' }}</p>
      </div>

      <div class="entities-section" v-if="entities.length">
        <h3>关联医学实体</h3>
        <div class="entity-tags">
          <span
            v-for="ent in entities"
            :key="ent.name"
            class="entity-card"
            :class="getEntityClass(ent.entity_type)"
            @click="viewInGraph(ent.name)"
          >
            <span class="entity-name">{{ ent.name }}</span>
            <span class="entity-type">{{ ent.entity_type }}</span>
          </span>
        </div>
      </div>

      <button class="btn-graph" v-if="entities.length" @click="viewInGraph()">在知识图谱中查看</button>
    </div>
  </div>
</template>

<script>
import api from '../api/client.js'

export default {
  name: 'DetailView',
  props: { articleId: { type: String, required: true } },
  emits: ['back'],
  data() {
    return {
      article: {},
      entities: [],
    }
  },
  async mounted() {
    await this.loadDetail()
  },
  methods: {
    async loadDetail() {
      try {
        // TODO: 从 API 加载文献详情和关联实体
        this.article = { title: this.articleId }
        this.entities = []
      } catch (e) {
        console.error('Load detail error:', e)
      }
    },
    getEntityClass(type) {
      return { 'card-disease': type === 'Disease', 'card-drug': type === 'Drug', 'card-symptom': type === 'Symptom' }
    },
    viewInGraph(entityName) {
      // TODO: 跳转到图谱页
    },
  },
}
</script>

<style scoped>
.detail-page { max-width: 900px; margin: 0 auto; }
.btn-back { padding: 8px 20px; background: #eee; border: none; border-radius: 6px; cursor: pointer; margin-bottom: 20px; }
.detail-card { background: #fff; border-radius: 10px; padding: 28px; border: 1px solid #eee; }
.detail-card h2 { margin-bottom: 20px; color: #333; border-bottom: 1px solid #eee; padding-bottom: 12px; }
.meta-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
.meta-table th { text-align: left; width: 80px; color: #888; padding: 6px 8px; font-weight: 500; }
.meta-table td { padding: 6px 8px; color: #333; }
.abstract-section { margin-bottom: 20px; }
.abstract-section h3 { color: #555; margin-bottom: 10px; }
.abstract-section p { line-height: 1.8; color: #444; }
.entities-section { margin-bottom: 20px; }
.entities-section h3 { color: #555; margin-bottom: 12px; }
.entity-tags { display: flex; gap: 10px; flex-wrap: wrap; }
.entity-card {
  display: flex; flex-direction: column; align-items: center;
  padding: 10px 16px; border-radius: 8px; cursor: pointer;
  min-width: 80px; transition: transform 0.2s;
}
.entity-card:hover { transform: translateY(-2px); }
.card-disease { background: #fde8e8; }
.card-drug { background: #dbeafe; }
.card-symptom { background: #d1fae5; }
.entity-name { font-size: 14px; font-weight: 500; }
.entity-type { font-size: 11px; opacity: 0.7; margin-top: 4px; }
.btn-graph { padding: 12px 24px; background: #667eea; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 15px; }
</style>
