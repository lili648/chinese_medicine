import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 5000,
})

export default {
  /** 按实体名查询关联 */
  queryByEntity(name) {
    return api.post('/query/entity', { name })
  },

  /** 按类型查 Top-N 实体 */
  queryTop(entityType, n = 20) {
    return api.get('/query/top', { params: { entity_type: entityType, n } })
  },

  /** 两实体最短路径 */
  queryShortestPath(source, target) {
    return api.post('/query/path', { source, target })
  },

  /** 查文献关联实体 */
  queryArticleEntities(articleId) {
    return api.get('/query/article', { params: { article_id: articleId } })
  },

  /** 关键词检索文献 */
  keywordSearch(q) {
    return api.get('/search', { params: { q } })
  },

  /** 获取图谱数据 (ECharts 力导向图) */
  getGraphData() {
    return api.get('/graph/data')
  },

  /** 获取数据库统计概览 */
  getStats() {
    return api.get('/stats')
  },

  /** 按类型列出实体 */
  listEntities(entityType) {
    return api.get('/entities', { params: { entity_type: entityType } })
  },
}
