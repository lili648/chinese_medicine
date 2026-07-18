<template>
  <div class="admin-page">
    <h2>管理后台</h2>

    <!-- 数据管理 -->
    <section class="section">
      <h3>数据管理</h3>
      <div class="info-grid">
        <div class="info-card">
          <span class="label">文献数据集</span>
          <span class="value">PubMed 500篇 + 中文 200篇</span>
          <button class="btn-reload" @click="reloadArticles">重新加载</button>
        </div>
        <div class="info-card">
          <span class="label">实体词典</span>
          <span class="value">疾病520 / 药物280 / 症状230</span>
          <button class="btn-reload" @click="reloadDicts">重新加载</button>
        </div>
        <div class="info-card">
          <span class="label">MySQL 状态</span>
          <span class="value" :class="{ connected: dbConnected, disconnected: !dbConnected }">
            {{ dbConnected ? '● 已连接' : '● 未连接' }}
          </span>
          <span class="stats">article: 700 | entity: 1,000 | relation: 5,400</span>
        </div>
      </div>
    </section>

    <!-- 操作区 -->
    <section class="section">
      <h3>操作</h3>
      <div class="ops">
        <div class="op-item">
          <button @click="runPreprocess" :disabled="processing">执行文本预处理</button>
          <span class="op-status">{{ status.preprocess }}</span>
        </div>
        <div class="op-item">
          <button @click="runNER" :disabled="processing">执行实体识别</button>
          <span class="op-status">{{ status.ner }}</span>
        </div>
        <div class="op-item">
          <button @click="runBuildGraph" :disabled="processing">构建知识图谱</button>
          <span class="op-status">{{ status.graph }}</span>
        </div>
        <div class="op-item">
          <button @click="clearData" class="btn-danger">清空图谱数据</button>
        </div>
      </div>
    </section>

    <!-- 系统信息 -->
    <section class="section">
      <h3>系统信息</h3>
      <div class="sys-info">MySQL版本: 8.x | Python: 3.9 | Vue: 3.x | FastAPI: 0.1xx</div>
    </section>
  </div>
</template>

<script>
export default {
  name: 'AdminView',
  data() {
    return {
      dbConnected: false,
      processing: false,
      status: { preprocess: '就绪', ner: '就绪', graph: '就绪' },
    }
  },
  methods: {
    reloadArticles() {},
    reloadDicts() {},
    runPreprocess() {},
    runNER() {},
    runBuildGraph() {},
    clearData() {},
  },
}
</script>

<style scoped>
.admin-page { max-width: 900px; margin: 0 auto; }
.admin-page h2 { margin-bottom: 24px; color: #333; }
.section { background: #fff; border-radius: 10px; padding: 20px; margin-bottom: 16px; border: 1px solid #eee; }
.section h3 { color: #555; margin-bottom: 16px; }
.info-grid { display: flex; gap: 16px; }
.info-card {
  flex: 1; padding: 16px; background: #f9fafb; border-radius: 8px;
  display: flex; flex-direction: column; gap: 8px;
}
.info-card .label { color: #888; font-size: 13px; }
.info-card .value { font-size: 15px; font-weight: 500; }
.connected { color: #2ecc71; }
.disconnected { color: #e74c3c; }
.stats { font-size: 12px; color: #999; }
.btn-reload { padding: 6px 14px; background: #eee; border: none; border-radius: 6px; cursor: pointer; margin-top: 4px; }
.ops { display: flex; flex-direction: column; gap: 12px; }
.op-item { display: flex; align-items: center; gap: 16px; }
.op-item button {
  padding: 10px 20px; background: #667eea; color: #fff;
  border: none; border-radius: 6px; cursor: pointer; min-width: 140px;
}
.op-item button:disabled { background: #ccc; cursor: not-allowed; }
.op-item button:hover:not(:disabled) { background: #5a6fd6; }
.btn-danger { background: #e74c3c !important; }
.btn-danger:hover { background: #c0392b !important; }
.op-status { font-size: 13px; color: #888; }
.sys-info { color: #666; font-size: 14px; }
</style>
