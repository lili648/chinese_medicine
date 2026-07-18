<template>
  <div class="search-page">
    <!-- 搜索区域 -->
    <div class="search-bar">
      <input
        v-model="keyword"
        type="text"
        placeholder="输入关键词检索文献..."
        @keyup.enter="search"
      />
      <button @click="search" class="btn-search">搜索</button>
    </div>

    <!-- 实体类型筛选 -->
    <div class="filter-bar">
      <label>实体类型筛选:</label>
      <select v-model="entityFilter" @change="search">
        <option value="">全部</option>
        <option value="Disease">疾病</option>
        <option value="Drug">药物</option>
        <option value="Symptom">症状</option>
      </select>
    </div>

    <!-- 检索结果 -->
    <div class="results">
      <div v-if="loading" class="loading">搜索中...</div>
      <div v-else-if="noResult" class="no-result">未找到相关文献，请尝试其他关键词</div>
      <template v-else>
        <h3>检索结果 (共 {{ totalCount }} 条)</h3>
        <div v-for="article in articles" :key="article.article_id" class="article-card">
          <div class="article-title" v-html="highlightMatch(article.title)"></div>
          <div class="article-meta">
            Authors: {{ article.authors || '暂无' }} |
            Journal: {{ article.journal || '暂无' }} |
            {{ article.pub_year || '未知' }}
          </div>
          <div class="article-abstract" v-html="highlightMatch(article.abstract || '暂无摘要')"></div>
          <div class="article-entities" v-if="article.entities && article.entities.length">
            关联实体:
            <span
              v-for="ent in article.entities"
              :key="ent.name"
              class="entity-tag"
              :class="getEntityClass(ent.entity_type)"
              @click="$emit('view-graph', ent.name)"
            >{{ ent.name }}</span>
          </div>
          <a class="detail-link" @click.prevent="$emit('view-detail', article.article_id)">[查看详情]</a>
        </div>
      </template>
    </div>
  </div>
</template>

<script>
import api from '../api/client.js'

export default {
  name: 'SearchView',
  emits: ['view-detail', 'view-graph'],
  data() {
    return {
      keyword: '',
      entityFilter: '',
      articles: [],
      totalCount: 0,
      loading: false,
    }
  },
  computed: {
    noResult() {
      return !this.loading && this.keyword && this.articles.length === 0
    },
  },
  methods: {
    async search() {
      if (!this.keyword.trim()) return
      this.loading = true
      try {
        const res = await api.keywordSearch(this.keyword)
        this.articles = res.data?.articles || []
        this.totalCount = res.data?.total || this.articles.length
      } catch (e) {
        console.error('Search error:', e)
      } finally {
        this.loading = false
      }
    },
    highlightMatch(text) {
      if (!this.keyword || !text) return text || ''
      const re = new RegExp(`(${this.keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
      return text.replace(re, '<mark>$1</mark>')
    },
    getEntityClass(type) {
      return { 'tag-disease': type === 'Disease', 'tag-drug': type === 'Drug', 'tag-symptom': type === 'Symptom' }
    },
  },
}
</script>

<style scoped>
.search-bar { display: flex; gap: 12px; margin-bottom: 16px; }
.search-bar input { flex: 1; padding: 12px 16px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 15px; }
.search-bar input:focus { border-color: #667eea; outline: none; }
.btn-search { padding: 12px 28px; background: #667eea; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 15px; }
.btn-search:hover { background: #5a6fd6; }
.filter-bar { margin-bottom: 20px; display: flex; align-items: center; gap: 8px; }
.filter-bar select { padding: 6px 12px; border-radius: 6px; border: 1px solid #ddd; }
.loading, .no-result { text-align: center; padding: 60px 0; color: #999; }
.results h3 { margin-bottom: 16px; color: #555; font-weight: 500; }
.article-card {
  background: #fff; border: 1px solid #eee; border-radius: 10px; padding: 18px 20px;
  margin-bottom: 12px; transition: box-shadow 0.2s;
}
.article-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
.article-title { font-size: 16px; font-weight: 600; color: #2c3e50; margin-bottom: 6px; }
.article-meta { font-size: 13px; color: #888; margin-bottom: 8px; }
.article-abstract { font-size: 14px; color: #555; line-height: 1.6; margin-bottom: 10px; }
.article-entities { font-size: 13px; color: #666; }
.entity-tag {
  display: inline-block; padding: 2px 8px; border-radius: 4px; margin: 0 2px;
  font-size: 12px; cursor: pointer;
}
.tag-disease { background: #fde8e8; color: #e74c3c; }
.tag-drug { background: #dbeafe; color: #3498db; }
.tag-symptom { background: #d1fae5; color: #2ecc71; }
.detail-link { color: #667eea; text-decoration: none; font-size: 14px; cursor: pointer; margin-top: 8px; display: inline-block; }
.detail-link:hover { text-decoration: underline; }
</style>
