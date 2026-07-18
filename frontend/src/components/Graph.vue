<template>
  <div class="graph-page">
    <div class="graph-main">
      <!-- 图谱区域 (65%) -->
      <div class="graph-area">
        <div class="graph-legend">
          <span class="legend-item"><span class="dot" style="background:#E74C3C"></span> 疾病</span>
          <span class="legend-item"><span class="dot" style="background:#3498DB"></span> 药物</span>
          <span class="legend-item"><span class="dot" style="background:#2ECC71"></span> 症状</span>
          <span class="legend-item"><span class="dot" style="background:#95A5A6"></span> 文献</span>
          <span class="total-nodes">总节点: {{ totalNodes }}</span>
        </div>
        <div class="chart-container">
          <div v-if="!connected" class="offline-hint">图谱服务暂不可用，请检查数据库连接</div>
          <div v-else ref="chartRef" class="chart"></div>
        </div>
        <!-- 路径查询栏 -->
        <div class="path-bar">
          <input v-model="pathFrom" type="text" placeholder="起始实体" />
          <span class="arrow">→</span>
          <input v-model="pathTo" type="text" placeholder="目标实体" />
          <button @click="findPath" class="btn-path">查询</button>
        </div>
        <div v-if="pathResult" class="path-result">
          <span v-if="pathResult.found">路径: {{ pathResult.path.join(' → ') }}</span>
          <span v-else class="no-path">未找到关联路径</span>
        </div>
      </div>

      <!-- 详情面板 (35%) -->
      <div class="detail-panel" v-if="selectedNode">
        <h3>实体详情</h3>
        <div class="detail-item"><label>实体名:</label> {{ selectedNode.name }}</div>
        <div class="detail-item"><label>类型:</label> {{ selectedNode.entity_type }}</div>
        <div class="detail-item"><label>关联文献数:</label> {{ selectedNode.article_count || 0 }}</div>
        <div class="detail-item">
          <label>关联实体:</label>
          <ul>
            <li v-for="neighbor in neighbors" :key="neighbor.id" @click="selectNode(neighbor)">
              {{ neighbor.name }} ({{ neighbor.entity_type }})
            </li>
          </ul>
        </div>
        <button class="btn-view-articles" @click="viewRelatedArticles">查看关联文献</button>
      </div>
    </div>
  </div>
</template>

<script>
import api from '../api/client.js'

const TYPE_COLORS = { Disease: '#E74C3C', Drug: '#3498DB', Symptom: '#2ECC71', Article: '#95A5A6' }

export default {
  name: 'GraphView',
  data() {
    return {
      connected: true,
      totalNodes: 0,
      selectedNode: null,
      neighbors: [],
      pathFrom: '',
      pathTo: '',
      pathResult: null,
    }
  },
  methods: {
    async loadGraph() {
      try {
        // TODO: 加载图谱数据并渲染 ECharts 力导向图
        this.totalNodes = 0
      } catch {
        this.connected = false
      }
    },
    findPath() {
      if (!this.pathFrom || !this.pathTo) return
      // TODO: 调用 api.queryShortestPath
    },
    selectNode(node) {
      this.selectedNode = node
      // TODO: 加载 1-hop 邻居
    },
    viewRelatedArticles() {
      // TODO: 跳转到检索页筛选
    },
  },
}
</script>

<style scoped>
.graph-page { height: 100%; }
.graph-main { display: flex; gap: 16px; height: calc(100vh - 160px); }
.graph-area { flex: 0 0 65%; background: #fff; border-radius: 10px; padding: 16px; display: flex; flex-direction: column; border: 1px solid #eee; }
.graph-legend { display: flex; gap: 16px; align-items: center; margin-bottom: 12px; font-size: 13px; }
.dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }
.total-nodes { margin-left: auto; color: #888; }
.chart-container { flex: 1; position: relative; }
.offline-hint { display: flex; align-items: center; justify-content: center; height: 100%; color: #e74c3c; font-size: 16px; }
.chart { width: 100%; height: 100%; }
.path-bar { display: flex; gap: 8px; align-items: center; margin-top: 12px; }
.path-bar input { flex: 1; padding: 8px; border: 1px solid #ddd; border-radius: 6px; }
.arrow { color: #999; }
.btn-path { padding: 8px 16px; background: #667eea; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.path-result { margin-top: 8px; font-size: 13px; color: #555; }
.no-path { color: #e74c3c; }
.detail-panel { flex: 0 0 35%; background: #fff; border-radius: 10px; padding: 20px; border: 1px solid #eee; overflow-y: auto; }
.detail-panel h3 { margin-bottom: 16px; color: #333; }
.detail-item { margin-bottom: 12px; font-size: 14px; }
.detail-item label { color: #888; display: block; margin-bottom: 4px; }
.detail-item ul { list-style: none; padding: 0; }
.detail-item li { padding: 4px 0; color: #667eea; cursor: pointer; }
.detail-item li:hover { text-decoration: underline; }
.btn-view-articles { margin-top: 16px; padding: 10px 20px; background: #667eea; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
</style>
